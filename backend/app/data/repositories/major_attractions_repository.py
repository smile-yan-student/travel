"""
主要景点库仓库（Major Attractions Repository）。

负责主要景点的数据库操作，包括：
- 查询主要景点（按城市、按名称、按分类等）
- 添加主要景点
- 更新主要景点
- 删除主要景点（软删除/硬删除）
- 批量导入主要景点
- 获取所有城市列表
- 获取统计信息

功能特性：
- 按城市查询主要景点
- 按名称查询主要景点
- 多条件搜索主要景点
- 添加主要景点（支持JSON字段）
- 更新主要景点（支持JSON字段）
- 删除主要景点（软删除/硬删除）
- 批量导入主要景点（幂等）
- 获取所有有主要景点的城市
- 获取统计信息

使用方式：
    from app.data.repositories.major_attractions_repository import (
        get_major_attractions_by_city,
        get_major_attraction_by_name,
        search_major_attractions,
        add_major_attraction,
        update_major_attraction,
        delete_major_attraction,
        batch_import_major_attractions,
        get_all_cities,
        get_stats
    )

    # 按城市获取主要景点
    attractions = get_major_attractions_by_city("杭州市")

    # 按名称获取主要景点
    attraction = get_major_attraction_by_name("西湖", "杭州市")

    # 搜索主要景点
    results = search_major_attractions(
        keyword="西湖", city="杭州市", category="景点", limit=10
    )

    # 添加主要景点
    new_id = add_major_attraction({
        "name": "西湖",
        "city": "杭州市",
        "province": "浙江省",
        "category": "景点",
        "level": "5A",
        "must_visit": True
    })
"""
import json
from typing import Any, Dict, List, Optional

from ..database import execute_query, get_conn, transaction


def get_major_attractions_by_city(
    city: str, include_inactive: bool = False
) -> List[Dict[str, Any]]:
    """
    根据城市获取主要景点。

    排序优先级：priority > must_visit > hot。

    Args:
        city: 城市名称
        include_inactive: 是否包含无效的景点

    Returns:
        List[Dict[str, Any]]: 主要景点列表

    Example:
        >>> attractions = get_major_attractions_by_city("杭州市")
        >>> print(len(attractions))
        10
    """
    sql = """
        SELECT * FROM major_attractions
        WHERE city = %s
    """
    params = [city]

    if not include_inactive:
        sql += " AND is_active = 1"

    sql += " ORDER BY priority DESC, must_visit DESC, hot DESC"

    return execute_query(sql, tuple(params), fetch="all") or []


def get_major_attraction_by_name(
    name: str, city: str = ""
) -> Optional[Dict[str, Any]]:
    """
    根据名称获取主要景点。

    Args:
        name: 景点名称
        city: 城市名称（可选，用于精确匹配）

    Returns:
        Optional[Dict[str, Any]]: 主要景点信息，找不到返回 None

    Example:
        >>> attraction = get_major_attraction_by_name("西湖", "杭州市")
        >>> print(attraction["name"])
        西湖
    """
    if city:
        sql = "SELECT * FROM major_attractions WHERE name = %s AND city = %s AND is_active = 1"
        return execute_query(sql, (name, city), fetch="one")
    else:
        sql = "SELECT * FROM major_attractions WHERE name = %s AND is_active = 1 LIMIT 1"
        return execute_query(sql, (name,), fetch="one")


def search_major_attractions(
    keyword: str = "",
    city: str = "",
    category: str = "",
    level: str = "",
    must_visit: Optional[bool] = None,
    hot: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """
    搜索主要景点。

    支持多条件筛选：关键词、城市、分类、等级、是否必去、是否热门。
    排序优先级：priority > must_visit > hot。

    Args:
        keyword: 关键词（搜索名称和描述）
        city: 城市名称
        category: 分类
        level: 景区等级
        must_visit: 是否必去
        hot: 是否热门
        limit: 返回数量
        offset: 偏移量

    Returns:
        List[Dict[str, Any]]: 主要景点列表

    Example:
        >>> results = search_major_attractions(
        ...     keyword="西湖", city="杭州市", category="景点", limit=10
        ... )
        >>> print(len(results))
        5
    """
    sql = "SELECT * FROM major_attractions WHERE is_active = 1"
    params = []

    if keyword:
        sql += " AND (name LIKE %s OR description LIKE %s)"
        params.extend([f"%{keyword}%", f"%{keyword}%"])

    if city:
        sql += " AND city = %s"
        params.append(city)

    if category:
        sql += " AND category = %s"
        params.append(category)

    if level:
        sql += " AND level = %s"
        params.append(level)

    if must_visit is not None:
        sql += " AND must_visit = %s"
        params.append(1 if must_visit else 0)

    if hot is not None:
        sql += " AND hot = %s"
        params.append(1 if hot else 0)

    sql += " ORDER BY priority DESC, must_visit DESC, hot DESC"
    sql += " LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    return execute_query(sql, tuple(params), fetch="all") or []


def add_major_attraction(attraction: Dict[str, Any]) -> int:
    """
    添加主要景点。

    支持JSON字段：aliases, tags, inner_route, nearby_attractions, avoid_tips。

    Args:
        attraction: 主要景点信息

    Returns:
        int: 新添加的景点ID

    Example:
        >>> new_id = add_major_attraction({
        ...     "name": "西湖",
        ...     "city": "杭州市",
        ...     "province": "浙江省",
        ...     "category": "景点",
        ...     "level": "5A",
        ...     "must_visit": True
        ... })
        >>> print(new_id)
        1
    """
    # 处理JSON字段
    aliases = (
        json.dumps(attraction.get("aliases", []), ensure_ascii=False)
        if attraction.get("aliases")
        else None
    )
    tags = (
        json.dumps(attraction.get("tags", []), ensure_ascii=False)
        if attraction.get("tags")
        else None
    )
    inner_route = (
        json.dumps(attraction.get("inner_route", []), ensure_ascii=False)
        if attraction.get("inner_route")
        else None
    )
    nearby_attractions = (
        json.dumps(attraction.get("nearby_attractions", []), ensure_ascii=False)
        if attraction.get("nearby_attractions")
        else None
    )
    avoid_tips = (
        json.dumps(attraction.get("avoid_tips", []), ensure_ascii=False)
        if attraction.get("avoid_tips")
        else None
    )

    sql = """
        INSERT INTO major_attractions (
            name, aliases, city, district, province, level, category,
            description, recommended_duration, lng, lat, must_visit, hot,
            tags, inner_route, nearby_attractions, best_time, avoid_tips,
            source, priority, is_active
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    params = (
        attraction.get("name", ""),
        aliases,
        attraction.get("city", ""),
        attraction.get("district", ""),
        attraction.get("province", ""),
        attraction.get("level", ""),
        attraction.get("category", "景点"),
        attraction.get("description", ""),
        attraction.get("recommended_duration", 120),
        attraction.get("lng"),
        attraction.get("lat"),
        1 if attraction.get("must_visit", True) else 0,
        1 if attraction.get("hot", False) else 0,
        tags,
        inner_route,
        nearby_attractions,
        attraction.get("best_time", ""),
        avoid_tips,
        attraction.get("source", "manual"),
        attraction.get("priority", 50),
        1 if attraction.get("is_active", True) else 0,
    )

    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.lastrowid


def update_major_attraction(
    attraction_id: int, attraction: Dict[str, Any]
) -> bool:
    """
    更新主要景点。

    支持JSON字段：aliases, tags, inner_route, nearby_attractions, avoid_tips。

    Args:
        attraction_id: 景点ID
        attraction: 要更新的字段

    Returns:
        bool: 是否更新成功

    Example:
        >>> success = update_major_attraction(
        ...     1, {"name": "新名称", "level": "5A", "must_visit": True}
        ... )
        >>> print(success)
        True
    """
    # 构建更新字段
    update_fields = []
    params = []

    for field in [
        "name",
        "city",
        "district",
        "province",
        "level",
        "category",
        "description",
        "recommended_duration",
        "lng",
        "lat",
        "must_visit",
        "hot",
        "best_time",
        "source",
        "priority",
        "is_active",
    ]:
        if field in attraction:
            update_fields.append(f"{field} = %s")
            if field in ["must_visit", "hot", "is_active"]:
                params.append(1 if attraction[field] else 0)
            else:
                params.append(attraction[field])

    # 处理JSON字段
    for json_field in [
        "aliases",
        "tags",
        "inner_route",
        "nearby_attractions",
        "avoid_tips",
    ]:
        if json_field in attraction:
            update_fields.append(f"{json_field} = %s")
            params.append(json.dumps(attraction[json_field], ensure_ascii=False))

    if not update_fields:
        return False

    sql = f"UPDATE major_attractions SET {', '.join(update_fields)} WHERE id = %s"
    params.append(attraction_id)

    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            return cur.rowcount > 0


def delete_major_attraction(
    attraction_id: int, soft_delete: bool = True
) -> bool:
    """
    删除主要景点。

    Args:
        attraction_id: 景点ID
        soft_delete: 是否软删除（默认软删除，设置is_active=0）

    Returns:
        bool: 是否删除成功

    Example:
        >>> # 软删除
        >>> success = delete_major_attraction(1)
        >>> print(success)
        True

        >>> # 硬删除
        >>> success = delete_major_attraction(1, soft_delete=False)
        >>> print(success)
        True
    """
    if soft_delete:
        sql = "UPDATE major_attractions SET is_active = 0 WHERE id = %s"
    else:
        sql = "DELETE FROM major_attractions WHERE id = %s"

    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (attraction_id,))
            return cur.rowcount > 0


def batch_import_major_attractions(
    attractions: List[Dict[str, Any]], update_if_exists: bool = True
) -> Dict[str, int]:
    """
    批量导入主要景点（幂等）。

    如果景点已存在（按名称+城市匹配），则根据update_if_exists决定是否更新。

    Args:
        attractions: 主要景点列表
        update_if_exists: 如果已存在是否更新

    Returns:
        Dict[str, int]: 导入结果统计（added, updated, skipped, failed）

    Example:
        >>> result = batch_import_major_attractions([
        ...     {"name": "西湖", "city": "杭州市", "must_visit": True},
        ...     {"name": "灵隐寺", "city": "杭州市", "must_visit": True}
        ... ])
        >>> print(result)
        {'added': 2, 'updated': 0, 'skipped': 0, 'failed': 0}
    """
    result = {"added": 0, "updated": 0, "skipped": 0, "failed": 0}

    for attraction in attractions:
        try:
            # 检查是否已存在
            existing = get_major_attraction_by_name(
                attraction.get("name", ""),
                attraction.get("city", ""),
            )

            if existing:
                if update_if_exists:
                    update_major_attraction(existing["id"], attraction)
                    result["updated"] += 1
                else:
                    result["skipped"] += 1
            else:
                add_major_attraction(attraction)
                result["added"] += 1
        except Exception:
            result["failed"] += 1

    return result


def get_all_cities() -> List[str]:
    """
    获取所有有主要景点的城市。

    Returns:
        List[str]: 城市名称列表（按字母排序）

    Example:
        >>> cities = get_all_cities()
        >>> print(cities)
        ['北京市', '杭州市', '济南市']
    """
    sql = "SELECT DISTINCT city FROM major_attractions WHERE is_active = 1 ORDER BY city"
    result = execute_query(sql, fetch="all") or []
    return [row["city"] for row in result if row.get("city")]


def get_stats() -> Dict[str, Any]:
    """
    获取主要景点库统计信息。

    包括：
    - 总景点数
    - 必去景点数
    - 热门景点数
    - 城市数
    - 省份数

    Returns:
        Dict[str, Any]: 统计信息

    Example:
        >>> stats = get_stats()
        >>> print(stats["total"])
        100
        >>> print(stats["must_visit_count"])
        50
    """
    sql = """
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN must_visit = 1 THEN 1 ELSE 0 END) as must_visit_count,
            SUM(CASE WHEN hot = 1 THEN 1 ELSE 0 END) as hot_count,
            COUNT(DISTINCT city) as city_count,
            COUNT(DISTINCT province) as province_count
        FROM major_attractions
        WHERE is_active = 1
    """
    result = execute_query(sql, fetch="one")
    return result or {}
