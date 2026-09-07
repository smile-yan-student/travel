"""
行程规划引擎 - 逐日构建模块。

从 planner.py 抽出的逐日构建相关函数，包括核心规划函数和辅助函数。

功能特性：
- 获取景点在指定天的开放时间信息
- 同日内按地理位置重排（最近邻 + 综合评分），减少来回折返
- 从城市候选池里为区域选就近辅助点（美食/购物/夜生活，不入主线）
- 远处区域（乌镇/千岛湖等）就地检索辅助点，避免跨区污染
- 同一天内，名称命中同一地标特征词的多个景点只保留评分最高的一个
- 根据当天景点区域，推荐住宿区域（不推荐具体酒店）
- 省级目的地：按市分隔分配天数
- 点位区域标签：优先高德区县名，缺失时按坐标网格兜底
- 一天的主区域：出现次数最多的区县；平票时取评分最高点位所在区县
- 按名称匹配点位池：先精确，再双向包含
- 品类均衡 + 补足：保证每天行程不是一顿接一顿的美食，且点位数量够用
- 把 [(poi_dict, raw_item)] 转成 PlanItem，并计算站间交通
- 时间轴合法性校验：按顺序累加「路上耗时 + 停留时长」
- 根据景点类型、推荐时长和重要性生成行程项
- 根据景点信息计算推荐停留时长
- 单日预算：门票 + 餐饮 + 交通 + 住宿摊到每天
- 总预算拆分
- 日期标签
- 构建一天：区域内 2-3 个景点（主线）+ 1 个就近辅助
- 规则化地理规划主入口：景点聚类成区域 → 短距同日 → 跨天不重复
- 为与更早一天主区域重复的当天，挑选一个未被占用的新主区域
- 用指定区域的未用点位按「景点/美食/购物/夜生活」骨架重建一天
- 把当天不在主区域 focus 的点位，替换为主区域未用点位（同品类优先）
- 跨天地域去重：让每天集中在一个区域，且不同天不重复使用同一主区域

使用方式：
    from app.services.planner.daily_build import (
        build_geo_day, geo_plan, enforce_region_distinct,
        reorder_day, apply_timeline, day_budget
    )

    # 构建一天
    day_plan = await build_geo_day(
        req, center, area, aux_pois, all_attrs,
        used_ids, day_no, day_start, is_last_day, return_station_geo
    )

    # 规则化地理规划主入口
    day_plans, source, plan_type = await geo_plan(
        req, center, aux_pois, attrs, is_province
    )

    # 跨天地域去重
    day_plans = await enforce_region_distinct(
        req, center, pois, day_plans
    )
"""
import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from ...data.models.models import DayPlan, PlanItem, PlanRequest, POI
from ...services import map as amap
from .cluster import area_label, assign_areas_to_days, cluster_attractions
from .constants import AUX_FOOD_BAD_NAMES, LANDMARK_WORDS
from .utils import (
    BUDGET_TABLE,
    GROUP_PACE,
    PACE_ITEMS,
    SLOT_TIME,
    _rank,
    daily_inspiration,
    is_closed as _is_closed,
    is_landmark as _is_landmark,
)


def _get_open_hours_info(poi_name: str, day_no: int) -> dict:
    """获取景点在指定天的开放时间信息

    Args:
        poi_name: 景点名称
        day_no: 第几天（从1开始）

    Returns:
        {is_open, open_time, close_time, note, open_hours_list}
    """
    try:
        from ...data.repositories.open_hours_repository import OpenHoursRepository
        check_date = datetime.date.today() + datetime.timedelta(days=day_no - 1)
        is_open, open_time, close_time, note = OpenHoursRepository.is_open_on_day(poi_name, check_date)
        open_hours_list = OpenHoursRepository.get_open_hours(poi_name)
        return {
            "is_open": is_open,
            "open_time": open_time,
            "close_time": close_time,
            "note": note,
            "open_hours_list": open_hours_list,
        }
    except Exception:
        return {"is_open": True, "open_time": "", "close_time": "", "note": "", "open_hours_list": []}


def reorder_day(poi_items: List[tuple], center: dict,
                 day_start: Optional[dict] = None) -> List[tuple]:
    """同日内按地理位置重排（最近邻 + 综合评分），减少来回折返。

    优化：
    - 必去景点（must_visit=True）优先安排在前面，然后是其他景点，最后是美食/购物/夜生活
    - 每组内部使用综合评分排序：距离（60%）+ 评分（30%）+ 热门程度（10%）
    - 避免核心景点被美食挤到后面
    - 考虑路径连贯性，避免来回折返
    """
    if len(poi_items) <= 1:
        return poi_items
    nights = [(p, it) for p, it in poi_items if p["category"] == "夜生活"]
    body = [(p, it) for p, it in poi_items if p["category"] != "夜生活"]
    if not body:
        return nights
    start = ([day_start["lng"], day_start["lat"]]
             if day_start and day_start.get("lng") is not None
             else [center["lng"], center["lat"]])

    # 按照优先级分组：必去景点 > 其他景点 > 美食/购物
    must_visit_attractions = [(p, it) for p, it in body if p["category"] == "景点" and p.get("must_visit")]
    other_attractions = [(p, it) for p, it in body if p["category"] == "景点" and not p.get("must_visit")]
    food_and_shopping = [(p, it) for p, it in body if p["category"] != "景点"]

    def _composite_score(cur, poi_item):
        """综合评分：距离（60%）+ 评分（30%）+ 热门程度（10%）"""
        p, _ = poi_item
        dist = amap.haversine(cur[0], cur[1], p["lng"], p["lat"])
        # 距离归一化（0-1，距离越近分数越高）
        max_dist = 50000  # 50公里
        dist_score = max(0, 1 - dist / max_dist)
        # 评分归一化（0-1）
        rating_score = min(1, (p.get("rating") or 0) / 5.0)
        # 热门程度（0-1）
        hot_score = 1.0 if p.get("hot") else 0.5
        # 综合评分
        return dist_score * 0.6 + rating_score * 0.3 + hot_score * 0.1

    def _pick_best(remaining, cur):
        """选择综合评分最高的下一个景点"""
        best = max(remaining, key=lambda x: _composite_score(cur, x))
        return best

    order = []
    cur = start

    # 第一步：安排必去景点（按照综合评分排序，距离优先）
    remaining_must = must_visit_attractions[:]
    while remaining_must:
        best = _pick_best(remaining_must, cur)
        order.append(best)
        remaining_must.remove(best)
        cur = [best[0]["lng"], best[0]["lat"]]

    # 第二步：安排其他景点（按照综合评分排序）
    remaining_other = other_attractions[:]
    while remaining_other:
        best = _pick_best(remaining_other, cur)
        order.append(best)
        remaining_other.remove(best)
        cur = [best[0]["lng"], best[0]["lat"]]

    # 第三步：安排美食/购物（按照综合评分排序）
    remaining_food = food_and_shopping[:]
    while remaining_food:
        best = _pick_best(remaining_food, cur)
        order.append(best)
        remaining_food.remove(best)
        cur = [best[0]["lng"], best[0]["lat"]]

    # 第四步：安排夜生活（排到最后）
    if nights:
        cur = [order[-1][0]["lng"], order[-1][0]["lat"]] if order else start
        ns = sorted(nights, key=lambda x: amap.haversine(cur[0], cur[1], x[0]["lng"], x[0]["lat"]))
        order.extend(ns)

    return order


def pick_auxiliary(area: dict, aux_pois: List[dict], used_ids: set) -> Optional[dict]:
    """从城市候选池里为区域选就近辅助点（美食/购物/夜生活，不入主线）。"""
    pref = {"美食": 0, "夜生活": 1, "购物": 2}
    cand = [p for p in aux_pois
            if p["category"] in ("美食", "购物", "夜生活") and p["id"] not in used_ids
            and not any(h in p["name"] for h in ("酒店", "宾馆", "大酒店", "大饭店", "客栈", "饭店"))
            and not _is_closed(p)
            and not (p["category"] == "美食"
                     and any(b in p["name"] for b in AUX_FOOD_BAD_NAMES))]
    cand.sort(key=lambda p: (pref.get(p["category"], 3),
                             amap.haversine(area["cx"], area["cy"], p["lng"], p["lat"])))
    for p in cand:
        if amap.haversine(area["cx"], area["cy"], p["lng"], p["lat"]) <= 15_000:
            return p
    return None


async def local_aux(area: dict, used_ids: set) -> Optional[dict]:
    """远处区域（乌镇/千岛湖等）就地检索辅助点，避免跨区污染。"""
    for cat in ("美食", "夜生活", "购物"):
        local = await amap.search_around(area["cx"], area["cy"], cat, 15_000, 6)
        for p in local:
            if p["id"] not in used_ids and not _is_closed(p) and not any(
                    h in p["name"] for h in ("酒店", "宾馆", "大酒店", "大饭店", "客栈", "饭店")):
                if cat == "美食" and any(b in p["name"] for b in AUX_FOOD_BAD_NAMES):
                    continue
                return p
    return None


def dedup_landmark_day(picked: List[dict]) -> List[dict]:
    """同一天内，名称命中同一地标特征词的多个景点只保留评分最高的一个。
    同时检查完全相同的名称，避免重复景点（如"杭州宋城"和"杭州宋城"）。
    """
    if len(picked) <= 1:
        return picked
    keep: List[dict] = []
    seen_names = set()  # 用于检查完全相同的名称
    for p in sorted(picked, key=lambda x: -_rank(x)):
        name = (p.get("name") or "").strip()
        # 检查完全相同的名称（忽略大小写和空格）
        normalized_name = name.lower().replace(" ", "")
        if normalized_name in seen_names:
            continue
        seen_names.add(normalized_name)
        # 检查地标特征词
        words = {w for w in LANDMARK_WORDS if w in name}
        if any(any(w in (q.get("name") or "") for w in words) for q in keep):
            continue
        keep.append(p)
    return keep


async def pick_hotel_area(area: dict, city_name: str = "") -> dict:
    """根据当天景点区域，推荐住宿区域（不推荐具体酒店）。

    策略：
    1. 计算当天景点的中心点
    2. 根据中心点附近的区域，推荐住宿区域
    3. 给出推荐理由（交通便利、靠近景点、餐饮丰富等）

    Args:
        area: 当天景点区域信息 {cx, cy, pois, ...}
        city_name: 城市名称

    Returns:
        {area_name, reason, center_lng, center_lat}
    """
    cx = area.get("cx", 0)
    cy = area.get("cy", 0)
    pois = area.get("pois", [])

    # 生成住宿区域名称（基于景点区域的简单描述）
    if pois:
        # 取第一个景点的区域作为住宿区域参考
        first_poi = pois[0] if isinstance(pois[0], dict) else {}
        district = first_poi.get("district", "") or first_poi.get("adname", "")
        cityname = first_poi.get("cityname", "") or city_name

        if district:
            area_name = f"{cityname}{district}一带"
        elif cityname:
            area_name = f"{cityname}市中心一带"
        else:
            area_name = "景点附近区域"
    else:
        area_name = f"{city_name}市中心一带" if city_name else "市中心区域"

    # 生成推荐理由
    reasons = []
    if pois:
        reasons.append(f"靠近今日{len(pois)}个景点，减少通勤时间")
    reasons.append("交通便利，地铁/公交可达各景点")
    reasons.append("餐饮购物丰富，晚间活动方便")

    reason = "；".join(reasons)

    return {
        "area_name": area_name,
        "reason": reason,
        "center_lng": cx,
        "center_lat": cy,
    }


async def pick_hotel(area: dict) -> Optional[POI]:
    """就近为当天选一个住宿点（当晚住宿 / 次日出发起点）。

    注意：已改为不推荐具体酒店，只推荐住宿区域。
    此函数保留用于向后兼容，返回None。
    """
    return None


def province_areas(attrs: List[dict], center: dict, days: int) -> List[dict]:
    """省级目的地：按市分隔分配天数。"""
    groups: dict = {}
    for p in attrs:
        cn = (p.get("cityname") or "").replace("市", "").strip() or (p.get("district") or "").strip()
        groups.setdefault(cn, []).append(p)
    city_clusters = [(cn, cluster_attractions(ps)) for cn, ps in groups.items()]

    def _city_key(item) -> tuple:
        cn, cls = item
        n_lm = sum(1 for c in cls for p in c.get("pois", []) if _is_landmark(p))
        best = max((c.get("avg_rating", 0) for c in cls), default=0.0)
        dist = min((amap.haversine(center["lng"], center["lat"], c["cx"], c["cy"]) for c in cls),
                   default=float("inf"))
        return (-n_lm, -best, dist)

    city_clusters.sort(key=_city_key)
    idx_by_city = {cn: 0 for cn, _ in city_clusters}
    areas: List[dict] = []
    while len(areas) < days:
        progressed = False
        for cn, cls in city_clusters:
            if len(areas) >= days:
                break
            i = idx_by_city[cn]
            if i < len(cls):
                c = dict(cls[i])
                c["city"] = cn
                areas.append(c)
                idx_by_city[cn] = i + 1
                progressed = True
        if not progressed:
            break
    return areas[:days]


def region_of(poi) -> str:
    """点位区域标签：优先高德区县名，缺失时按坐标网格兜底。"""
    if isinstance(poi, dict):
        d = poi.get("district", "") or ""
        lng, lat = poi.get("lng"), poi.get("lat")
    else:
        d = getattr(poi, "district", "") or ""
        lng, lat = poi.lng, poi.lat
    if d:
        return d
    if lng is None or lat is None:
        return "?"
    return f"G{round(float(lng), 2)},{round(float(lat), 2)}"


def day_focus(day: DayPlan) -> str:
    """一天的主区域：出现次数最多的区县；平票时取评分最高点位所在区县。"""
    counts: dict = {}
    for it in day.items:
        r = region_of(it.poi)
        counts.setdefault(r, []).append(it)
    if not counts:
        return ""
    best_key, best_r = None, ""
    for r, its in counts.items():
        key = (len(its), max(it.poi.rating for it in its))
        if best_key is None or key > best_key:
            best_key, best_r = key, r
    return best_r


def match_pool_by_name(pool_by_name: dict, name: str) -> Optional[dict]:
    """按名称匹配点位池：先精确，再双向包含。"""
    if not name:
        return None
    if name in pool_by_name:
        return pool_by_name[name]
    for pn, p in pool_by_name.items():
        if name in pn or pn in name:
            return p
    return None


def balance_day(poi_items: List[tuple], spare_pois: List[dict], used_ids: set) -> List[tuple]:
    """品类均衡 + 补足：保证每天行程不是一顿接一顿的美食，且点位数量够用。"""
    if not poi_items:
        return poi_items
    food_seen = 0
    balanced: List[tuple] = []
    for poi, it in poi_items:
        if poi["category"] == "美食":
            if food_seen >= 2:
                continue
            food_seen += 1
        balanced.append((poi, it))
    if not any(poi["category"] != "美食" for poi, _ in balanced):
        spare = [p for p in spare_pois
                 if p["id"] not in used_ids and p["category"] in ("景点", "购物", "夜生活")]
        if spare:
            spare = sorted(spare, key=lambda p: -p.get("rating", 0))
            p = spare[0]
            balanced.append((p, {"slot": "上午", "duration_min": 150, "note": "补充当日亮点，建议错峰前往"}))
            used_ids.add(p["id"])
    cur_cats = {poi["category"] for poi, _ in balanced}
    while len(balanced) < 3:
        prefer = [c for c in ("景点", "美食", "购物", "夜生活") if c not in cur_cats]
        cand = [p for p in spare_pois if p["id"] not in used_ids and p["category"] in prefer]
        if not cand:
            cand = [p for p in spare_pois if p["id"] not in used_ids]
        if not cand:
            break
        cand = sorted(cand, key=lambda p: -p.get("rating", 0))
        p = cand[0]
        balanced.append((p, {"slot": "上午", "duration_min": 150, "note": "顺路补充的人气点位"}))
        cur_cats.add(p["category"])
        used_ids.add(p["id"])
    return balanced


# ============ 核心规划函数 ============

async def build_items(poi_items: List[tuple], traffic_mode: str = "混合") -> List[PlanItem]:
    """把 [(poi_dict, raw_item)] 转成 PlanItem，并计算站间交通。"""
    out: List[PlanItem] = []
    prev: dict = None
    for poi, it in poi_items:
        slot = it.get("slot", "上午")
        # 数据清洗：确保POI字段类型正确
        cleaned_poi = _clean_poi_dict(poi)
        item = PlanItem(
            slot=slot,
            start_time=SLOT_TIME.get(slot, "09:00"),
            poi=POI(**cleaned_poi),
            duration_min=int(it.get("duration_min", 120)),
            note=it.get("note", ""),
        )
        if prev is not None:
            r = await amap.route([prev["lng"], prev["lat"]], [poi["lng"], poi["lat"]], traffic_mode)
            item.transport = r["transport"]
            item.transit_min = r["transit_min"]
            item.distance_m = r["distance_m"]
        prev = poi
        out.append(item)
    return out


def _clean_poi_dict(poi: dict) -> dict:
    """清洗POI字典，确保字段类型符合POI模型定义。

    主要处理：
    - open_hours: 字符串转列表（第三方API可能返回字符串）
    - avoid_tips: 字符串转列表
    - inner_route: 确保是列表
    - nearby_attractions: 确保是列表
    - lng/lat: 确保是float
    - rating/price: 确保是float
    - must_visit/hot/has_hierarchy: 确保是bool
    """
    cleaned = dict(poi)

    # open_hours: 字符串转列表
    if 'open_hours' in cleaned:
        oh = cleaned['open_hours']
        if isinstance(oh, str) and oh.strip():
            # 将字符串格式的开放时间转换为列表格式
            cleaned['open_hours'] = [{
                'day_of_week': 'all',
                'open_time': '',
                'close_time': '',
                'is_closed': False,
                'note': oh,
            }]
        elif not isinstance(oh, list):
            cleaned['open_hours'] = []

    # avoid_tips: 字符串转列表
    if 'avoid_tips' in cleaned:
        at = cleaned['avoid_tips']
        if isinstance(at, str) and at.strip():
            cleaned['avoid_tips'] = [at]
        elif not isinstance(at, list):
            cleaned['avoid_tips'] = []

    # inner_route: 确保是列表
    if 'inner_route' in cleaned and not isinstance(cleaned['inner_route'], list):
        cleaned['inner_route'] = []

    # nearby_attractions: 确保是列表
    if 'nearby_attractions' in cleaned and not isinstance(cleaned['nearby_attractions'], list):
        cleaned['nearby_attractions'] = []

    # lng/lat: 确保是float
    for field in ['lng', 'lat']:
        if field in cleaned and cleaned[field] is not None:
            try:
                cleaned[field] = float(cleaned[field])
            except (ValueError, TypeError):
                cleaned[field] = 0.0

    # rating/price: 确保是float
    for field in ['rating', 'price']:
        if field in cleaned and cleaned[field] is not None:
            try:
                cleaned[field] = float(cleaned[field])
            except (ValueError, TypeError):
                cleaned[field] = 0.0

    # recommended_duration: 确保是int
    if 'recommended_duration' in cleaned and cleaned['recommended_duration'] is not None:
        try:
            cleaned['recommended_duration'] = int(cleaned['recommended_duration'])
        except (ValueError, TypeError):
            cleaned['recommended_duration'] = 0

    # must_visit/hot/has_hierarchy: 确保是bool
    for field in ['must_visit', 'hot', 'has_hierarchy']:
        if field in cleaned and cleaned[field] is not None:
            cleaned[field] = bool(cleaned[field])

    return cleaned


def apply_timeline(req: PlanRequest, items: List[PlanItem]) -> List[PlanItem]:
    """时间轴合法性校验：按顺序累加「路上耗时 + 停留时长」。

    优化：
    - 考虑用餐时间（午餐12:00-13:00，晚餐18:00-19:00）
    - 考虑休息时间（每2小时休息15分钟）
    - 避免在闭馆时间安排景点（简单处理：晚上不安排景点）
    - 时间超时时，优先保留重要景点（必去景点、高评分景点）
    """
    sh, sm = map(int, req.daily_start_time.split(":"))
    eh, em = map(int, req.daily_end_time.split(":"))
    window_start = sh * 60 + sm
    window_end = eh * 60 + em
    cur = window_start
    out: List[PlanItem] = []

    # 用餐时间范围
    lunch_start = 12 * 60  # 12:00
    lunch_end = 13 * 60    # 13:00
    dinner_start = 18 * 60 # 18:00
    dinner_end = 19 * 60   # 19:00

    # 记录上次休息时间
    last_break_time = window_start

    for i, it in enumerate(items):
        # 加上路上耗时
        if i > 0:
            cur += it.transit_min

        # 检查是否需要用餐时间（如果当前时间在用餐时间范围内，且下一个景点不是美食）
        is_meal_time = (lunch_start <= cur < lunch_end) or (dinner_start <= cur < dinner_end)
        is_food_item = it.poi.category == "美食" if it.poi else False

        if is_meal_time and not is_food_item and out:
            # 如果在用餐时间，且当前景点不是美食，跳过用餐时间
            if cur < lunch_end and cur >= lunch_start:
                cur = lunch_end
            elif cur < dinner_end and cur >= dinner_start:
                cur = dinner_end

        # 检查是否需要休息（每2小时休息15分钟）
        if cur - last_break_time >= 120 and out:
            cur += 15  # 休息15分钟
            last_break_time = cur

        if cur < window_start:
            cur = window_start

        # 检查时间是否超时
        if cur + it.duration_min > window_end:
            if not out:
                cur = window_start
            else:
                # 时间超时，检查是否是必去景点，如果是则尝试压缩时长
                if it.poi and (it.poi.must_visit or it.poi.hot):
                    # 压缩必去景点的时长（最少30分钟）
                    available_time = window_end - cur
                    if available_time >= 30:
                        it.duration_min = max(30, available_time)
                    else:
                        break
                else:
                    break

        # 设置开始时间和时段
        it.start_time = f"{cur // 60:02d}:{cur % 60:02d}"
        h = cur // 60
        it.slot = "上午" if h < 11 else ("中午" if h < 14 else ("下午" if h < 18 else "晚上"))

        # 晚上不安排景点（除非是夜生活）
        if h >= 18 and it.poi and it.poi.category == "景点" and not it.poi.must_visit:
            # 晚上的非必去景点，跳过
            continue

        cur += it.duration_min
        out.append(it)

    return out


def rule_item(poi: dict, slot: str, duration: int = None) -> dict:
    """根据景点类型、推荐时长和重要性生成行程项。

    优化：
    - 如果景点有推荐时长（recommended_duration），优先使用推荐时长
    - 根据景点类型和重要性，合理分配停留时长
    - 必去景点和热门景点分配更长的停留时长
    - 美食/购物/夜生活分配较短的停留时长
    """
    # 如果没有指定时长，根据景点信息计算推荐时长
    if duration is None:
        duration = _calculate_recommended_duration(poi)

    note = {
        "景点": "热门打卡点，建议错峰前往。",
        "美食": "本地人气美食，饭点需排队，建议错峰。",
        "购物": "适合逛街购物，注意保留体力。",
        "夜生活": "夜景观赏好去处。",
    }.get(poi.get("category", ""), "")

    # 必去景点添加特别提示
    if poi.get("must_visit"):
        note = "必去景点，建议预留充足时间深度游览。" + note

    return {"poi_id": poi["id"], "slot": slot, "duration_min": duration, "note": note}


def _calculate_recommended_duration(poi: dict) -> int:
    """根据景点信息计算推荐停留时长。

    优先级：
    1. 景点自带的推荐时长（recommended_duration）
    2. 景点类型和重要性
    3. 默认时长

    【关键修复】时长范围：30分钟 - 180分钟（3小时），确保每天能安排3-4个景点
    """
    # 1. 如果景点有推荐时长，优先使用
    if poi.get("recommended_duration"):
        try:
            duration = int(poi["recommended_duration"])
            # 限制在合理范围内（最多3小时）
            return max(30, min(180, duration))
        except (TypeError, ValueError):
            pass

    category = poi.get("category", "")
    rating = poi.get("rating") or 0
    is_must_visit = poi.get("must_visit", False)
    is_hot = poi.get("hot", False)

    # 2. 根据景点类型分配基础时长
    base_duration = {
        "景点": 120,      # 景点默认2小时
        "美食": 60,       # 美食默认1小时
        "购物": 90,       # 购物默认1.5小时
        "夜生活": 120,    # 夜生活默认2小时
    }.get(category, 90)

    # 3. 根据评分调整时长（评分越高，时长越长）
    if rating >= 4.8:
        base_duration += 30
    elif rating >= 4.5:
        base_duration += 15
    elif rating < 4.0:
        base_duration -= 15

    # 4. 根据重要性调整时长
    if is_must_visit:
        base_duration += 30  # 必去景点增加30分钟
    if is_hot:
        base_duration += 15  # 热门景点增加15分钟

    # 5. 限制在合理范围内（最多3小时，确保每天能安排3-4个景点）
    return max(30, min(180, base_duration))


def day_budget(req: PlanRequest, items: List[PlanItem]) -> tuple:
    """单日预算：门票 + 餐饮 + 交通 + 住宿摊到每天"""
    level = BUDGET_TABLE.get(req.budget_level, BUDGET_TABLE["适中"])
    n_meals = sum(1 for it in items if it.poi.category in ("美食", "购物", "夜生活"))
    meals = max(n_meals, 2)
    food = meals * level["food"]
    ticket = sum(it.poi.price for it in items if it.poi.category == "景点")
    transport = level["transport"]
    hotel = level["hotel"]
    breakdown = {
        "餐饮": round(food, 1), "门票": round(ticket, 1),
        "交通": transport, "住宿": hotel,
    }
    return round(food + ticket + transport + hotel, 1), breakdown


def total_breakdown(day_plans: List[DayPlan]) -> dict:
    keys = ("餐饮", "门票", "交通", "住宿")
    out = {k: 0.0 for k in keys}
    for dp in day_plans:
        out["餐饮"] += dp.budget * 0.4
        out["住宿"] += dp.budget * 0.35
        out["交通"] += dp.budget * 0.15
        out["门票"] += dp.budget * 0.1
    return {k: round(v, 1) for k, v in out.items()}


def date_label(day_no: int, days: int) -> str:
    start = datetime.date.today()
    return f"第{day_no}天 · {(start + datetime.timedelta(days=day_no - 1)).strftime('%m-%d')}"


async def build_geo_day(req: PlanRequest, center: dict, area: dict,
                         aux_pois: List[dict], all_attrs: List[dict],
                         used_ids: set, day_no: int,
                         day_start: Optional[dict] = None,
                         is_last_day: bool = False,
                         return_station_geo: Optional[dict] = None) -> Optional[DayPlan]:
    """构建一天：区域内 2-3 个景点（主线）+ 1 个就近辅助。

    返程车站优化：如果是最后一天且有返程车站，景点优先选择离车站近的，确保返程方便。
    """
    pace_items = PACE_ITEMS.get(req.pace, 4)
    if req.group_type in GROUP_PACE:
        pace_items = PACE_ITEMS.get(GROUP_PACE[req.group_type], pace_items)
    n_attr = 2 if pace_items <= 3 else 3

    # 返程车站优化：最后一天且有返程车站时，优先选择离车站近的景点
    if is_last_day and return_station_geo:
        station_lng = return_station_geo.get("lng", 0)
        station_lat = return_station_geo.get("lat", 0)
        if station_lng and station_lat:
            # 区域内景点按离返程车站距离排序，必去景点优先
            area_pois_sorted = sorted(
                [p for p in area["pois"] if p["id"] not in used_ids],
                key=lambda p: (0 if p.get("must_visit") else 1,
                              amap.haversine(station_lng, station_lat, p["lng"], p["lat"]))
            )
            picked = area_pois_sorted[:n_attr]
        else:
            picked = [p for p in area["pois"] if p["id"] not in used_ids][:n_attr]
    else:
        # 必去景点优先：先选择必去景点，再选择其他景点
        # 主线景点优先选择景点类别，减少美食/购物/夜生活的使用
        must_visit_pois = [p for p in area["pois"] if p["id"] not in used_ids and p.get("must_visit")]
        # 其他景点中，优先选择景点类别，再选择美食/购物/夜生活
        other_attractions = [p for p in area["pois"] 
                            if p["id"] not in used_ids and not p.get("must_visit") 
                            and p.get("category") == "景点"]
        other_others = [p for p in area["pois"] 
                       if p["id"] not in used_ids and not p.get("must_visit") 
                       and p.get("category") != "景点"]
        # 过滤掉不适合的美食（蜜雪冰城、肯德基等）
        bad_food_keywords = ['蜜雪冰城', '肯德基', '麦当劳', '星巴克', '瑞幸', '奶茶', '饮品', '快餐', '便利店']
        other_others = [p for p in other_others 
                       if not (p.get("category") == "美食" and any(kw in p.get("name", "") for kw in bad_food_keywords))]
        
        picked = must_visit_pois[:n_attr]
        if len(picked) < n_attr:
            picked.extend(other_attractions[:n_attr - len(picked)])
        if len(picked) < n_attr:
            picked.extend(other_others[:n_attr - len(picked)])

    if len(picked) < n_attr:
        used_now = {p["id"] for p in picked}
        rest = [p for p in all_attrs
                if p["id"] not in used_ids and p["id"] not in used_now
                and amap.haversine(area["cx"], area["cy"], p["lng"], p["lat"]) <= 10_000]
        # 返程车站优化：最后一天且有返程车站时，补充景点也优先选择离车站近的
        if is_last_day and return_station_geo:
            station_lng = return_station_geo.get("lng", 0)
            station_lat = return_station_geo.get("lat", 0)
            if station_lng and station_lat:
                rest.sort(key=lambda p: amap.haversine(station_lng, station_lat, p["lng"], p["lat"]))
            else:
                rest.sort(key=lambda p: amap.haversine(area["cx"], area["cy"], p["lng"], p["lat"]))
        else:
            rest.sort(key=lambda p: amap.haversine(area["cx"], area["cy"], p["lng"], p["lat"]))
        picked.extend(rest[: n_attr - len(picked)])
    picked = dedup_landmark_day(picked)
    # 基于ID的去重：确保同一个POI不会被重复选择（解决area["pois"]中存在相同ID的问题）
    seen_ids = set()
    unique_picked = []
    for p in picked:
        poi_id = p.get("id", "")
        if poi_id and poi_id in seen_ids:
            continue
        seen_ids.add(poi_id)
        unique_picked.append(p)
    picked = unique_picked
    if not picked:
        return None
    poi_items = []
    for p in picked:
        used_ids.add(p["id"])
        duration = int(p.get("llm_duration", 150))
        slot = p.get("llm_best_slot", "上午")
        if slot not in ("上午", "中午", "下午", "晚上"):
            slot = "上午"
        note = p.get("llm_reason", "") or "热门景点，建议错峰前往。"
        # 开放时间检查：查询景点在该天的开放时间，如果闭馆则添加提示
        open_hours_info = _get_open_hours_info(p.get("name", ""), day_no)
        if not open_hours_info["is_open"]:
            note = f"⚠️ 注意：{open_hours_info['note']}，建议调整行程或确认开放时间。{note}"
        elif open_hours_info["open_time"] and open_hours_info["close_time"]:
            note = f"🕐 开放时间：{open_hours_info['open_time']}-{open_hours_info['close_time']}。{note}"
        poi_items.append((p, {"slot": slot, "duration_min": duration, "note": note, "open_hours": open_hours_info["open_hours_list"]}))
    aux = pick_auxiliary(area, aux_pois, used_ids)
    if aux is None:
        aux = await local_aux(area, used_ids)
    if aux:
        used_ids.add(aux["id"])
        slot = "晚上" if aux["category"] == "夜生活" else "中午"
        poi_items.append((aux, {"slot": slot, "duration_min": 90,
                                "note": {"美食": "就近用餐，饭点可能排队。", "购物": "就近购物逛街。",
                                         "夜生活": "晚间休闲好去处。"}.get(aux["category"], "")}))
    poi_items = reorder_day(poi_items, center, day_start)
    items = await build_items(poi_items, req.traffic_mode)
    items = apply_timeline(req, items)
    if not items:
        return None
    budget, _bd = day_budget(req, items)
    hotel_area = await pick_hotel_area(area, req.destination)
    theme_counts = {}
    for p in picked:
        t = p.get("llm_theme", "")
        if t:
            theme_counts[t] = theme_counts.get(t, 0) + 1
    if theme_counts:
        day_theme = max(theme_counts, key=theme_counts.get)
    else:
        day_theme = f"{area_label({'pois': picked})} · 经典一日"
    # 返程车站提示：最后一天且有返程车站时，添加返程提示
    day_tip = "热门场馆建议提前预约；早晚温差大，记得带件外套。"
    if is_last_day and return_station_geo:
        station_name = req.return_station or "返程车站"
        # 计算最后一个景点到返程车站的距离和时间
        if items:
            last_poi = items[-1].poi
            try:
                route_info = await amap.route(
                    [last_poi.lng, last_poi.lat],
                    [return_station_geo["lng"], return_station_geo["lat"]],
                    req.traffic_mode
                )
                dist_km = round(route_info.get("distance_m", 0) / 1000, 1)
                transit_min = route_info.get("transit_min", 0)
                day_tip = f"今日为最后一天，景点已优先安排在{station_name}附近。最后一个景点到{station_name}约{dist_km}公里，{route_info.get('transport', '交通')}约{transit_min}分钟，请预留充足时间返程。"
            except Exception:
                day_tip = f"今日为最后一天，景点已优先安排在{station_name}附近，请预留充足时间返程。"
        else:
            day_tip = f"今日为最后一天，景点已优先安排在{station_name}附近，请预留充足时间返程。"

    return DayPlan(
        day=day_no,
        theme=day_theme,
        date_label=date_label(day_no, req.days),
        items=items, budget=budget,
        hotel=None,
        hotel_area=hotel_area,
        tip=day_tip,
        inspiration=daily_inspiration(day_theme, day_no),
    )


async def geo_plan(req: PlanRequest, center: dict, aux_pois: List[dict],
                   attrs: List[dict], is_province: bool = False) -> tuple:
    """规则化地理规划主入口：景点聚类成区域 → 短距同日 → 跨天不重复。

    返程车站优化：如果用户提供了返程车站（return_station），最后一天的景点优先选择离车站近的，
    确保返程方便，避免赶车紧张。
    """
    if req.must_include_poi:
        known_names = {a["name"] for a in attrs}
        for n in req.must_include_poi:
            n = n.strip()
            if not n or n in known_names:
                continue
            rp = await amap.resolve_poi(req.destination, n, "景点")
            if rp and rp["name"] not in known_names:
                attrs.insert(0, rp)
                known_names.add(rp["name"])
    if len(attrs) < 6:
        seen = {a["name"] for a in attrs}
        for p in aux_pois:
            if p["category"] == "景点" and p["name"] not in seen:
                attrs.append(p)
                seen.add(p["name"])

    # 返程车站处理：如果有返程车站，先地理编码获取车站位置
    return_station_geo = None
    if req.return_station:
        try:
            return_station_geo = await amap.geocode(req.return_station)
        except Exception:
            pass

    if is_province:
        areas = province_areas(attrs, center, req.days)
    else:
        clusters = cluster_attractions(attrs)
        areas = assign_areas_to_days(clusters, center, req.days)

    # 返程车站优化：将离返程车站最近的区域调整到最后一天
    if return_station_geo and len(areas) >= 2:
        station_lng = return_station_geo.get("lng", 0)
        station_lat = return_station_geo.get("lat", 0)
        if station_lng and station_lat:
            # 计算每个区域到返程车站的距离
            areas_with_dist = []
            for i, area in enumerate(areas):
                area_cx = area.get("cx", 0)
                area_cy = area.get("cy", 0)
                dist = amap.haversine(area_cx, area_cy, station_lng, station_lat)
                areas_with_dist.append((i, area, dist))
            # 按距离排序，找到离车站最近的区域
            areas_with_dist.sort(key=lambda x: x[2])
            closest_idx = areas_with_dist[0][0]
            # 如果最近的区域不在最后一天，交换到最后一天
            if closest_idx != len(areas) - 1:
                areas[closest_idx], areas[-1] = areas[-1], areas[closest_idx]

    used_ids: set = set()
    day_plans: List[DayPlan] = []
    prev_hotel_area: Optional[dict] = None
    for day_no, area in enumerate(areas, 1):
        day_start = None
        if prev_hotel_area is not None:
            day_start = {"lng": prev_hotel_area.get("center_lng", 0), "lat": prev_hotel_area.get("center_lat", 0)}
        # 最后一天且有返程车站时，传递返程车站信息给build_geo_day
        is_last_day = (day_no == len(areas))
        dp = await build_geo_day(
            req, center, area, aux_pois, attrs, used_ids, day_no, day_start,
            is_last_day=is_last_day, return_station_geo=return_station_geo if is_last_day else None
        )
        if dp:
            day_plans.append(dp)
            if dp.hotel_area is not None:
                prev_hotel_area = dp.hotel_area
    return day_plans, "(规则引擎)", "geo"


def pick_new_focus(dp: DayPlan, cur_focus: str, claimed: set,
                    region_pool: dict, used_ids: set) -> Optional[str]:
    """为与更早一天主区域重复的当天，挑选一个未被占用的新主区域。"""
    counts: dict = {}
    for it in dp.items:
        r = region_of(it.poi)
        if r == cur_focus or r in claimed:
            continue
        counts[r] = counts.get(r, 0) + 1
    for r in sorted(counts, key=lambda x: -counts[x]):
        usable = [p for p in region_pool.get(r, []) if p["id"] not in used_ids]
        if len(usable) >= 2:
            return r
    if dp.items:
        cx = sum(it.poi.lng for it in dp.items) / len(dp.items)
        cy = sum(it.poi.lat for it in dp.items) / len(dp.items)
        best_r, best_d = None, float("inf")
        for r, ps in region_pool.items():
            if not r or r in claimed or r == cur_focus:
                continue
            usable = [p for p in ps if p["id"] not in used_ids]
            if len(usable) < 2:
                continue
            d = min(amap.haversine(cx, cy, p["lng"], p["lat"]) for p in usable)
            if d < best_d:
                best_d, best_r = d, r
        return best_r
    return None


async def rebuild_day_from_region(req: PlanRequest, center: dict, region: str,
                                   dp: DayPlan, region_pool: dict, used_ids: set) -> Optional[List[PlanItem]]:
    """用指定区域的未用点位按「景点/美食/购物/夜生活」骨架重建一天。"""
    avail = [p for p in region_pool.get(region, []) if p["id"] not in used_ids]
    if len(avail) < 2:
        return None
    by_cat: dict = {}
    for p in avail:
        by_cat.setdefault(p["category"], []).append(p)
    for lst in by_cat.values():
        lst.sort(key=lambda p: -p.get("rating", 0))

    def pop(cat: str) -> Optional[dict]:
        lst = by_cat.get(cat) or []
        return lst.pop(0) if lst else None

    plan = []
    a = pop("景点")
    if a:
        plan.append(rule_item(a, "上午", 150))
    f = pop("美食")
    if f:
        plan.append(rule_item(f, "中午", 75))
    a2 = pop("景点")
    if a2:
        plan.append(rule_item(a2, "下午", 150))
    s = pop("购物")
    if s:
        plan.append(rule_item(s, "下午", 90))
    n = pop("夜生活")
    if n:
        plan.append(rule_item(n, "晚上", 90))
    poi_map = {p["id"]: p for p in avail}
    poi_items = [(poi_map[it["poi_id"]], it) for it in plan if it["poi_id"] in poi_map]
    if len(poi_items) < 2:
        return None
    poi_items = reorder_day(poi_items, center)
    items = await build_items(poi_items, req.traffic_mode)
    return apply_timeline(req, items) or None


async def replace_strays(req: PlanRequest, center: dict, dp: DayPlan, focus: str,
                         region_pool: dict, used_ids: set) -> Optional[List[PlanItem]]:
    """把当天不在主区域 focus 的点位，替换为主区域未用点位（同品类优先）。"""
    if not focus:
        return None
    avail = [p for p in region_pool.get(focus, []) if p["id"] not in used_ids]
    if not avail:
        return None
    new_items = []
    changed = False
    for it in dp.items:
        if region_of(it.poi) == focus:
            new_items.append(it)
            continue
        same = [p for p in avail if p["category"] == it.poi.category]
        pool2 = same or avail
        if not pool2:
            new_items.append(it)
            continue
        pool2 = sorted(pool2, key=lambda p: -p.get("rating", 0))
        p_new = pool2[0]
        avail.remove(p_new)
        new_items.append(PlanItem(
            slot="上午", start_time="", poi=POI(**p_new),
            duration_min=it.duration_min,
            note="已调整为同区域人气点位（避免跨天重复地域）",
        ))
        changed = True
    if not changed:
        return None
    poi_items = [(it.poi.model_dump(),
                  {"slot": it.slot, "duration_min": it.duration_min, "note": it.note})
                 for it in new_items]
    poi_items = reorder_day(poi_items, center)
    rebuilt = await build_items(poi_items, req.traffic_mode)
    rebuilt = apply_timeline(req, rebuilt)
    return rebuilt or new_items


async def enforce_region_distinct(req: PlanRequest, center: dict, pois: List[dict],
                                  day_plans: List[DayPlan]) -> List[DayPlan]:
    """跨天地域去重：让每天集中在一个区域，且不同天不重复使用同一主区域。"""
    if len(day_plans) <= 1:
        return day_plans
    region_pool: dict = {}
    for p in pois:
        region_pool.setdefault(region_of(p), []).append(p)
    used_ids = {it.poi.id for dp in day_plans for it in dp.items}
    claimed: set = set()
    for dp in day_plans:
        focus = day_focus(dp)
        if focus and focus in claimed:
            new_focus = pick_new_focus(dp, focus, claimed, region_pool, used_ids)
            if new_focus:
                rebuilt = await rebuild_day_from_region(req, center, new_focus, dp,
                                                         region_pool, used_ids)
                if rebuilt:
                    dp.items = rebuilt
                    dp.budget, _bd = day_budget(req, rebuilt)
                    focus = new_focus
        if focus:
            claimed.add(focus)
        rebuilt2 = await replace_strays(req, center, dp, focus, region_pool, used_ids)
        if rebuilt2:
            dp.items = rebuilt2
            dp.budget, _bd = day_budget(req, rebuilt2)
        used_ids = {it.poi.id for d in day_plans for it in d.items}
    return day_plans
