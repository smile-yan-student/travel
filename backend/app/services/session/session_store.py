"""
会话存储（Session Store）。

管理行程工作记忆的创建、读取、更新、删除。
支持内存缓存 + 数据库持久化（MySQL）。

功能特性：
- 内存缓存（快速访问）
- 数据库持久化（重启后可恢复，支持用户关联和查询）
- LRU淘汰（超过最大会话数时淘汰最久未使用的）
- 会话创建、读取、更新、删除
- 获取或创建会话
- 列出所有会话（摘要信息）
- 清理过期会话（默认72小时）
- 全局单例

使用方式：
    from app.services.session.session_store import get_session_store

    # 获取全局会话存储单例
    session_store = get_session_store()

    # 创建新会话
    workspace = session_store.create_session("abc123", user_id=1, conversation_id=97)

    # 获取会话
    workspace = session_store.get_session("abc123")

    # 获取或创建会话
    workspace = session_store.get_or_create_session("abc123")

    # 更新会话
    success = session_store.update_session(workspace)

    # 删除会话
    success = session_store.delete_session("abc123")

    # 列出所有会话
    sessions = session_store.list_sessions(limit=50)

    # 清理过期会话
    session_store.cleanup_expired(max_age_hours=72)
"""
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .itinerary_workspace import ItineraryWorkspace


def _get_db_connection():
    """
    获取数据库连接。

    Returns:
        pymysql.Connection: 数据库连接
    """
    from app.data.database import get_conn
    return get_conn()


def _workspace_to_db_dict(workspace: ItineraryWorkspace, user_id: Optional[int] = None,
                           conversation_id: Optional[int] = None) -> Dict[str, Any]:
    """
    将工作区对象转换为数据库字段字典。

    Args:
        workspace: 行程工作区
        user_id: 用户ID
        conversation_id: 对话ID

    Returns:
        Dict[str, Any]: 数据库字段字典
    """
    data = workspace.to_dict()

    # 从行程中提取目的地和天数，便于查询
    destination = None
    days = None
    current_plan = data.get("current_plan", {})
    if current_plan:
        destination = current_plan.get("destination")
        days = current_plan.get("days")

    return {
        "session_id": data.get("session_id", ""),
        "user_id": user_id,
        "conversation_id": conversation_id,
        "status": data.get("status", "draft"),
        "source": data.get("source", ""),
        "destination": destination,
        "days": days,
        "original_params": json.dumps(data.get("original_params", {}), ensure_ascii=False) if data.get("original_params") else None,
        "current_plan": json.dumps(data.get("current_plan", {}), ensure_ascii=False) if data.get("current_plan") else None,
        "preferences": json.dumps(data.get("preferences", {}), ensure_ascii=False) if data.get("preferences") else None,
        "modification_history": json.dumps(data.get("modification_history", []), ensure_ascii=False) if data.get("modification_history") else None,
        "recent_instructions": json.dumps(data.get("recent_instructions", []), ensure_ascii=False) if data.get("recent_instructions") else None,
    }


def _db_row_to_workspace(row: Dict[str, Any]) -> Optional[ItineraryWorkspace]:
    """
    将数据库行转换为工作区对象。

    Args:
        row: 数据库行

    Returns:
        Optional[ItineraryWorkspace]: 工作区对象，转换失败返回None
    """
    try:
        data = {
            "session_id": row.get("session_id", ""),
            "created_at": row.get("created_at", datetime.now()).timestamp() if isinstance(row.get("created_at"), datetime) else time.time(),
            "updated_at": row.get("updated_at", datetime.now()).timestamp() if isinstance(row.get("updated_at"), datetime) else time.time(),
            "original_params": json.loads(row["original_params"]) if row.get("original_params") else {},
            "current_plan": json.loads(row["current_plan"]) if row.get("current_plan") else {},
            "preferences": json.loads(row["preferences"]) if row.get("preferences") else {},
            "modification_history": json.loads(row["modification_history"]) if row.get("modification_history") else [],
            "status": row.get("status", "draft"),
            "source": row.get("source", ""),
            "recent_instructions": json.loads(row["recent_instructions"]) if row.get("recent_instructions") else [],
        }
        return ItineraryWorkspace.from_dict(data)
    except Exception as e:
        print(f"[SessionStore] db_row_to_workspace failed: {e}")
        return None


class SessionStore:
    """
    会话存储。

    - 内存缓存：快速访问
    - 数据库持久化：重启后可恢复，支持用户关联和查询
    - LRU淘汰：超过最大会话数时淘汰最久未使用的
    """

    def __init__(self, max_sessions: int = 1000) -> None:
        """
        初始化会话存储。

        Args:
            max_sessions: 最大会话数（LRU淘汰阈值）
        """
        self.max_sessions = max_sessions
        self._cache: Dict[str, ItineraryWorkspace] = {}
        self._access_order: List[str] = []  # LRU顺序，最近使用的在末尾
        self._user_map: Dict[str, Optional[int]] = {}  # session_id -> user_id
        self._conversation_map: Dict[str, Optional[int]] = {}  # session_id -> conversation_id

    def _touch_access(self, session_id: str) -> None:
        """
        更新访问顺序（LRU）。

        Args:
            session_id: 会话ID
        """
        if session_id in self._access_order:
            self._access_order.remove(session_id)
        self._access_order.append(session_id)
        # 超过最大会话数时淘汰最久未使用的
        while len(self._access_order) > self.max_sessions:
            oldest = self._access_order.pop(0)
            if oldest in self._cache:
                # 持久化后再淘汰（数据库已持久化，直接删除缓存）
                del self._cache[oldest]
                self._user_map.pop(oldest, None)
                self._conversation_map.pop(oldest, None)

    def create_session(self, session_id: str = "", user_id: Optional[int] = None,
                       conversation_id: Optional[int] = None) -> ItineraryWorkspace:
        """
        创建新会话。

        Args:
            session_id: 会话ID，为空时自动生成
            user_id: 用户ID
            conversation_id: 对话ID

        Returns:
            ItineraryWorkspace: 新的行程工作记忆
        """
        if not session_id:
            session_id = uuid.uuid4().hex[:16]
        workspace = ItineraryWorkspace(session_id=session_id)
        self._cache[session_id] = workspace
        self._user_map[session_id] = user_id
        self._conversation_map[session_id] = conversation_id
        self._touch_access(session_id)
        self._persist(session_id)
        return workspace

    def get_session(self, session_id: str) -> Optional[ItineraryWorkspace]:
        """
        获取会话。

        Args:
            session_id: 会话ID

        Returns:
            Optional[ItineraryWorkspace]: 行程工作记忆，不存在时返回None
        """
        # 先查内存缓存
        if session_id in self._cache:
            self._touch_access(session_id)
            return self._cache[session_id]
        # 再查数据库
        workspace = self._load_from_db(session_id)
        if workspace:
            self._cache[session_id] = workspace
            self._touch_access(session_id)
        return workspace

    def get_or_create_session(self, session_id: str = "", user_id: Optional[int] = None,
                               conversation_id: Optional[int] = None) -> ItineraryWorkspace:
        """
        获取或创建会话。

        Args:
            session_id: 会话ID，为空时自动生成
            user_id: 用户ID
            conversation_id: 对话ID

        Returns:
            ItineraryWorkspace: 行程工作记忆
        """
        if session_id:
            workspace = self.get_session(session_id)
            if workspace:
                # 更新用户关联（如果之前没有关联）
                if user_id and not self._user_map.get(session_id):
                    self._user_map[session_id] = user_id
                    self._update_user_link(session_id, user_id, conversation_id)
                return workspace
        return self.create_session(session_id, user_id=user_id, conversation_id=conversation_id)

    def update_session(self, workspace: ItineraryWorkspace) -> bool:
        """
        更新会话。

        Args:
            workspace: 行程工作记忆

        Returns:
            bool: 是否成功
        """
        session_id = workspace.session_id
        if not session_id:
            return False
        workspace.updated_at = time.time()
        self._cache[session_id] = workspace
        self._touch_access(session_id)
        self._persist(session_id)
        return True

    def delete_session(self, session_id: str) -> bool:
        """
        删除会话。

        Args:
            session_id: 会话ID

        Returns:
            bool: 是否成功
        """
        if session_id in self._cache:
            del self._cache[session_id]
        if session_id in self._access_order:
            self._access_order.remove(session_id)
        self._user_map.pop(session_id, None)
        self._conversation_map.pop(session_id, None)
        # 从数据库删除
        return self._delete_from_db(session_id)

    def list_sessions(self, limit: int = 50, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        列出所有会话（摘要信息）。

        Args:
            limit: 返回数量限制
            user_id: 用户ID过滤（可选）

        Returns:
            List[Dict[str, Any]]: 会话摘要列表
        """
        sessions = []
        # 从内存缓存获取
        for session_id in reversed(self._access_order):
            if session_id in self._cache:
                if user_id and self._user_map.get(session_id) != user_id:
                    continue
                sessions.append(self._cache[session_id].summary())
                if len(sessions) >= limit:
                    return sessions
        # 从数据库获取（如果内存中不够）
        if len(sessions) < limit:
            db_sessions = self._list_from_db(limit=limit, user_id=user_id)
            existing_ids = {s["session_id"] for s in sessions}
            for ws in db_sessions:
                if ws.session_id not in existing_ids:
                    sessions.append(ws.summary())
                    # 加入缓存
                    self._cache[ws.session_id] = ws
                    self._touch_access(ws.session_id)
                    if len(sessions) >= limit:
                        break
        return sessions

    def _persist(self, session_id: str) -> None:
        """
        持久化会话到数据库。

        Args:
            session_id: 会话ID
        """
        if session_id not in self._cache:
            return
        try:
            workspace = self._cache[session_id]
            user_id = self._user_map.get(session_id)
            conversation_id = self._conversation_map.get(session_id)
            self._save_to_db(workspace, user_id, conversation_id)
        except Exception as e:
            # 持久化失败不影响内存使用
            print(f"[SessionStore] persist failed for {session_id}: {e}")

    def _save_to_db(self, workspace: ItineraryWorkspace, user_id: Optional[int] = None,
                     conversation_id: Optional[int] = None) -> None:
        """
        保存会话到数据库（UPSERT）。

        Args:
            workspace: 行程工作区
            user_id: 用户ID
            conversation_id: 对话ID
        """
        db_data = _workspace_to_db_dict(workspace, user_id, conversation_id)
        conn = _get_db_connection()
        try:
            with conn.cursor() as cursor:
                # 检查是否已存在
                cursor.execute("SELECT id FROM itinerary_sessions WHERE session_id = %s", (db_data["session_id"],))
                existing = cursor.fetchone()

                if existing:
                    # 更新
                    update_fields = ["user_id", "conversation_id", "status", "source", "destination", "days",
                                     "original_params", "current_plan", "preferences", "modification_history",
                                     "recent_instructions"]
                    set_clause = ", ".join([f"{f} = %s" for f in update_fields])
                    values = [db_data[f] for f in update_fields] + [db_data["session_id"]]
                    cursor.execute(f"UPDATE itinerary_sessions SET {set_clause} WHERE session_id = %s", values)
                else:
                    # 插入
                    insert_fields = ["session_id", "user_id", "conversation_id", "status", "source",
                                     "destination", "days", "original_params", "current_plan", "preferences",
                                     "modification_history", "recent_instructions"]
                    placeholders = ", ".join(["%s"] * len(insert_fields))
                    values = [db_data[f] for f in insert_fields]
                    cursor.execute(
                        f"INSERT INTO itinerary_sessions ({', '.join(insert_fields)}) VALUES ({placeholders})",
                        values
                    )
            conn.commit()
        finally:
            conn.close()

    def _load_from_db(self, session_id: str) -> Optional[ItineraryWorkspace]:
        """
        从数据库加载会话。

        Args:
            session_id: 会话ID

        Returns:
            Optional[ItineraryWorkspace]: 行程工作记忆，加载失败返回None
        """
        conn = _get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM itinerary_sessions WHERE session_id = %s", (session_id,))
                row = cursor.fetchone()
                if row:
                    ws = _db_row_to_workspace(row)
                    if ws:
                        # 缓存用户关联
                        self._user_map[session_id] = row.get("user_id")
                        self._conversation_map[session_id] = row.get("conversation_id")
                    return ws
        except Exception as e:
            print(f"[SessionStore] load_from_db failed for {session_id}: {e}")
        finally:
            conn.close()
        return None

    def _delete_from_db(self, session_id: str) -> bool:
        """
        从数据库删除会话。

        Args:
            session_id: 会话ID

        Returns:
            bool: 是否成功
        """
        conn = _get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM itinerary_sessions WHERE session_id = %s", (session_id,))
            conn.commit()
            return True
        except Exception as e:
            print(f"[SessionStore] delete_from_db failed for {session_id}: {e}")
            return False
        finally:
            conn.close()

    def _list_from_db(self, limit: int = 50, user_id: Optional[int] = None) -> List[ItineraryWorkspace]:
        """
        从数据库列出会话。

        Args:
            limit: 返回数量限制
            user_id: 用户ID过滤

        Returns:
            List[ItineraryWorkspace]: 工作区列表
        """
        conn = _get_db_connection()
        try:
            with conn.cursor() as cursor:
                if user_id:
                    cursor.execute(
                        "SELECT * FROM itinerary_sessions WHERE user_id = %s ORDER BY updated_at DESC LIMIT %s",
                        (user_id, limit)
                    )
                else:
                    cursor.execute(
                        "SELECT * FROM itinerary_sessions ORDER BY updated_at DESC LIMIT %s",
                        (limit,)
                    )
                rows = cursor.fetchall()
                workspaces = []
                for row in rows:
                    ws = _db_row_to_workspace(row)
                    if ws:
                        workspaces.append(ws)
                return workspaces
        except Exception as e:
            print(f"[SessionStore] list_from_db failed: {e}")
            return []
        finally:
            conn.close()

    def _update_user_link(self, session_id: str, user_id: Optional[int],
                          conversation_id: Optional[int] = None) -> None:
        """
        更新会话的用户关联。

        Args:
            session_id: 会话ID
            user_id: 用户ID
            conversation_id: 对话ID
        """
        conn = _get_db_connection()
        try:
            with conn.cursor() as cursor:
                if conversation_id:
                    cursor.execute(
                        "UPDATE itinerary_sessions SET user_id = %s, conversation_id = %s WHERE session_id = %s",
                        (user_id, conversation_id, session_id)
                    )
                else:
                    cursor.execute(
                        "UPDATE itinerary_sessions SET user_id = %s WHERE session_id = %s",
                        (user_id, session_id)
                    )
            conn.commit()
        except Exception as e:
            print(f"[SessionStore] update_user_link failed for {session_id}: {e}")
        finally:
            conn.close()

    def cleanup_expired(self, max_age_hours: int = 72) -> None:
        """
        清理过期会话（默认72小时）。

        Args:
            max_age_hours: 最大存活时间（小时）
        """
        cutoff = time.time() - max_age_hours * 3600
        cutoff_datetime = datetime.fromtimestamp(cutoff)

        # 清理内存
        expired = [
            sid for sid, ws in self._cache.items() if ws.updated_at < cutoff
        ]
        for sid in expired:
            self.delete_session(sid)

        # 清理数据库
        conn = _get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM itinerary_sessions WHERE updated_at < %s AND status = 'draft'",
                    (cutoff_datetime,)
                )
            conn.commit()
        except Exception as e:
            print(f"[SessionStore] cleanup_expired db failed: {e}")
        finally:
            conn.close()


# 全局单例
_session_store: Optional[SessionStore] = None


def get_session_store() -> SessionStore:
    """
    获取全局会话存储单例。

    Returns:
        SessionStore: 全局会话存储单例
    """
    global _session_store
    if _session_store is None:
        _session_store = SessionStore()
    return _session_store
