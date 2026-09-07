# -*- coding: utf-8 -*-
"""
管理后台存储层：admins / 用户治理 / must_visit / site_config / generation_log。

数据表在 user_repository.init_db() 中统一创建；本模块只做后台侧的数据访问，
供 admin_router.py（/api/admin/*）调用。planner 读取 must_visit 时也会
优先使用本模块的 get_must_visit（表优先，表空回退到 data/must_visit.py）。

功能特性：
- 管理员管理（登录、列表、创建、启用/禁用、重置密码）
- 用户治理（用户列表、用户详情、启用/禁用）
- 行程与足迹（行程列表、行程统计）
- 对话运营（对话列表、对话详情、对话统计）
- 必去景点管理（获取、添加、更新、删除）
- AI 生成日志（添加、列表）
- 系统配置（获取、设置）

使用方式：
    from app.data.repositories.admin_repository import (
        admin_login, admin_by_token, list_admins, create_admin,
        list_users, user_detail, set_user_enabled,
        list_trips, trips_stats,
        list_convos, convo_detail, convo_stats,
        get_must_visit, add_must_visit, update_must_visit, delete_must_visit,
        add_gen_log, list_gen_logs,
        get_config, set_config
    )

    # 管理员登录
    result = admin_login("admin", "password")
    if result:
        token, admin = result["token"], result["admin"]

    # 校验管理员 token
    admin = admin_by_token(token)

    # 获取用户列表
    result = list_users(keyword="", page=1, size=20)

    # 获取必去景点
    must_visit = get_must_visit("杭州")

    # 获取系统配置
    config = get_config(include_secret=True)
"""
import datetime
from typing import Any, Dict, List, Optional, Tuple

import bcrypt
import jwt
import pymysql

from ...config import settings
from ..database import get_conn, read_connection, transaction

# 初始管理员账号
INIT_ADMIN_USER = "admin01"
INIT_ADMIN_PASS = "Admin@123456"


def init_admin_data() -> None:
    """
    初始化管理员数据：admins 空则创建初始超级管理员。

    must_visit 数据已迁移到数据库，不再从静态文件导入。
    如需重新初始化，请使用数据迁移接口。
    """
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS c FROM admins")
            if cur.fetchone()["c"] == 0:
                pw = bcrypt.hashpw(
                    INIT_ADMIN_PASS.encode(), bcrypt.gensalt()
                ).decode()
                cur.execute(
                    "INSERT INTO admins (username, password_hash, role, enabled, created_at) "
                    "VALUES (%s,%s,%s,1,%s)",
                    (INIT_ADMIN_USER, pw, "super", datetime.datetime.now()),
                )
            cur.execute("SELECT COUNT(*) AS c FROM must_visit")
            # must_visit 数据已迁移到数据库，不再从静态文件导入
            # 如需重新初始化，请使用数据迁移接口


# ---------------- 管理员 ----------------


def _admin_by_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    将数据库行转换为管理员字典。

    Args:
        row: 数据库行

    Returns:
        Dict[str, Any]: 管理员字典
    """
    return {
        "id": row["id"],
        "username": row["username"],
        "role": row["role"],
        "enabled": bool(row["enabled"]),
        "created_at": str(row["created_at"]),
    }


def create_admin_token(admin_id: int, username: str, role: str) -> str:
    """
    创建管理员 JWT token。

    Args:
        admin_id: 管理员ID
        username: 用户名
        role: 角色（super/ops）

    Returns:
        str: JWT token
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": str(admin_id),
        "username": username,
        "role": role,
        "scope": "admin",
        "iat": now,
        "exp": now + datetime.timedelta(hours=settings.token_expire_hours),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def admin_login(username: str, password: str) -> Optional[Dict[str, Any]]:
    """
    管理员登录。成功返回 {token, admin}；失败返回 None（含停用账号）。

    Args:
        username: 用户名
        password: 密码

    Returns:
        Optional[Dict[str, Any]]: {token, admin}，失败返回 None
    """
    with read_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, password_hash, role, enabled, created_at FROM admins "
                "WHERE username=%s",
                (username.strip(),),
            )
            row = cur.fetchone()
            if not row or not row["enabled"]:
                return None
            if not bcrypt.checkpw(password.encode(), row["password_hash"].encode()):
                return None
            admin = _admin_by_row(row)
            token = create_admin_token(admin["id"], admin["username"], admin["role"])
            return {"token": token, "admin": admin}


def admin_by_token(token: str) -> Optional[Dict[str, Any]]:
    """
    校验管理员 JWT（scope=admin + 账号存在且启用）；无效返回 None。

    Args:
        token: JWT token

    Returns:
        Optional[Dict[str, Any]]: 管理员信息，无效返回 None
    """
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        if payload.get("scope") != "admin":
            return None
        aid = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
    with read_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, role, enabled, created_at FROM admins WHERE id=%s",
                (aid,),
            )
            row = cur.fetchone()
            if not row or not row["enabled"]:
                return None
            return _admin_by_row(row)


def list_admins() -> List[Dict[str, Any]]:
    """
    获取管理员列表。

    Returns:
        List[Dict[str, Any]]: 管理员列表
    """
    with read_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, role, enabled, created_at FROM admins ORDER BY id"
            )
            return [_admin_by_row(r) for r in cur.fetchall()]


def create_admin(
    username: str, password: str, role: str
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    创建管理员。

    Args:
        username: 用户名（3-32字符）
        password: 密码（至少8位）
        role: 角色（super/ops）

    Returns:
        Tuple[Optional[Dict[str, Any]], Optional[str]]: (管理员信息, 错误信息)
    """
    if not (3 <= len(username) <= 32):
        return None, "管理员用户名长度需 3-32 字符"
    if len(password) < 8:
        return None, "密码至少 8 位"
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM admins WHERE username=%s", (username,))
            if cur.fetchone():
                return None, "管理员用户名已存在"
            pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            cur.execute(
                "INSERT INTO admins (username, password_hash, role, enabled, created_at) "
                "VALUES (%s,%s,%s,1,%s)",
                (username, pw, role, datetime.datetime.now()),
            )
            cur.execute(
                "SELECT id, username, role, enabled, created_at FROM admins "
                "WHERE username=%s",
                (username,),
            )
            return _admin_by_row(cur.fetchone()), None


def set_admin_enabled(admin_id: int, enabled: bool) -> bool:
    """
    设置管理员启用/禁用状态。

    Args:
        admin_id: 管理员ID
        enabled: 是否启用

    Returns:
        bool: 是否成功
    """
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE admins SET enabled=%s WHERE id=%s",
                (1 if enabled else 0, admin_id),
            )
            return cur.rowcount > 0


def reset_admin_password(admin_id: int, password: str) -> bool:
    """
    重置管理员密码。

    Args:
        admin_id: 管理员ID
        password: 新密码（至少8位）

    Returns:
        bool: 是否成功
    """
    if len(password) < 8:
        return False
    pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE admins SET password_hash=%s WHERE id=%s", (pw, admin_id)
            )
            return cur.rowcount > 0


# ---------------- 用户治理 ----------------


def list_users(
    keyword: str = "", page: int = 1, size: int = 20
) -> Dict[str, Any]:
    """
    获取用户列表（含出行数、对话数、城市数）。

    Args:
        keyword: 关键词（用户名模糊匹配）
        page: 页码
        size: 每页大小

    Returns:
        Dict[str, Any]: {total, items}
    """
    with read_connection() as conn:
        with conn.cursor() as cur:
            where, params = "", []
            if keyword:
                where = "WHERE u.username LIKE %s"
                params.append(f"%{keyword}%")
            cur.execute(f"SELECT COUNT(*) AS c FROM users u {where}", params)
            total = cur.fetchone()["c"]
            cur.execute(
                f"""
                SELECT u.id, u.username, u.enabled, u.created_at,
                  (SELECT COUNT(*) FROM trips t WHERE t.user_id=u.id) AS trip_cnt,
                  (SELECT COUNT(*) FROM conversations c WHERE c.user_id=u.id) AS convo_cnt
                FROM users u {where}
                ORDER BY u.id DESC LIMIT %s OFFSET %s
                """,
                params + [size, (page - 1) * size],
            )
            rows = cur.fetchall()
            items = []
            for r in rows:
                # 足迹城市集合（去过几个不同城市）
                cur.execute(
                    "SELECT COUNT(DISTINCT destination) AS cities FROM trips WHERE user_id=%s",
                    (r["id"],),
                )
                cities = cur.fetchone()["cities"]
                items.append(
                    {
                        "id": r["id"],
                        "username": r["username"],
                        "enabled": bool(r["enabled"]),
                        "created_at": str(r["created_at"]),
                        "trip_cnt": r["trip_cnt"],
                        "convo_cnt": r["convo_cnt"],
                        "city_cnt": cities,
                    }
                )
            return {"total": total, "items": items}


def user_detail(uid: int) -> Optional[Dict[str, Any]]:
    """
    获取用户详情（含最近50条行程和对话）。

    Args:
        uid: 用户ID

    Returns:
        Optional[Dict[str, Any]]: 用户详情，不存在返回 None
    """
    with read_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, enabled, created_at FROM users WHERE id=%s",
                (uid,),
            )
            u = cur.fetchone()
            if not u:
                return None
            cur.execute(
                "SELECT id, destination, days, style, created_at FROM trips "
                "WHERE user_id=%s ORDER BY id DESC LIMIT 50",
                (uid,),
            )
            trips = [
                {
                    "id": t["id"],
                    "destination": t["destination"],
                    "days": t["days"],
                    "style": t["style"],
                    "created_at": str(t["created_at"]),
                }
                for t in cur.fetchall()
            ]
            cur.execute(
                "SELECT id, title, updated_at FROM conversations WHERE user_id=%s "
                "ORDER BY id DESC LIMIT 50",
                (uid,),
            )
            convos = [
                {
                    "id": c["id"],
                    "title": c["title"],
                    "updated_at": str(c["updated_at"]),
                }
                for c in cur.fetchall()
            ]
            return {
                "id": u["id"],
                "username": u["username"],
                "enabled": bool(u["enabled"]),
                "created_at": str(u["created_at"]),
                "trips": trips,
                "conversations": convos,
            }


def set_user_enabled(uid: int, enabled: bool) -> bool:
    """
    设置用户启用/禁用状态。

    Args:
        uid: 用户ID
        enabled: 是否启用

    Returns:
        bool: 是否成功
    """
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET enabled=%s WHERE id=%s",
                (1 if enabled else 0, uid),
            )
            return cur.rowcount > 0


# ---------------- 行程与足迹 ----------------


def list_trips(
    destination: str = "", page: int = 1, size: int = 20
) -> Dict[str, Any]:
    """
    获取行程列表（含用户名）。

    Args:
        destination: 目的地关键词
        page: 页码
        size: 每页大小

    Returns:
        Dict[str, Any]: {total, items}
    """
    with read_connection() as conn:
        with conn.cursor() as cur:
            where, params = "", []
            if destination:
                where = "WHERE t.destination LIKE %s"
                params.append(f"%{destination}%")
            cur.execute(f"SELECT COUNT(*) AS c FROM trips t {where}", params)
            total = cur.fetchone()["c"]
            cur.execute(
                f"""
                SELECT t.id, t.destination, t.days, t.style, t.created_at, u.username
                FROM trips t JOIN users u ON u.id=t.user_id {where}
                ORDER BY t.id DESC LIMIT %s OFFSET %s
                """,
                params + [size, (page - 1) * size],
            )
            return {
                "total": total,
                "items": [
                    {
                        "id": r["id"],
                        "destination": r["destination"],
                        "days": r["days"],
                        "style": r["style"],
                        "username": r["username"],
                        "created_at": str(r["created_at"]),
                    }
                    for r in cur.fetchall()
                ],
            }


def trips_stats() -> Dict[str, Any]:
    """
    获取行程统计（总数、平均天数、热门城市、风格分布）。

    Returns:
        Dict[str, Any]: 行程统计
    """
    with read_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT destination, COUNT(*) AS cnt FROM trips "
                "GROUP BY destination ORDER BY cnt DESC LIMIT 20"
            )
            cities = [
                {"destination": r["destination"], "count": r["cnt"]}
                for r in cur.fetchall()
            ]
            cur.execute(
                "SELECT style, COUNT(*) AS cnt FROM trips GROUP BY style "
                "ORDER BY cnt DESC"
            )
            styles = [
                {"style": r["style"] or "未标注", "count": r["cnt"]}
                for r in cur.fetchall()
            ]
            cur.execute("SELECT COUNT(*) AS c, AVG(days) AS avg_days FROM trips")
            row = cur.fetchone()
            return {
                "total": row["c"],
                "avg_days": round(float(row["avg_days"] or 0), 1),
                "top_cities": cities,
                "styles": styles,
            }


# ---------------- 对话运营 ----------------


def list_convos(
    keyword: str = "", page: int = 1, size: int = 20
) -> Dict[str, Any]:
    """
    获取对话列表（含用户名、消息数）。

    Args:
        keyword: 关键词（标题/用户名模糊匹配）
        page: 页码
        size: 每页大小

    Returns:
        Dict[str, Any]: {total, items}
    """
    with read_connection() as conn:
        with conn.cursor() as cur:
            where, params = "", []
            if keyword:
                where = "WHERE c.title LIKE %s OR u.username LIKE %s"
                params.extend([f"%{keyword}%", f"%{keyword}%"])
            cur.execute(
                f"SELECT COUNT(*) AS c FROM conversations c JOIN users u ON u.id=c.user_id {where}",
                params,
            )
            total = cur.fetchone()["c"]
            cur.execute(
                f"""
                SELECT c.id, c.title, c.messages, c.updated_at, u.username
                FROM conversations c JOIN users u ON u.id=c.user_id {where}
                ORDER BY c.id DESC LIMIT %s OFFSET %s
                """,
                params + [size, (page - 1) * size],
            )
            items = []
            for r in cur.fetchall():
                msgs = r["messages"]
                items.append(
                    {
                        "id": r["id"],
                        "title": r["title"],
                        "username": r["username"],
                        "msg_cnt": len(msgs) if isinstance(msgs, list) else 0,
                        "updated_at": str(r["updated_at"]),
                    }
                )
            return {"total": total, "items": items}


def convo_detail(cid: int) -> Optional[Dict[str, Any]]:
    """
    获取对话详情（含消息列表、是否含行程）。

    Args:
        cid: 对话ID

    Returns:
        Optional[Dict[str, Any]]: 对话详情，不存在返回 None
    """
    with read_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT c.id, c.title, c.messages, c.created_at, c.updated_at, u.username "
                "FROM conversations c JOIN users u ON u.id=c.user_id WHERE c.id=%s",
                (cid,),
            )
            r = cur.fetchone()
            if not r:
                return None
            msgs = r["messages"] if isinstance(r["messages"], list) else []
            has_plan = any(
                isinstance(m, dict) and m.get("kind") == "plan" for m in msgs
            )
            return {
                "id": r["id"],
                "title": r["title"],
                "username": r["username"],
                "has_plan": has_plan,
                "messages": msgs,
                "created_at": str(r["created_at"]),
                "updated_at": str(r["updated_at"]),
            }


def convo_stats() -> Dict[str, Any]:
    """
    获取对话统计（总数、含行程数、纯聊天数）。

    Returns:
        Dict[str, Any]: 对话统计
    """
    with read_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS c FROM conversations")
            total = cur.fetchone()["c"]
            cur.execute(
                "SELECT COUNT(*) AS c FROM conversations c WHERE "
                "JSON_SEARCH(c.messages, 'one', 'plan') IS NOT NULL"
            )
            with_plan = cur.fetchone()["c"]
            cur.execute(
                "SELECT COUNT(*) AS c FROM conversations c WHERE "
                "JSON_EXTRACT(c.messages, '$[*].kind') IS NULL"
            )
            legacy = cur.fetchone()["c"]
            return {
                "total": total,
                "with_plan": with_plan,
                "plain_chat": total - with_plan,
                "note": "with_plan=会话内含行程卡片；plain_chat=纯聊天会话",
            }


# ---------------- must_visit（内容管理） ----------------


def get_must_visit(city: str = "") -> Optional[List[Dict[str, Any]]]:
    """
    后台优先读取 must_visit 表；表里无该城市数据返回 None（由 planner 回退 py）。

    Args:
        city: 城市（空字符串返回所有城市）

    Returns:
        Optional[List[Dict[str, Any]]]: 必去景点列表，无数据返回 None
    """
    with read_connection() as conn:
        with conn.cursor() as cur:
            if city:
                cur.execute(
                    "SELECT id, city, name, kw, category, rating, priority FROM must_visit "
                    "WHERE city=%s ORDER BY priority DESC, id",
                    (city,),
                )
            else:
                cur.execute(
                    "SELECT id, city, name, kw, category, rating, priority FROM must_visit "
                    "ORDER BY city, priority DESC, id"
                )
            rows = cur.fetchall()
            if not rows:
                return None
            return [
                {
                    "id": r["id"],
                    "city": r["city"],
                    "name": r["name"],
                    "kw": r["kw"],
                    "category": r["category"],
                    "rating": float(r["rating"]),
                    "priority": r["priority"],
                }
                for r in rows
            ]


def add_must_visit(
    city: str,
    name: str,
    category: str = "景点",
    rating: float = 4.5,
    kw: str = "",
    priority: int = 50,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    添加必去景点。

    Args:
        city: 城市
        name: 景点名称
        category: 分类（景点/美食/购物等）
        rating: 评分
        kw: 关键词
        priority: 优先级

    Returns:
        Tuple[Optional[Dict[str, Any]], Optional[str]]: (新建景点信息, 错误信息)
    """
    if not city or not name:
        return None, "城市与地标名不能为空"
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO must_visit (city, name, kw, category, rating, priority, created_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (
                    city,
                    name,
                    kw,
                    category,
                    rating,
                    priority,
                    datetime.datetime.now(),
                ),
            )
            new_id = cur.lastrowid
            return {"id": new_id, "city": city, "name": name}, None


def update_must_visit(mid: int, fields: Dict[str, Any]) -> bool:
    """
    更新必去景点。

    Args:
        mid: 景点ID
        fields: 要更新的字段（name/kw/category/rating/priority/city）

    Returns:
        bool: 是否成功
    """
    allowed = {"name", "kw", "category", "rating", "priority", "city"}
    updates, params = [], []
    for k, v in fields.items():
        if k in allowed:
            updates.append(f"{k}=%s")
            params.append(v)
    if not updates:
        return False
    params.append(mid)
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE must_visit SET {', '.join(updates)} WHERE id=%s", params
            )
            return cur.rowcount > 0


def delete_must_visit(mid: int) -> bool:
    """
    删除必去景点。

    Args:
        mid: 景点ID

    Returns:
        bool: 是否成功
    """
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM must_visit WHERE id=%s", (mid,))
            return cur.rowcount > 0


# ---------------- AI 生成日志 ----------------


def add_gen_log(
    kind: str, model: str, status: str, ms: int, detail: str = ""
) -> None:
    """
    添加 AI 生成日志。

    Args:
        kind: 类型（plan/intent/chat）
        model: 模型名称
        status: 状态（ok/fail）
        ms: 耗时（毫秒）
        detail: 详情
    """
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO generation_log (kind, model, status, ms, detail, created_at) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (kind, model, status, ms, detail, datetime.datetime.now()),
            )


def list_gen_logs(limit: int = 50) -> List[Dict[str, Any]]:
    """
    获取 AI 生成日志列表。

    Args:
        limit: 返回数量

    Returns:
        List[Dict[str, Any]]: 日志列表
    """
    with read_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, kind, model, status, ms, detail, created_at FROM generation_log "
                "ORDER BY id DESC LIMIT %s",
                (limit,),
            )
            return [
                {
                    "id": r["id"],
                    "kind": r["kind"],
                    "model": r["model"],
                    "status": r["status"],
                    "ms": r["ms"],
                    "detail": r["detail"] or "",
                    "created_at": str(r["created_at"]),
                }
                for r in cur.fetchall()
            ]


# ---------------- 系统配置 ----------------


def get_config(include_secret: bool = False) -> Dict[str, Any]:
    """
    返回 site_config 全量（键值对），带默认值兜底。

    include_secret=False（默认）时剔除敏感键（如 amap_key），供 C 端公开接口使用；
    后台管理接口传 include_secret=True 读取完整配置。

    Args:
        include_secret: 是否包含敏感配置

    Returns:
        Dict[str, Any]: 系统配置
    """
    defaults = {
        "brand_slogan": "世界在等你，去见山海！",
        "brand_hero": "用对话生成你的专属旅行计划",
        "brand_footer": "去见山海 · 激发行走天下的勇气",
        "ttl_geo_days": "7",
        "ttl_poi_days": "1",
        "ttl_route_min": "30",
        "ttl_weather_h": "2",
    }
    with read_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT k, v FROM site_config")
            rows = {r["k"]: r["v"] for r in cur.fetchall()}
        merged = dict(defaults)
        merged.update(rows)
        if not include_secret:
            merged.pop("amap_key", None)
            merged.pop("tencent_key", None)
        return merged


def set_config(pairs: Dict[str, Any]) -> None:
    """
    设置系统配置（upsert）。

    Args:
        pairs: 配置键值对
    """
    with transaction() as conn:
        with conn.cursor() as cur:
            for k, v in pairs.items():
                cur.execute(
                    "INSERT INTO site_config (k, v, updated_at) VALUES (%s,%s,%s) "
                    "ON DUPLICATE KEY UPDATE v=VALUES(v), updated_at=VALUES(updated_at)",
                    (k, str(v), datetime.datetime.now()),
                )
