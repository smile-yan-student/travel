"""
地图服务 - POI搜索模块。

从 amap.py 抽出的 POI搜索功能：
- search_pois：按类别检索 POI（高德→腾讯→无可用Provider返回空）
- search_attractions：行政分级景点检索
- search_around：坐标就近检索
- explore_around：周边探索（放射状）
- resolve_poi：点位名解析（同名消歧）
- search_hotel_near：就近酒店检索
- 内部辅助函数（_filter_by_range、_quality_trim、_attach_must_visit、_infer_category等）

功能特性：
- 双Provider兼容（高德/腾讯），自动降级
- 三级缓存（内存缓存、数据库缓存、TTL缓存）
- 省级数据富化（避免城市名称重复时数据混乱）
- POI类别推断（根据类型和名称推断业务品类）
- 质量裁剪（必去景点优先保留 + 综合评分排序 + 每类限量）
- 范围过滤（剔除离市中心过远的点位）
- 翻页检索（提高景点覆盖率）
- 多类型码检索（提高景点覆盖率）
- 同名消歧（点位名解析）
- 周边探索（放射状展示）

使用方式：
    from app.services.map.poi import search_pois, search_attractions, search_around

    # 按类别检索POI
    pois = await search_pois("北京", center, ["景点", "美食"])

    # 行政分级景点检索
    attractions = await search_attractions("110000", ["景区", "5A"])

    # 坐标就近检索
    around = await search_around(116.4, 39.9, "美食", radius=15000, limit=10)
"""
import asyncio
from typing import Any, Dict, List, Optional, Tuple

from ...config import settings
from ...constants import (
    AMAP_ATTRACTION_KEYWORDS,
    AMAP_POI_TYPES,
    AROUND_TYPES,
    AUX_FOOD_BAD_NAMES,
    CLOSED_MARKERS,
    HOT_RANGE,
    HOTEL_TYPES,
    LANDMARK_WORDS,
    MAX_POOL,
    MAX_RANGE,
    POI_CATEGORIES,
    POI_KEYWORDS_LIMIT,
    POI_SEARCH_OFFSET,
    POI_SEARCH_PAGES,
    TENCENT_POI_KW,
)
from ...infrastructure.cache import TTL_POI, cache, get_ttl
from .client import (
    AMAP_BASE,
    TENCENT_BASE,
    amap_get,
    haversine,
    provider,
    tencent_get,
)


# ---------------- 内部工具 ----------------

def _save_to_memory_cache(province: str, city: str, categories: List[str], pois: List[dict]) -> None:
    """将POI搜索结果写入内存缓存。"""
    if not pois:
        return
    try:
        memory_cache_key = f"{province}:{city}:{','.join(categories)}"
        cache.set("poi_memory", memory_cache_key, pois, ttl=get_ttl("poi_memory", TTL_POI))
        print(f"[search_pois] memory cache saved: {city}, {len(pois)} pois")
    except Exception as e:
        print(f"[search_pois] memory cache save error: {e}")
def to_float(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def to_str(v) -> str:
    """安全转字符串：高德可能返回空数组 [] / None / 数字，需归一为 str。"""
    if v is None:
        return ""
    if isinstance(v, (list, tuple)):
        return "、".join(str(x) for x in v if x)
    return str(v)


def dedup(items: List[dict]) -> List[dict]:
    seen, out = set(), []
    for it in items:
        key = (it["name"], round(it["lng"], 4), round(it["lat"], 4))
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def infer_category(amap_type: str, fallback: str = "景点", name: str = "") -> str:
    """根据高德 POI 真实类型推断业务品类。
    
    优化：
    1. 增加更多类型关键词，提高识别准确率
    2. 结合名称进行判断，避免类别混杂
    3. 过滤民宿、酒店等不应该出现在景点分类中的POI
    """
    t = amap_type or ""
    n = name or ""
    
    # 1. 先根据名称判断（更准确）
    # 民宿、酒店、旅馆等 → 不应该出现在景点分类中
    if any(kw in n for kw in ["民宿", "酒店", "宾馆", "旅馆", "客栈", "住宿", "公寓"]):
        return "美食" if fallback == "美食" else "购物"  # 归到其他类别，不影响景点
    
    # 小吃、快餐、奶茶等 → 美食
    if any(kw in n for kw in ["小吃", "快餐", "奶茶", "饮品", "咖啡", "餐厅", "饭店", "食堂"]):
        return "美食"
    
    # 便利店、超市、药店等 → 购物
    if any(kw in n for kw in ["便利店", "超市", "药店", "商场", "百货", "市场"]):
        return "购物"
    
    # 2. 根据类型判断
    if any(k in t for k in ("娱乐", "影剧院", "夜总会", "KTV", "酒吧", "演出", "歌舞", "夜店", "游戏厅", "棋牌室")):
        return "夜生活"
    if any(k in t for k in ("餐饮", "美食", "咖啡", "茶", "饭店", "餐厅", "小吃", "快餐")):
        return "美食"
    if any(k in t for k in ("购物", "商场", "超市", "百货", "市场", "便利店")):
        return "购物"
    if any(k in t for k in ("风景名胜", "景点", "旅游", "公园", "博物馆", "纪念馆", "寺庙", "文化", "遗址", "古迹", "展馆", "植物园", "动物园", "水族馆", "游乐园", "度假区", "古镇", "古城", "书院", "祠堂", "陵墓", "塔", "阁", "楼", "台", "坛", "桥", "湖", "山", "河", "海", "岛", "洞", "瀑", "泉", "林", "草原", "沙漠", "峡谷", "溶洞")):
        return "景点"
    
    # 3. 如果类型不明确，根据名称判断是否是景点
    if any(kw in n for kw in LANDMARK_WORDS):
        return "景点"
    
    return fallback if fallback in ("景点", "美食", "购物", "夜生活") else "景点"


def filter_by_range(pois: List[dict], center: dict) -> List[dict]:
    """剔除离市中心过远的点位。"""
    cx, cy = center["lng"], center["lat"]
    keep, dropped_by_cat = [], {}
    for p in pois:
        d = haversine(cx, cy, p["lng"], p["lat"])
        limit = HOT_RANGE if p.get("hot") else MAX_RANGE
        if d <= limit:
            keep.append(p)
        else:
            dropped_by_cat.setdefault(p["category"], []).append(p)
    for cat, ps in dropped_by_cat.items():
        if any(p["category"] == cat for p in keep):
            continue
        near = sorted(ps, key=lambda p: haversine(cx, cy, p["lng"], p["lat"]))[:5]
        keep.extend(near)
    return keep


def quality_trim(items: List[dict]) -> List[dict]:
    """候选池质量裁剪：必去景点优先保留 + 综合评分排序 + 每类限量。
    
    优化：
    1. 必去景点（hot=True）不参与限量，始终保留
    2. 不单纯依赖高德评分，结合知名度、必去标记等多维度综合评分
    3. 景点类限量增加，美食/购物/夜生活限量减少
    4. 过滤掉民宿、酒店、小吃等不应该出现在景点分类中的POI
    """
    # 1. 先过滤掉类别混杂的POI
    filtered_items = []
    for p in items:
        category = p.get("category", "")
        name = p.get("name", "")
        amap_type = p.get("type", "") or p.get("poi_type", "")
        
        # 景点分类过滤：排除民宿、酒店、小吃等
        if category == "景点":
            # 检查是否是民宿、酒店、小吃等不应该出现在景点分类中的POI
            bad_keywords = ["民宿", "酒店", "宾馆", "旅馆", "客栈", "小吃", "快餐", "奶茶", "饮品", "便利店", "超市", "药店"]
            if any(kw in name for kw in bad_keywords):
                # 但是如果是hot（必去景点），保留
                if not p.get("hot", False):
                    continue
        
        filtered_items.append(p)
    
    # 2. 按分类分组
    by_cat = {}
    for p in filtered_items:
        by_cat.setdefault(p["category"], []).append(p)
    
    out = []
    # 景点类限量增加到25，其他类别减少
    adjusted_max_pool = {
        "景点": 25,
        "美食": 8,
        "购物": 6,
        "夜生活": 6,
    }
    
    for cat in ("景点", "美食", "购物", "夜生活"):
        lst = by_cat.get(cat, [])
        if not lst:
            continue
        
        # 3. 分离必去景点和普通景点
        hot_items = [p for p in lst if p.get("hot", False)]
        normal_items = [p for p in lst if not p.get("hot", False)]
        
        # 4. 综合评分排序（不单纯依赖高德评分）
        def composite_score(p):
            """综合评分：高德评分 + 知名度 + 必去标记"""
            base_rating = p.get("rating", 0) or 0
            hot_bonus = 2.0 if p.get("hot", False) else 0
            # 名称中包含知名地标特征词的加分
            name = p.get("name", "")
            landmark_bonus = 0.5 if any(kw in name for kw in LANDMARK_WORDS[:20]) else 0
            return base_rating + hot_bonus + landmark_bonus
        
        normal_items_sorted = sorted(normal_items, key=composite_score, reverse=True)
        
        # 5. 必去景点始终保留（不参与限量），普通景点限量
        limit = adjusted_max_pool.get(cat, MAX_POOL.get(cat, 10))
        out.extend(hot_items)  # 必去景点优先
        out.extend(normal_items_sorted[:limit])
    
    return out


def t_poi(p: dict, cat: str) -> Optional[dict]:
    """把腾讯 POI 结果转成统一结构。"""
    loc = p.get("location") or {}
    if not loc.get("lng"):
        return None
    ad = p.get("ad_info") or {}
    return {
        "id": p.get("id", ""), "name": p.get("title", ""),
        "lng": float(loc.get("lng", 0)), "lat": float(loc.get("lat", 0)),
        "address": to_str(p.get("address")),
        "category": infer_category(p.get("category", ""), cat, p.get("title", "")),
        "price": to_float(p.get("price")) if p.get("price") else 0.0,
        "rating": to_float(p.get("rating")) if p.get("rating") else 0.0,
        "district": ad.get("district", "") or "",
        "cityname": ad.get("city", "") or "",
        "province": ad.get("province", "") or "",
        "source": "tencent",
    }


# ---------------- POI 检索 ----------------
async def search_pois(city: str, center: dict, categories: List[str]) -> List[dict]:
    """按类别检索 POI，返回统一结构列表。

    优先从数据库缓存检索，缓存不存在或不足时再去第三方检索，然后将结果存储到缓存。
    
    优化：在上游数据富化省级数据，缓存时使用省份+城市名，避免城市名称重复时数据混乱。
    """
    # 0. 富化省级数据：通过地理编码获取城市的省份信息
    province = ""
    try:
        from .geocode import geocode
        geo_info = await geocode(city)
        if geo_info:
            province = geo_info.get("province", "") or geo_info.get("pname", "")
            # 确保center也包含省份信息
            if province and "province" not in center:
                center["province"] = province
    except Exception as e:
        print(f"[search_pois] geocode province error: {e}")

    # 0.1 内存缓存：在数据库缓存之前再加一层内存缓存，提升性能
    memory_cache_key = f"{province}:{city}:{','.join(categories)}"
    try:
        cached = cache.get("poi_memory", memory_cache_key, get_ttl("poi_memory", TTL_POI))
        if cached:
            print(f"[search_pois] memory cache hit: {city}, {len(cached)} pois")
            return cached
    except Exception as e:
        print(f"[search_pois] memory cache read error: {e}")

    # 1. 先从缓存中获取POI（使用省份+城市名）
    cached_pois = []
    try:
        from ...data.repositories.poi_cache_repository import get_poi_cache_repository
        poi_cache = get_poi_cache_repository()
        # 按分类从缓存中获取（使用省份+城市名，避免重名冲突）
        for category in categories:
            pois = poi_cache.get_pois_by_region(
                province=province,
                city=city,
                category=category,
                limit=50,
            )
            cached_pois.extend(pois)
        # 去重
        seen_names = set()
        unique_cached = []
        for p in cached_pois:
            name = p.get("name", "")
            if name and name not in seen_names:
                seen_names.add(name)
                # 确保缓存数据也包含省份信息
                if province and not p.get("province"):
                    p["province"] = province
                if city and not p.get("cityname"):
                    p["cityname"] = city
                unique_cached.append(p)
        cached_pois = unique_cached
    except Exception as e:
        print(f"[search_pois] cache read error: {e}")

    # 如果缓存中有足够的POI（每个分类至少10个），直接返回
    if cached_pois and len(cached_pois) >= len(categories) * 10:
        cached_pois = filter_by_range(cached_pois, center)
        if cached_pois:
            # 写入内存缓存
            _save_to_memory_cache(province, city, categories, cached_pois)
            return cached_pois

    # 2. 缓存不足，去第三方检索
    prov = provider()
    pois = []
    if prov == "amap":
        pois = await _search_pois_amap(city, categories)
        # 富化省级数据：为所有POI添加省份和城市名
        for p in pois:
            if province and not p.get("province"):
                p["province"] = province
            if city and not p.get("cityname"):
                p["cityname"] = city
        pois = await _attach_must_visit(city, pois)
        pois = filter_by_range(pois, center)
        if pois:
            # 存储到缓存（使用省份+城市名）
            try:
                from ...data.repositories.poi_cache_repository import get_poi_cache_repository
                poi_cache = get_poi_cache_repository()
                for category in categories:
                    category_pois = [p for p in pois if p.get("category") == category]
                    if category_pois:
                        poi_cache.save_pois(
                            category_pois,
                            province=province,
                            city=city,
                            category=category,
                            source="amap",
                        )
            except Exception as e:
                print(f"[search_pois] cache save error: {e}")
            # 写入内存缓存
            _save_to_memory_cache(province, city, categories, pois)
            return pois
        if settings.tencent_ready:
            pois = await _search_pois_tencent(city, categories)
            # 富化省级数据
            for p in pois:
                if province and not p.get("province"):
                    p["province"] = province
                if city and not p.get("cityname"):
                    p["cityname"] = city
            pois = await _attach_must_visit(city, pois)
            pois = filter_by_range(pois, center)
            if pois:
                # 存储到缓存（使用省份+城市名）
                try:
                    from ...data.repositories.poi_cache_repository import get_poi_cache_repository
                    poi_cache = get_poi_cache_repository()
                    for category in categories:
                        category_pois = [p for p in pois if p.get("category") == category]
                        if category_pois:
                            poi_cache.save_pois(
                                category_pois,
                                province=province,
                                city=city,
                                category=category,
                                source="tencent",
                            )
                except Exception as e:
                    print(f"[search_pois] cache save error: {e}")
                return pois
    if prov == "tencent":
        pois = await _search_pois_tencent(city, categories)
        # 富化省级数据
        for p in pois:
            if province and not p.get("province"):
                p["province"] = province
            if city and not p.get("cityname"):
                p["cityname"] = city
        pois = await _attach_must_visit(city, pois)
        pois = filter_by_range(pois, center)
        if pois:
            # 存储到缓存（使用省份+城市名）
            try:
                from ...data.repositories.poi_cache_repository import get_poi_cache_repository
                poi_cache = get_poi_cache_repository()
                for category in categories:
                    category_pois = [p for p in pois if p.get("category") == category]
                    if category_pois:
                        poi_cache.save_pois(
                            category_pois,
                            province=province,
                            city=city,
                            category=category,
                            source="tencent",
                        )
            except Exception as e:
                print(f"[search_pois] cache save error: {e}")
            # 写入内存缓存
            _save_to_memory_cache(province, city, categories, pois)
            return pois

    # 3. 第三方检索失败，返回缓存中的POI（即使不足）
    if cached_pois:
        return cached_pois

    return []


async def _attach_must_visit(city: str, pois: List[dict]) -> List[dict]:
    """把「必打卡」知名点位注入候选池。"""
    try:
        from ...data.repositories.admin_repository import get_must_visit
    except Exception:
        return pois
    key = city.rstrip("市")
    entries = get_must_visit(key) or get_must_visit(city) or []
    if not entries:
        return pois
    seen_names = {p["name"] for p in pois}

    async def _one(e: dict) -> Optional[dict]:
        name = e.get("name", "")
        if not name:
            return None
        rp = await resolve_poi(city, e.get("kw") or name, e.get("category", "景点"))
        if not rp:
            return None
        rp["rating"] = max(rp["rating"], float(e.get("rating", 4.8)))
        rp["hot"] = True
        return rp

    results = await asyncio.gather(*[_one(e) for e in entries])
    hot = []
    for r in results:
        if not r or r["name"] in seen_names:
            continue
        seen_names.add(r["name"])
        hot.append(r)
    if not hot:
        return pois
    return hot + pois


async def _search_pois_amap(city: str, categories: List[str]) -> List[dict]:
    """真实 POI 检索（高德）。
    
    优化：
    1. 增加翻页检索（检索3页，每页20条，共60条）
    2. 使用多类型码检索（提高景点覆盖率）
    3. 限制关键词数量（避免API调用过多）
    4. 缓存原始检索结果，而不是过滤后的结果
    """
    type_map = AMAP_POI_TYPES
    attraction_keywords = AMAP_ATTRACTION_KEYWORDS[:POI_KEYWORDS_LIMIT]  # 限制关键词数量
    out = []
    seen = set()
    cache_key = f"pois:{city}:{','.join(categories)}"
    hit = cache.get("poi", cache_key, get_ttl("poi", TTL_POI))
    if hit is not None:
        return hit

    def _append(p: dict, cat: str) -> None:
        loc = (p.get("location") or "").split(",")
        if len(loc) != 2:
            return
        key = (p.get("name", ""), round(float(loc[0]), 4), round(float(loc[1]), 4))
        if key in seen:
            return
        seen.add(key)
        biz = p.get("biz_ext") or {}
        out.append({
            "id": p.get("id", ""), "name": p.get("name", ""),
            "lng": float(loc[0]), "lat": float(loc[1]),
            "address": to_str(p.get("address")),
            "category": infer_category(p.get("type", ""), cat, p.get("name", "")),
            "price": to_float(p.get("cost")) or to_float(biz.get("cost")),
            "rating": to_float(p.get("rating")) or to_float(biz.get("rating")),
            "province": p.get("pname", "") or "",
            "cityname": p.get("cityname", "") or "",
            "district": p.get("adname", "") or "",
            "adcode": p.get("adcode", "") or "",
            "type": to_str(p.get("type")),
            "source": "amap",
        })

    for cat in categories:
        types = type_map.get(cat, "110200")
        # 翻页检索（检索3页，每页20条）
        for page in range(1, POI_SEARCH_PAGES + 1):
            data = await amap_get(f"{AMAP_BASE}/place/text",
                              {"city": city, "types": types, "offset": POI_SEARCH_OFFSET, "page": page, "extensions": "all"}, retry_empty=True)
            pois = (data.get("pois") or []) if data else []
            if not pois:
                break  # 没有更多数据，停止翻页
            for p in pois:
                _append(p, cat)
        
        # 景点分类额外按关键词检索
        if cat == "景点":
            for kw in attraction_keywords:
                # 每个关键词只检索第一页（避免API调用过多）
                d2 = await amap_get(f"{AMAP_BASE}/place/text",
                                {"city": city, "keywords": kw, "offset": POI_SEARCH_OFFSET, "page": 1, "extensions": "all"}, retry_empty=True)
                for p in (d2.get("pois") or []) if d2 else []:
                    _append(p, cat)
    
    # 先去重，然后缓存原始检索结果（不过滤）
    raw_result = dedup(out)
    cache.set("poi", cache_key, raw_result)
    
    # 返回过滤后的结果
    result = quality_trim(raw_result)
    return result


async def _search_pois_tencent(city: str, categories: List[str]) -> List[dict]:
    """腾讯 place/search：region(城市) 内关键词召回各类 POI。
    
    优化：
    1. 增加翻页检索（检索3页）
    2. 缓存原始检索结果，而不是过滤后的结果
    """
    cache_key = f"pois_t:{city}:{','.join(categories)}"
    hit = cache.get("poi", cache_key, get_ttl("poi", TTL_POI))
    if hit is not None:
        return hit
    out: List[dict] = []
    seen: set = set()
    for cat in categories:
        for kw in TENCENT_POI_KW.get(cat, [cat])[:POI_KEYWORDS_LIMIT]:
            # 翻页检索（检索3页）
            for page in range(1, POI_SEARCH_PAGES + 1):
                data = await tencent_get(f"{TENCENT_BASE}/place/v1/search",
                                    {"keyword": kw, "boundary": f"region({city},0)",
                                     "page_size": POI_SEARCH_OFFSET, "page_index": page}, retry_empty=True)
                pois = (data.get("data") or []) if data else []
                if not pois:
                    break  # 没有更多数据，停止翻页
                for p in pois:
                    it = t_poi(p, cat)
                    if not it:
                        continue
                    k = (it["name"], round(it["lng"], 4), round(it["lat"], 4))
                    if k in seen:
                        continue
                    seen.add(k)
                    out.append(it)
    
    # 先去重，然后缓存原始检索结果（不过滤）
    raw_result = dedup(out)
    cache.set("poi", cache_key, raw_result)
    
    # 返回过滤后的结果
    result = quality_trim(raw_result)
    return result


# ---------------- 行政分级景点检索 ----------------
async def search_attractions(adcode: str, keywords: List[str], limit: int = 80) -> List[dict]:
    """按行政编码（区/县、市、省）检索景点。
    
    优化：
    1. 使用多类型码检索（提高景点覆盖率）
    2. 增加翻页检索
    3. 缓存原始检索结果，而不是过滤后的结果
    """
    if not adcode:
        return []
    prov = provider()
    if prov == "none":
        return []
    cache_key = f"attrs:{prov}:{adcode}:{','.join(keywords)}:{limit}"
    hit = cache.get("poi", cache_key, get_ttl("poi", TTL_POI))
    if hit is not None:
        return hit
    if prov == "tencent":
        return await _search_attrs_tencent(adcode, keywords, limit, cache_key)
    out: List[dict] = []
    seen: dict = {}
    # 使用多类型码检索（提高景点覆盖率）
    attraction_types = AMAP_POI_TYPES.get("景点", "110200")
    
    for kw in keywords[:POI_KEYWORDS_LIMIT]:
        # 翻页检索（检索2页，每页50条，共100条）
        for page in range(1, 3):
            data = await amap_get(f"{AMAP_BASE}/place/text",
                              {"city": adcode, "types": attraction_types, "keywords": kw,
                               "offset": 50, "page": page, "extensions": "all"}, retry_empty=True)
            pois = (data.get("pois") or []) if data else []
            if not pois:
                break  # 没有更多数据，停止翻页
            for p in pois:
                loc = (p.get("location") or "").split(",")
                if len(loc) != 2:
                    continue
                key = (p.get("name", ""), round(float(loc[0]), 4), round(float(loc[1]), 4))
                biz = p.get("biz_ext") or {}
                if key in seen:
                    if kw == "5A":
                        seen[key]["is_5a"] = True
                    continue
                item = {
                    "id": p.get("id", ""), "name": p.get("name", ""),
                    "lng": float(loc[0]), "lat": float(loc[1]),
                    "address": to_str(p.get("address")),
                    "category": infer_category(p.get("type", ""), "景点", p.get("name", "")),
                    "price": to_float(p.get("cost")) or to_float(biz.get("cost")),
                    "rating": to_float(p.get("rating")) or to_float(biz.get("rating")),
                    "type": to_str(p.get("type")),
                    "province": p.get("pname", "") or to_str(p.get("province")) or "",
                    "cityname": to_str(p.get("cityname")) or "",
                    "district": p.get("adname", "") or "",
                    "adcode": p.get("adcode", "") or "",
                    "source": "amap",
                    "is_5a": kw == "5A",
                }
                seen[key] = item
                out.append(item)
    
    if not out and settings.tencent_ready:
        return await _search_attrs_tencent(adcode, keywords, limit, cache_key)
    
    # 先缓存原始检索结果（不过滤）
    cache.set("poi", cache_key, out)
    
    # 返回过滤后的结果
    out.sort(key=lambda p: -p["rating"])
    result = out[:limit]
    return result


async def _search_attrs_tencent(adcode: str, keywords: List[str], limit: int,
                                cache_key: str) -> List[dict]:
    """腾讯行政分级景点枚举：region(adcode) 内关键词召回。"""
    out: List[dict] = []
    seen: set = set()
    for kw in keywords:
        data = await tencent_get(f"{TENCENT_BASE}/place/v1/search",
                            {"keyword": kw, "boundary": f"region({adcode},0)",
                             "page_size": 50, "page_index": 1}, retry_empty=True)
        for p in (data.get("data") or []) if data else []:
            it = t_poi(p, "景点")
            if not it:
                continue
            k = (it["name"], round(it["lng"], 4), round(it["lat"], 4))
            if k in seen:
                continue
            seen.add(k)
            it["is_5a"] = (kw == "5A")
            out.append(it)
    out.sort(key=lambda p: -p["rating"])
    result = out[:limit]
    cache.set("poi", cache_key, result)
    return result


# ---------------- 坐标就近检索 ----------------
async def search_around(lng: float, lat: float, category: str = "美食",
                        radius: int = 15_000, limit: int = 10) -> List[dict]:
    """以坐标为中心检索附近 POI。"""
    prov = provider()
    if prov == "none":
        return []
    cache_key = f"around:{prov}:{round(lng, 5)},{round(lat, 5)}:{category}:{radius}:{limit}"
    hit = cache.get("poi", cache_key, get_ttl("poi", TTL_POI))
    if hit is not None:
        return hit
    if prov == "tencent":
        data = await tencent_get(f"{TENCENT_BASE}/place/v1/search",
                            {"keyword": TENCENT_POI_KW.get(category, [category])[0],
                             "boundary": f"nearby({lat},{lng},{radius},0)",
                             "page_size": 20, "page_index": 1}, retry_empty=True)
        out, seen = [], set()
        for p in (data.get("data") or []) if data else []:
            it = t_poi(p, category)
            if not it:
                continue
            k = (it["name"], round(it["lng"], 4), round(it["lat"], 4))
            if k in seen:
                continue
            seen.add(k)
            out.append(it)
        out.sort(key=lambda p: (-p["rating"], haversine(lng, lat, p["lng"], p["lat"])))
        result = out[:limit]
        cache.set("poi", cache_key, result)
        return result
    types = AROUND_TYPES.get(category, "050000")
    data = await amap_get(f"{AMAP_BASE}/place/around",
                      {"location": f"{lng},{lat}", "types": types, "radius": radius,
                       "offset": 20, "page": 1, "extensions": "all"}, retry_empty=True)
    out, seen = [], set()
    for p in (data.get("pois") or []) if data else []:
        loc = (p.get("location") or "").split(",")
        if len(loc) != 2:
            continue
        key = (p.get("name", ""), round(float(loc[0]), 4), round(float(loc[1]), 4))
        if key in seen:
            continue
        seen.add(key)
        biz = p.get("biz_ext") or {}
        out.append({
            "id": p.get("id", ""), "name": p.get("name", ""),
            "lng": float(loc[0]), "lat": float(loc[1]),
            "address": to_str(p.get("address")),
            "category": infer_category(p.get("type", ""), category),
            "price": to_float(p.get("cost")) or to_float(biz.get("cost")),
            "rating": to_float(p.get("rating")) or to_float(biz.get("rating")),
            "district": p.get("adname", "") or "",
            "source": "amap",
        })
    out.sort(key=lambda p: -p["rating"])
    result = out[:limit]
    cache.set("poi", cache_key, result)
    return result


# ---------------- 周边探索 ----------------
async def explore_around(lng: float, lat: float, categories: List[str],
                         radius: int = 10_000, limit: int = 40) -> List[dict]:
    """周边探索：以地图选点为中心，检索周围可去 POI（放射状展示用）。"""
    cats = [c for c in categories if c in AROUND_TYPES] or ["景点"]
    radius = min(max(int(radius), 1000), 50_000)
    prov = provider()
    cache_key = f"explore:{prov}:{round(lng, 5)},{round(lat, 5)}:{','.join(cats)}:{radius}:{limit}"
    hit = cache.get("poi", cache_key, get_ttl("poi", TTL_POI))
    if hit is not None:
        return hit
    out, seen = [], set()

    if prov == "tencent":
        for cat in cats:
            data = await tencent_get(f"{TENCENT_BASE}/place/v1/search",
                                {"keyword": TENCENT_POI_KW.get(cat, [cat])[0],
                                 "boundary": f"nearby({lat},{lng},{radius},0)",
                                 "page_size": 25, "page_index": 1}, retry_empty=True)
            for p in (data.get("data") or []) if data else []:
                it = t_poi(p, cat)
                if not it:
                    continue
                k = (it["name"], round(it["lng"], 4), round(it["lat"], 4))
                if k in seen:
                    continue
                seen.add(k)
                it["distance_m"] = haversine(lng, lat, it["lng"], it["lat"])
                out.append(it)

    if prov == "amap":
        for cat in cats:
            types = AROUND_TYPES[cat]
            data = await amap_get(f"{AMAP_BASE}/place/around",
                              {"location": f"{lng},{lat}", "types": types, "radius": radius,
                               "offset": 25, "page": 1, "extensions": "all"}, retry_empty=True)
            for p in (data.get("pois") or []) if data else []:
                loc = (p.get("location") or "").split(",")
                if len(loc) != 2:
                    continue
                px, py = float(loc[0]), float(loc[1])
                key = (p.get("name", ""), round(px, 4), round(py, 4))
                if key in seen:
                    continue
                seen.add(key)
                biz = p.get("biz_ext") or {}
                out.append({
                    "id": p.get("id", ""), "name": p.get("name", ""),
                    "lng": px, "lat": py,
                    "address": to_str(p.get("address")),
                    "category": infer_category(p.get("type", ""), cat, p.get("name", "")),
                    "price": to_float(p.get("cost")) or to_float(biz.get("cost")),
                    "rating": to_float(p.get("rating")) or to_float(biz.get("rating")),
                    "district": p.get("adname", "") or "",
                    "distance_m": haversine(lng, lat, px, py),
                    "source": "amap",
                })
    out.sort(key=lambda p: (-p["rating"], p["distance_m"]))
    result = dedup(out)[:limit]
    cache.set("poi", cache_key, result)
    return result


# ---------------- 点位解析 ----------------
async def resolve_poi(city: str, name: str, category: str = "景点",
                      center: list = None) -> Optional[dict]:
    """把 AI 提议的知名点位名解析成真实 POI（同名消歧）。"""
    if not name:
        return None
    prov = provider()
    if prov == "none":
        return None
    cache_key = f"resolve:{prov}:{city}:{name}:{category}"
    hit = cache.get("poi", cache_key, get_ttl("poi", TTL_POI))
    if hit is not None:
        return hit
    all_results = []
    if prov == "tencent":
        data = await tencent_get(f"{TENCENT_BASE}/place/v1/search",
                            {"keyword": name, "boundary": f"region({city},0)",
                             "page_size": 5, "page_index": 1}, retry_empty=True)
        for p in (data.get("data") or []) if data else []:
            it = t_poi(p, category)
            if not it:
                continue
            it["name"] = it["name"] or name
            it["id"] = it["id"] or f"R{abs(hash(name)) & 0xffff:04d}"
            all_results.append(it)
    else:
        data = await amap_get(f"{AMAP_BASE}/place/text",
                          {"city": city, "keywords": name, "offset": 5, "page": 1, "extensions": "all"}, retry_empty=True)
        if data and data.get("pois"):
            for p in data["pois"]:
                loc = (p.get("location") or "").split(",")
                if len(loc) != 2:
                    continue
                biz = p.get("biz_ext") or {}
                all_results.append({
                    "id": p.get("id", f"R{abs(hash(name)) & 0xffff:04d}"),
                    "name": p.get("name", name),
                    "lng": float(loc[0]), "lat": float(loc[1]),
                    "address": to_str(p.get("address")),
                    "category": infer_category(p.get("type", ""), category),
                    "price": to_float(p.get("cost")) or to_float(biz.get("cost")),
                    "rating": to_float(p.get("rating")) or to_float(biz.get("rating")),
                    "district": p.get("adname", "") or "",
                    "cityname": p.get("cityname", ""),
                    "source": "amap",
                })

    if not all_results:
        return None

    # 同名检测
    name_groups = {}
    for r in all_results:
        key = r.get("name", "").strip()
        name_groups.setdefault(key, []).append(r)
    ambiguous = any(len(v) > 1 for v in name_groups.values())

    # 距离排序
    result = all_results[0]
    if center and len(center) == 2:
        all_results.sort(key=lambda r: haversine(center[0], center[1], r["lng"], r["lat"]))
        result = all_results[0]

    if ambiguous:
        result["ambiguous"] = True
        result["candidates"] = [
            {"name": r.get("name"), "address": r.get("address"),
             "district": r.get("district"), "cityname": r.get("cityname", ""),
             "lng": r.get("lng"), "lat": r.get("lat")}
            for r in all_results[:5]
        ]

    cache.set("poi", cache_key, result)
    return result


# ---------------- 住宿（酒店）检索 ----------------
async def search_hotel_near(lng: float, lat: float, radius: int = 12_000) -> Optional[dict]:
    """就近检索一个住宿点（酒店/宾馆）。"""
    cache_key = f"hotel:{provider()}:{round(lng, 5)},{round(lat, 5)}:{radius}"
    hit = cache.get("poi", cache_key, get_ttl("poi", TTL_POI))
    if hit is not None:
        return hit or None
    result = None
    if settings.amap_ready:
        data = await amap_get(f"{AMAP_BASE}/place/around",
                          {"location": f"{lng},{lat}", "types": HOTEL_TYPES, "radius": radius,
                           "offset": 10, "page": 1, "extensions": "all"}, retry_empty=True)
        cands = []
        for p in (data.get("pois") or []) if data else []:
            loc = (p.get("location") or "").split(",")
            if len(loc) != 2:
                continue
            name = to_str(p.get("name"))
            if any(b in name for b in ("公寓", "青旅", "民宿", "客栈")):
                continue
            biz = p.get("biz_ext") or {}
            cands.append({
                "id": p.get("id", f"H{abs(hash(name)) & 0xffff:04d}"),
                "name": name,
                "lng": float(loc[0]), "lat": float(loc[1]),
                "address": to_str(p.get("address")),
                "category": "酒店",
                "price": to_float(p.get("cost")) or to_float(biz.get("cost")),
                "rating": to_float(p.get("rating")) or to_float(biz.get("rating")),
                "district": p.get("adname", "") or "",
                "source": "amap",
            })
        if cands:
            result = max(cands, key=lambda x: x.get("rating") or 0)
    elif settings.tencent_ready:
        data = await tencent_get(f"{TENCENT_BASE}/place/v1/search",
                            {"keyword": "酒店", "boundary": f"nearby({lat},{lng},{radius},0)",
                             "page_size": 10, "page_index": 1}, retry_empty=True)
        cands = []
        for p in (data.get("data") or []) if data else []:
            it = t_poi(p, "酒店")
            if not it:
                continue
            if any(b in it["name"] for b in ("公寓", "青旅", "民宿", "客栈")):
                continue
            it["category"] = "酒店"
            cands.append(it)
        if cands:
            result = cands[0]
    if result is None:
        return None
    cache.set("poi", cache_key, result)
    return result
