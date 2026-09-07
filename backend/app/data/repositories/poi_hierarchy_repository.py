"""
POI层级数据访问层（Repository）。

提供主POI、内部子POI、周边附属POI的CRUD操作，以及数据迁移功能。

功能特性：
- 主POI管理（列表、获取、创建、更新、删除）
- 内部子POI管理（列表、创建、更新、删除）
- 周边附属POI管理（列表、创建、更新、删除）
- 数据迁移（从静态数据迁移到数据库）
- 统计信息

使用方式：
    from app.data.repositories.poi_hierarchy_repository import PoiHierarchyRepository

    # 获取主POI列表
    main_pois, total = PoiHierarchyRepository.list_main_pois(
        city="杭州市", page=1, page_size=20
    )

    # 获取单个主POI（含内部子POI和周边附属POI）
    poi = PoiHierarchyRepository.get_main_poi(1)

    # 根据名称和城市获取主POI
    poi = PoiHierarchyRepository.get_main_poi_by_name("西湖", "杭州市")

    # 创建主POI
    main_id = PoiHierarchyRepository.create_main_poi({
        "name": "西湖",
        "city": "杭州市",
        "level": "5A",
        "category": "景点"
    })

    # 创建内部子POI
    inner_id = PoiHierarchyRepository.create_inner_poi(main_id, {
        "name": "断桥残雪",
        "sort_order": 1,
        "must_see": True
    })

    # 创建周边附属POI
    nearby_id = PoiHierarchyRepository.create_nearby_poi(main_id, {
        "name": "河坊街",
        "category": "美食街",
        "distance_m": 2000
    })
"""
import json
from typing import Any, Dict, List, Optional, Tuple

from ..database import read_connection, transaction


class PoiHierarchyRepository:
    """
    POI层级数据访问类。

    提供主POI、内部子POI、周边附属POI的CRUD操作。

    Example:
        >>> poi = PoiHierarchyRepository.get_main_poi_by_name("西湖", "杭州市")
        >>> print(poi["name"])
        西湖
    """

    # ========== 主POI管理 ==========

    @staticmethod
    def list_main_pois(
        city: Optional[str] = None,
        level: Optional[str] = None,
        keyword: Optional[str] = None,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        获取主POI列表（分页）。

        支持按城市、等级、关键词、是否活跃筛选。
        排序：城市 > 等级 > 名称。

        Args:
            city: 城市名称（模糊匹配，可选）
            level: 景区等级（可选）
            keyword: 关键词（名称/描述/别名模糊匹配，可选）
            is_active: 是否活跃（可选）
            page: 页码（从1开始）
            page_size: 每页大小

        Returns:
            Tuple[List[Dict[str, Any]], int]: (主POI列表, 总数)

        Example:
            >>> main_pois, total = PoiHierarchyRepository.list_main_pois(
            ...     city="杭州市", page=1, page_size=20
            ... )
            >>> print(total)
            10
        """
        with read_connection() as conn:
            with conn.cursor() as cur:
                conditions = []
                params = []
                if city:
                    conditions.append("city LIKE %s")
                    params.append(f"%{city}%")
                if level:
                    conditions.append("level = %s")
                    params.append(level)
                if keyword:
                    conditions.append(
                        "(name LIKE %s OR description LIKE %s OR alias LIKE %s)"
                    )
                    params.extend(
                        [f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"]
                    )
                if is_active is not None:
                    conditions.append("is_active = %s")
                    params.append(1 if is_active else 0)
                where = " AND ".join(conditions) if conditions else "1=1"

                cur.execute(
                    f"SELECT COUNT(*) as total FROM poi_main WHERE {where}", params
                )
                total = cur.fetchone()["total"]

                offset = (page - 1) * page_size
                cur.execute(
                    f"SELECT * FROM poi_main WHERE {where} ORDER BY city, level DESC, name LIMIT %s OFFSET %s",
                    params + [page_size, offset],
                )
                return cur.fetchall(), total

    @staticmethod
    def get_main_poi(poi_id: int) -> Optional[Dict[str, Any]]:
        """
        获取单个主POI（含内部子POI和周边附属POI）。

        Args:
            poi_id: 主POI ID

        Returns:
            Optional[Dict[str, Any]]: 主POI信息（含inner_route和nearby_attractions），不存在返回 None

        Example:
            >>> poi = PoiHierarchyRepository.get_main_poi(1)
            >>> print(poi["name"])
            西湖
            >>> print(len(poi["inner_route"]))
            5
        """
        with read_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM poi_main WHERE id = %s", (poi_id,))
                poi = cur.fetchone()
                if not poi:
                    return None

                # 获取内部子POI
                cur.execute(
                    "SELECT * FROM poi_inner WHERE poi_main_id = %s AND is_active = 1 ORDER BY sort_order",
                    (poi_id,),
                )
                poi["inner_route"] = cur.fetchall()

                # 获取周边附属POI
                cur.execute(
                    "SELECT * FROM poi_nearby WHERE poi_main_id = %s AND is_active = 1 ORDER BY distance_m",
                    (poi_id,),
                )
                poi["nearby_attractions"] = cur.fetchall()

                # 解析JSON字段
                if poi.get("alias"):
                    try:
                        poi["alias"] = json.loads(poi["alias"])
                    except Exception:
                        poi["alias"] = []
                else:
                    poi["alias"] = []
                if poi.get("avoid_tips"):
                    try:
                        poi["avoid_tips"] = json.loads(poi["avoid_tips"])
                    except Exception:
                        poi["avoid_tips"] = []
                else:
                    poi["avoid_tips"] = []

                return poi

    @staticmethod
    def get_main_poi_by_name(
        name: str, city: str = ""
    ) -> Optional[Dict[str, Any]]:
        """
        根据名称和城市获取主POI。

        Args:
            name: 主POI名称
            city: 城市名称（可选，用于精确匹配）

        Returns:
            Optional[Dict[str, Any]]: 主POI信息（含内部子POI和周边附属POI），不存在返回 None

        Example:
            >>> poi = PoiHierarchyRepository.get_main_poi_by_name("西湖", "杭州市")
            >>> print(poi["name"])
            西湖
        """
        with read_connection() as conn:
            with conn.cursor() as cur:
                if city:
                    cur.execute(
                        "SELECT id FROM poi_main WHERE name = %s AND city = %s AND is_active = 1",
                        (name, city),
                    )
                else:
                    cur.execute(
                        "SELECT id FROM poi_main WHERE name = %s AND is_active = 1 LIMIT 1",
                        (name,),
                    )
                row = cur.fetchone()
                if not row:
                    return None
                return PoiHierarchyRepository.get_main_poi(row["id"])

    @staticmethod
    def create_main_poi(data: Dict[str, Any]) -> int:
        """
        创建主POI。

        Args:
            data: 主POI信息（name, city, district, category, level, description, recommended_duration, best_time, avoid_tips, lng, lat）

        Returns:
            int: 新建主POI的ID

        Example:
            >>> main_id = PoiHierarchyRepository.create_main_poi({
            ...     "name": "西湖",
            ...     "city": "杭州市",
            ...     "level": "5A",
            ...     "category": "景点"
            ... })
            >>> print(main_id)
            1
        """
        with transaction() as conn:
            with conn.cursor() as cur:
                alias = json.dumps(data.get("alias", []), ensure_ascii=False)
                avoid_tips = json.dumps(
                    data.get("avoid_tips", []), ensure_ascii=False
                )
                cur.execute(
                    """INSERT INTO poi_main
                       (name, alias, city, district, category, level, description,
                        recommended_duration, best_time, avoid_tips, lng, lat)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        data["name"],
                        alias,
                        data.get("city", ""),
                        data.get("district", ""),
                        data.get("category", "景点"),
                        data.get("level", ""),
                        data.get("description", ""),
                        data.get("recommended_duration", 180),
                        data.get("best_time", ""),
                        avoid_tips,
                        data.get("lng"),
                        data.get("lat"),
                    ),
                )
                return cur.lastrowid

    @staticmethod
    def update_main_poi(poi_id: int, data: Dict[str, Any]) -> bool:
        """
        更新主POI。

        Args:
            poi_id: 主POI ID
            data: 要更新的字段

        Returns:
            bool: 是否更新成功

        Example:
            >>> success = PoiHierarchyRepository.update_main_poi(
            ...     1, {"name": "新名称", "level": "5A"}
            ... )
            >>> print(success)
            True
        """
        if not data:
            return False
        with transaction() as conn:
            with conn.cursor() as cur:
                update_data = data.copy()
                if "alias" in update_data:
                    update_data["alias"] = json.dumps(
                        update_data["alias"], ensure_ascii=False
                    )
                if "avoid_tips" in update_data:
                    update_data["avoid_tips"] = json.dumps(
                        update_data["avoid_tips"], ensure_ascii=False
                    )
                fields = ", ".join([f"{k} = %s" for k in update_data.keys()])
                values = list(update_data.values()) + [poi_id]
                cur.execute(
                    f"UPDATE poi_main SET {fields} WHERE id = %s", values
                )
                return cur.rowcount > 0

    @staticmethod
    def delete_main_poi(poi_id: int) -> bool:
        """
        删除主POI（同时删除内部子POI和周边附属POI）。

        Args:
            poi_id: 主POI ID

        Returns:
            bool: 是否删除成功

        Example:
            >>> success = PoiHierarchyRepository.delete_main_poi(1)
            >>> print(success)
            True
        """
        with transaction() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM poi_inner WHERE poi_main_id = %s", (poi_id,))
                cur.execute(
                    "DELETE FROM poi_nearby WHERE poi_main_id = %s", (poi_id,)
                )
                cur.execute("DELETE FROM poi_main WHERE id = %s", (poi_id,))
                return cur.rowcount > 0

    # ========== 内部子POI管理 ==========

    @staticmethod
    def list_inner_pois(poi_main_id: int) -> List[Dict[str, Any]]:
        """
        获取主POI的内部子POI列表。

        Args:
            poi_main_id: 主POI ID

        Returns:
            List[Dict[str, Any]]: 内部子POI列表（按sort_order排序）

        Example:
            >>> inner_pois = PoiHierarchyRepository.list_inner_pois(1)
            >>> print(len(inner_pois))
            5
        """
        with read_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM poi_inner WHERE poi_main_id = %s ORDER BY sort_order",
                    (poi_main_id,),
                )
                return cur.fetchall()

    @staticmethod
    def create_inner_poi(poi_main_id: int, data: Dict[str, Any]) -> int:
        """
        创建内部子POI。

        Args:
            poi_main_id: 主POI ID
            data: 内部子POI信息（name, description, duration_min, sort_order, highlight, must_see）

        Returns:
            int: 新建内部子POI的ID

        Example:
            >>> inner_id = PoiHierarchyRepository.create_inner_poi(1, {
            ...     "name": "断桥残雪",
            ...     "sort_order": 1,
            ...     "must_see": True
            ... })
            >>> print(inner_id)
            1
        """
        with transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO poi_inner
                       (poi_main_id, name, description, duration_min, sort_order, highlight, must_see)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (
                        poi_main_id,
                        data["name"],
                        data.get("description", ""),
                        data.get("duration_min", 30),
                        data.get("sort_order", 0),
                        data.get("highlight", ""),
                        1 if data.get("must_see") else 0,
                    ),
                )
                return cur.lastrowid

    @staticmethod
    def update_inner_poi(inner_id: int, data: Dict[str, Any]) -> bool:
        """
        更新内部子POI。

        Args:
            inner_id: 内部子POI ID
            data: 要更新的字段

        Returns:
            bool: 是否更新成功

        Example:
            >>> success = PoiHierarchyRepository.update_inner_poi(
            ...     1, {"name": "新名称", "must_see": True}
            ... )
            >>> print(success)
            True
        """
        if not data:
            return False
        with transaction() as conn:
            with conn.cursor() as cur:
                if "must_see" in data:
                    data["must_see"] = 1 if data["must_see"] else 0
                fields = ", ".join([f"{k} = %s" for k in data.keys()])
                values = list(data.values()) + [inner_id]
                cur.execute(
                    f"UPDATE poi_inner SET {fields} WHERE id = %s", values
                )
                return cur.rowcount > 0

    @staticmethod
    def delete_inner_poi(inner_id: int) -> bool:
        """
        删除内部子POI。

        Args:
            inner_id: 内部子POI ID

        Returns:
            bool: 是否删除成功

        Example:
            >>> success = PoiHierarchyRepository.delete_inner_poi(1)
            >>> print(success)
            True
        """
        with transaction() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM poi_inner WHERE id = %s", (inner_id,))
                return cur.rowcount > 0

    # ========== 周边附属POI管理 ==========

    @staticmethod
    def list_nearby_pois(poi_main_id: int) -> List[Dict[str, Any]]:
        """
        获取主POI的周边附属POI列表。

        Args:
            poi_main_id: 主POI ID

        Returns:
            List[Dict[str, Any]]: 周边附属POI列表（按distance_m排序）

        Example:
            >>> nearby_pois = PoiHierarchyRepository.list_nearby_pois(1)
            >>> print(len(nearby_pois))
            3
        """
        with read_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM poi_nearby WHERE poi_main_id = %s ORDER BY distance_m",
                    (poi_main_id,),
                )
                return cur.fetchall()

    @staticmethod
    def create_nearby_poi(poi_main_id: int, data: Dict[str, Any]) -> int:
        """
        创建周边附属POI。

        Args:
            poi_main_id: 主POI ID
            data: 周边附属POI信息（name, category, description, distance_m, recommended_slot, duration_min）

        Returns:
            int: 新建周边附属POI的ID

        Example:
            >>> nearby_id = PoiHierarchyRepository.create_nearby_poi(1, {
            ...     "name": "河坊街",
            ...     "category": "美食街",
            ...     "distance_m": 2000
            ... })
            >>> print(nearby_id)
            1
        """
        with transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO poi_nearby
                       (poi_main_id, name, category, description, distance_m, recommended_slot, duration_min)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (
                        poi_main_id,
                        data["name"],
                        data.get("category", "美食街"),
                        data.get("description", ""),
                        data.get("distance_m", 500),
                        data.get("recommended_slot", "晚上"),
                        data.get("duration_min", 60),
                    ),
                )
                return cur.lastrowid

    @staticmethod
    def update_nearby_poi(nearby_id: int, data: Dict[str, Any]) -> bool:
        """
        更新周边附属POI。

        Args:
            nearby_id: 周边附属POI ID
            data: 要更新的字段

        Returns:
            bool: 是否更新成功

        Example:
            >>> success = PoiHierarchyRepository.update_nearby_poi(
            ...     1, {"name": "新名称", "distance_m": 1000}
            ... )
            >>> print(success)
            True
        """
        if not data:
            return False
        with transaction() as conn:
            with conn.cursor() as cur:
                fields = ", ".join([f"{k} = %s" for k in data.keys()])
                values = list(data.values()) + [nearby_id]
                cur.execute(
                    f"UPDATE poi_nearby SET {fields} WHERE id = %s", values
                )
                return cur.rowcount > 0

    @staticmethod
    def delete_nearby_poi(nearby_id: int) -> bool:
        """
        删除周边附属POI。

        Args:
            nearby_id: 周边附属POI ID

        Returns:
            bool: 是否删除成功

        Example:
            >>> success = PoiHierarchyRepository.delete_nearby_poi(1)
            >>> print(success)
            True
        """
        with transaction() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM poi_nearby WHERE id = %s", (nearby_id,))
                return cur.rowcount > 0

    # ========== 数据迁移 ==========

    @staticmethod
    def migrate_from_static() -> Dict[str, Any]:
        """
        从静态数据迁移到数据库。

        从 poi_hierarchy.py 和 poi_hierarchy_extra.py 静态数据文件迁移到数据库。
        如果主POI已存在（按名称+城市匹配），则跳过。

        Returns:
            Dict[str, Any]: 迁移结果统计（migrated, skipped, total）

        Example:
            >>> result = PoiHierarchyRepository.migrate_from_static()
            >>> print(result)
            {'migrated': 50, 'skipped': 10, 'total': 60}
        """
        try:
            from ..static.poi_hierarchy import POI_HIERARCHY
            from ..static.poi_hierarchy_extra import EXTRA_POI_HIERARCHY
        except ImportError:
            return {"migrated": 0, "skipped": 0, "error": "静态数据文件不存在"}

        migrated = 0
        skipped = 0
        all_pois = {**POI_HIERARCHY, **EXTRA_POI_HIERARCHY}

        for name, poi in all_pois.items():
            # 检查是否已存在
            existing = PoiHierarchyRepository.get_main_poi_by_name(name, poi.city)
            if existing:
                skipped += 1
                continue

            try:
                # 创建主POI
                poi_dict = poi.to_dict()
                main_id = PoiHierarchyRepository.create_main_poi(poi_dict)

                # 创建内部子POI
                for inner in poi.inner_route:
                    inner_dict = inner.to_dict()
                    PoiHierarchyRepository.create_inner_poi(main_id, inner_dict)

                # 创建周边附属POI
                for nearby in poi.nearby_attractions:
                    nearby_dict = nearby.to_dict()
                    PoiHierarchyRepository.create_nearby_poi(main_id, nearby_dict)

                migrated += 1
            except Exception as e:
                skipped += 1
                print(f"迁移失败: {name} - {str(e)}")

        return {"migrated": migrated, "skipped": skipped, "total": len(all_pois)}

    # ========== 统计 ==========

    @staticmethod
    def get_stats() -> Dict[str, Any]:
        """
        获取POI层级统计信息。

        包括：
        - 主POI总数
        - 内部子POI总数
        - 周边附属POI总数
        - 城市分布
        - 等级分布

        Returns:
            Dict[str, Any]: 统计信息

        Example:
            >>> stats = PoiHierarchyRepository.get_stats()
            >>> print(stats["total_main"])
            100
            >>> print(stats["total_inner"])
            500
        """
        with read_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) as total FROM poi_main WHERE is_active = 1"
                )
                total_main = cur.fetchone()["total"]

                cur.execute(
                    "SELECT COUNT(*) as total FROM poi_inner WHERE is_active = 1"
                )
                total_inner = cur.fetchone()["total"]

                cur.execute(
                    "SELECT COUNT(*) as total FROM poi_nearby WHERE is_active = 1"
                )
                total_nearby = cur.fetchone()["total"]

                cur.execute(
                    "SELECT city, COUNT(*) as count FROM poi_main WHERE is_active = 1 GROUP BY city ORDER BY count DESC"
                )
                city_distribution = cur.fetchall()

                cur.execute(
                    "SELECT level, COUNT(*) as count FROM poi_main WHERE is_active = 1 AND level != '' GROUP BY level ORDER BY count DESC"
                )
                level_distribution = cur.fetchall()

                return {
                    "total_main": total_main,
                    "total_inner": total_inner,
                    "total_nearby": total_nearby,
                    "city_distribution": city_distribution,
                    "level_distribution": level_distribution,
                }
