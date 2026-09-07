"""
行程规划引擎 - 两阶段规划模块（空间规划 + 时间拆分）。

策略：
第一阶段（空间规划）：先忽略时间，按照 出发点 -> 目的城市(多个景点) -> 返程点
                    确定整体路线，形成一条完整的空间游览序列
第二阶段（时间拆分）：将整体路线按照天数、每天时间跨度、景点停留时间、
                    交通时间拆分成每天的行程

优势：
1. 空间上更合理：先确定整体路线，避免每天的景点在地理上分散
2. 时间上更灵活：可以根据用户的时间跨度灵活拆分
3. 更符合用户思维：先确定要去哪里，再安排每天的行程
4. 支持多城市路线：可以规划跨城市的整体路线

功能特性：
- 空间路线数据类（SpatialRoute）：出发点、目的城市中心、返程点、按游览顺序排列的景点列表、总距离、总游览时间、总交通时间、路线摘要
- 单日拆分数据类（DaySplit）：第几天、景点列表、当天起点、当天终点、游览时间、交通时间、距离
- 第一阶段：构建空间整体路线（忽略时间）
- 筛选用于空间路线的景点（必去 > 地标 > 评分）
- 按照地理位置排序景点（最近邻贪心算法）
- 估算景点游览时间（分钟）
- 估算交通时间（分钟）
- 第二阶段：将空间路线拆分成每天的行程
- 将天拆分结果构建成最终的DayPlan列表
- 根据当天景点确定主题
- 两阶段规划主入口

使用方式：
    from app.services.planner.spatial_temporal_planner import spatial_temporal_plan

    # 两阶段规划主入口
    day_plans, spatial_route, day_splits = await spatial_temporal_plan(
        req, origin, center, return_point, attrs, aux_pois
    )
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ...data.models.models import DayPlan, PlanItem, PlanRequest, POI
from ...services import map as amap
from .cluster import _is_landmark, _rank
from .daily_build import (
    apply_timeline,
    build_items,
    date_label,
    day_budget,
    local_aux,
    pick_auxiliary,
    rule_item,
)


@dataclass
class SpatialRoute:
    """空间路线（第一阶段输出）"""
    origin: Optional[Dict] = None  # 出发点
    destination: Optional[Dict] = None  # 目的城市中心
    return_point: Optional[Dict] = None  # 返程点
    pois: List[Dict] = field(default_factory=list)  # 按游览顺序排列的景点列表
    total_distance_km: float = 0.0  # 总距离（公里）
    total_visit_minutes: int = 0  # 总游览时间（分钟）
    total_transit_minutes: int = 0  # 总交通时间（分钟）
    route_summary: str = ""  # 路线摘要


@dataclass
class DaySplit:
    """单日拆分（第二阶段输出）"""
    day_no: int
    pois: List[Dict] = field(default_factory=list)
    start_point: Optional[Dict] = None  # 当天起点（住宿点）
    end_point: Optional[Dict] = None  # 当天终点（住宿点）
    visit_minutes: int = 0
    transit_minutes: int = 0
    distance_km: float = 0.0


# ========== 第一阶段：空间整体路线规划 ==========

def build_spatial_route(
    req: PlanRequest,
    origin: Optional[Dict],
    center: Dict,
    return_point: Optional[Dict],
    attrs: List[Dict],
    aux_pois: List[Dict],
) -> SpatialRoute:
    """
    第一阶段：构建空间整体路线（忽略时间）

    策略：
    1. 筛选候选景点（评分、必去、地标优先）
    2. 按照地理位置排序，形成一条完整的游览路线
    3. 出发点 -> 景点1 -> 景点2 -> ... -> 景点N -> 返程点
    4. 计算总距离、总游览时间、总交通时间

    Args:
        req: 规划请求
        origin: 出发点（经纬度）
        center: 目的城市中心
        return_point: 返程点
        attrs: 候选景点列表
        aux_pois: 辅助POI列表（美食、购物等）

    Returns:
        SpatialRoute: 空间路线
    """
    # 1. 筛选候选景点
    # 如果attrs已经很少（经过上游过滤），直接使用所有attrs，不再进一步筛选
    # 同时从aux_pois中补充景点（如果aux_pois中有景点类别的POI）
    all_attrs = list(attrs)
    for p in aux_pois:
        if p.get("category") == "景点" and p.get("name") not in {a.get("name") for a in all_attrs}:
            all_attrs.append(p)

    if len(all_attrs) <= 6:
        selected_pois = all_attrs
    else:
        selected_pois = _select_pois_for_route(req, all_attrs)

    if not selected_pois:
        # 降级：使用所有候选景点
        selected_pois = all_attrs[:10] if all_attrs else []

    # 2. 按照地理位置排序（最近邻贪心算法）
    ordered_pois = _order_pois_by_location(
        selected_pois,
        start_point=origin or center,
        end_point=return_point,
    )

    # 3. 计算路线统计
    total_visit_minutes = sum(
        _estimate_visit_minutes(p, req.pace) for p in ordered_pois
    )
    total_distance_km = 0.0
    total_transit_minutes = 0

    prev_point = origin or center
    for poi in ordered_pois:
        dist = amap.haversine(
            prev_point.get("lng", 0), prev_point.get("lat", 0),
            poi.get("lng", 0), poi.get("lat", 0),
        )
        total_distance_km += dist
        total_transit_minutes += _estimate_transit_minutes(dist, req.traffic_mode)
        prev_point = poi

    if return_point:
        dist = amap.haversine(
            prev_point.get("lng", 0), prev_point.get("lat", 0),
            return_point.get("lng", 0), return_point.get("lat", 0),
        )
        total_distance_km += dist
        total_transit_minutes += _estimate_transit_minutes(dist, req.traffic_mode)

    # 4. 生成路线摘要
    poi_names = [p.get("name", "") for p in ordered_pois[:5]]
    route_summary = f"共{len(ordered_pois)}个景点，路线：{' → '.join(poi_names)}"
    if len(ordered_pois) > 5:
        route_summary += f" → ...（共{len(ordered_pois)}个）"

    return SpatialRoute(
        origin=origin,
        destination=center,
        return_point=return_point,
        pois=ordered_pois,
        total_distance_km=round(total_distance_km, 1),
        total_visit_minutes=total_visit_minutes,
        total_transit_minutes=total_transit_minutes,
        route_summary=route_summary,
    )


def _select_pois_for_route(req: PlanRequest, attrs: List[Dict]) -> List[Dict]:
    """
    筛选用于空间路线的景点

    筛选策略：
    1. 必去景点优先
    2. 地标景点优先
    3. 评分高的优先
    4. 根据天数和节奏确定景点数量
    """
    if not attrs:
        return []

    # 根据天数和节奏确定目标景点数量
    pace_factor = {
        "轻松": 2.5,   # 每天2-3个景点
        "适中": 3.5,   # 每天3-4个景点
        "暴走": 5.0,   # 每天5-6个景点
    }.get(req.pace or "适中", 3.5)

    target_count = max(6, int(req.days * pace_factor))
    target_count = min(target_count, len(attrs), 30)  # 最多30个景点

    # 排序：必去 > 地标 > 评分
    def sort_key(p):
        must_visit = 100 if p.get("must_visit") else 0
        landmark = 50 if _is_landmark(p) else 0
        rating = _rank(p)
        return must_visit + landmark + rating

    sorted_pois = sorted(attrs, key=sort_key, reverse=True)

    # 去重（同名景点只保留一个）
    seen_names = set()
    selected = []
    for p in sorted_pois:
        name = p.get("name", "").strip()
        if name and name not in seen_names:
            seen_names.add(name)
            selected.append(p)
            if len(selected) >= target_count:
                break

    return selected


def _order_pois_by_location(
    pois: List[Dict],
    start_point: Dict,
    end_point: Optional[Dict] = None,
) -> List[Dict]:
    """
    按照地理位置排序景点（最近邻贪心算法）

    策略：
    1. 从出发点开始，每次选择距离当前位置最近的未访问景点
    2. 直到所有景点都被访问
    3. 如果指定了终点，最后考虑终点方向

    Args:
        pois: 待排序的景点列表
        start_point: 起点（经纬度）
        end_point: 终点（经纬度，可选）

    Returns:
        排序后的景点列表
    """
    if not pois:
        return []

    remaining = list(pois)
    ordered = []
    current = start_point

    while remaining:
        # 找到距离当前位置最近的景点
        best_idx = 0
        best_dist = float("inf")
        for i, p in enumerate(remaining):
            dist = amap.haversine(
                current.get("lng", 0), current.get("lat", 0),
                p.get("lng", 0), p.get("lat", 0),
            )
            # 如果有终点，考虑终点方向（距离终点更近的稍微优先）
            if end_point:
                dist_to_end = amap.haversine(
                    p.get("lng", 0), p.get("lat", 0),
                    end_point.get("lng", 0), end_point.get("lat", 0),
                )
                # 综合考虑：当前距离 + 到终点距离的0.3倍
                dist = dist + dist_to_end * 0.3

            if dist < best_dist:
                best_dist = dist
                best_idx = i

        best_poi = remaining.pop(best_idx)
        ordered.append(best_poi)
        current = best_poi

    return ordered


def _estimate_visit_minutes(poi: Dict, pace: str = "适中") -> int:
    """估算景点游览时间（分钟）"""
    base = poi.get("duration_min") or 0
    if base > 0:
        return base

    # 根据景点类型和等级估算
    name = poi.get("name", "")
    poi_level = poi.get("poi_level") or poi.get("level") or ""

    # 大型景区（5A/世界遗产）
    if "5A" in poi_level or _is_landmark(poi):
        base = 120
    # 中型景区（4A）
    elif "4A" in poi_level:
        base = 90
    # 普通景点
    else:
        base = 60

    # 根据节奏调整
    pace_factor = {"轻松": 1.3, "适中": 1.0, "暴走": 0.7}.get(pace, 1.0)
    return int(base * pace_factor)


def _estimate_transit_minutes(distance_km: float, traffic_mode: str = "混合") -> int:
    """估算交通时间（分钟）"""
    if distance_km <= 0:
        return 0

    # 根据交通方式估算速度（km/h）
    speed = {
        "自驾": 40,
        "公共交通": 25,
        "骑行": 15,
        "步行": 5,
        "混合": 30,
    }.get(traffic_mode, 30)

    # 加上等车/换乘时间
    wait_time = 10 if traffic_mode in ("公共交通", "混合") else 5
    return int(distance_km / speed * 60 + wait_time)


# ========== 第二阶段：时间拆分 ==========

def split_route_to_days(
    req: PlanRequest,
    route: SpatialRoute,
    aux_pois: List[Dict],
) -> List[DaySplit]:
    """
    第二阶段：将空间路线拆分成每天的行程

    拆分原则：
    1. 每天的景点数量合理（根据节奏）
    2. 每天的总游览时间不超过合理范围（8-10小时）
    3. 每天的景点在地理上尽量集中（连续的路线段）
    4. 住宿点作为第二天的起点
    5. 跨天出行内容不重复

    Args:
        req: 规划请求
        route: 空间路线
        aux_pois: 辅助POI列表

    Returns:
        List[DaySplit]: 按天拆分的行程
    """
    if not route.pois:
        return []

    days = req.days
    pois = route.pois
    n_pois = len(pois)

    # 计算每天的目标游览时间（分钟）
    daily_visit_minutes = {
        "轻松": 360,   # 6小时
        "适中": 480,   # 8小时
        "暴走": 600,   # 10小时
    }.get(req.pace or "适中", 480)

    # 贪心拆分：每天尽量装满，但不超过目标时间
    day_splits = []
    poi_idx = 0

    for day_no in range(1, days + 1):
        day_pois = []
        day_visit_minutes = 0
        day_transit_minutes = 0
        day_distance_km = 0.0

        # 确定当天起点
        if day_no == 1:
            start_point = route.origin or route.destination
        else:
            start_point = day_splits[-1].end_point or route.destination

        current_point = start_point

        # 最后一天要留时间返程
        is_last_day = (day_no == days)
        remaining_pois = n_pois - poi_idx
        remaining_days = days - day_no + 1

        # 计算当天最多能装多少景点（平均分配，最后一天多装）
        if is_last_day:
            max_pois = remaining_pois  # 最后一天装完所有剩余景点
        else:
            max_pois = max(1, remaining_pois // remaining_days)
            # 适当浮动（±1）
            if day_visit_minutes < daily_visit_minutes * 0.7:
                max_pois += 1

        # 贪心填充当天的景点
        while poi_idx < n_pois and len(day_pois) < max_pois:
            poi = pois[poi_idx]

            # 估算加入这个景点后的总时间
            visit_minutes = _estimate_visit_minutes(poi, req.pace)
            dist = amap.haversine(
                current_point.get("lng", 0), current_point.get("lat", 0),
                poi.get("lng", 0), poi.get("lat", 0),
            )
            transit_minutes = _estimate_transit_minutes(dist, req.traffic_mode)

            # 检查是否超过当天时间限制（最后一天除外）
            if not is_last_day and day_visit_minutes + visit_minutes > daily_visit_minutes * 1.2:
                break

            day_pois.append(poi)
            day_visit_minutes += visit_minutes
            day_transit_minutes += transit_minutes
            day_distance_km += dist
            current_point = poi
            poi_idx += 1

        # 当天终点（住宿点）= 当天最后一个景点
        end_point = day_pois[-1] if day_pois else current_point

        day_split = DaySplit(
            day_no=day_no,
            pois=day_pois,
            start_point=start_point,
            end_point=end_point,
            visit_minutes=day_visit_minutes,
            transit_minutes=day_transit_minutes,
            distance_km=round(day_distance_km, 1),
        )
        day_splits.append(day_split)

    # 如果还有剩余景点（理论上不应该，因为最后一天会装完），加到最后一天
    if poi_idx < n_pois:
        for poi in pois[poi_idx:]:
            day_splits[-1].pois.append(poi)

    return day_splits


# ========== 构建最终行程 ==========

async def build_day_plans_from_splits(
    req: PlanRequest,
    center: Dict,
    day_splits: List[DaySplit],
    aux_pois: List[Dict],
    attrs: List[Dict],
) -> List[DayPlan]:
    """
    将天拆分结果构建成最终的DayPlan列表

    Args:
        req: 规划请求
        center: 目的城市中心
        day_splits: 天拆分结果
        aux_pois: 辅助POI列表
        attrs: 所有候选景点

    Returns:
        List[DayPlan]: 最终行程列表
    """
    day_plans = []
    used_ids = set()

    for split in day_splits:
        if not split.pois:
            continue

        # 构建POI items（景点 + 辅助POI）
        poi_items = []
        area = {
            "cx": sum(p.get("lng", 0) for p in split.pois) / len(split.pois),
            "cy": sum(p.get("lat", 0) for p in split.pois) / len(split.pois),
            "pois": split.pois,
        }

        # 添加主景点
        for poi in split.pois:
            poi_items.append((poi, {"slot": "上午", "duration_min": _estimate_visit_minutes(poi, req.pace)}))
            used_ids.add(poi.get("id") or poi.get("name"))

        # 添加辅助POI（美食/购物/夜生活）
        aux = pick_auxiliary(area, aux_pois, used_ids)
        if aux:
            poi_items.append((aux, {"slot": "中午", "duration_min": 60}))

        # 构建PlanItem列表
        items = await build_items(poi_items, req.traffic_mode)

        # 应用时间轴
        items = apply_timeline(req, items)

        # 计算当天预算
        budget, breakdown = day_budget(req, items)

        # 确定当天主题
        theme = _determine_day_theme(split)

        dp = DayPlan(
            day=split.day_no,
            theme=theme,
            date_label=date_label(split.day_no, req.days),
            items=items,
            budget=round(budget, 1),
            budget_breakdown=breakdown,
            hotel=None,  # 住宿点可以后续添加
        )
        day_plans.append(dp)

    return day_plans


def _determine_day_theme(split: DaySplit) -> str:
    """根据当天景点确定主题"""
    if not split.pois:
        return f"第{split.day_no}天"

    # 取第一个景点的区域作为主题
    first_poi = split.pois[0]
    adname = first_poi.get("adname") or first_poi.get("district") or ""
    name = first_poi.get("name", "")

    if adname and len(split.pois) > 1:
        return f"{adname}深度游"
    elif name:
        return f"{name}周边"
    else:
        return f"第{split.day_no}天"


# ========== 主入口 ==========

async def spatial_temporal_plan(
    req: PlanRequest,
    origin: Optional[Dict],
    center: Dict,
    return_point: Optional[Dict],
    attrs: List[Dict],
    aux_pois: List[Dict],
) -> Tuple[List[DayPlan], SpatialRoute, List[DaySplit]]:
    """
    两阶段规划主入口

    第一阶段：空间整体路线规划
    第二阶段：时间拆分

    Args:
        req: 规划请求
        origin: 出发点
        center: 目的城市中心
        return_point: 返程点
        attrs: 候选景点列表
        aux_pois: 辅助POI列表

    Returns:
        (day_plans, spatial_route, day_splits): 最终行程、空间路线、天拆分结果
    """
    # 第一阶段：空间整体路线规划
    spatial_route = build_spatial_route(
        req, origin, center, return_point, attrs, aux_pois
    )

    # 第二阶段：时间拆分
    day_splits = split_route_to_days(req, spatial_route, aux_pois)

    # 构建最终行程
    day_plans = await build_day_plans_from_splits(
        req, center, day_splits, aux_pois, attrs
    )

    return day_plans, spatial_route, day_splits
