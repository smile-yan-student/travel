"""
地图服务 - 地理编码模块。

从 amap.py 抽出的地理编码功能：
- 内置地名坐标表加载和查询
- geocode：地名 -> 坐标（本地库→缓存→高德→腾讯→内置兜底）

功能特性：
- 地名 -> 坐标转换
- 多级检索优先级：本地行政区域库（上下文消歧）→ 缓存 → 高德 → 腾讯 → 内置地名表兜底
- 知名景点坐标知识库（解决同名地点歧义）
- 同名地点歧义处理（用户明确指定行政区域时尊重用户指定）
- 第三方命中后自动增量回写本地行政区域库（减少后续调用）
- TTL缓存（7天）

使用方式：
    from app.services.map.geocode import geocode, lookup_place_geo, load_place_geo

    # 地名 -> 坐标
    result = await geocode("杭州")
    print(result["lng"])  # 120.155
    print(result["lat"])  # 30.274
    print(result["city"])  # 杭州市
    print(result["source"])  # local / amap / tencent / fallback / famous_landmark

    # 带上下文消歧
    result = await geocode("大明湖", context_province="山东", context_city="济南")

    # 内置地名坐标查询
    coords = lookup_place_geo("杭州")  # [120.155, 30.274]

    # 加载内置地名坐标表
    data = load_place_geo()
"""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from ...core import geo_local
from ...infrastructure import logger as log_mod
from ...infrastructure.cache import TTL_GEO, cache, get_ttl
from .client import (
    AMAP_BASE,
    CITY_CENTERS,
    TENCENT_BASE,
    amap_get,
    provider,
    tencent_get,
)

_amap_logger = log_mod.get_logger("amap")

_PLACE_GEO: Optional[Dict[str, Any]] = None


def load_place_geo() -> Dict[str, Any]:
    """
    懒加载内置地名坐标表（data/place_geo.json）。

    Returns:
        Dict[str, Any]: 地名坐标表数据
    """
    global _PLACE_GEO
    if _PLACE_GEO is None:
        try:
            path = (
                Path(__file__).resolve().parent.parent.parent
                / "data"
                / "place_geo.json"
            )
            _PLACE_GEO = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            _PLACE_GEO = {}
    return _PLACE_GEO


def lookup_place_geo(city: str) -> Optional[List[float]]:
    """
    内置地名坐标查询：地级市 / 省 / 精确区县 / 区县->所属地级市。找不到返回 None。

    Args:
        city: 城市名称

    Returns:
        Optional[List[float]]: 坐标 [经度, 纬度]，找不到返回 None
    """
    d = load_place_geo()
    if not d:
        return None
    cities: Dict[str, Any] = d.get("cities", {})
    base = city.strip()
    candidates = {
        base,
        base + "市",
        base + "区",
        base + "县",
        base.rstrip("市"),
        base.rstrip("区"),
        base.rstrip("县"),
    }
    # 1) 地级市
    for name in candidates:
        if name in cities:
            return cities[name]
    # 2) 省
    for name in candidates:
        if name in d.get("provinces", {}):
            return d["provinces"][name]
    # 3) 精确区县（含坐标的大城市辖区）
    for name in candidates:
        if name in d.get("districts_geo", {}):
            return d["districts_geo"][name]
    # 4) 区县 -> 所属地级市
    for name in candidates:
        parent = d.get("district_to_city", {}).get(name)
        if parent and parent in cities:
            return cities[parent]
    return None


async def geocode(
    city: str,
    context_province: Optional[str] = None,
    context_city: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    地名 -> {lng, lat, city, adcode, formatted, level, parent, source, ambiguous?, candidates?}。

    检索优先级：本地行政区域库（上下文消歧）→ 缓存 → 高德 → 腾讯 → 内置地名表兜底。
    第三方命中后自动增量回写本地行政区域库（减少后续调用）。

    Args:
        city: 地名
        context_province: 上下文省份（用于消歧）
        context_city: 上下文城市（用于消歧）

    Returns:
        Optional[Dict[str, Any]]: 地理编码结果，找不到返回 None
    """
    city = (city or "").strip()
    if not city:
        return None

    # 判断输入是否包含明确的行政区域信息（用户已指定城市/省份）
    # 如"乌鲁木齐大明湖"、"新疆的大明湖"、"北京市圆明园"
    has_explicit_region = any(
        kw in city for kw in ["市", "省", "自治区", "地区", "自治州", "的"]
    )

    # 0) 优先知名景点坐标知识库（仅当用户未明确指定行政区域时使用）
    # 解决同名地点歧义，如"大明湖"默认指济南的，但"乌鲁木齐大明湖"应尊重用户指定
    if not has_explicit_region:
        try:
            from ...data.repositories.poi_hierarchy_repository import (
                PoiHierarchyRepository,
            )

            repo = PoiHierarchyRepository()
            # 从数据库查询著名景点坐标
            famous = repo.get_main_poi_by_name(city)
            if famous and famous.get("lng") and famous.get("lat"):
                return {
                    "lng": float(famous["lng"]),
                    "lat": float(famous["lat"]),
                    "city": famous.get("city", city),
                    "adcode": famous.get("adcode", ""),
                    "province": "",
                    "district": famous.get("district", ""),
                    "level": "景点",
                    "parent": famous.get("city", ""),
                    "formatted": f"{famous.get('city', '')}{city}",
                    "source": "famous_landmark",
                }
        except Exception:
            pass

    # 1) 优先本地行政区域检索（上下文消歧）
    entry, candidates, resolved = geo_local.lookup_with_context(
        city, context_province, context_city
    )
    if entry:
        result = {
            "lng": entry["lng"],
            "lat": entry["lat"],
            "city": entry.get("name", city),
            "adcode": entry.get("adcode", ""),
            "province": "",
            "district": "",
            "level": entry.get("level", ""),
            "parent": entry.get("parent"),
            "formatted": entry.get("name", city),
            "source": "local",
        }
        if not resolved and len(candidates) > 1:
            result["ambiguous"] = True
            result["candidates"] = [
                {
                    "name": c.get("name"),
                    "level": c.get("level"),
                    "parent": c.get("parent"),
                    "lng": c.get("lng"),
                    "lat": c.get("lat"),
                }
                for c in candidates
            ]
        return result

    # 1.5) 本地未命中但有同名候选
    all_candidates = geo_local.lookup_all(city)
    if all_candidates:
        entry = all_candidates[0]
        result = {
            "lng": entry["lng"],
            "lat": entry["lat"],
            "city": entry.get("name", city),
            "adcode": entry.get("adcode", ""),
            "province": "",
            "district": "",
            "level": entry.get("level", ""),
            "parent": entry.get("parent"),
            "formatted": entry.get("name", city),
            "source": "local",
            "ambiguous": True,
            "candidates": [
                {
                    "name": c.get("name"),
                    "level": c.get("level"),
                    "parent": c.get("parent"),
                    "lng": c.get("lng"),
                    "lat": c.get("lat"),
                }
                for c in all_candidates
            ],
        }
        return result

    # 2) 缓存（7 天）
    prov = provider()
    key = f"geo:{prov}:{city}"
    hit = cache.get("geo", key, get_ttl("geo", TTL_GEO))
    if hit is not None:
        return hit

    # 3) 第三方：高德优先 → 腾讯兜底
    result = None
    if prov == "amap":
        data = await amap_get(
            f"{AMAP_BASE}/geocode/geo", {"address": city, "city": city}
        )
        if data and data.get("geocodes"):
            g = data["geocodes"][0]
            lng, lat = g.get("location", "").split(",")
            result = {
                "lng": float(lng),
                "lat": float(lat),
                "city": g.get("city", city),
                "adcode": g.get("adcode", ""),
                "province": g.get("province", ""),
                "district": g.get("district", ""),
                "level": g.get("level", ""),
                "formatted": g.get("formatted_address", city),
                "source": "amap",
            }
    if result is None and prov == "tencent":
        data = await tencent_get(
            f"{TENCENT_BASE}/geocoder/v1/", {"address": city}
        )
        if data and data.get("result"):
            r = data["result"]
            loc = r.get("location") or {}
            ad = r.get("ad_info") or {}
            result = {
                "lng": float(loc.get("lng", 0)),
                "lat": float(loc.get("lat", 0)),
                "city": ad.get("city") or city,
                "adcode": ad.get("adcode", ""),
                "province": ad.get("province", ""),
                "district": ad.get("district", ""),
                "level": str(r.get("level", "")),
                "formatted": r.get("title") or r.get("address") or city,
                "source": "tencent",
            }

    # 4) 第三方命中：写入缓存 + 增量回写本地行政区域库
    if result and result.get("lng") and result.get("lat"):
        cache.set("geo", key, result)
        geo_local.save_entry(
            {
                "name": result.get("city") or city,
                "adcode": result.get("adcode", ""),
                "level": result.get("level", ""),
                "lng": result["lng"],
                "lat": result["lat"],
                "parent": result.get("province") or None,
            }
        )
        return result

    # 5) 第三方失败兜底：CITY_CENTERS → 内置地名表 → 返回 None
    center = CITY_CENTERS.get(city.rstrip("市")) or lookup_place_geo(city)
    if not center:
        _amap_logger.warning(
            "geocode_not_found",
            extra={"fields": {"city": city, "provider": prov}},
        )
        return None
    result = {
        "lng": center[0],
        "lat": center[1],
        "city": city,
        "adcode": "",
        "province": "",
        "district": "",
        "level": "",
        "formatted": city,
        "source": "fallback",
    }
    cache.set("geo", key, result)
    return result
