"""
地图服务模块。

从 amap.py 拆分的模块化地图服务：
- client：基础客户端（HTTP请求、Provider探测、距离计算、城市坐标）
- geocode：地理编码（地名→坐标）
- poi：POI搜索（按类别/行政分级/就近/周边探索/点位解析/酒店）
- route：路径规划（两点间交通方案）
- weather：天气查询

所有函数保持与原 amap.py 相同的接口，向后兼容。
"""
from .client import (
    provider, probe_amap, probe_tencent,
    haversine, AMAP_BASE, TENCENT_BASE, CITY_CENTERS,
    amap_get, tencent_get, tencent_sign,
)
from .geocode import geocode, lookup_place_geo, load_place_geo
from .poi import (
    search_pois, search_attractions, search_around, explore_around,
    resolve_poi, search_hotel_near,
    infer_category, dedup, to_float, to_str, filter_by_range, quality_trim,
)
from .route import route, route_impl, route_tencent
from .weather import weather, weather_tips

__all__ = [
    # client
    "provider", "probe_amap", "probe_tencent",
    "haversine", "AMAP_BASE", "TENCENT_BASE", "CITY_CENTERS",
    "amap_get", "tencent_get", "tencent_sign",
    # geocode
    "geocode", "lookup_place_geo", "load_place_geo",
    # poi
    "search_pois", "search_attractions", "search_around", "explore_around",
    "resolve_poi", "search_hotel_near",
    "infer_category", "dedup", "to_float", "to_str", "filter_by_range", "quality_trim",
    # route
    "route", "route_impl", "route_tencent",
    # weather
    "weather", "weather_tips",
]
