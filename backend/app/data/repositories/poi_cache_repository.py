"""
POI检索缓存数据访问层（Repository）。

按行政区域缓存POI检索结果，优先从数据库检索，数据库不存在再去第三方检索，减少第三方API调用。

缓存策略：
- 按行政区域（省/市/区县/adcode）+ 分类缓存
- 缓存有效期：7天（可配置）
- 缓存失效后自动重新检索
- 使用 INSERT ... ON DUPLICATE KEY UPDATE 实现幂等保存

功能特性：
- 按行政区域获取POI缓存
- 保存POI到缓存（幂等）
- 清理过期缓存
- 获取缓存统计信息
- 单例模式

使用方式：
    from app.data.repositories.poi_cache_repository import get_poi_cache_repository

    # 获取单例
    repo = get_poi_cache_repository()

    # 按行政区域获取POI
    pois = repo.get_pois_by_region(
        province="浙江省",
        city="杭州市",
        district="西湖区",
        category="景点",
        limit=50
    )

    # 保存POI到缓存
    saved_count = repo.save_pois(
        pois=[...],
        province="浙江省",
        city="杭州市",
        category="景点",
        source="amap"
    )

    # 清理过期缓存
    cleared_count = repo.clear_expired_cache()

    # 获取缓存统计
    stats = repo.get_cache_stats()
"""
import datetime
import json
from typing import Any, Dict, List, Optional

from ..database import read_connection, transaction


class PoiCacheRepository:
    """
    POI检索缓存数据访问类。

    提供POI缓存的查询、保存、清理、统计功能。

    Example:
        >>> repo = PoiCacheRepository()
        >>> pois = repo.get_pois_by_region(city="杭州市", category="景点")
        >>> print(len(pois))
        10
    """

    # 缓存有效期（天）
    CACHE_EXPIRE_DAYS: int = 7

    def get_pois_by_region(
        self,
        province: str = "",
        city: str = "",
        district: str = "",
        adcode: str = "",
        category: str = "景点",
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        按行政区域从缓存中获取POI。

        查询优先级：
        1. 如果指定了 adcode，则按 adcode 查询
        2. 否则按 province/city/district 组合查询

        只返回未过期的缓存（expire_at IS NULL OR expire_at > NOW()）。

        Args:
            province: 省份
            city: 城市
            district: 区县
            adcode: 行政区划代码
            category: 分类（景点/美食/购物/夜生活）
            limit: 返回数量上限

        Returns:
            List[Dict[str, Any]]: POI列表，如果缓存不存在或已过期返回空列表

        Example:
            >>> repo = PoiCacheRepository()
            >>> pois = repo.get_pois_by_region(
            ...     province="浙江省", city="杭州市", category="景点", limit=50
            ... )
            >>> print(pois[0]["name"])
            西湖
        """
        try:
            with read_connection() as conn:
                with conn.cursor() as cursor:
                    # 构建查询条件
                    conditions = ["is_active = 1", "category = %s"]
                    params = [category]

                    if adcode:
                        conditions.append("adcode = %s")
                        params.append(adcode)
                    else:
                        if province:
                            conditions.append("province = %s")
                            params.append(province)
                        if city:
                            conditions.append("city = %s")
                            params.append(city)
                        if district:
                            conditions.append("district = %s")
                            params.append(district)

                    # 检查缓存是否过期
                    conditions.append("(expire_at IS NULL OR expire_at > NOW())")

                    where_clause = " AND ".join(conditions)
                    sql = f"""
                        SELECT * FROM poi_cache
                        WHERE {where_clause}
                        ORDER BY rating DESC, cached_at DESC
                        LIMIT %s
                    """
                    params.append(limit)

                    cursor.execute(sql, params)
                    results = cursor.fetchall()

                    # 转换为POI格式
                    pois = []
                    for row in results:
                        poi = {
                            "id": row.get("poi_id") or str(row.get("id")),
                            "name": row.get("poi_name", ""),
                            "category": row.get("category", ""),
                            "address": row.get("address", ""),
                            "lng": float(row["lng"]) if row.get("lng") else 0,
                            "lat": float(row["lat"]) if row.get("lat") else 0,
                            "rating": float(row["rating"]) if row.get("rating") else 0,
                            "tel": row.get("tel", ""),
                            "business_area": row.get("business_area", ""),
                            "source": row.get("source", "amap"),
                            "cached": True,
                        }
                        # 解析原始数据
                        if row.get("raw_data"):
                            try:
                                raw_data = (
                                    json.loads(row["raw_data"])
                                    if isinstance(row["raw_data"], str)
                                    else row["raw_data"]
                                )
                                poi.update(raw_data)
                            except Exception:
                                pass
                        pois.append(poi)

                    return pois
        except Exception as e:
            print(f"[PoiCacheRepository] get_pois_by_region error: {e}")
            return []

    def save_pois(
        self,
        pois: List[Dict[str, Any]],
        province: str = "",
        city: str = "",
        district: str = "",
        adcode: str = "",
        category: str = "景点",
        source: str = "amap",
    ) -> int:
        """
        保存POI到缓存（幂等）。

        使用 INSERT ... ON DUPLICATE KEY UPDATE 实现幂等保存。
        如果POI已存在，则更新相关字段。

        行政区域信息优先级：
        1. 外部参数（province/city/district/adcode）
        2. POI数据中的字段（pname/cityname/adname/adcode）

        Args:
            pois: POI列表
            province: 省份
            city: 城市
            district: 区县
            adcode: 行政区划代码
            category: 分类
            source: 数据来源（amap/tencent）

        Returns:
            int: 保存的POI数量

        Example:
            >>> repo = PoiCacheRepository()
            >>> saved_count = repo.save_pois(
            ...     pois=[{"name": "西湖", "lng": 120.15, "lat": 30.28}],
            ...     city="杭州市",
            ...     category="景点",
            ...     source="amap"
            ... )
            >>> print(saved_count)
            1
        """
        if not pois:
            return 0

        try:
            with transaction() as conn:
                with conn.cursor() as cursor:
                    # 计算过期时间
                    expire_at = (
                        datetime.datetime.now()
                        + datetime.timedelta(days=self.CACHE_EXPIRE_DAYS)
                    ).strftime("%Y-%m-%d %H:%M:%S")

                    saved_count = 0
                    for poi in pois:
                        try:
                            poi_name = poi.get("name", "")
                            if not poi_name:
                                continue

                            poi_id = poi.get("id", "")
                            address = poi.get("address", "")
                            lng = poi.get("lng", 0)
                            lat = poi.get("lat", 0)
                            rating = poi.get("rating", 0)
                            tel = poi.get("tel", "")
                            business_area = poi.get("business_area", "")

                            # 从POI数据中获取行政区域信息（如果外部参数为空）
                            poi_province = (
                                province
                                or poi.get("province", "")
                                or poi.get("pname", "")
                            )
                            poi_city = (
                                city
                                or poi.get("cityname", "")
                                or poi.get("city", "")
                            )
                            poi_district = (
                                district
                                or poi.get("district", "")
                                or poi.get("adname", "")
                            )
                            poi_adcode = adcode or poi.get("adcode", "")

                            # 保存原始数据（排除已有的字段）
                            raw_data = {}
                            for key, value in poi.items():
                                if key not in [
                                    "id",
                                    "name",
                                    "category",
                                    "address",
                                    "lng",
                                    "lat",
                                    "rating",
                                    "tel",
                                    "business_area",
                                    "province",
                                    "cityname",
                                    "city",
                                    "district",
                                    "adname",
                                    "adcode",
                                ]:
                                    raw_data[key] = value
                            raw_data_json = (
                                json.dumps(raw_data, ensure_ascii=False)
                                if raw_data
                                else None
                            )

                            # 使用INSERT ... ON DUPLICATE KEY UPDATE
                            sql = """
                                INSERT INTO poi_cache
                                (province, city, district, adcode, category, poi_name, poi_id, address, lng, lat, rating, tel, business_area, source, raw_data, cached_at, expire_at, is_active)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s, 1)
                                ON DUPLICATE KEY UPDATE
                                    province = VALUES(province),
                                    city = VALUES(city),
                                    district = VALUES(district),
                                    adcode = VALUES(adcode),
                                    address = VALUES(address),
                                    lng = VALUES(lng),
                                    lat = VALUES(lat),
                                    rating = VALUES(rating),
                                    tel = VALUES(tel),
                                    business_area = VALUES(business_area),
                                    raw_data = VALUES(raw_data),
                                    cached_at = NOW(),
                                    expire_at = VALUES(expire_at),
                                    is_active = 1
                            """
                            cursor.execute(
                                sql,
                                (
                                    poi_province,
                                    poi_city,
                                    poi_district,
                                    poi_adcode,
                                    category,
                                    poi_name,
                                    poi_id,
                                    address,
                                    lng,
                                    lat,
                                    rating,
                                    tel,
                                    business_area,
                                    source,
                                    raw_data_json,
                                    expire_at,
                                ),
                            )
                            saved_count += 1
                        except Exception as e:
                            print(
                                f"[PoiCacheRepository] save_poi error: {e}, poi: {poi.get('name', '')}"
                            )
                            continue

                    return saved_count
        except Exception as e:
            print(f"[PoiCacheRepository] save_pois error: {e}")
            return 0

    def clear_expired_cache(self) -> int:
        """
        清理过期的缓存。

        将过期的缓存标记为无效（is_active = 0）。

        Returns:
            int: 清理的缓存数量

        Example:
            >>> repo = PoiCacheRepository()
            >>> cleared_count = repo.clear_expired_cache()
            >>> print(cleared_count)
            100
        """
        try:
            with transaction() as conn:
                with conn.cursor() as cursor:
                    sql = "UPDATE poi_cache SET is_active = 0 WHERE expire_at < NOW() AND is_active = 1"
                    cursor.execute(sql)
                    return cursor.rowcount
        except Exception as e:
            print(f"[PoiCacheRepository] clear_expired_cache error: {e}")
            return 0

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息。

        包括：
        - 总缓存数量
        - 有效缓存数量
        - 过期缓存数量
        - 按分类统计
        - 按城市统计（前10）

        Returns:
            Dict[str, Any]: 缓存统计信息

        Example:
            >>> repo = PoiCacheRepository()
            >>> stats = repo.get_cache_stats()
            >>> print(stats["total"])
            1000
            >>> print(stats["active"])
            800
        """
        try:
            with read_connection() as conn:
                with conn.cursor() as cursor:
                    # 总缓存数量
                    cursor.execute("SELECT COUNT(*) as total FROM poi_cache")
                    total = cursor.fetchone()["total"]

                    # 有效缓存数量
                    cursor.execute(
                        "SELECT COUNT(*) as active FROM poi_cache WHERE is_active = 1 AND (expire_at IS NULL OR expire_at > NOW())"
                    )
                    active = cursor.fetchone()["active"]

                    # 过期缓存数量
                    cursor.execute(
                        "SELECT COUNT(*) as expired FROM poi_cache WHERE is_active = 0 OR expire_at < NOW()"
                    )
                    expired = cursor.fetchone()["expired"]

                    # 按分类统计
                    cursor.execute(
                        """
                        SELECT category, COUNT(*) as count
                        FROM poi_cache
                        WHERE is_active = 1 AND (expire_at IS NULL OR expire_at > NOW())
                        GROUP BY category
                    """
                    )
                    by_category = {
                        row["category"]: row["count"] for row in cursor.fetchall()
                    }

                    # 按城市统计（前10）
                    cursor.execute(
                        """
                        SELECT city, COUNT(*) as count
                        FROM poi_cache
                        WHERE is_active = 1 AND (expire_at IS NULL OR expire_at > NOW())
                        GROUP BY city
                        ORDER BY count DESC
                        LIMIT 10
                    """
                    )
                    by_city = {row["city"]: row["count"] for row in cursor.fetchall()}

                    return {
                        "total": total,
                        "active": active,
                        "expired": expired,
                        "by_category": by_category,
                        "by_city": by_city,
                    }
        except Exception as e:
            print(f"[PoiCacheRepository] get_cache_stats error: {e}")
            return {
                "total": 0,
                "active": 0,
                "expired": 0,
                "by_category": {},
                "by_city": {},
            }


# 单例
_poi_cache_repository: Optional[PoiCacheRepository] = None


def get_poi_cache_repository() -> PoiCacheRepository:
    """
    获取POI缓存数据访问层单例。

    Returns:
        PoiCacheRepository: POI缓存数据访问层实例

    Example:
        >>> repo = get_poi_cache_repository()
        >>> pois = repo.get_pois_by_region(city="杭州市")
    """
    global _poi_cache_repository
    if _poi_cache_repository is None:
        _poi_cache_repository = PoiCacheRepository()
    return _poi_cache_repository
