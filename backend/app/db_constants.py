# -*- coding: utf-8 -*-
"""
数据库常量获取服务

优先从数据库 site_config 表获取常量，数据库中没有的使用代码中的默认值。
带有内存缓存机制，避免频繁查询数据库。

使用方式：
    from app.db_constants import get_db_constant, get_db_list, get_db_dict, get_db_int
"""
import json
import threading
import time
from typing import Any, Dict, List, Optional, Tuple


# 缓存有效期（秒）
CACHE_TTL = 300  # 5分钟

# 内存缓存
_cache: Dict[str, Tuple[Any, float]] = {}
_cache_lock = threading.Lock()


def _get_from_cache(key: str) -> Optional[Any]:
    """从缓存中获取值"""
    with _cache_lock:
        item = _cache.get(key)
        if item is None:
            return None
        value, timestamp = item
        if time.time() - timestamp > CACHE_TTL:
            del _cache[key]
            return None
        return value


def _set_to_cache(key: str, value: Any) -> None:
    """设置缓存值"""
    with _cache_lock:
        _cache[key] = (value, time.time())


def _get_from_db(key: str) -> Optional[str]:
    """从数据库获取原始字符串值"""
    try:
        from .data.repositories.admin_repository import get_config
        config = get_config(include_secret=True)
        return config.get(key)
    except Exception as e:
        print(f"[db_constants] 获取数据库配置失败: {key}, {e}")
        return None


def get_db_constant(key: str, default: Any = None) -> Any:
    """
    获取常量值（通用）

    Args:
        key: 配置键名
        default: 默认值（数据库中没有时使用）

    Returns:
        配置值（字符串），如果数据库中没有则返回默认值
    """
    # 1. 先从缓存获取
    cached = _get_from_cache(key)
    if cached is not None:
        return cached

    # 2. 从数据库获取
    value = _get_from_db(key)
    if value is None:
        value = default

    # 3. 写入缓存
    _set_to_cache(key, value)
    return value


def get_db_list(key: str, default: List[str] = None) -> List[str]:
    """
    获取列表类型的常量值（JSON数组）

    Args:
        key: 配置键名
        default: 默认值

    Returns:
        列表值
    """
    if default is None:
        default = []

    value = get_db_constant(key, None)
    if value is None:
        return default

    # 如果已经是列表，直接返回
    if isinstance(value, list):
        return value

    # 尝试解析JSON
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass

    return default


def get_db_dict(key: str, default: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    获取字典类型的常量值（JSON对象）

    Args:
        key: 配置键名
        default: 默认值

    Returns:
        字典值
    """
    if default is None:
        default = {}

    value = get_db_constant(key, None)
    if value is None:
        return default

    # 如果已经是字典，直接返回
    if isinstance(value, dict):
        return value

    # 尝试解析JSON
    try:
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass

    return default


def get_db_int(key: str, default: int = 0) -> int:
    """
    获取整数类型的常量值

    Args:
        key: 配置键名
        default: 默认值

    Returns:
        整数值
    """
    value = get_db_constant(key, None)
    if value is None:
        return default

    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def get_db_float(key: str, default: float = 0.0) -> float:
    """
    获取浮点数类型的常量值

    Args:
        key: 配置键名
        default: 默认值

    Returns:
        浮点数值
    """
    value = get_db_constant(key, None)
    if value is None:
        return default

    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def invalidate_cache(key: str = None) -> None:
    """
    使缓存失效

    Args:
        key: 配置键名，如果为None则清空所有缓存
    """
    with _cache_lock:
        if key is None:
            _cache.clear()
        else:
            _cache.pop(key, None)


def reload_all() -> None:
    """重新加载所有配置（清空缓存）"""
    invalidate_cache(None)


# ============================================================
# 常用常量的便捷获取函数
# ============================================================

def get_closed_markers() -> Tuple[str, ...]:
    """获取闭馆/停业标记词"""
    from .constants import CLOSED_MARKERS
    db_list = get_db_list("closed_markers", list(CLOSED_MARKERS))
    return tuple(db_list)


def get_aux_food_bad_names() -> Tuple[str, ...]:
    """获取美食辅助点的名称护栏"""
    from .constants import AUX_FOOD_BAD_NAMES
    db_list = get_db_list("aux_food_bad_names", list(AUX_FOOD_BAD_NAMES))
    return tuple(db_list)


def get_landmark_words() -> Tuple[str, ...]:
    """获取全国知名地标特征词"""
    from .constants import LANDMARK_WORDS
    db_list = get_db_list("landmark_words", list(LANDMARK_WORDS))
    return tuple(db_list)


def get_scope_keywords() -> Dict[str, List[str]]:
    """获取行政分级 → 景点枚举关键词"""
    from .constants import SCOPE_KEYWORDS
    return get_db_dict("scope_keywords", SCOPE_KEYWORDS)


def get_cluster_max_dist() -> int:
    """获取区域聚类距离上限（米）"""
    from .constants import CLUSTER_MAX_DIST
    return get_db_int("cluster_max_dist", CLUSTER_MAX_DIST)


def get_scope_max_range() -> int:
    """获取省内景点距离市中心上限（米）"""
    from .constants import SCOPE_MAX_RANGE
    return get_db_int("scope_max_range", SCOPE_MAX_RANGE)


def get_ttl_geo() -> int:
    """获取地理编码缓存TTL（秒）"""
    from .constants import TTL_GEO
    days = get_db_int("ttl_geo_days", TTL_GEO // (24 * 3600))
    return days * 24 * 3600


def get_ttl_poi() -> int:
    """获取POI检索缓存TTL（秒）"""
    from .constants import TTL_POI
    days = get_db_int("ttl_poi_days", TTL_POI // (24 * 3600))
    return days * 24 * 3600


def get_ttl_route() -> int:
    """获取路径规划缓存TTL（秒）"""
    from .constants import TTL_ROUTE
    minutes = get_db_int("ttl_route_min", TTL_ROUTE // 60)
    return minutes * 60


def get_ttl_weather() -> int:
    """获取天气缓存TTL（秒）"""
    from .constants import TTL_WEATHER
    hours = get_db_int("ttl_weather_h", TTL_WEATHER // 3600)
    return hours * 3600


def get_brand_slogan() -> str:
    """获取品牌标语"""
    from .constants import DEFAULT_BRAND_SLOGAN
    return get_db_constant("brand_slogan", DEFAULT_BRAND_SLOGAN)


def get_brand_footer() -> str:
    """获取品牌页脚"""
    from .constants import DEFAULT_BRAND_FOOTER
    return get_db_constant("brand_footer", DEFAULT_BRAND_FOOTER)