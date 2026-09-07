"""
地图服务 - 路径规划模块。

从 amap.py 抽出的路径规划功能：
- route：两点间交通方案（缓存30分钟）
- route_tencent：腾讯 direction 接口
- route_impl：路径规划实现（自驾/公共交通/骑行/步行/混合）

功能特性：
- 路径规划（两点间交通方案）
- 多种出行方式支持（自驾/公共交通/骑行/步行/混合）
- TTL缓存（30分钟，路况会波动，短 TTL；规划参考足够）
- 高德/腾讯双Provider兼容
- 短距离自动步行（<1.5km 一律步行）
- 失败回退均速估算

使用方式：
    from app.services.map.route import route

    # 查询路径
    result = await route([120.15, 30.28], [120.17, 30.30], "公共交通")
    print(result["distance_m"])  # 距离（米）
    print(result["transit_min"])  # 时间（分钟）
    print(result["transport"])  # 交通方式
"""
from typing import Any, Dict, List, Optional

from ...config import settings
from ...infrastructure.cache import TTL_ROUTE, cache, get_ttl
from .client import (
    AMAP_BASE,
    TENCENT_BASE,
    amap_get,
    haversine,
    provider,
    tencent_get,
)


async def route(
    origin: List[float], destination: List[float], traffic_mode: str = "混合"
) -> Dict[str, Any]:
    """
    两点间交通方案 -> {distance_m, transit_min, transport}。

    traffic_mode：自驾 / 公共交通 / 混合（默认）。
    真实模式下调用高德接口；步行<1.5km 一律步行。
    结果缓存 30 分钟（路况会波动，短 TTL；规划参考足够）。

    Args:
        origin: 起点坐标 [经度, 纬度]
        destination: 终点坐标 [经度, 纬度]
        traffic_mode: 出行方式（自驾/公共交通/骑行/步行/混合）

    Returns:
        Dict[str, Any]: 交通方案（distance_m, transit_min, transport）

    Example:
        >>> result = await route([120.15, 30.28], [120.17, 30.30], "公共交通")
        >>> print(result["distance_m"])
        2500
        >>> print(result["transit_min"])
        15
        >>> print(result["transport"])
        公交地铁
    """
    key = (
        f"route:{origin[0]:.5f},{origin[1]:.5f}|"
        f"{destination[0]:.5f},{destination[1]:.5f}|{traffic_mode}"
    )
    hit = cache.get("route", key, get_ttl("route", TTL_ROUTE))
    if hit is not None:
        return hit
    result = await route_impl(origin, destination, traffic_mode)
    if result:
        cache.set("route", key, result)
    return result


async def route_tencent(
    origin: List[float], destination: List[float], mode: str
) -> Optional[Dict[str, Any]]:
    """
    腾讯 direction：driving/transit/walking/bicycling，成功返回 {distance_m, transit_min, transport}。

    Args:
        origin: 起点坐标 [经度, 纬度]
        destination: 终点坐标 [经度, 纬度]
        mode: 出行方式（自驾/公共交通/骑行/步行/混合）

    Returns:
        Optional[Dict[str, Any]]: 交通方案，失败返回 None
    """
    f = f"{origin[1]},{origin[0]}"  # 腾讯 from/to 为 纬度,经度
    t = f"{destination[1]},{destination[0]}"
    ep = {
        "骑行": "bicycling/",
        "步行": "walking/",
        "公共交通": "transit/",
        "自驾": "driving/",
        "混合": "driving/",
    }.get(mode, "driving/")
    data = await tencent_get(
        f"{TENCENT_BASE}/direction/v1/{ep}", {"from": f, "to": t}
    )
    if not data:
        return None
    routes = (data.get("result") or {}).get("routes") or []
    if not routes:
        return None
    r = routes[0]
    transport = {
        "骑行": "骑行",
        "步行": "步行",
        "公共交通": "公交地铁",
        "自驾": "驾车",
        "混合": "驾车",
    }.get(mode, "驾车")
    return {
        "distance_m": int(r.get("distance", 0)),
        "transit_min": max(1, int(r.get("duration", 0)) // 60),
        "transport": transport,
    }


async def route_impl(
    origin: List[float], destination: List[float], traffic_mode: str = "混合"
) -> Dict[str, Any]:
    """
    路径规划实现（自驾/公共交通/骑行/步行/混合）。

    Args:
        origin: 起点坐标 [经度, 纬度]
        destination: 终点坐标 [经度, 纬度]
        traffic_mode: 出行方式（自驾/公共交通/骑行/步行/混合）

    Returns:
        Dict[str, Any]: 交通方案（distance_m, transit_min, transport）
    """
    o = f"{origin[0]},{origin[1]}"
    d = f"{destination[0]},{destination[1]}"
    dist_est = haversine(origin[0], origin[1], destination[0], destination[1])

    # 腾讯模式：direction 优先，失败回退均速估算（不调用高德）
    if provider() == "tencent":
        tr = await route_tencent(origin, destination, traffic_mode)
        if tr:
            return tr

    # 骑行模式
    if traffic_mode == "骑行":
        if settings.amap_ready:
            b = await amap_get(
                f"{AMAP_BASE}/direction/bicycling",
                {"origin": o, "destination": d},
            )
            if b and b.get("route", {}).get("paths"):
                path = b["route"]["paths"][0]
                return {
                    "distance_m": int(path.get("distance", dist_est)),
                    "transit_min": int(path.get("duration", 0)) // 60,
                    "transport": "骑行",
                }
        return {
            "distance_m": dist_est,
            "transit_min": max(5, round(dist_est / (15 * 1000 / 60))),
            "transport": "骑行",
        }

    # 步行模式（或短距离）
    if traffic_mode == "步行" or dist_est <= 1500:
        if settings.amap_ready:
            w = await amap_get(
                f"{AMAP_BASE}/direction/walking",
                {"origin": o, "destination": d},
            )
            if w and w.get("route", {}).get("paths"):
                path = w["route"]["paths"][0]
                return {
                    "distance_m": int(path.get("distance", dist_est)),
                    "transit_min": int(path.get("duration", 0)) // 60,
                    "transport": "步行",
                }
        return {
            "distance_m": dist_est,
            "transit_min": max(3, round(dist_est / 70)),
            "transport": "步行",
        }

    # 公共交通模式
    if traffic_mode == "公共交通":
        if settings.amap_ready:
            t = await amap_get(
                f"{AMAP_BASE}/direction/transit/integrated",
                {"origin": o, "destination": d, "city": ""},
            )
            if t and t.get("route", {}).get("transits"):
                tr = t["route"]["transits"][0]
                dur = int(tr.get("duration", 0)) // 60
                return {
                    "distance_m": dist_est,
                    "transit_min": max(5, dur),
                    "transport": "公交地铁",
                }
        # 估算：公交/地铁均速 ~22km/h
        return {
            "distance_m": dist_est,
            "transit_min": max(10, round(dist_est / (22 * 1000 / 60))),
            "transport": "公交地铁",
        }

    # 自驾 / 混合
    if settings.amap_ready:
        v = await amap_get(
            f"{AMAP_BASE}/direction/driving",
            {"origin": o, "destination": d},
        )
        if v and v.get("route", {}).get("paths"):
            path = v["route"]["paths"][0]
            return {
                "distance_m": int(path.get("distance", dist_est)),
                "transit_min": int(path.get("duration", 0)) // 60,
                "transport": "驾车",
            }
    speed = 35 * 1000 / 60
    return {
        "distance_m": dist_est,
        "transit_min": max(8, round(dist_est / speed)),
        "transport": "驾车",
    }
