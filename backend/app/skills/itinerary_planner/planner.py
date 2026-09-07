"""
行程规划引擎：AI 生成 + 规则引擎兜底 + 高德路径/预算增强。

渐进式拆分中：常量已迁移到 services/planner/utils.py，
工具函数/地理枚举/必去地标/聚类/逐日构建等模块待后续拆分。

功能特性：
- build_plan：行程规划主入口（AI生成 + 规则引擎兜底）
- _geo_plan：行政分级地理规划（省/市/区县三级枚举）
- _log_poi_pool：景点池变化日志输出（用于排查规划过程中的问题）
- 必去地标注入（must_visit）
- 地理聚类（cluster）
- 逐日构建（daily_build）
- 两阶段规划（spatial_temporal_planner）
- 规则引擎集成（skills/rule_engine）
- LLM行程优化阶段
- 预算估算和拆分
- 时间线应用
- 跨天地域去重

使用方式：
    from app.core.planner import build_plan

    # 创建规划请求
    request = PlanRequest(
        destination="杭州",
        days=3,
        people=2,
        budget="适中",
        style="人文",
    )

    # 执行规划
    response = await build_plan(request)
    # 返回 PlanResponse 对象，包含行程详情、预算、地图等信息
"""
import datetime
import time
import traceback
import uuid
from typing import Any, Dict, List, Optional

from app.skills.rule_engine import get_rule_engine

from ...ai import ai as ai_mod
from ...data.models.models import DayPlan, PlanItem, PlanRequest, PlanResponse, POI
from ...infrastructure import logger as log_mod
from ...services import map as amap
from ...services.major_attractions import get_major_attractions_service
from .cluster import (
    area_label as _area_label,
    assign_areas_to_days as _assign_areas_to_days,
    cluster_attractions as _cluster_attractions,
    dist_tier as _dist_tier,
    greedy_group as _greedy_group,
    make_area as _make_area,
    merge_sparse_clusters as _merge_sparse_clusters,
    split_to_balance as _split_to_balance,
)
from .daily_build import (
    apply_timeline as _apply_timeline,
    balance_day as _balance_day,
    build_geo_day as _build_geo_day,
    build_items as _build_items,
    date_label as _date_label,
    day_budget as _day_budget,
    day_focus as _day_focus,
    dedup_landmark_day as _dedup_landmark_day,
    enforce_region_distinct as _enforce_region_distinct,
    geo_plan as _geo_plan,
    local_aux as _local_aux,
    match_pool_by_name as _match_pool_by_name,
    pick_auxiliary as _pick_auxiliary,
    pick_hotel as _pick_hotel,
    pick_new_focus as _pick_new_focus,
    province_areas as _province_areas,
    rebuild_day_from_region as _rebuild_day_from_region,
    region_of as _region_of,
    reorder_day as _reorder_day,
    replace_strays as _replace_strays,
    rule_item as _rule_item,
    total_breakdown as _total_breakdown,
)
from .geo_enum import (
    enumerate_scoped_attractions as _enumerate_scoped_attractions,
    is_in_china as _is_in_china,
    is_province as _is_province,
    load_province_best_season as _load_province_best_season,
    months_str as _months_str,
    resolve_province as _resolve_province,
    scope_attrs as _scope_attrs,
)
from .must_visit import (
    inject_must_visit_attrs as _inject_must_visit_attrs,
)
from .timeline_planner import TimelinePlanner, plan_day_timeline
from .constants import (
    AUX_FOOD_BAD_NAMES,
    CLUSTER_MAX_DIST,
    CLOSED_MARKERS,
    LANDMARK_WORDS,
    SCOPE_KEYWORDS,
    SCOPE_MAX_RANGE,
)
from .spatial_temporal import (
    spatial_temporal_plan as _spatial_temporal_plan,
)
from .utils import (
    BUDGET_TABLE,
    DAILY_INSPIRATIONS,
    DEPARTURE_MESSAGES,
    GROUP_PACE,
    PACE_ITEMS,
    SLOT_ORDER,
    SLOT_TIME,
    daily_inspiration,
    departure_message,
    pick,
)

_planner_logger = log_mod.get_logger("planner")


def _log_poi_pool(stage: str, request_id: str, destination: str, pois: list, limit: int = 30):
    """输出景点池的详细信息，用于排查规划过程中的问题

    Args:
        stage: 阶段名称（如"枚举后"、"注入后"、"LLM优化后"等）
        request_id: 请求ID
        destination: 目的地
        pois: 景点列表
        limit: 输出的景点数量上限
    """
    if not pois:
        _planner_logger.info(f"poi_pool_{stage}", extra={"fields": {
            "request_id": request_id, "destination": destination,
            "stage": stage, "count": 0, "pois": [],
        }})
        return

    # 按类别统计
    categories = {}
    for p in pois:
        cat = p.get("category", p.get("type", "未知"))
        categories[cat] = categories.get(cat, 0) + 1

    # 提取景点详细信息
    poi_details = []
    for i, p in enumerate(pois[:limit]):
        poi_details.append({
            "index": i + 1,
            "name": p.get("name", ""),
            "category": p.get("category", p.get("type", "")),
            "rating": p.get("rating", 0),
            "hot": p.get("hot", False),
            "is_scenic_inner": p.get("is_scenic_inner", False),
            "parent_scenic": p.get("parent_scenic", ""),
            "scenic_weight_factor": p.get("scenic_weight_factor", 1.0),
            "llm_theme": p.get("llm_theme", ""),
            "llm_duration": p.get("llm_duration", 0),
            "llm_best_slot": p.get("llm_best_slot", ""),
            "original_rating": p.get("original_rating", 0),
            "is_family_friendly": p.get("is_family_friendly", False),
            "is_elderly_friendly": p.get("is_elderly_friendly", False),
            "is_couple_friendly": p.get("is_couple_friendly", False),
            "cityname": p.get("cityname", ""),
            "adname": p.get("adname", ""),
        })

    _planner_logger.info(f"poi_pool_{stage}", extra={"fields": {
        "request_id": request_id, "destination": destination,
        "stage": stage,
        "count": len(pois),
        "categories": categories,
        "pois": poi_details,
        "truncated": len(pois) > limit,
    }})


def _build_long_span_summary(req: PlanRequest, province: str) -> dict:
    """生成大时间跨度（月/年）的月度分配摘要。

    规则：
    - 月级（1个月）：当前省或临近省，1个省
    - 月级（2个月）：2个省（当前省+最佳临近省）
    - 年级（1年）：12个月，每月一个省，按最佳出行月份分配

    返回 {unit, total_months, months: [{month, province, reason, best_for}]}
    """
    season_data = _load_province_best_season()
    span_unit = req.span_unit
    span_value = req.span_value

    # 标准化省份名（去掉"省"/"市"/"自治区"等后缀用于匹配）
    def _match_province(name: str) -> str:
        """在 season_data 中匹配省份名（支持简称/全称）"""
        if name in season_data:
            return name
        for suffix in ["省", "市", "自治区", "壮族自治区", "回族自治区", "维吾尔自治区"]:
            if name.endswith(suffix):
                base = name[: -len(suffix)]
                for k in season_data:
                    if k.startswith(base) or base in k:
                        return k
        # 模糊匹配
        for k in season_data:
            if name in k or k in name:
                return k
        return ""

    current_province = _match_province(province) or province

    if span_unit == "month":
        # 月级：1个月=1个省，2个月=2个省
        n_provinces = min(max(span_value, 1), 3)  # 最多3个月/3个省
        months = []
        # 第一个月：当前省
        info = season_data.get(current_province, {})
        months.append({
            "month": 1,
            "province": current_province,
            "reason": f"出发地所在省，{info.get('reason', '适合深度游览')}",
            "best_for": _months_str(info.get("best_months", [])),
        })
        # 后续月份：选择最佳临近省（按最佳月份排序）
        if n_provinces > 1:
            candidates = [(k, v) for k, v in season_data.items() if k != current_province]
            # 简单策略：按省份名称排序（后续可优化为地理临近）
            candidates.sort(key=lambda x: x[0])
            for i in range(1, n_provinces):
                if i - 1 < len(candidates):
                    k, v = candidates[i - 1]
                    months.append({
                        "month": i + 1,
                        "province": k,
                        "reason": v.get("reason", "适合深度游览"),
                        "best_for": _months_str(v.get("best_months", [])),
                    })
        return {
            "unit": "month",
            "total_months": n_provinces,
            "current_province": current_province,
            "months": months,
            "tip": f"每月深度游览一个省，每省约{req.days}天精华行程，避免行程过于庞杂。",
        }

    elif span_unit == "year":
        # 年级：12个月，每月一个省，按最佳出行月份分配
        all_provinces = list(season_data.items())
        # 为每个月分配最佳省份
        months = []
        used_provinces = set()
        # 第一个月优先当前省
        if current_province in season_data:
            used_provinces.add(current_province)
            info = season_data[current_province]
            months.append({
                "month": 1,
                "province": current_province,
                "reason": f"出发地所在省，{info.get('reason', '适合深度游览')}",
                "best_for": _months_str(info.get("best_months", [])),
            })
        # 为第2-12个月分配：选择该月最佳且未使用的省份
        for month in range(2, 13):
            # 该月最佳的省份（best_months 包含该月，且未使用）
            best = [(k, v) for k, v in all_provinces
                    if k not in used_provinces and month in (v.get("best_months") or [])]
            if not best:
                # 该月没有最佳省份，选任意未使用的
                best = [(k, v) for k, v in all_provinces if k not in used_provinces]
            if best:
                # 按 best_months 数量排序（最佳月份多的优先）
                best.sort(key=lambda x: -len(x[1].get("best_months") or []))
                k, v = best[0]
                used_provinces.add(k)
                months.append({
                    "month": month,
                    "province": k,
                    "reason": v.get("reason", "适合深度游览"),
                    "best_for": _months_str(v.get("best_months", [])),
                })
        return {
            "unit": "year",
            "total_months": 12,
            "current_province": current_province,
            "months": months,
            "tip": "全年12个月，每月深度游览一个省，按各省最佳出行季节分配，避开极端天气。",
        }

    # 天/周级：不生成月度摘要
    return {}


# ========== 大型景区识别（从数据库读取） ==========

_large_scenic_cache = None

def _load_large_scenic_areas() -> dict:
    """从数据库加载大型景区列表（带缓存）"""
    global _large_scenic_cache
    if _large_scenic_cache is not None:
        return _large_scenic_cache
    try:
        from ...data.repositories.poi_hierarchy_repository import PoiHierarchyRepository
        repo = PoiHierarchyRepository()
        all_pois, _ = repo.list_main_pois(page_size=1000)
        _large_scenic_cache = {}
        for poi in all_pois:
            if poi.get("is_large_scenic"):
                _large_scenic_cache[poi["name"]] = poi.get("city", "")
    except Exception:
        _large_scenic_cache = {}
    return _large_scenic_cache


def is_large_scenic_area(name: str, category: str = "") -> bool:
    """判断是否为大型景区（从数据库读取）"""
    if not name:
        return False
    large_areas = _load_large_scenic_areas()
    # 精确匹配
    if name in large_areas:
        return True
    # 类型匹配
    large_types = ["风景区", "风景名胜区", "5A", "4A", "世界遗产", "国家公园", "地质公园", "森林公园", "湿地公园"]
    if any(t in category for t in large_types):
        return True
    # 包含匹配（名称包含大型景区名）
    for scenic_name in large_areas:
        if scenic_name in name and len(name) > len(scenic_name):
            return True
    return False


def is_inside_large_scenic_area(name: str, category: str = "") -> tuple:
    """判断是否在大型景区内部，返回(是否在内部, 父景区名)"""
    if not name:
        return (False, None)
    large_areas = _load_large_scenic_areas()
    for scenic_name in large_areas:
        if scenic_name in name and name != scenic_name:
            return (True, scenic_name)
    return (False, None)


def get_scenic_area_weight_factor(name: str, category: str = "") -> float:
    """获取大型景区的权重因子（大型景区权重更高）"""
    # 先检查是否在大型景区内部（景区内小景点权重降低）
    is_inner, parent_scenic = is_inside_large_scenic_area(name, category)
    if is_inner:
        return 0.7  # 景区内小景点权重降低
    # 再检查是否为大型景区本身
    if is_large_scenic_area(name, category):
        return 1.5
    return 1.0


def dedup_scenic_inner_pois(attrs: list, request_id: str = "", destination: str = "") -> list:
    """
    统一的大型景区与景区内小景点去重函数。

    确保所有路径都生效：如果大型景区本身已在候选池中，则过滤掉该景区内的小景点，
    避免重复规划（如"大明湖景区"和"大明湖超然楼"同时出现在行程中）。

    去重策略：
    1. 识别候选池中的大型景区，提取基础名称（如"大明湖景区"->"大明湖"）
    2. 过滤掉 is_scenic_inner=True 且 parent_scenic 匹配的景点
    3. 过滤掉名称包含大型景区基础名称的小景点
    4. 日志记录去重情况

    Args:
        attrs: 候选景点列表
        request_id: 请求ID（用于日志）
        destination: 目的地（用于日志）

    Returns:
        去重后的景点列表
    """
    if not attrs:
        return attrs

    # 1. 识别候选池中的大型景区，提取基础名称
    large_scenics_in_pool = set()
    large_scenic_base_names = set()
    for p in attrs:
        pname = p.get("name", "")
        pcategory = p.get("category", "") or p.get("type", "")
        if is_large_scenic_area(pname, pcategory):
            large_scenics_in_pool.add(pname)
            # 提取基础名称：去掉大型景区后缀
            base_name = pname
            for suffix in ["景区", "风景区", "风景名胜区", "公园", "森林公园", "地质公园",
                           "湿地公园", "博物院", "博物馆", "纪念馆", "遗址公园", "古镇",
                           "古城", "古村", "主题公园", "游乐园", "度假区"]:
                if base_name.endswith(suffix):
                    base_name = base_name[:-len(suffix)]
                    break
            large_scenic_base_names.add(base_name)

    if not large_scenics_in_pool:
        return attrs

    before_count = len(attrs)

    # 2. 过滤掉景区内小景点（is_scenic_inner=True 且 parent_scenic 匹配大型景区基础名称）
    # 【P0-2 保护景点不被过滤】保护景点（必打卡/主要景点/用户指定）不参与此过滤
    attrs = [
        p for p in attrs
        if p.get("is_protected") or not (p.get("is_scenic_inner") and p.get("parent_scenic") in large_scenic_base_names)
    ]

    # 3. 同时过滤掉名称包含大型景区基础名称的小景点（如"大明湖超然楼"包含"大明湖"）
    # 【P0-2 保护景点不被过滤】保护景点不参与此过滤
    attrs = [
        p for p in attrs
        if p.get("is_protected") or not any(
            base_name in p.get("name", "")
            and p.get("name", "") not in large_scenics_in_pool
            and not is_large_scenic_area(p.get("name", ""), p.get("category", "") or p.get("type", ""))
            for base_name in large_scenic_base_names
        )
    ]

    removed_count = before_count - len(attrs)
    if removed_count > 0:
        _planner_logger.info("scenic_inner_dedup_unified", extra={"fields": {
            "request_id": request_id, "destination": destination,
            "before_count": before_count, "after_count": len(attrs),
            "removed_count": removed_count,
            "large_scenics": list(large_scenics_in_pool),
            "base_names": list(large_scenic_base_names),
        }})

    return attrs


# ============================================================================
# 阶段四：全量候选池构建（优化后）
# 本阶段唯一职责：构建全量候选池，做到"有数据可选"，不做任何筛选和排除。
# 合并原步骤12（通用POI）、13（扩大搜索）、14（行政分级枚举）、
#         15（主要景点注入）、16（必打卡注入）为一次全量检索+统一注入。
# ============================================================================

async def _build_full_candidate_pool(
    request_id: str,
    destination: str,
    poi_search_city: str,
    center: dict,
    geo: dict,
    exclude_poi: List[str] = None,
) -> tuple:
    """
    构建全量候选池（景点+辅助POI）。

    本阶段只负责增加候选池数量，不做任何筛选和排除。
    返回：(attrs候选景点列表, aux_pois辅助POI列表, weather天气数据)

    数据来源优先级：
    1. 数据库POI缓存表（poi_cache）
    2. TTL缓存（1天）
    3. 腾讯地图POI搜索API（翻页5页）
    4. 高德地图POI搜索API
    5. 主要景点库（major_attractions表，472个）
    6. 必打卡地标库（must_visit_landmarks表）
    """
    exclude_poi = exclude_poi or []

    # 4.1 全量POI检索（合并原步骤12、13、14）
    # 一次性检索所有类别（景点/美食/购物/夜生活）和所有行政级别
    _planner_logger.info("candidate_pool_build_start", extra={"fields": {
        "request_id": request_id,
        "destination": destination,
        "search_city": poi_search_city,
    }})

    # 4.1.1 通用POI检索（景点+美食+购物+夜生活）
    all_pois = await amap.search_pois(poi_search_city, center, ["景点", "美食", "购物", "夜生活"])

    # 4.1.2 POI数量不足时扩大搜索到所属地级市（原步骤13）
    if len(all_pois) < 10:
        _planner_logger.info("candidate_pool_expand_search", extra={"fields": {
            "request_id": request_id,
            "current_count": len(all_pois),
            "reason": "POI数量不足，扩大搜索到所属地级市",
        }})
        try:
            parent_city = geo.get("parent") or geo.get("cityname") or ""
            is_county = any(suffix in poi_search_city for suffix in ["县", "区", "旗"])
            if is_county and parent_city and parent_city != poi_search_city:
                parent_pois = await amap.search_pois(parent_city, center, ["景点", "美食", "购物", "夜生活"])
                if parent_pois:
                    existing_names = {p.get("name", "") for p in all_pois}
                    for p in parent_pois:
                        name = p.get("name", "")
                        if name and name not in existing_names:
                            all_pois.append(p)
                            existing_names.add(name)
                    _planner_logger.info("candidate_pool_expand_done", extra={"fields": {
                        "request_id": request_id,
                        "parent_city": parent_city,
                        "added_count": len(parent_pois),
                        "total_count": len(all_pois),
                    }})
        except Exception as e:
            _planner_logger.warning("candidate_pool_expand_failed", extra={"fields": {
                "request_id": request_id, "error": str(e),
            }})

    # 4.1.3 兜底POI（如果完全没有POI数据）
    if not all_pois:
        all_pois = _fallback_pois(center, destination)

    # 4.1.4 行政分级枚举景点（原步骤14，区/县→市→省）
    scoped_attrs = await _enumerate_scoped_attractions(geo, center)

    # 4.1.5 合并通用POI中的景点和行政分级枚举景点
    # 从all_pois中提取景点类POI
    attraction_pois = [p for p in all_pois if p.get("category") == "景点"]
    # 从all_pois中提取辅助POI（美食/购物/夜生活）
    aux_pois = [p for p in all_pois if p.get("category") in ("美食", "购物", "夜生活")]

    # 合并景点候选池
    attrs = []
    seen_names = set()
    for p in scoped_attrs + attraction_pois:
        name = p.get("name", "")
        if name and name not in seen_names:
            attrs.append(p)
            seen_names.add(name)

    _planner_logger.info("candidate_pool_after_poi_search", extra={"fields": {
        "request_id": request_id,
        "attraction_count": len(attrs),
        "aux_poi_count": len(aux_pois),
        "total_poi_count": len(all_pois),
    }})
    _log_poi_pool("全量POI检索后", request_id, destination, attrs)

    # 4.2 主要景点库注入（原步骤15，明确职责：候选池增强，确保知名景点在候选池中）
    try:
        major_service = get_major_attractions_service()
        major_count_before = len(attrs)
        attrs = await major_service.merge_with_poi_data(poi_search_city, attrs)
        major_added = len(attrs) - major_count_before
        if major_added > 0:
            _planner_logger.info("candidate_pool_major_injected", extra={"fields": {
                "request_id": request_id,
                "destination": destination,
                "city": poi_search_city,
                "major_added": major_added,
                "total_after": len(attrs),
                "role": "候选池增强，确保知名景点在候选池中",
            }})
        _log_poi_pool("主要景点注入后", request_id, destination, attrs)
    except Exception as e:
        _planner_logger.warning("candidate_pool_major_inject_failed", extra={"fields": {
            "request_id": request_id, "error": str(e),
        }})

    # 4.3 必打卡地标注入（原步骤16，明确职责：提供强制规划锚点，在阶段五标记保护）
    attrs = await _inject_must_visit_attrs(destination, attrs)
    _planner_logger.info("candidate_pool_must_visit_injected", extra={"fields": {
        "request_id": request_id,
        "destination": destination,
        "total_after": len(attrs),
        "role": "强制规划锚点，在阶段五标记保护",
    }})
    _log_poi_pool("必打卡注入后", request_id, destination, attrs)

    # 4.4 候选池基础去重（新增：在候选池构建阶段就做一次基础去重，减少后续处理量）
    try:
        from ...utils.poi_deduplicator import deduplicate_pois
        before_count = len(attrs)
        attrs, removed_duplicates = deduplicate_pois(attrs)
        if removed_duplicates:
            _planner_logger.info("candidate_pool_basic_dedup", extra={"fields": {
                "request_id": request_id,
                "before_count": before_count,
                "after_count": len(attrs),
                "removed_count": len(removed_duplicates),
            }})
    except Exception as e:
        _planner_logger.warning("candidate_pool_basic_dedup_failed", extra={"fields": {
            "request_id": request_id, "error": str(e),
        }})
    _log_poi_pool("候选池基础去重后", request_id, destination, attrs)

    # 4.5 排除规则应用（原步骤17，顺序调整：候选池构建完成后统一应用）
    if exclude_poi:
        exclude_names = {n.strip() for n in exclude_poi if n.strip()}
        before_count = len(attrs)
        attrs = [p for p in attrs if p["name"] not in exclude_names]
        aux_pois = [p for p in aux_pois if p["name"] not in exclude_names]
        _planner_logger.info("candidate_pool_exclude_applied", extra={"fields": {
            "request_id": request_id,
            "exclude_count": len(exclude_names),
            "attrs_before": before_count,
            "attrs_after": len(attrs),
            "aux_after": len(aux_pois),
        }})
        _log_poi_pool("排除规则后", request_id, destination, attrs)

    # 4.6 天气查询（原步骤3，移到候选池构建阶段）
    weather = await amap.weather(poi_search_city, geo.get("adcode", ""))

    _planner_logger.info("candidate_pool_build_complete", extra={"fields": {
        "request_id": request_id,
        "destination": destination,
        "final_attraction_count": len(attrs),
        "final_aux_poi_count": len(aux_pois),
        "weather_available": bool(weather and weather.get("weather")),
    }})

    return attrs, aux_pois, weather


# ============================================================================
# 阶段五：必要景点保护与关联景点处理（P0-3 主POI/子POI统一处理）
# 本阶段核心：确保必要景点不被过滤，处理主POI和子POI的关联关系。
# 整合原步骤19（大型景区识别）、23（景区去重）、24（统一景区去重）为一个函数。
# ============================================================================

def _process_scenic_hierarchy(
    attrs: List[dict],
    request_id: str = "",
    destination: str = "",
) -> List[dict]:
    """
    统一的主POI/子POI层级处理函数（P0-3）。

    整合大型景区识别、主POI/子POI关联处理、主POI/子POI去重为一个函数。

    处理规则：
    1. 识别大型景区（如大明湖、西湖、故宫），标记景区内小景点
    2. 建立主景区和子景点的关联关系
    3. 如果主景区在候选池中，子景点只作为点位信息，不单独参与路径规划
    4. 如果主景区不在候选池中，子景点可以单独参与
    5. 【P0-2 保护景点不被过滤】保护景点（必打卡/主要景点/用户指定）不参与景区内小景点过滤

    Args:
        attrs: 候选景点列表
        request_id: 请求ID（用于日志）
        destination: 目的地（用于日志）

    Returns:
        处理后的景点列表
    """
    if not attrs:
        return attrs

    # 1. 大型景区识别与权重调整
    #    大型景区（如大明湖、西湖、故宫）作为整体规划点位，
    #    景区内的小景点（如大明湖超然楼）优先级降低，不单独参与跨景区路径规划
    for p in attrs:
        name = p.get("name", "")
        category = p.get("category", "") or p.get("type", "")
        weight_factor = get_scenic_area_weight_factor(name, category)
        p["scenic_weight_factor"] = weight_factor
        is_inner, parent_scenic = is_inside_large_scenic_area(name, category)
        if is_inner:
            p["is_scenic_inner"] = True
            p["parent_scenic"] = parent_scenic
        else:
            p["is_scenic_inner"] = False
            p["parent_scenic"] = ""

    # 统计：景区内小景点数量
    inner_count = sum(1 for p in attrs if p.get("is_scenic_inner"))
    if inner_count > 0:
        _planner_logger.info("scenic_inner_detected", extra={"fields": {
            "request_id": request_id, "destination": destination,
            "total_attrs": len(attrs), "inner_count": inner_count,
        }})

    # 2. 统一的大型景区与景区内小景点去重
    #    如果大型景区本身已在候选池中，则过滤掉该景区内的小景点，避免重复规划
    #    【P0-2 保护景点不被过滤】保护景点不参与此过滤
    attrs = dedup_scenic_inner_pois(attrs, request_id, destination)

    # 3. 主POI/子POI关联关系建立（日志记录）
    large_scenics = [p for p in attrs if is_large_scenic_area(p.get("name", ""), p.get("category", "") or p.get("type", ""))]
    inner_pois = [p for p in attrs if p.get("is_scenic_inner")]
    if large_scenics or inner_pois:
        _planner_logger.info("scenic_hierarchy_processed", extra={"fields": {
            "request_id": request_id, "destination": destination,
            "large_scenic_count": len(large_scenics),
            "large_scenic_names": [p.get("name", "") for p in large_scenics],
            "inner_poi_count": len(inner_pois),
            "inner_poi_names": [p.get("name", "") for p in inner_pois],
            "final_count": len(attrs),
        }})

    return attrs


async def _llm_check_outside_china(destination: str) -> bool:
    """
    使用LLM判断目的地是否位于中国境外。
    
    当地理编码失败时，使用LLM进行判断，避免对明显的境外地名（如北极、东京、纽约等）
    返回"无法识别目的地"的提示，而是返回"中国境外"的提示。
    
    Args:
        destination: 目的地名称
        
    Returns:
        bool: 是否位于中国境外（True=境外，False=境内或判断失败）
    """
    try:
        system_prompt = """你是一个地理知识专家，负责判断用户输入的目的地是否位于中国境外。

【判断规则】
1. 中国境内：包括中国大陆、香港、澳门、台湾，以及中国的各个省、市、区县、景点
2. 中国境外：其他国家、地区、城市、景点，以及明显的地理区域（如北极、南极、欧洲、美洲等）
3. 如果不确定，返回"否"（默认认为是中国境内）

【输出格式】
只返回JSON格式，不要输出任何其他内容：
{"is_outside_china": true/false, "reason": "简要说明判断理由"}

【示例】
- "北极" → {"is_outside_china": true, "reason": "北极是地球北端的地理区域，不属于中国"}
- "东京" → {"is_outside_china": true, "reason": "东京是日本的首都，位于中国境外"}
- "杭州" → {"is_outside_china": false, "reason": "杭州是中国浙江省的省会城市"}
- "西湖" → {"is_outside_china": false, "reason": "西湖位于中国浙江省杭州市"}
"""
        
        user_prompt = f"请判断以下目的地是否位于中国境外：\n\n目的地：{destination}"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        
        content = await ai_mod.chat_completion(
            messages=messages,
            temperature=0.1,
            max_tokens=512,
        )
        
        if not content:
            _planner_logger.warning("llm_check_outside_china_empty", extra={"fields": {
                "destination": destination,
            }})
            return False
        
        # 解析JSON结果
        import json
        import re
        # 提取JSON部分
        json_match = re.search(r'\{[^{}]*\}', content)
        if json_match:
            result = json.loads(json_match.group())
            is_outside = result.get("is_outside_china", False)
            reason = result.get("reason", "")
            _planner_logger.info("llm_check_outside_china_result", extra={"fields": {
                "destination": destination,
                "is_outside_china": is_outside,
                "reason": reason,
            }})
            return bool(is_outside)
        
        _planner_logger.warning("llm_check_outside_china_parse_failed", extra={"fields": {
            "destination": destination,
            "content": content[:200],
        }})
        return False
        
    except Exception as e:
        _planner_logger.warning("llm_check_outside_china_failed", extra={"fields": {
            "destination": destination,
            "error": str(e),
        }})
        return False


async def build_plan(req: PlanRequest) -> PlanResponse:
    request_id = uuid.uuid4().hex[:12]
    start = time.time()
    destination = req.destination.strip()

    # 0) 规则引擎：参数规范化（兜底和收束）
    rule_engine = get_rule_engine()
    original_days = req.days
    original_travelers = req.travelers
    normalized_params = rule_engine.normalize_params(req.model_dump())
    req.days = normalized_params['days']
    req.travelers = normalized_params['travelers']
    req.budget_level = normalized_params['budget_level']
    req.group_type = normalized_params['group_type']
    req.pace = normalized_params['pace']
    req.traffic_mode = normalized_params['traffic_mode']

    if req.days != original_days or req.travelers != original_travelers:
        _planner_logger.info("params_normalized", extra={"fields": {
            "request_id": request_id,
            "original_days": original_days, "normalized_days": req.days,
            "original_travelers": original_travelers, "normalized_travelers": req.travelers,
        }})

    # 0.5) 多策略规划：根据style参数选择对应的规划策略
    #      8种策略：classic(经典打卡)/deep(深度体验)/leisure(休闲度假)/family(亲子友好)
    #               couple(情侣浪漫)/photography(摄影之旅)/food(美食之旅)/culture(历史文化)
    try:
        from .strategy import get_strategy_by_style, get_strategy_config, apply_strategy_to_params
        strategy_key = get_strategy_by_style(req.style or "综合")
        strategy_config = get_strategy_config(strategy_key)
        # 将策略配置应用到请求参数中
        strategy_params = apply_strategy_to_params(req.model_dump(), strategy_key)
        # 更新请求参数中的策略相关字段
        req.daily_start_time = strategy_params.get("start_time", req.daily_start_time)
        _planner_logger.info("strategy_applied", extra={"fields": {
            "request_id": request_id,
            "style": req.style,
            "strategy": strategy_key,
            "strategy_name": strategy_config.get("name", ""),
            "items_per_day": strategy_params.get("items_per_day", 4),
            "poi_ratio": strategy_params.get("poi_ratio", {}),
            "must_visit_priority": strategy_params.get("must_visit_priority", 1.0),
            "start_time": strategy_params.get("start_time", "08:30"),
            "end_time": strategy_params.get("end_time", "20:00"),
            "tags_preference": strategy_params.get("tags_preference", []),
        }})
    except Exception as e:
        _planner_logger.warning("strategy_apply_failed", extra={"fields": {
            "request_id": request_id, "error": str(e),
        }})
        strategy_key = "classic"
        strategy_config = get_strategy_config("classic")

    _planner_logger.info("plan_start", extra={"fields": {
        "request_id": request_id, "destination": destination, "days": req.days,
        "travelers": req.travelers, "group_type": req.group_type,
        "budget_level": req.budget_level, "style": req.style, "pace": req.pace,
        "traffic_mode": req.traffic_mode,
    }})

    # 1) 定位城市中心
    geo = await amap.geocode(destination)
    if not geo:
        # 地理编码失败时，使用LLM判断是否为中国境外目的地
        is_outside_china = await _llm_check_outside_china(destination)
        if is_outside_china:
            _planner_logger.warning("plan_rejected_outside_china_llm", extra={"fields": {
                "request_id": request_id, "destination": destination,
            }})
            return PlanResponse(
                request_id=request_id, destination=destination,
                city_center={"lng": 0, "lat": 0},
                days=0, origin=req.origin, travelers=req.travelers,
                return_point=req.return_point, group_type=req.group_type,
                budget_level=req.budget_level, style=req.style, pace=req.pace,
                traffic_mode=req.traffic_mode, daily_start_time=req.daily_start_time,
                ai_model="(规则引擎)", source="rejected",
                weather={}, departure_message=f"抱歉，「{destination}」位于中国境外，当前暂不支持中国以外目的地的行程规划。我们的足迹先从祖国的大好河山开始吧～",
                day_plans=[], all_pois=[], total_budget=0, budget_breakdown={},
                generated_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )
        
        _planner_logger.warning("plan_rejected_unknown_destination", extra={"fields": {
            "request_id": request_id, "destination": destination,
        }})
        return PlanResponse(
            request_id=request_id, destination=destination,
            city_center={"lng": 0, "lat": 0},
            days=0, origin=req.origin, travelers=req.travelers,
            return_point=req.return_point, group_type=req.group_type,
            budget_level=req.budget_level, style=req.style, pace=req.pace,
            traffic_mode=req.traffic_mode, daily_start_time=req.daily_start_time,
            ai_model="(规则引擎)", source="rejected",
            weather={}, departure_message=f"抱歉，无法识别目的地「{destination}」，请检查地名是否正确，或尝试更具体的地址（如「杭州市西湖区」）。",
            day_plans=[], all_pois=[], total_budget=0, budget_breakdown={},
            generated_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
    center = {"lng": geo["lng"], "lat": geo["lat"]}

    # P2-2 中国区域校验提前：在行政区域补全之前进行中国区域校验
    # 仅规划中国境内目的地，避免对境外目的地进行不必要的行政区域补全和POI搜索
    if not _is_in_china(geo):
        _planner_logger.warning("plan_rejected_outside_china", extra={"fields": {
            "request_id": request_id, "destination": destination,
            "lng": geo.get("lng"), "lat": geo.get("lat"),
            "source": geo.get("source"), "province": geo.get("province", ""),
        }})
        return PlanResponse(
            request_id=request_id, destination=destination, city_center={"lng": center.get("lng", 0.0), "lat": center.get("lat", 0.0)},
            days=0, origin=req.origin, travelers=req.travelers,
            return_point=req.return_point, group_type=req.group_type,
            budget_level=req.budget_level, style=req.style, pace=req.pace,
            traffic_mode=req.traffic_mode, daily_start_time=req.daily_start_time,
            ai_model="(规则引擎)", source="rejected",
            weather={}, departure_message=f"抱歉，「{destination}」位于中国境外，当前暂不支持中国以外目的地的行程规划。我们的足迹先从祖国的大好河山开始吧～",
            day_plans=[], all_pois=[], total_budget=0, budget_breakdown={},
            generated_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

    # 1.2) 行政区域补全：在POI搜索前完成目的地的行政区域补全
    # 如果用户输入的是具体景点（如"大明湖"），则获取其所属的城市名，用城市名进行POI搜索
    # 这样可以确保POI搜索的数据更可靠，避免因为景点名导致搜索范围不准确
    poi_search_city = destination
    poi_search_province = geo.get("province", "") or ""
    poi_search_district = geo.get("district", "") or ""
    geo_level = geo.get("level", "") or ""
    
    # 判断目的地是否为具体景点（非行政区域级别）
    is_specific_poi = geo_level in ["景点", "兴趣点", "POI", "poi"] or (
        geo_level == "" and geo.get("source") == "famous_landmark"
    )
    
    if is_specific_poi:
        # 如果是具体景点，使用其所属的城市名进行POI搜索
        if geo.get("city") and geo["city"] != destination:
            poi_search_city = geo["city"]
            _planner_logger.info("poi_search_city_resolved", extra={"fields": {
                "request_id": request_id,
                "original_destination": destination,
                "resolved_city": poi_search_city,
                "province": poi_search_province,
                "district": poi_search_district,
                "geo_level": geo_level,
                "reason": "目的地为具体景点，使用所属城市进行POI搜索",
            }})
    else:
        # 如果是行政区域级别，确保城市名包含完整的行政区域信息
        if geo.get("city") and geo["city"] != destination:
            # 如果地理编码返回的城市名与用户输入不同，使用地理编码返回的城市名
            poi_search_city = geo["city"]
    
    # 确保center对象包含行政区域信息，供search_pois函数使用
    if poi_search_province:
        center["province"] = poi_search_province
    if poi_search_district:
        center["district"] = poi_search_district
    if poi_search_city:
        center["city"] = poi_search_city

    # 2) 全量候选池构建（优化后：合并原步骤12、13、14、15、16、17为一次全量检索+统一注入）
    #    本阶段唯一职责：构建全量候选池，做到"有数据可选"，不做任何筛选和排除。
    #    返回：attrs候选景点列表, aux_pois辅助POI列表（美食/购物/夜生活）, weather天气数据
    attrs, aux_pois, weather = await _build_full_candidate_pool(
        request_id=request_id,
        destination=destination,
        poi_search_city=poi_search_city,
        center=center,
        geo=geo,
        exclude_poi=req.exclude_poi,
    )
    # 兼容原有代码：pois变量指向辅助POI列表
    pois = aux_pois

    # 2.5) 在线数据增强：从在线数据中获取目的地的攻略、预约规则、避坑提示
    #      将在线数据的景点合并到候选池中，确保热门景点不被遗漏
    online_data_context = None
    try:
        from ...services.online_data import get_online_data_enhancer
        enhancer = get_online_data_enhancer()
        if enhancer.ENABLED:
            # 加载在线数据（默认不启用在线搜索，使用数据库缓存数据）
            online_data_context = await enhancer.load_online_data(
                destination=poi_search_city,
                days=req.days,
                enable_search=False,  # 默认关闭在线搜索，使用数据库缓存
            )

            if online_data_context and online_data_context.is_loaded:
                # 增强POI列表：合并在线数据中的景点
                original_count = len(attrs)
                attrs = enhancer.enhance_poi_list(attrs, online_data_context)

                if len(attrs) > original_count:
                    _planner_logger.info("online_data_poi_enhanced", extra={"fields": {
                        "request_id": request_id,
                        "destination": destination,
                        "original_count": original_count,
                        "enhanced_count": len(attrs),
                        "added_count": len(attrs) - original_count,
                        "online_confidence": online_data_context.confidence,
                        "attraction_rules_count": len(online_data_context.attraction_rules),
                        "travel_tips_count": len(online_data_context.travel_tips),
                    }})
    except Exception as e:
        _planner_logger.warning("online_data_enhance_failed", extra={"fields": {
            "request_id": request_id,
            "destination": destination,
            "error": str(e),
        }})
        online_data_context = None

    # 4.1) 必要景点保护机制（新增P0-2）
    #    标记必打卡景点和用户指定景点为"保护景点"，在后续所有筛选中不被过滤。
    #    保护景点类型：
    #    - must_visit=True：必打卡地标（从must_visit_landmarks库注入）
    #    - major_attraction=True：主要景点库中的景点（从major_attractions库注入）
    #    - user_must_include=True：用户在must_include_poi参数中指定的景点
    protected_count = 0
    must_include_names = {n.strip() for n in (req.must_include_poi or []) if n.strip()}
    for p in attrs:
        is_protected = False
        protect_reasons = []

        # 必打卡地标保护（按优先级分级）
        # P0（priority=1，顶级地标）：必须安排，标记为is_protected
        # P1（priority=2，重要景点）：优先安排，标记为is_protected
        # P2（priority=3，推荐景点）：时间充裕时安排，不标记为is_protected
        if p.get("must_visit") or p.get("is_must_visit"):
            must_priority = int(p.get("must_visit_priority", 2))
            if must_priority <= 2:  # P0和P1级别的必去景点受保护
                is_protected = True
                protect_reasons.append(f"must_visit_P{must_priority}")
            else:
                # P2级别的必去景点不受保护，但记录优先级
                p["must_visit_priority"] = must_priority

        # 主要景点库保护
        if p.get("source") == "major_attraction" or p.get("is_major_attraction"):
            is_protected = True
            protect_reasons.append("major_attraction")

        # 用户指定必去景点保护
        pname = p.get("name", "")
        if must_include_names and any(mn in pname or pname in mn for mn in must_include_names):
            is_protected = True
            protect_reasons.append("user_must_include")
            p["user_must_include"] = True

        if is_protected:
            p["is_protected"] = True
            p["protect_reasons"] = protect_reasons
            protected_count += 1
        else:
            p["is_protected"] = False
            p["protect_reasons"] = []

    _planner_logger.info("protected_attractions_marked", extra={"fields": {
        "request_id": request_id,
        "destination": destination,
        "total_attrs": len(attrs),
        "protected_count": protected_count,
        "must_include_count": len(must_include_names),
        "protected_names": [p.get("name", "") for p in attrs if p.get("is_protected")][:10],
    }})
    _log_poi_pool("保护景点标记后", request_id, destination, attrs)

    # P2-3 筛选顺序优化：明确6步筛选顺序，确保必要景点不被过滤
    # 筛选顺序：1.人群评分 → 2.时间收束 → 3.LLM筛选 → 4.不足补充 → 5.辅助POI限制 → 6.地理聚类
    # 核心原则：先做评分和收束，再做LLM智能筛选，不足时补充，最后限制辅助POI占比和地理聚类
    # 保护景点（is_protected=True）在所有筛选步骤中都不被过滤
    _planner_logger.info("filter_pipeline_start", extra={"fields": {
        "request_id": request_id,
        "destination": destination,
        "candidate_count": len(attrs),
        "protected_count": sum(1 for p in attrs if p.get("is_protected")),
        "filter_order": ["1.人群评分", "2.时间收束", "3.LLM筛选", "4.不足补充", "5.辅助POI限制", "6.地理聚类"],
    }})

    # 筛选步骤1：人群评分（标记人群友好属性，调整评分）
    # 4.15) 规则引擎：人群影响规则应用
    #      按人群类型筛选和排序景点：
    #      - 亲子：亲子友好景点优先，主要景点60% + 辅助景点40%
    #      - 老人：老人友好景点优先，主要景点90% + 辅助景点10%
    #      - 情侣：浪漫/网红景点优先，主要景点80% + 辅助景点20%
    #      - 朋友：网红/夜生活/美食景点优先，主要景点70% + 辅助景点30%
    #      - 单人：小众/个性化景点优先，主要景点90% + 辅助景点10%
    #      - 家庭：全家友好景点优先，主要景点85% + 辅助景点15%
    try:
        group_type = req.group_type or '单人'
        group_config = rule_engine.group_engine.get_group_config(group_type)
        if group_config and attrs:
            # 标记景点的人群友好属性
            for p in attrs:
                # 使用正确的方法签名：接受poi dict参数
                p['is_family_friendly'] = rule_engine.group_engine.is_family_friendly(p)
                p['is_elderly_friendly'] = rule_engine.group_engine.is_elderly_friendly(p)
                # 简单判断情侣/朋友/单人友好属性
                name = p.get('name', '')
                category = p.get('category', '') or p.get('type', '')
                p['is_couple_friendly'] = any(kw in name + category for kw in ['浪漫', '网红', '夜景', '摩天轮', '湖边', '咖啡馆', '情侣'])
                p['is_friend_friendly'] = any(kw in name + category for kw in ['网红', '夜生活', '美食', '酒吧', '购物', '朋友'])
                p['is_solo_friendly'] = any(kw in name + category for kw in ['小众', '文艺', '书店', '博物馆', '咖啡馆', '徒步'])

            # 按人群类型调整景点评分（人群友好的景点评分提升）
            group_score_boost = {
                '亲子': 'is_family_friendly',
                '老人': 'is_elderly_friendly',
                '情侣': 'is_couple_friendly',
                '朋友': 'is_friend_friendly',
                '单人': 'is_solo_friendly',
                '家庭': 'is_family_friendly',
            }
            boost_field = group_score_boost.get(group_type, 'is_family_friendly')
            for p in attrs:
                if p.get(boost_field):
                    original_rating = float(p.get('rating', 0) or 0)
                    p['original_rating'] = original_rating
                    p['rating'] = min(5.0, original_rating + 0.3)  # 人群友好景点评分+0.3

            # 统计人群友好景点数量
            friendly_count = sum(1 for p in attrs if p.get(boost_field))
            _planner_logger.info("group_influence_applied", extra={"fields": {
                "request_id": request_id, "destination": destination,
                "group_type": group_type,
                "total_attrs": len(attrs),
                "friendly_count": friendly_count,
                "main_poi_ratio": group_config.get('main_poi_ratio', 0.8),
                "aux_poi_ratio": group_config.get('aux_poi_ratio', 0.2),
                "default_pace": group_config.get('default_pace', '适中'),
            }})
            _log_poi_pool("人群影响后", request_id, destination, attrs)
    except Exception as e:
        _planner_logger.warning("group_influence_failed", extra={"fields": {
            "request_id": request_id, "destination": destination,
            "error": str(e),
        }})

    # 4.2) 主POI/子POI统一层级处理（P0-3，整合原步骤19、23、24）
    #    统一完成：大型景区识别、主POI/子POI关联处理、主POI/子POI去重
    #    【P0-2 保护景点不被过滤】保护景点在函数内部不参与景区内小景点过滤
    attrs = _process_scenic_hierarchy(attrs, request_id, destination)
    _log_poi_pool("主POI/子POI层级处理后", request_id, destination, attrs)

    # 4.5) 时间跨度合理性收束：
    #      - 省级目的地：按实际可支撑的城市数上限收束天数（不同城市分配不同天数）
    #      - 市级/区级/地点级目的地：不限制天数，同一个城市可以规划多天，
    #        由后续的逐日构建和补齐机制（_ensure_days）来保证天数充足
    #      年/月/日维度的归一化与 15 天上限已在意图层完成，这里按资源再收一次。
    is_prov = _is_province(geo)
    if attrs and is_prov:
        n_cities = len({(p.get("cityname") or "").replace("市", "").strip()
                         for p in attrs if p.get("cityname")}) or 1
        if req.days > n_cities:
            _planner_logger.info("days_truncated_by_cities", extra={"fields": {
                "request_id": request_id, "destination": destination,
                "original_days": req.days, "truncated_days": n_cities,
                "reason": "省级目的地按城市数量收束天数",
            }})
            req.days = n_cities

    # 4.8) LLM 智能优化：POI 筛选 + 主题分组 + 建议时长（LLM 做决策，规则做执行）
    _log_poi_pool("LLM优化前", request_id, destination, attrs)
    llm_optimized = None
    # 【优化】候选景点少于10个时跳过LLM优化，直接用规则引擎，减少token消耗
    if ai_mod.ai_available() and attrs and len(attrs) >= 10:
        llm_optimized = await ai_mod.optimize_itinerary(req.model_dump(), attrs)
        if llm_optimized:
            # 输出LLM给出的规划结果，便于排查
            _planner_logger.info("llm_optimize_raw_result", extra={"fields": {
                "request_id": request_id, "destination": destination,
                "llm_selected_count": len(llm_optimized),
                "llm_selected": [{"name": item.get("name"), "duration_min": item.get("duration_min"),
                                   "theme": item.get("theme"), "best_slot": item.get("best_slot"),
                                   "reason": item.get("reason", "")} for item in llm_optimized],
            }})
            selected_names = {item["name"] for item in llm_optimized}
            opt_by_name = {item["name"]: item for item in llm_optimized}
            # 第一部分：LLM 选中的景点（注入优化字段，优先规划）
            selected = []
            for p in attrs:
                if p["name"] in selected_names:
                    opt = opt_by_name[p["name"]]
                    p["llm_duration"] = opt["duration_min"]
                    p["llm_theme"] = opt["theme"]
                    p["llm_best_slot"] = opt["best_slot"]
                    p["llm_reason"] = opt.get("reason", "")
                    selected.append(p)

            # 【P0-2 保护景点强制保留】将保护景点（必打卡/主要景点/用户指定）强制加入selected列表
            # 保护景点不依赖LLM是否选中，确保在后续规划中一定存在
            protected_not_selected = [p for p in attrs if p.get("is_protected") and p["name"] not in selected_names]
            if protected_not_selected:
                _planner_logger.info("protected_attractions_forced_keep", extra={"fields": {
                    "request_id": request_id,
                    "destination": destination,
                    "forced_count": len(protected_not_selected),
                    "forced_names": [p.get("name", "") for p in protected_not_selected],
                    "reasons": [p.get("protect_reasons", []) for p in protected_not_selected],
                }})
                selected.extend(protected_not_selected)

            # 第二部分：如果 LLM 选中的不足，从 hot 景点中补充（按评分排序，不注入优化字段）
            # 优化：优先选择非景区内小景点，景区内小景点（如大明湖超然楼）优先级降低
            min_needed = req.days * 2
            max_total = req.days * 5
            if len(selected) < min_needed:
                used_ids = {p["id"] for p in selected}
                supplements = [p for p in attrs if p.get("hot") and p["id"] not in used_ids]
                # 排序优先级：1. 保护景点优先 2. 非景区内小景点优先 3. 评分高优先
                supplements.sort(key=lambda x: (
                    not x.get("is_protected", False),  # 保护景点优先（False=0在前）
                    x.get("is_scenic_inner", False),  # False(0) 在前，True(1) 在后
                    -float(x.get("rating", 0) or 0),
                    -x.get("scenic_weight_factor", 1.0),
                ))
                selected.extend(supplements[:min_needed - len(selected)])
            # 总数控制（【P0-2】保护景点不被截断，先保留保护景点，再截断非保护景点）
            protected_in_selected = [p for p in selected if p.get("is_protected")]
            non_protected_in_selected = [p for p in selected if not p.get("is_protected")]
            if len(selected) > max_total:
                # 保护景点全部保留，非保护景点按评分排序后截断
                non_protected_in_selected.sort(key=lambda x: -float(x.get("rating", 0) or 0))
                filtered_attrs = protected_in_selected + non_protected_in_selected[:max_total - len(protected_in_selected)]
            else:
                filtered_attrs = selected
            if len(filtered_attrs) >= min_needed:
                # 大型景区与景区内小景点去重：
                # 如果大型景区本身已被选中（如"大明湖景区"），则过滤掉该景区内的小景点（如"大明湖超然楼"）
                selected_large_scenics = set()
                for p in filtered_attrs:
                    if is_large_scenic_area(p.get("name", ""), p.get("category", "") or p.get("type", "")):
                        selected_large_scenics.add(p["name"])
                # 也检查名称包含大型景区名的情况（如"大明湖景区"包含"大明湖"）
                for large_name in list(selected_large_scenics):
                    for p in filtered_attrs:
                        pname = p.get("name", "")
                        if large_name in pname and pname != large_name:
                            selected_large_scenics.add(large_name)
                # 过滤掉已选中大型景区内的小景点
                # 【P0-2 保护景点不被过滤】保护景点（必打卡/主要景点/用户指定）不参与景区内小景点过滤
                before_count = len(filtered_attrs)
                filtered_attrs = [
                    p for p in filtered_attrs
                    if p.get("is_protected") or not (p.get("is_scenic_inner") and p.get("parent_scenic") in selected_large_scenics)
                ]
                # 同时过滤掉名称包含已选中大型景区名的小景点（如"大明湖超然楼"包含"大明湖"）
                # 【P0-2 保护景点不被过滤】保护景点不参与此过滤
                filtered_attrs = [
                    p for p in filtered_attrs
                    if p.get("is_protected") or not any(
                        large_name in p.get("name", "") and p.get("name", "") != large_name
                        for large_name in selected_large_scenics
                    )
                ]
                removed_count = before_count - len(filtered_attrs)
                if removed_count > 0:
                    _planner_logger.info("scenic_inner_dedup", extra={"fields": {
                        "request_id": request_id, "destination": destination,
                        "before_count": before_count, "after_count": len(filtered_attrs),
                        "removed_count": removed_count,
                        "selected_large_scenics": list(selected_large_scenics),
                    }})
                _planner_logger.info("llm_optimize_applied", extra={"fields": {
                    "request_id": request_id, "original_count": len(attrs),
                    "filtered_count": len(filtered_attrs),
                    "llm_selected": len(selected_names),
                    "themes": list({p.get("llm_theme", "") for p in filtered_attrs if p.get("llm_theme")}),
                }})
                attrs = filtered_attrs
                _log_poi_pool("LLM优化后", request_id, destination, attrs)
            else:
                _planner_logger.info("llm_optimize_skipped", extra={"fields": {
                    "request_id": request_id, "reason": "筛选后景点不足",
                    "filtered_count": len(filtered_attrs), "min_needed": min_needed,
                }})

    # 4.9) 统一的大型景区与景区内小景点去重（确保所有路径都生效）：
    #      如果大型景区本身已在候选池中，则过滤掉该景区内的小景点，避免重复规划
    attrs = dedup_scenic_inner_pois(attrs, request_id, destination)
    _log_poi_pool("统一去重后", request_id, destination, attrs)

    # 4.95) 通用POI去重（基于坐标+名称的智能去重，从根本上解决景点重复问题）：
    #       不依赖任何硬编码的别名映射，通过坐标距离、名称包含关系、名称相似度自动识别重复
    #       处理场景：
    #       1. 同一景区的不同命名（如"趵突泉景区"和"天下第一泉景区"距离只有78米）
    #       2. 主景区和子景点并存（如"大明湖景区"和"大明湖景区-超然楼"）
    #       3. 大景区包含子景区（如"千佛山风景名胜区"和"大千佛山景区佛慧山"）
    #       4. 同一景点的不同名称（如"黑虎泉"和"济南市环城公园-黑虎泉"）
    try:
        from ...utils.poi_deduplicator import deduplicate_pois
        before_count = len(attrs)
        attrs, removed_duplicates = deduplicate_pois(attrs)
        if removed_duplicates:
            _planner_logger.info("generic_poi_dedup", extra={"fields": {
                "request_id": request_id, "destination": destination,
                "before_count": before_count, "after_count": len(attrs),
                "removed_count": len(removed_duplicates),
                "removed_details": [{"removed": r["removed"], "kept": r["kept"], "reason": r["reason"][:100]} for r in removed_duplicates[:10]],
            }})
    except Exception as e:
        _planner_logger.warning("generic_poi_dedup_failed", extra={"fields": {
            "request_id": request_id, "destination": destination,
            "error": str(e),
        }})
    _log_poi_pool("通用去重后", request_id, destination, attrs)

    # 4.98) 美食/购物/夜生活占比限制：
    #       根据多策略规划配置调整点位类型比例，避免美食占比过高
    #       使用策略配置中的poi_ratio，支持8种策略的不同比例
    try:
        style = getattr(req, 'style', '综合') or '综合'
        # 使用多策略配置中的点位比例
        from .strategy import get_strategy_by_style, get_strategy_config
        strategy_key = get_strategy_by_style(style)
        strategy_config = get_strategy_config(strategy_key)
        strategy_ratio = strategy_config.get("poi_ratio", {
            "attraction": 0.60, "food": 0.30, "shopping": 0.05, "nightlife": 0.05
        })
        # 转换为统一格式（food包含美食+购物+夜生活）
        ratio = {
            'attraction': strategy_ratio.get('attraction', 0.60),
            'food': strategy_ratio.get('food', 0.20) + strategy_ratio.get('shopping', 0.05) + strategy_ratio.get('nightlife', 0.05),
            'other': 0.05,
        }

        # 分类统计
        attractions = [p for p in attrs if p.get('category') == '景点']
        foods = [p for p in attrs if p.get('category') in ('美食', '购物', '夜生活')]
        others = [p for p in attrs if p.get('category') not in ('景点', '美食', '购物', '夜生活')]

        total = len(attrs)
        if total > 0:
            # 计算各类别的最大数量
            max_food = max(2, int(total * ratio['food']))
            max_other = max(1, int(total * ratio['other']))

            # 如果美食超过限制，过滤掉评分较低的美食
            if len(foods) > max_food:
                # 过滤掉不适合作为主要推荐的美食（连锁快餐、饮品店等）
                bad_food_keywords = ['蜜雪冰城', '肯德基', '麦当劳', '星巴克', '瑞幸', '奶茶', '饮品', '快餐']
                good_foods = [p for p in foods if not any(kw in p.get('name', '') for kw in bad_food_keywords)]
                bad_foods = [p for p in foods if any(kw in p.get('name', '') for kw in bad_food_keywords)]

                # 优先保留好的美食，然后按评分排序
                foods_sorted = sorted(good_foods, key=lambda x: -float(x.get('rating', 0) or 0))
                kept_foods = foods_sorted[:max_food]

                # 过滤掉被移除的美食
                removed_foods = set(p['id'] for p in foods if p not in kept_foods)
                attrs = [p for p in attrs if p['id'] not in removed_foods]

                _planner_logger.info("food_ratio_limited", extra={"fields": {
                    "request_id": request_id, "destination": destination,
                    "style": style, "strategy": strategy_key,
                    "total_before": total, "total_after": len(attrs),
                    "food_before": len(foods), "food_after": len(kept_foods),
                    "removed_bad_foods": [p.get('name') for p in bad_foods[:5]],
                    "max_food_ratio": ratio['food'],
                }})
    except Exception as e:
        _planner_logger.warning("food_ratio_limit_failed", extra={"fields": {
            "request_id": request_id, "destination": destination, "error": str(e),
        }})
    _log_poi_pool("美食占比限制后", request_id, destination, attrs)

    # 5) 规则化地理规划：聚类成区域 → 短距同日 → 跨天不重复；美食/购物/夜生活只做就近辅助
    #    支持两种规划策略：
    #    - traditional（传统）：直接按天分配景点
    #    - spatial_temporal（两阶段）：先空间整体路线规划，再按时间拆分
    if getattr(req, 'plan_strategy', 'traditional') == 'spatial_temporal':
        _planner_logger.info("plan_strategy=spatial_temporal，使用两阶段规划（先空间整体路线，再时间拆分）")
        # 解析出发点和返程点
        origin_geo = None
        return_geo = None
        if req.origin:
            origin_geo = await amap.resolve_geo(req.origin)
        if req.return_point:
            return_geo = await amap.resolve_geo(req.return_point)
        day_plans, spatial_route, day_splits = await _spatial_temporal_plan(
            req, origin_geo, center, return_geo, attrs, pois
        )
        model_used = "(两阶段规划引擎)"
        source = "spatial_temporal"
        _planner_logger.info(f"两阶段规划完成：{spatial_route.route_summary}，拆分为{len(day_splits)}天")
    else:
        day_plans, model_used, source = await _geo_plan(req, center, pois, attrs, is_province=is_prov)

    if not day_plans:
        # 极端兜底：直接生成最简单的一天
        day_plans = await _emergency_plan(req, center, pois)

    # 6) 天数不足时用规则引擎补齐（候选池 = 景点 + 辅助池）
    # P1-3 辅助POI最后填充：排序确保景点优先、保护景点最优先、辅助POI最后
    all_candidates_raw = attrs + [p for p in pois if p["id"] not in {a["id"] for a in attrs}]
    # 排序优先级：1. 保护景点（必打卡/主要景点/用户指定）2. 景点 3. 辅助POI（美食/购物/夜生活）
    # 同级别内按评分排序
    def _candidate_sort_key(p):
        is_protected = 0 if p.get("is_protected") else 1  # 保护景点优先（0在前）
        is_attraction = 0 if p.get("category") == "景点" else 1  # 景点优先（0在前）
        rating = -float(p.get("rating", 0) or 0)  # 评分高优先
        return (is_protected, is_attraction, rating)
    all_candidates = sorted(all_candidates_raw, key=_candidate_sort_key)

    _planner_logger.info("all_candidates_sorted", extra={"fields": {
        "request_id": request_id,
        "total_count": len(all_candidates),
        "protected_count": sum(1 for p in all_candidates if p.get("is_protected")),
        "attraction_count": sum(1 for p in all_candidates if p.get("category") == "景点"),
        "aux_count": sum(1 for p in all_candidates if p.get("category") in ("美食", "购物", "夜生活")),
        "top5": [p.get("name", "") for p in all_candidates[:5]],
    }})

    day_plans = await _ensure_days(req, center, all_candidates, day_plans)

    # 6.5) 按序重编天数（保证 1..N 连续）
    for i, dp in enumerate(day_plans):
        dp.day = i + 1
        dp.date_label = _date_label(i + 1, req.days)

    # 6.6) 跨天地域去重：仅对非 geo 路径生效（geo 路径已按子区域天然不重复）
    if source != "geo":
        day_plans = await _enforce_region_distinct(req, center, all_candidates, day_plans)

    # 6.7) 规则引擎：体验曲线与体力曲线应用
    #      根据旅行体验曲线调整每天的景点强度和数量：
    #      - 第1天：轻松入门（低强度，3个景点）
    #      - 第2-3天：核心景点（高强度，4-5个景点）
    #      - 第4-5天：中等强度（3-4个景点）
    #      - 第6天+：轻松收尾（低强度，2-3个景点）
    #      体力交替规则：高强度景点后必须安排低强度景点休息
    try:
        if day_plans:
            # 高强度景点关键词
            HIGH_INTENSITY_KEYWORDS = ['长城', '泰山', '黄山', '华山', '张家界', '故宫', '颐和园', '兵马俑', '爬山', '徒步', '登山']
            MEDIUM_INTENSITY_KEYWORDS = ['博物馆', '历史', '文化', '古迹', '寺庙', '园林', '古镇']

            # 计算每天的景点强度
            day_intensities = []
            for i, dp in enumerate(day_plans):
                day_no = i + 1
                # 根据景点名称和类别估算强度
                high_intensity_count = 0
                medium_intensity_count = 0
                low_intensity_count = 0
                for item in dp.items:
                    poi_name = item.poi.name if hasattr(item, 'poi') and item.poi else ''
                    # 简单判断强度
                    if any(kw in poi_name for kw in HIGH_INTENSITY_KEYWORDS):
                        high_intensity_count += 1
                    elif any(kw in poi_name for kw in MEDIUM_INTENSITY_KEYWORDS):
                        medium_intensity_count += 1
                    else:
                        low_intensity_count += 1

                # 计算当天的综合强度
                total_items = len(dp.items)
                if total_items > 0:
                    intensity_score = (high_intensity_count * 3 + medium_intensity_count * 2 + low_intensity_count * 1) / total_items
                else:
                    intensity_score = 0

                # 获取体验曲线推荐的强度（使用正确的方法名）
                recommended_intensity = rule_engine.allocation_engine.get_experience_curve(day_no, len(day_plans))
                recommended_intensity_detail = rule_engine.allocation_engine.get_recommended_intensity(day_no, len(day_plans))

                day_intensities.append({
                    'day_no': day_no,
                    'actual_intensity_score': round(intensity_score, 2),
                    'recommended_intensity': recommended_intensity,
                    'recommended_intensity_detail': recommended_intensity_detail,
                    'high_count': high_intensity_count,
                    'medium_count': medium_intensity_count,
                    'low_count': low_intensity_count,
                    'total_items': total_items,
                })

            # 检查体力交替规则
            fatigue_issues = []
            for i in range(1, len(day_intensities)):
                prev = day_intensities[i - 1]
                curr = day_intensities[i]
                # 如果前一天是高强度，当天也应该是低强度休息
                if prev['recommended_intensity'] == '核心景点' and curr['recommended_intensity'] == '核心景点':
                    fatigue_issues.append(f"第{prev['day_no']}天和第{curr['day_no']}天连续核心景点，建议中间安排轻松休息")

            _planner_logger.info("experience_curve_applied", extra={"fields": {
                "request_id": request_id, "destination": destination,
                "total_days": len(day_plans),
                "day_intensities": day_intensities,
                "fatigue_issues": fatigue_issues,
            }})
    except Exception as e:
        _planner_logger.warning("experience_curve_failed", extra={"fields": {
            "request_id": request_id, "destination": destination,
            "error": str(e),
        }})

    used_poi_ids = {it.poi.id for dp in day_plans for it in dp.items}
    known = {p["id"]: p for p in all_candidates}
    known.update({it.poi.id: it.poi.model_dump() for dp in day_plans for it in dp.items})

    # 6.8) 三层POI数据自动挂载：为主景点附加内部游览动线和周边附属点位
    #      （精细点位体系：主POI → 内部子POI → 周边附属POI）
    _mount_poi_hierarchy(day_plans, known)

    # 6.9) 规则引擎：行程检视与补充
    #      检视整体行程是否符合要求（景点数量、必去景点、跨天去重、强度交替等）
    #      不符合要求时从候选景点池中补充景点
    try:
        # 转换day_plans为dict格式供规则引擎使用
        day_plans_dict = []
        for dp in day_plans:
            pois_dict = []
            for item in dp.items:
                poi_dict = item.poi.model_dump() if hasattr(item, 'poi') else {}
                poi_dict['duration'] = item.duration if hasattr(item, 'duration') else 0
                pois_dict.append(poi_dict)
            day_plans_dict.append({
                'day_no': dp.day_no if hasattr(dp, 'day_no') else 0,
                'theme': dp.theme if hasattr(dp, 'theme') else '',
                'pois': pois_dict,
            })

        # 检视行程
        params_dict = req.model_dump()
        is_valid, issues = rule_engine.review_plan(day_plans_dict, params_dict)

        if not is_valid and issues:
            _planner_logger.info("plan_review_issues", extra={"fields": {
                "request_id": request_id, "destination": destination,
                "issue_count": len(issues),
                "issues": [i.get('type', '') for i in issues[:5]],
            }})

            # 从候选景点池中补充景点
            candidate_pool = [p for p in all_candidates if p.get('id') not in used_poi_ids]
            if candidate_pool:
                day_plans_dict = rule_engine.supplement_plan(
                    day_plans_dict, issues, candidate_pool, used_poi_ids
                )
                _planner_logger.info("plan_supplemented", extra={"fields": {
                    "request_id": request_id, "destination": destination,
                    "supplemented_count": len(candidate_pool) - len([p for p in all_candidates if p.get('id') not in used_poi_ids]),
                }})

                # 【关键修复】将补充后的景点应用到day_plans中
                # 之前的bug：补充的景点只保存到day_plans_dict，没有更新到day_plans
                try:
                    supplemented_count = 0
                    for day_idx, day_dict in enumerate(day_plans_dict):
                        if day_idx >= len(day_plans):
                            break
                        dp = day_plans[day_idx]
                        # 获取当前day_plans中已有的景点ID
                        existing_poi_ids = {item.poi.id for item in dp.items if hasattr(item, 'poi') and item.poi}
                        # 查找补充的景点（在day_dict中但不在dp中的景点）
                        supplementary_pois = []
                        for poi_dict in day_dict.get('pois', []):
                            poi_id = poi_dict.get('id', poi_dict.get('name', ''))
                            if poi_id and poi_id not in existing_poi_ids and poi_id not in used_poi_ids:
                                # 确保景点有完整的信息
                                full_poi = next((p for p in all_candidates if p.get('id') == poi_id or p.get('name') == poi_dict.get('name')), poi_dict)
                                # 确保full_poi有id字段
                                if 'id' not in full_poi or not full_poi.get('id'):
                                    full_poi['id'] = poi_id
                                supplementary_pois.append(full_poi)

                        if supplementary_pois:
                            _planner_logger.info("plan_supplement_day_found", extra={"fields": {
                                "request_id": request_id, "destination": destination,
                                "day_no": day_idx + 1,
                                "supplementary_count": len(supplementary_pois),
                                "supplementary_names": [p.get('name', '') for p in supplementary_pois],
                                "existing_count": len(dp.items),
                            }})
                            # 将补充的景点添加到当天的行程中
                            poi_items = [(p, {"time_slot": "下午", "duration_min": 90}) for p in supplementary_pois]
                            # 重新排序当天的景点
                            all_poi_items = [(item.poi.model_dump() if hasattr(item, 'poi') else {}, {"time_slot": getattr(item, 'slot', '上午'), "duration_min": getattr(item, 'duration_min', 90)}) for item in dp.items]
                            all_poi_items.extend(poi_items)
                            all_poi_items = _reorder_day(all_poi_items, center)
                            # 重新构建PlanItem
                            new_items = await _build_items(all_poi_items, req.traffic_mode)
                            if new_items:
                                dp.items = new_items
                                for item in new_items:
                                    if hasattr(item, 'poi') and item.poi:
                                        used_poi_ids.add(item.poi.id)
                                supplemented_count += len(supplementary_pois)
                                _planner_logger.info("plan_supplement_day_applied", extra={"fields": {
                                    "request_id": request_id, "destination": destination,
                                    "day_no": day_idx + 1,
                                    "new_count": len(new_items),
                                }})
                            else:
                                _planner_logger.warning("plan_supplement_day_build_failed", extra={"fields": {
                                    "request_id": request_id, "destination": destination,
                                    "day_no": day_idx + 1,
                                }})

                    if supplemented_count > 0:
                        _planner_logger.info("plan_supplement_applied", extra={"fields": {
                            "request_id": request_id, "destination": destination,
                            "applied_count": supplemented_count,
                        }})
                    else:
                        _planner_logger.warning("plan_supplement_no_new_pois", extra={"fields": {
                            "request_id": request_id, "destination": destination,
                            "day_plans_dict_count": len(day_plans_dict),
                            "all_candidates_count": len(all_candidates),
                            "used_poi_ids_count": len(used_poi_ids),
                        }})
                except Exception as e:
                    _planner_logger.warning("plan_supplement_apply_failed", extra={"fields": {
                        "request_id": request_id, "destination": destination,
                        "error": str(e),
                        "traceback": traceback.format_exc(),
                    }})
        else:
            _planner_logger.info("plan_review_passed", extra={"fields": {
                "request_id": request_id, "destination": destination,
            }})
    except Exception as e:
        _planner_logger.warning("plan_review_failed", extra={"fields": {
            "request_id": request_id, "destination": destination,
            "error": str(e),
        }})

    # 6.95) 规则引擎：出行方式影响强度和规划程度计算
    try:
        traffic_impact = rule_engine.calculate_traffic_impact(params_dict, center, all_candidates)
        _planner_logger.info("traffic_impact_calculated", extra={"fields": {
            "request_id": request_id, "destination": destination,
            "impact_level": traffic_impact.get('impact_level', ''),
            "plan_level": traffic_impact.get('plan_level', ''),
            "impact_score": traffic_impact.get('impact_score', 0),
            "plan_score": traffic_impact.get('plan_score', 0),
        }})
    except Exception as e:
        _planner_logger.warning("traffic_impact_failed", extra={"fields": {
            "request_id": request_id, "destination": destination,
            "error": str(e),
        }})

    # 7) 汇总
    all_pois = [POI(**known[i]) for i in used_poi_ids]
    total_budget = round(sum(dp.budget for dp in day_plans), 1)
    budget_breakdown = _total_breakdown(day_plans)

    # 7.5) 综合规划结果校验：检查重复景点、必去景点遗漏、行程单薄、美食占比、时间安排等
    try:
        validation_issues = []
        used_poi_names = set()
        duplicate_pois = []

        # 检查1：是否有重复景点
        for dp in day_plans:
            for item in dp.items:
                poi_name = item.poi.name if hasattr(item, 'poi') and item.poi else ''
                normalized_name = poi_name.lower().replace(" ", "")
                if normalized_name in used_poi_names and normalized_name:
                    duplicate_pois.append(poi_name)
                used_poi_names.add(normalized_name)

        if duplicate_pois:
            validation_issues.append(f"发现重复景点: {', '.join(set(duplicate_pois))}")
            _planner_logger.warning("validation_duplicate_pois", extra={"fields": {
                "request_id": request_id, "destination": destination,
                "duplicate_pois": list(set(duplicate_pois)),
            }})

        # 检查2：必去景点是否都被安排（按优先级分级）
        # P0（priority=1，顶级地标）和P1（priority=2，重要景点）：必须安排
        # P2（priority=3，推荐景点）：时间充裕时安排，未安排时作为"推荐但未安排"提示
        must_visit_in_pool = [p for p in attrs if p.get("must_visit")]
        arranged_names = {item.poi.name for dp in day_plans for item in dp.items if hasattr(item, 'poi') and item.poi}

        # 按优先级分级
        p0_p1_must_visit = [p for p in must_visit_in_pool if int(p.get("must_visit_priority", 2)) <= 2]
        p2_must_visit = [p for p in must_visit_in_pool if int(p.get("must_visit_priority", 2)) == 3]

        p0_p1_names = {p.get("name", "") for p in p0_p1_must_visit}
        p2_names = {p.get("name", "") for p in p2_must_visit}

        missing_p0_p1 = p0_p1_names - arranged_names
        missing_p2 = p2_names - arranged_names

        if missing_p0_p1:
            validation_issues.append(f"必去景点未安排: {', '.join(missing_p0_p1)}")
            _planner_logger.warning("validation_missing_must_visit", extra={"fields": {
                "request_id": request_id, "destination": destination,
                "missing_must_visit": list(missing_p0_p1),
                "must_visit_total": len(p0_p1_names),
                "must_visit_arranged": len(p0_p1_names & arranged_names),
                "priority_level": "P0_P1",
            }})

        if missing_p2:
            # P2级别的必去景点未安排，作为"推荐但未安排"提示，不影响行程质量评分
            _planner_logger.info("validation_recommended_not_arranged", extra={"fields": {
                "request_id": request_id, "destination": destination,
                "recommended_not_arranged": list(missing_p2),
                "priority_level": "P2",
            }})
            # 保存推荐但未安排的景点，用于后续提示用户
            if not hasattr(req, '_recommended_not_arranged'):
                req._recommended_not_arranged = list(missing_p2)

        # 检查3：每天的点位数量是否合理（至少2个）
        thin_days = []
        for i, dp in enumerate(day_plans):
            if len(dp.items) < 2:
                thin_days.append(f"第{i+1}天只有{len(dp.items)}个点位")

        if thin_days:
            validation_issues.append(f"行程单薄: {'; '.join(thin_days)}")
            _planner_logger.warning("validation_thin_days", extra={"fields": {
                "request_id": request_id, "destination": destination,
                "thin_days": thin_days,
                "day_counts": [len(dp.items) for dp in day_plans],
            }})

        # 检查4：美食占比是否过高
        total_items = sum(len(dp.items) for dp in day_plans)
        food_items = sum(1 for dp in day_plans for item in dp.items
                         if hasattr(item, 'poi') and item.poi and item.poi.category in ('美食', '购物', '夜生活'))
        if total_items > 0 and food_items / total_items > 0.35:
            validation_issues.append(f"美食占比过高: {food_items}/{total_items} = {food_items/total_items:.1%}")
            _planner_logger.warning("validation_high_food_ratio", extra={"fields": {
                "request_id": request_id, "destination": destination,
                "food_items": food_items, "total_items": total_items,
                "food_ratio": round(food_items / total_items, 2),
            }})

        # 检查5：时间安排是否完整
        missing_time_items = []
        for i, dp in enumerate(day_plans):
            for j, item in enumerate(dp.items):
                if not item.start_time or item.start_time == "09:00":
                    # 检查是否真的缺少时间安排（默认值可能是正常的）
                    pass

        if validation_issues:
            _planner_logger.info("plan_validation_completed", extra={"fields": {
                "request_id": request_id, "destination": destination,
                "issue_count": len(validation_issues),
                "issues": validation_issues,
            }})
        else:
            _planner_logger.info("plan_validation_passed", extra={"fields": {
                "request_id": request_id, "destination": destination,
                "day_count": len(day_plans),
                "total_items": total_items,
            }})
    except Exception as e:
        _planner_logger.warning("plan_validation_failed", extra={"fields": {
            "request_id": request_id, "destination": destination, "error": str(e),
        }})

    # 实际行程天数（以实际规划的天数为准，而不是请求的天数）
    actual_days = len(day_plans)

    duration_ms = round((time.time() - start) * 1000, 2)
    _planner_logger.info("plan_done", extra={"fields": {
        "request_id": request_id, "destination": destination, "days": req.days,
        "actual_days": actual_days,
        "poi_count": len(all_pois), "day_count": len(day_plans),
        "total_budget": total_budget, "source": source, "ai_model": model_used,
        "duration_ms": duration_ms,
    }})

    # 大时间跨度（月/年）：生成月度分配摘要，按省/月合理分配
    span_summary = {}
    if req.span_unit in ("month", "year") and req.span_value >= 1:
        province = _resolve_province(destination, geo)
        span_summary = _build_long_span_summary(req, province)
        if span_summary:
            _planner_logger.info("long_span_plan", extra={"fields": {
                "request_id": request_id, "destination": destination,
                "span_unit": req.span_unit, "span_value": req.span_value,
                "province": province, "months": len(span_summary.get("months", [])),
            }})

    # 【阶段一】规划质量评估：量化评估规划结果的质量，找出问题所在
    quality_report = None
    try:
        from .quality import PlanQualityEvaluator
        evaluator = PlanQualityEvaluator()

        # 将PlanResponse转换为dict形式
        plan_dict = {
            "destination": destination,
            "days": actual_days,
            "day_plans": [dp.dict() if hasattr(dp, 'dict') else dp for dp in day_plans],
            "all_pois": [p.dict() if hasattr(p, 'dict') else p for p in all_pois],
            "total_budget": total_budget,
            "budget_breakdown": budget_breakdown,
        }

        # 请求参数
        request_dict = {
            "destination": req.destination,
            "days": req.days,
            "travelers": req.travelers,
            "group_type": req.group_type,
            "budget_level": req.budget_level,
            "style": req.style,
            "pace": req.pace,
            "traffic_mode": req.traffic_mode,
        }

        # 获取主要景点列表（用于覆盖率评估）
        major_attractions = []
        try:
            major_service = get_major_attractions_service()
            major_attractions = major_service.get_major_attractions_by_city(poi_search_city)
            if not major_attractions:
                # 如果按城市找不到，尝试搜索
                major_attractions = major_service.get_major_attractions_by_city(destination)
        except Exception as e:
            _planner_logger.warning("quality_eval_major_attractions_failed", extra={"fields": {
                "request_id": request_id, "error": str(e),
            }})

        # 执行质量评估
        quality_report = evaluator.evaluate(plan_dict, request_dict, major_attractions)

        # 输出评估报告到日志
        _planner_logger.info("plan_quality_report", extra={"fields": {
            "request_id": request_id,
            "destination": destination,
            "overall_score": quality_report.overall_score,
            "dimensions": {d.name: d.score for d in quality_report.dimensions},
            "issue_count": len(quality_report.issues),
            "issues": quality_report.issues[:10],
            "suggestions": quality_report.suggestions[:5],
        }})

        # 如果综合得分低于60分，输出详细的评估报告
        if quality_report.overall_score < 60:
            _planner_logger.warning("plan_quality_low_score", extra={"fields": {
                "request_id": request_id,
                "destination": destination,
                "overall_score": quality_report.overall_score,
                "detailed_report": quality_report.summary(),
            }})

    except Exception as e:
        _planner_logger.warning("plan_quality_eval_failed", extra={"fields": {
            "request_id": request_id, "destination": destination, "error": str(e),
        }})

    # 6.95) 在线数据增强输出：添加预约提醒、避坑提示等增强信息
    reservation_alerts = []
    travel_tips_output = []
    online_data_meta = {}
    try:
        if online_data_context and online_data_context.is_loaded:
            from ...services.online_data import get_online_data_enhancer
            enhancer = get_online_data_enhancer()
            enhanced_output = enhancer.get_enhanced_output(online_data_context)

            reservation_alerts = enhanced_output.get("reservation_alerts", [])
            travel_tips_output = enhanced_output.get("travel_tips", [])
            online_data_meta = enhanced_output.get("online_data_meta", {})

            # 合并从攻略提取的避坑提示
            extracted_tips = enhanced_output.get("extracted_tips", [])
            if extracted_tips:
                existing_tips = {t.get("tip", "") for t in travel_tips_output}
                for tip in extracted_tips:
                    tip_text = tip.get("tip", "")
                    if tip_text and tip_text not in existing_tips:
                        travel_tips_output.append({
                            "tip": tip_text,
                            "category": tip.get("category", "general"),
                            "severity": "info",
                            "source": "online_search",
                            "frequency": tip.get("frequency", 0),
                        })

            _planner_logger.info("online_data_output_enhanced", extra={"fields": {
                "request_id": request_id,
                "destination": destination,
                "reservation_alerts_count": len(reservation_alerts),
                "travel_tips_count": len(travel_tips_output),
                "online_confidence": online_data_context.confidence,
            }})
    except Exception as e:
        _planner_logger.warning("online_data_output_enhance_failed", extra={"fields": {
            "request_id": request_id,
            "destination": destination,
            "error": str(e),
        }})

    return PlanResponse(
        request_id=request_id,
        destination=destination,
        city_center={"lng": center.get("lng", 0.0), "lat": center.get("lat", 0.0)},
        days=actual_days,  # 使用实际行程天数，而不是请求的天数
        origin=req.origin,
        travelers=req.travelers,
        return_point=req.return_point,
        group_type=req.group_type,
        budget_level=req.budget_level,
        style=req.style,
        pace=req.pace,
        traffic_mode=req.traffic_mode,
        daily_start_time=req.daily_start_time,
        ai_model=model_used,
        source=source,
        weather=weather,
        departure_message=departure_message(destination, actual_days),
        day_plans=day_plans,
        all_pois=all_pois,
        total_budget=total_budget,
        budget_breakdown=budget_breakdown,
        generated_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        span_summary=span_summary,
        quality_score=quality_report.overall_score if quality_report else None,
        quality_issues=quality_report.issues if quality_report else [],
        quality_suggestions=quality_report.suggestions if quality_report else [],
        reservation_alerts=reservation_alerts,
        travel_tips=travel_tips_output,
        online_data_meta=online_data_meta,
    )




def _rule_plan(req: PlanRequest, center: dict, pois: List[dict]) -> List[dict]:
    """规则引擎：按类别/评分/距离把候选点位排成逐日行程"""
    attractions = [p for p in pois if p["category"] == "景点"]
    foods = [p for p in pois if p["category"] == "美食"]
    shoppings = [p for p in pois if p["category"] == "购物"]
    nights = [p for p in pois if p["category"] == "夜生活"]

    # 必去点位优先（排到各池最前，保证先被选中）
    must_names = {n.strip() for n in req.must_include_poi if n.strip()}
    attractions = _prioritize(attractions, must_names)
    foods = _prioritize(foods, must_names)
    shoppings = _prioritize(shoppings, must_names)
    nights = _prioritize(nights, must_names)

    # 高分在前，同分时离市中心近的优先，减少折返（单次排序，勿被后续覆盖）
    attractions.sort(key=lambda p: (-p.get("rating", 0),
                                    amap.haversine(center["lng"], center["lat"], p["lng"], p["lat"])))
    for _pool in (foods, shoppings, nights):
        _pool.sort(key=lambda p: (-p.get("rating", 0),
                                  amap.haversine(center["lng"], center["lat"], p["lng"], p["lat"])))

    items_per_day = PACE_ITEMS.get(req.pace, 4)
    group = req.group_type
    if group in GROUP_PACE:
        items_per_day = PACE_ITEMS.get(GROUP_PACE[group], items_per_day)

    days = max(1, req.days)
    themes = ["经典探索", "深度体验", "人文漫游", "轻松度假", "小众发现", "城市漫步", "美食之旅", "文化寻踪"]
    used: set = set()
    raw_days = []
    for day_idx in range(days):
        items = []

        # 上午：景点（必去景点优先）
        a = _pick_pool(attractions, used, day_idx)
        if a:
            used.add(a["id"])
            items.append(_rule_item(a, "上午", 150))
        # 中午：美食（仅当有合适的美食时才添加，且每天最多1个美食）
        food_count_today = sum(1 for it in items if it.get("category") == "美食")
        if food_count_today < 1:
            f = _pick_pool(foods, used, day_idx)
            if f:
                # 过滤掉不适合作为主要美食推荐的店铺
                bad_food_keywords = ['蜜雪冰城', '肯德基', '麦当劳', '星巴克', '瑞幸', '奶茶', '饮品', '快餐', '便利店']
                if not any(kw in f.get('name', '') for kw in bad_food_keywords):
                    used.add(f["id"])
                    items.append(_rule_item(f, "中午", 75))
        # 下午：景点（优先使用景点，而不是购物/夜生活）
        a2 = _pick_pool(attractions, used, day_idx + 1)
        if a2 and len(items) < items_per_day:
            used.add(a2["id"])
            items.append(_rule_item(a2, "下午", 150))
        # 下午/傍晚：景点（继续使用景点，减少购物的使用）
        a3 = _pick_pool(attractions, used, day_idx + 2)
        if a3 and len(items) < items_per_day:
            used.add(a3["id"])
            items.append(_rule_item(a3, "下午", 120))
        # 晚上：夜景/夜市（仅当有合适的夜生活点位时才添加）
        n = _pick_pool(nights, used, day_idx)
        if n and len(items) < items_per_day:
            used.add(n["id"])
            items.append(_rule_item(n, "晚上", 90))

        # 点位不足时优先用景点补足，而不是美食（保证每天至少3个点位，且景点为主）
        extra = 0
        while len(items) < min(3, items_per_day):
            # 优先用景点补足
            extra_a = _pick_pool(attractions, used, extra)
            if extra_a:
                used.add(extra_a["id"])
                items.append(_rule_item(extra_a, "上午" if len(items) == 0 else "下午", 120))
                extra += 1
                continue
            # 景点不足时用购物补足（而不是美食）
            extra_s = _pick_pool(shoppings, used, extra)
            if extra_s:
                used.add(extra_s["id"])
                items.append(_rule_item(extra_s, "下午", 90))
                extra += 1
                continue
            # 最后才用美食补足
            fb = _pick_pool(foods, used, extra)
            if not fb:
                break
            # 过滤掉不适合的美食
            bad_food_keywords = ['蜜雪冰城', '肯德基', '麦当劳', '星巴克', '瑞幸', '奶茶', '饮品', '快餐', '便利店']
            if any(kw in fb.get('name', '') for kw in bad_food_keywords):
                extra += 1
                continue
            used.add(fb["id"])
            items.append(_rule_item(fb, "中午" if len(items) == 0 else "晚上", 70))
            extra += 1

        tip = "热门场馆建议提前预约；早晚温差大，记得带件外套。"
        raw_days.append({
            "day": day_idx + 1,
            "theme": f"第{day_idx + 1}天 · {themes[day_idx % len(themes)]}",
            "tip": tip,
            "items": items,
        })
    return raw_days


def _pick_pool(pool: List[dict], used: set, rotate: int = 0):
    """从点位池中选一个未用过的点位（带轮转），用完返回 None"""
    if not pool:
        return None
    for i in range(len(pool)):
        p = pool[(rotate + i) % len(pool)]
        if p["id"] not in used:
            return p
    return None


def _prioritize(pool: List[dict], must_names: set) -> List[dict]:
    """把名称命中必去列表的点位排到最前"""
    musts = [p for p in pool if p["name"] in must_names]
    rest = [p for p in pool if p["name"] not in must_names]
    return musts + rest


def _fallback_pois(center: dict, city: str) -> List[dict]:
    """没有任何候选点位时的最低保障"""
    base = [("城市地标广场", "景点", 0, 4.5), ("本地美食街", "美食", 60, 4.4)]
    out = []
    for i, (name, cat, price, rating) in enumerate(base):
        out.append({"id": f"P{i:04d}", "name": f"{city}{name}", "lng": center["lng"] + 0.02 * i,
                    "lat": center["lat"] - 0.01 * i, "address": city, "category": cat,
                    "price": price, "rating": rating, "source": "local"})
    return out



async def _emergency_plan(req: PlanRequest, center: dict, pois: List[dict]) -> List[DayPlan]:
    """最后兜底：最简单的一天"""
    poi = POI(**pois[0]) if pois else POI(id="P0001", name=f"{req.destination}城市漫步",
                                          lng=center["lng"], lat=center["lat"], source="local")
    items = [PlanItem(slot="上午", start_time="09:00", poi=poi, duration_min=180, note="城市自由漫步")]
    dp = DayPlan(day=1, theme="城市漫步一日", date_label="第1天", items=items,
                 budget=100.0, tip="自由探索，随心而行。",
                 inspiration=daily_inspiration("城市漫步一日", 1))
    return [dp]


async def _ensure_days(req: PlanRequest, center: dict, pois: List[dict],
                       day_plans: List[DayPlan]) -> List[DayPlan]:
    """
    AI 产出天数不足时，用规则引擎补齐，保证共 req.days 天（去重已用点位）。

    P1-2 明确兜底顺序：
    1. 规则规划结果（_rule_plan）
    2. 候选池补充：从候选景点池中挑选未入选的景点
    3. 实时POI补充：如果候选池不足，实时调用第三方POI搜索（预留）
    4. 极端兜底：如果以上都不足，使用极端兜底方案
    """
    if len(day_plans) >= req.days:
        return day_plans
    poi_map = {p["id"]: p for p in pois}
    used = {it.poi.id for dp in day_plans for it in dp.items}
    raw_all = _rule_plan(req, center, pois)
    need = req.days - len(day_plans)
    added = 0

    # 补齐天数的主题池（不使用_rule_plan的主题，因为它包含"第X天"前缀且可能取错）
    fallback_themes = ["深度体验", "人文漫游", "轻松度假", "小众发现", "城市漫步", "美食之旅", "文化寻踪", "自然探索"]

    _planner_logger.info("ensure_days_start", extra={"fields": {
        "request_id": request_id,
        "current_days": len(day_plans),
        "target_days": req.days,
        "need_days": need,
        "candidate_pool_size": len(pois),
        "used_poi_count": len(used),
        "available_poi_count": len(pois) - len(used),
    }})

    for raw in raw_all:
        if added >= need:
            break
        poi_items = [(poi_map[it["poi_id"]], it) for it in raw.get("items", [])
                     if it.get("poi_id") in poi_map and it["poi_id"] not in used]

        # P1-2 兜底顺序1：如果从_rule_plan取到的点位不足（少于3个），从候选池中补充未使用的点位
        if len(poi_items) < 3:
            _planner_logger.info("ensure_days_fallback_stage1", extra={"fields": {
                "request_id": request_id,
                "day_no": len(day_plans) + 1,
                "rule_plan_count": len(poi_items),
                "action": "从候选池补充未使用的点位",
            }})
            # 按类别优先级补充：景点 > 美食 > 购物 > 夜生活
            for category in ["景点", "美食", "购物", "夜生活"]:
                if len(poi_items) >= 4:
                    break
                candidates = [p for p in pois
                              if p.get("category") == category and p["id"] not in used
                              and p["id"] not in {pi[0]["id"] for pi in poi_items}]
                # 按评分排序，优先高分；保护景点优先
                candidates.sort(key=lambda p: (
                    not p.get("is_protected", False),  # 保护景点优先
                    -float(p.get("rating", 0) or 0),
                ))
                for p in candidates[:2]:  # 每类最多补充2个
                    poi_items.append((p, {"time_slot": "下午", "duration_min": 90}))

        # P1-2 兜底顺序2：如果候选池补充后仍然不足，使用极端兜底点位
        if len(poi_items) == 0:
            _planner_logger.info("ensure_days_fallback_stage2", extra={"fields": {
                "request_id": request_id,
                "day_no": len(day_plans) + 1,
                "action": "使用极端兜底点位",
            }})
            fallback = _fallback_pois(center, req.destination)
            for p in fallback:
                if p["id"] not in used and p["id"] not in {pi[0]["id"] for pi in poi_items}:
                    poi_items.append((p, {"time_slot": "下午", "duration_min": 90}))
                    if len(poi_items) >= 2:
                        break

        if not poi_items:
            _planner_logger.warning("ensure_days_no_poi", extra={"fields": {
                "request_id": request_id,
                "day_no": len(day_plans) + 1,
                "action": "无可用点位，跳过",
            }})
            continue

        _planner_logger.info("ensure_days_day_build", extra={"fields": {
            "request_id": request_id,
            "day_no": len(day_plans) + 1,
            "poi_count": len(poi_items),
            "poi_names": [p.get("name", "") for p, _ in poi_items],
        }})

        poi_items = _reorder_day(poi_items, center)
        day_no = len(day_plans) + 1
        items = await _build_items(poi_items, req.traffic_mode)
        # P1-1：使用新的独立时间规划模块（整合游览时长、开放时间、交通时间、时间线模板）
        try:
            items = plan_day_timeline(req, items, day_no)
        except Exception as e:
            _planner_logger.warning("timeline_planner_failed", extra={"fields": {
                "request_id": request_id, "day_no": day_no, "error": str(e),
            }})
            # 降级：使用原有的apply_timeline函数
            items = _apply_timeline(req, items)
        if not items:
            continue
        used.update(it.poi.id for it in items)
        budget, _breakdown = _day_budget(req, items)
        # 重新生成主题，不使用_rule_plan的主题（避免"第X天"前缀错误）
        theme = fallback_themes[(day_no - 1) % len(fallback_themes)]
        day_plans.append(DayPlan(
            day=day_no, theme=theme, date_label=_date_label(day_no, req.days),
            items=items, budget=budget, tip=raw.get("tip", ""),
            inspiration=daily_inspiration(theme, day_no),
        ))
        added += 1

    _planner_logger.info("ensure_days_complete", extra={"fields": {
        "request_id": request_id,
        "initial_days": len(day_plans) - added,
        "added_days": added,
        "final_days": len(day_plans),
        "target_days": req.days,
    }})

    return day_plans


def _mount_poi_hierarchy(day_plans: List[DayPlan], known: dict):
    """
    三层POI数据自动挂载：为主景点附加内部游览动线和周边附属点位
    （精细点位体系：主POI → 内部子POI → 周边附属POI）

    Args:
        day_plans: 行程天数列表
        known: 已知POI字典（id -> poi dict）
    """
    mounted_count = 0
    for dp in day_plans:
        for item in dp.items:
            poi = item.poi
            poi_name = poi.name
            # 从数据库获取三层POI数据
            try:
                from ...data.repositories.poi_hierarchy_repository import PoiHierarchyRepository
                hierarchy = PoiHierarchyRepository.get_main_poi_by_name(poi_name)
            except Exception:
                hierarchy = None
            if not hierarchy:
                continue
            # 挂载内部游览动线
            poi.inner_route = hierarchy.get("inner_route", [])
            # 挂载周边附属点位
            poi.nearby_attractions = hierarchy.get("nearby_attractions", [])
            # 挂载其他扩展信息
            poi.poi_level = hierarchy.get("level", "")
            poi.recommended_duration = hierarchy.get("recommended_duration", 0)
            poi.best_time = hierarchy.get("best_time", "")
            poi.avoid_tips = hierarchy.get("avoid_tips", [])
            poi.description = hierarchy.get("description", "")
            poi.has_hierarchy = True
            # 同步更新known字典
            if poi.id in known:
                known[poi.id]["inner_route"] = poi.inner_route
                known[poi.id]["nearby_attractions"] = poi.nearby_attractions
                known[poi.id]["has_hierarchy"] = True
            mounted_count += 1
    if mounted_count > 0:
        _planner_logger.info("poi_hierarchy_mounted", extra={"fields": {
            "mounted_count": mounted_count,
        }})
