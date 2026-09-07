"""
历史名人数据访问层（Repository）。

提供历史名人、相关地点的CRUD操作，以及数据迁移功能。
已接入TTL缓存：get_figure、get_figure_by_name、get_stats带缓存，
创建/更新/删除时自动清除相关缓存。

功能特性：
- 历史名人管理（列表、获取、创建、更新、删除）
- 相关地点管理（创建、更新、删除）
- 审核功能（审核、待审核列表、审核统计）
- 数据迁移（从静态数据迁移到数据库）
- 统计信息
- TTL缓存（1天）

使用方式：
    from app.data.repositories.historical_figure_repository import HistoricalFigureRepository

    # 获取历史名人列表
    figures, total = HistoricalFigureRepository.list_figures(
        category="历史名人", page=1, page_size=20
    )

    # 获取单个历史名人（含相关地点）
    figure = HistoricalFigureRepository.get_figure(1)

    # 根据名称获取历史名人（支持别名匹配）
    figure = HistoricalFigureRepository.get_figure_by_name("孔子")

    # 创建历史名人
    figure_id = HistoricalFigureRepository.create_figure({
        "name": "孔子",
        "category": "历史名人",
        "brief_intro": "中国古代思想家、教育家",
        "related_places": [
            {"place_name": "曲阜", "relation": "出生地", "attractions": ["孔庙", "孔府", "孔林"]}
        ]
    })
"""
import json
from typing import Any, Dict, List, Optional, Tuple

from ...infrastructure.cache import TTL_POI, cache
from ..database import read_connection, transaction


# 缓存命名空间
CACHE_NS = "historical_figure"
# 历史名人数据TTL（1天，数据变化不频繁）
CACHE_TTL = TTL_POI


def _cache_key(*parts: Any) -> str:
    """
    生成缓存键。

    Args:
        *parts: 缓存键的各个部分

    Returns:
        str: 拼接后的缓存键
    """
    return ":".join(str(p) for p in parts)


def _invalidate_figure_cache(
    figure_id: Optional[int] = None, name: Optional[str] = None
) -> None:
    """
    清除历史名人相关缓存。

    简单有效：清除整个命名空间的缓存。

    Args:
        figure_id: 历史名人ID（可选）
        name: 历史名人名称（可选）
    """
    # 清除整个命名空间的缓存（简单有效）
    cache.clear(CACHE_NS)


class HistoricalFigureRepository:
    """
    历史名人数据访问类。

    提供历史名人、相关地点的CRUD操作，以及数据迁移功能。

    Example:
        >>> figure = HistoricalFigureRepository.get_figure_by_name("孔子")
        >>> print(figure["name"])
        孔子
    """

    @staticmethod
    def list_figures(
        category: Optional[str] = None,
        keyword: Optional[str] = None,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        获取历史名人列表（分页）。

        支持按分类、关键词、是否活跃筛选。
        排序：分类 > 名称。

        Args:
            category: 分类（历史名人/革命先辈/文人墨客，可选）
            keyword: 关键词（名称/简介/别名模糊匹配，可选）
            is_active: 是否活跃（可选）
            page: 页码（从1开始）
            page_size: 每页大小

        Returns:
            Tuple[List[Dict[str, Any]], int]: (历史名人列表, 总数)

        Example:
            >>> figures, total = HistoricalFigureRepository.list_figures(
            ...     category="历史名人", page=1, page_size=20
            ... )
            >>> print(total)
            50
        """
        with read_connection() as conn:
            with conn.cursor() as cur:
                conditions = []
                params = []
                if category:
                    conditions.append("category = %s")
                    params.append(category)
                if keyword:
                    conditions.append(
                        "(name LIKE %s OR brief_intro LIKE %s OR aliases LIKE %s)"
                    )
                    params.extend(
                        [f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"]
                    )
                if is_active is not None:
                    conditions.append("is_active = %s")
                    params.append(1 if is_active else 0)
                where = " AND ".join(conditions) if conditions else "1=1"

                cur.execute(
                    f"SELECT COUNT(*) as total FROM historical_figure WHERE {where}",
                    params,
                )
                total = cur.fetchone()["total"]

                offset = (page - 1) * page_size
                cur.execute(
                    f"SELECT * FROM historical_figure WHERE {where} ORDER BY category, name LIMIT %s OFFSET %s",
                    params + [page_size, offset],
                )
                figures = cur.fetchall()
                # 解析JSON字段
                for f in figures:
                    if f.get("aliases"):
                        try:
                            f["aliases"] = json.loads(f["aliases"])
                        except Exception:
                            f["aliases"] = []
                    else:
                        f["aliases"] = []
                return figures, total

    @staticmethod
    def get_figure(figure_id: int) -> Optional[Dict[str, Any]]:
        """
        获取单个历史名人（含相关地点），带缓存。

        Args:
            figure_id: 历史名人ID

        Returns:
            Optional[Dict[str, Any]]: 历史名人信息（含related_places），不存在返回 None

        Example:
            >>> figure = HistoricalFigureRepository.get_figure(1)
            >>> print(figure["name"])
            孔子
            >>> print(len(figure["related_places"]))
            3
        """
        # 先查缓存
        cache_key = _cache_key("figure", figure_id)
        cached = cache.get(CACHE_NS, cache_key, CACHE_TTL)
        if cached is not None:
            return cached

        with read_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM historical_figure WHERE id = %s", (figure_id,)
                )
                figure = cur.fetchone()
                if not figure:
                    return None

                # 解析JSON字段
                if figure.get("aliases"):
                    try:
                        figure["aliases"] = json.loads(figure["aliases"])
                    except Exception:
                        figure["aliases"] = []
                else:
                    figure["aliases"] = []

                # 获取相关地点
                cur.execute(
                    "SELECT * FROM historical_figure_place WHERE figure_id = %s AND is_active = 1 ORDER BY sort_order",
                    (figure_id,),
                )
                places = cur.fetchall()
                for p in places:
                    if p.get("attractions"):
                        try:
                            p["attractions"] = json.loads(p["attractions"])
                        except Exception:
                            p["attractions"] = []
                    else:
                        p["attractions"] = []
                figure["related_places"] = places

                # 写入缓存
                cache.set(CACHE_NS, cache_key, figure, ttl=CACHE_TTL)
                return figure

    @staticmethod
    def get_figure_by_name(name: str) -> Optional[Dict[str, Any]]:
        """
        根据名称获取历史名人（支持别名匹配），带缓存。

        匹配优先级：
        1. 精确匹配名称
        2. 匹配别名

        Args:
            name: 历史名人名称或别名

        Returns:
            Optional[Dict[str, Any]]: 历史名人信息（含related_places），不存在返回 None

        Example:
            >>> figure = HistoricalFigureRepository.get_figure_by_name("孔子")
            >>> print(figure["name"])
            孔子
        """
        # 先查缓存
        cache_key = _cache_key("figure_by_name", name)
        cached = cache.get(CACHE_NS, cache_key, CACHE_TTL)
        if cached is not None:
            return cached

        with read_connection() as conn:
            with conn.cursor() as cur:
                # 先精确匹配名称
                cur.execute(
                    "SELECT id FROM historical_figure WHERE name = %s AND is_active = 1",
                    (name,),
                )
                row = cur.fetchone()
                if row:
                    figure = HistoricalFigureRepository.get_figure(row["id"])
                    cache.set(CACHE_NS, cache_key, figure, ttl=CACHE_TTL)
                    return figure

                # 再匹配别名
                cur.execute(
                    "SELECT id, aliases FROM historical_figure WHERE is_active = 1"
                )
                all_figures = cur.fetchall()
                for f in all_figures:
                    if f.get("aliases"):
                        try:
                            aliases = json.loads(f["aliases"])
                        except Exception:
                            aliases = []
                        if name in aliases:
                            figure = HistoricalFigureRepository.get_figure(f["id"])
                            cache.set(CACHE_NS, cache_key, figure, ttl=CACHE_TTL)
                            return figure
                # 缓存未找到的结果（避免重复查询）
                cache.set(CACHE_NS, cache_key, None, ttl=CACHE_TTL)
                return None

    @staticmethod
    def create_figure(data: Dict[str, Any]) -> int:
        """
        创建历史名人。

        支持同时创建相关地点（兼容静态数据格式：name -> place_name）。

        Args:
            data: 历史名人信息（name, aliases, category, brief_intro, travel_theme, related_places）

        Returns:
            int: 新建历史名人的ID

        Example:
            >>> figure_id = HistoricalFigureRepository.create_figure({
            ...     "name": "孔子",
            ...     "category": "历史名人",
            ...     "brief_intro": "中国古代思想家、教育家",
            ...     "related_places": [
            ...         {"place_name": "曲阜", "relation": "出生地", "attractions": ["孔庙", "孔府", "孔林"]}
            ...     ]
            ... })
            >>> print(figure_id)
            1
        """
        with transaction() as conn:
            with conn.cursor() as cur:
                aliases = json.dumps(data.get("aliases", []), ensure_ascii=False)
                cur.execute(
                    """INSERT INTO historical_figure
                       (name, aliases, category, brief_intro, travel_theme)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (
                        data["name"],
                        aliases,
                        data.get("category", "历史名人"),
                        data.get("brief_intro", ""),
                        data.get("travel_theme", ""),
                    ),
                )
                figure_id = cur.lastrowid

                # 创建相关地点（兼容静态数据格式：name -> place_name）
                for place in data.get("related_places", []):
                    place_data = place.copy()
                    if "name" in place_data and "place_name" not in place_data:
                        place_data["place_name"] = place_data.pop("name")
                    HistoricalFigureRepository.create_place(figure_id, place_data)

                # 清除缓存
                _invalidate_figure_cache(
                    figure_id=figure_id, name=data.get("name")
                )
                return figure_id

    @staticmethod
    def update_figure(figure_id: int, data: Dict[str, Any]) -> bool:
        """
        更新历史名人。

        Args:
            figure_id: 历史名人ID
            data: 要更新的字段

        Returns:
            bool: 是否更新成功

        Example:
            >>> success = HistoricalFigureRepository.update_figure(
            ...     1, {"name": "新名称", "category": "历史名人"}
            ... )
            >>> print(success)
            True
        """
        if not data:
            return False
        with transaction() as conn:
            with conn.cursor() as cur:
                update_data = data.copy()
                if "aliases" in update_data:
                    update_data["aliases"] = json.dumps(
                        update_data["aliases"], ensure_ascii=False
                    )
                fields = ", ".join([f"{k} = %s" for k in update_data.keys()])
                values = list(update_data.values()) + [figure_id]
                cur.execute(
                    f"UPDATE historical_figure SET {fields} WHERE id = %s", values
                )
                # 清除缓存
                _invalidate_figure_cache(figure_id=figure_id)
                return cur.rowcount > 0

    @staticmethod
    def delete_figure(figure_id: int) -> bool:
        """
        删除历史名人（同时删除相关地点）。

        Args:
            figure_id: 历史名人ID

        Returns:
            bool: 是否删除成功

        Example:
            >>> success = HistoricalFigureRepository.delete_figure(1)
            >>> print(success)
            True
        """
        with transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM historical_figure_place WHERE figure_id = %s",
                    (figure_id,),
                )
                cur.execute(
                    "DELETE FROM historical_figure WHERE id = %s", (figure_id,)
                )
                # 清除缓存
                _invalidate_figure_cache(figure_id=figure_id)
                return cur.rowcount > 0

    @staticmethod
    def review_figure(
        figure_id: int, status: str, comment: str = ""
    ) -> bool:
        """
        审核历史名人。

        Args:
            figure_id: 人物ID
            status: 审核状态（approved/rejected/pending）
            comment: 审核意见

        Returns:
            bool: 是否成功

        Example:
            >>> success = HistoricalFigureRepository.review_figure(
            ...     1, "approved", "内容准确，审核通过"
            ... )
            >>> print(success)
            True
        """
        if status not in ["approved", "rejected", "pending"]:
            return False

        with transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE historical_figure SET review_status = %s, review_comment = %s, reviewed_at = NOW() WHERE id = %s",
                    (status, comment, figure_id),
                )
                # 清除缓存
                _invalidate_figure_cache(figure_id=figure_id)
                return cur.rowcount > 0

    @staticmethod
    def list_pending_review(
        page: int = 1, page_size: int = 20
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        获取待审核的历史名人列表。

        Args:
            page: 页码（从1开始）
            page_size: 每页大小

        Returns:
            Tuple[List[Dict[str, Any]], int]: (待审核历史名人列表, 总数)

        Example:
            >>> figures, total = HistoricalFigureRepository.list_pending_review()
            >>> print(total)
            5
        """
        with read_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) as total FROM historical_figure WHERE review_status = 'pending'"
                )
                total = cur.fetchone()["total"]

                offset = (page - 1) * page_size
                cur.execute(
                    "SELECT * FROM historical_figure WHERE review_status = 'pending' ORDER BY created_at DESC LIMIT %s OFFSET %s",
                    (page_size, offset),
                )
                figures = cur.fetchall()
                # 解析JSON字段
                for f in figures:
                    if f.get("aliases"):
                        try:
                            f["aliases"] = json.loads(f["aliases"])
                        except Exception:
                            f["aliases"] = []
                    else:
                        f["aliases"] = []
                return figures, total

    @staticmethod
    def get_review_stats() -> Dict[str, Any]:
        """
        获取审核统计信息。

        包括：
        - 总数
        - 待审核数
        - 已通过数
        - 已拒绝数
        - 状态分布

        Returns:
            Dict[str, Any]: 审核统计信息

        Example:
            >>> stats = HistoricalFigureRepository.get_review_stats()
            >>> print(stats["total"])
            50
            >>> print(stats["pending"])
            5
        """
        with read_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT review_status, COUNT(*) as count FROM historical_figure GROUP BY review_status"
                )
                status_distribution = cur.fetchall()

                result = {
                    "total": 0,
                    "pending": 0,
                    "approved": 0,
                    "rejected": 0,
                    "status_distribution": status_distribution,
                }

                for item in status_distribution:
                    status = item["review_status"]
                    count = item["count"]
                    result["total"] += count
                    if status in result:
                        result[status] = count

                return result

    @staticmethod
    def create_place(figure_id: int, data: Dict[str, Any]) -> int:
        """
        创建历史名人相关地点。

        Args:
            figure_id: 历史名人ID
            data: 相关地点信息（place_name, relation, attractions, travel_recommendation, sort_order）

        Returns:
            int: 新建相关地点的ID

        Example:
            >>> place_id = HistoricalFigureRepository.create_place(1, {
            ...     "place_name": "曲阜",
            ...     "relation": "出生地",
            ...     "attractions": ["孔庙", "孔府", "孔林"]
            ... })
            >>> print(place_id)
            1
        """
        with transaction() as conn:
            with conn.cursor() as cur:
                attractions = json.dumps(
                    data.get("attractions", []), ensure_ascii=False
                )
                cur.execute(
                    """INSERT INTO historical_figure_place
                       (figure_id, place_name, relation, attractions, travel_recommendation, sort_order)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (
                        figure_id,
                        data["place_name"],
                        data.get("relation", ""),
                        attractions,
                        data.get("travel_recommendation", ""),
                        data.get("sort_order", 0),
                    ),
                )
                return cur.lastrowid

    @staticmethod
    def update_place(place_id: int, data: Dict[str, Any]) -> bool:
        """
        更新历史名人相关地点。

        Args:
            place_id: 相关地点ID
            data: 要更新的字段

        Returns:
            bool: 是否更新成功

        Example:
            >>> success = HistoricalFigureRepository.update_place(
            ...     1, {"place_name": "新名称", "relation": "主要活动地"}
            ... )
            >>> print(success)
            True
        """
        if not data:
            return False
        with transaction() as conn:
            with conn.cursor() as cur:
                update_data = data.copy()
                if "attractions" in update_data:
                    update_data["attractions"] = json.dumps(
                        update_data["attractions"], ensure_ascii=False
                    )
                fields = ", ".join([f"{k} = %s" for k in update_data.keys()])
                values = list(update_data.values()) + [place_id]
                cur.execute(
                    f"UPDATE historical_figure_place SET {fields} WHERE id = %s",
                    values,
                )
                return cur.rowcount > 0

    @staticmethod
    def delete_place(place_id: int) -> bool:
        """
        删除历史名人相关地点。

        Args:
            place_id: 相关地点ID

        Returns:
            bool: 是否删除成功

        Example:
            >>> success = HistoricalFigureRepository.delete_place(1)
            >>> print(success)
            True
        """
        with transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM historical_figure_place WHERE id = %s", (place_id,)
                )
                return cur.rowcount > 0

    @staticmethod
    def migrate_from_static() -> Dict[str, Any]:
        """
        从静态数据迁移到数据库。

        从 historical_figures.py 静态数据文件迁移到数据库。
        如果历史名人已存在（按名称匹配），则跳过。

        Returns:
            Dict[str, Any]: 迁移结果统计（migrated, skipped, total）

        Example:
            >>> result = HistoricalFigureRepository.migrate_from_static()
            >>> print(result)
            {'migrated': 50, 'skipped': 10, 'total': 60}
        """
        try:
            from ..static.historical_figures import HISTORICAL_FIGURES
        except ImportError:
            return {"migrated": 0, "skipped": 0, "error": "静态数据文件不存在"}

        migrated = 0
        skipped = 0

        for figure_data in HISTORICAL_FIGURES:
            name = figure_data.get("name", "")
            if not name:
                skipped += 1
                continue

            # 检查是否已存在
            existing = HistoricalFigureRepository.get_figure_by_name(name)
            if existing:
                skipped += 1
                continue

            try:
                HistoricalFigureRepository.create_figure(figure_data)
                migrated += 1
            except Exception as e:
                skipped += 1
                print(f"迁移失败: {name} - {str(e)}")

        return {
            "migrated": migrated,
            "skipped": skipped,
            "total": len(HISTORICAL_FIGURES),
        }

    @staticmethod
    def get_stats() -> Dict[str, Any]:
        """
        获取历史名人统计信息，带缓存。

        包括：
        - 历史名人总数
        - 相关地点总数
        - 分类分布

        Returns:
            Dict[str, Any]: 统计信息

        Example:
            >>> stats = HistoricalFigureRepository.get_stats()
            >>> print(stats["total_figures"])
            100
            >>> print(stats["total_places"])
            300
        """
        # 先查缓存
        cache_key = _cache_key("stats")
        cached = cache.get(CACHE_NS, cache_key, CACHE_TTL)
        if cached is not None:
            return cached

        with read_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) as total FROM historical_figure WHERE is_active = 1"
                )
                total_figures = cur.fetchone()["total"]

                cur.execute(
                    "SELECT category, COUNT(*) as count FROM historical_figure WHERE is_active = 1 GROUP BY category"
                )
                category_distribution = cur.fetchall()

                cur.execute(
                    "SELECT COUNT(*) as total FROM historical_figure_place WHERE is_active = 1"
                )
                total_places = cur.fetchone()["total"]

                stats = {
                    "total_figures": total_figures,
                    "total_places": total_places,
                    "category_distribution": category_distribution,
                }
                # 写入缓存
                cache.set(CACHE_NS, cache_key, stats, ttl=CACHE_TTL)
                return stats
