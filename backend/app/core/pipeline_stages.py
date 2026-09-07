# -*- coding: utf-8 -*-
"""
规划Pipeline阶段化模块。

将庞大的build_plan函数拆分为多个独立的阶段，每个阶段有明确的输入和输出，
便于维护、测试和优化。

阶段划分：
1. 参数规范化阶段（normalize_params）
2. 目的地解析阶段（resolve_destination）
3. POI检索阶段（fetch_pois）
4. 景点池构建阶段（build_attraction_pool）
5. 聚类分组阶段（cluster_and_group）
6. 逐日规划阶段（build_daily_plan）
7. 验证优化阶段（validate_and_optimize）

设计原则：
- 每个阶段都是纯函数（或异步函数），输入明确，输出明确
- 使用PlanContext在各个阶段之间传递数据
- 每个阶段都有详细的日志，便于排查问题
- 支持阶段级别的缓存和重试

功能特性：
- PlanContext：规划上下文，在各个阶段之间传递数据
- 阶段开始/结束/错误日志记录
- 各阶段独立实现，便于测试和优化
- 阶段性能计时
- 错误收集和汇总

使用方式：
    from app.core.pipeline_stages import PlanContext, run_pipeline

    # 创建规划上下文
    context = PlanContext(request=request)

    # 运行规划流水线
    final_plan = await run_pipeline(context)
"""
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..infrastructure.logger import get_logger
from ..skills.itinerary_planner import is_in_china

logger = get_logger("planner.pipeline")


@dataclass
class PlanContext:
    """规划上下文，在各个阶段之间传递数据。"""

    # 请求信息
    request: Any = None
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    # 阶段1：参数规范化结果
    normalized_params: Dict[str, Any] = field(default_factory=dict)

    # 阶段2：目的地解析结果
    geo_info: Optional[Dict[str, Any]] = None
    center: Dict[str, Any] = field(default_factory=dict)
    poi_search_city: str = ""
    poi_search_province: str = ""
    poi_search_district: str = ""
    geo_level: str = ""
    is_specific_poi: bool = False
    is_in_china: bool = True

    # 阶段3：POI检索结果
    pois: List[Dict[str, Any]] = field(default_factory=list)
    weather: Dict[str, Any] = field(default_factory=dict)

    # 阶段4：景点池构建结果
    attractions: List[Dict[str, Any]] = field(default_factory=list)

    # 阶段5：聚类分组结果
    clusters: List[Dict[str, Any]] = field(default_factory=list)

    # 阶段6：逐日规划结果
    day_plans: List[Dict[str, Any]] = field(default_factory=list)

    # 阶段7：验证优化结果
    final_plan: Optional[Dict[str, Any]] = None

    # 元信息
    start_time: float = field(default_factory=time.time)
    stage_timings: Dict[str, float] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    def log_stage_start(self, stage_name: str) -> None:
        """记录阶段开始。"""
        logger.info(f"stage_start: {stage_name}", extra={
            "fields": {
                "request_id": self.request_id,
                "stage": stage_name,
            }
        })

    def log_stage_end(self, stage_name: str, result_summary: str = "") -> None:
        """记录阶段结束。"""
        elapsed = time.time() - self.start_time
        self.stage_timings[stage_name] = elapsed
        logger.info(f"stage_end: {stage_name}", extra={
            "fields": {
                "request_id": self.request_id,
                "stage": stage_name,
                "elapsed_ms": round(elapsed * 1000, 2),
                "result_summary": result_summary,
            }
        })

    def log_stage_error(self, stage_name: str, error: str) -> None:
        """记录阶段错误。"""
        self.errors.append(f"{stage_name}: {error}")
        logger.warning(f"stage_error: {stage_name}", extra={
            "fields": {
                "request_id": self.request_id,
                "stage": stage_name,
                "error": error,
            }
        })

    def get_total_elapsed(self) -> float:
        """获取总耗时（秒）。"""
        return time.time() - self.start_time


# ---------------- 阶段1：参数规范化 ----------------

async def stage_normalize_params(ctx: PlanContext) -> bool:
    """
    阶段1：参数规范化。

    使用规则引擎对参数进行兜底和收束：
    - 时间跨度：最小1天，最大365天，超出范围进行收束
    - 人数：最小1人，最大50人，超出范围进行收束
    - 预算：默认适中，可选项：经济、适中、舒适
    - 人群类型：根据人数推断，1人→单人，2人→情侣/朋友，3人以上→家庭/朋友
    - 节奏：默认适中，可选项：轻松、适中、紧凑
    - 出行方式：默认公共交通，可选项：自驾、公共交通、骑行、步行、混合

    返回：
        bool: 是否成功（失败时应该终止规划）
    """
    ctx.log_stage_start("normalize_params")

    try:
        from app.skills.rule_engine import get_rule_engine

        req = ctx.request
        original_days = req.days
        original_travelers = req.travelers

        rule_engine = get_rule_engine()
        normalized_params = rule_engine.normalize_params(req.model_dump())

        # 更新请求参数
        req.days = normalized_params['days']
        req.travelers = normalized_params['travelers']
        req.budget_level = normalized_params['budget_level']
        req.group_type = normalized_params['group_type']
        req.pace = normalized_params['pace']
        req.traffic_mode = normalized_params['traffic_mode']

        ctx.normalized_params = normalized_params

        result_summary = (
            f"days: {original_days}→{req.days}, "
            f"travelers: {original_travelers}→{req.travelers}, "
            f"group_type: {req.group_type}, "
            f"budget_level: {req.budget_level}, "
            f"pace: {req.pace}, "
            f"traffic_mode: {req.traffic_mode}"
        )
        ctx.log_stage_end("normalize_params", result_summary)
        return True

    except Exception as e:
        ctx.log_stage_error("normalize_params", str(e))
        return False


# ---------------- 阶段2：目的地解析 ----------------

async def stage_resolve_destination(ctx: PlanContext) -> bool:
    """
    阶段2：目的地解析。

    包括：
    - 地理编码：将地名转换为坐标
    - 行政区域补全：如果用户输入的是具体景点，获取其所属的城市名
    - 中国区域校验：仅规划中国境内目的地

    返回：
        bool: 是否成功（失败时应该终止规划）
    """
    ctx.log_stage_start("resolve_destination")

    try:
        from ..services.map import geocode as amap_geocode

        req = ctx.request
        destination = req.destination.strip()

        # 地理编码
        geo = await amap_geocode.geocode(destination)
        if not geo:
            ctx.log_stage_error("resolve_destination", f"无法识别目的地「{destination}」")
            return False

        ctx.geo_info = geo
        ctx.center = {"lng": geo["lng"], "lat": geo["lat"]}

        # 行政区域补全
        ctx.poi_search_city = destination
        ctx.poi_search_province = geo.get("province", "") or ""
        ctx.poi_search_district = geo.get("district", "") or ""
        ctx.geo_level = geo.get("level", "") or ""

        # 判断目的地是否为具体景点
        ctx.is_specific_poi = ctx.geo_level in ["景点", "兴趣点", "POI", "poi"] or (
            ctx.geo_level == "" and geo.get("source") == "famous_landmark"
        )

        if ctx.is_specific_poi:
            # 如果是具体景点，使用其所属的城市名进行POI搜索
            if geo.get("city") and geo["city"] != destination:
                ctx.poi_search_city = geo["city"]
        else:
            # 如果是行政区域级别，确保城市名包含完整的行政区域信息
            if geo.get("city") and geo["city"] != destination:
                ctx.poi_search_city = geo["city"]

        # 确保center对象包含行政区域信息
        if ctx.poi_search_province:
            ctx.center["province"] = ctx.poi_search_province
        if ctx.poi_search_district:
            ctx.center["district"] = ctx.poi_search_district
        if ctx.poi_search_city:
            ctx.center["city"] = ctx.poi_search_city

        # 中国区域校验
        ctx.is_in_china = is_in_china(geo)
        if not ctx.is_in_china:
            ctx.log_stage_error("resolve_destination", f"目的地「{destination}」位于中国境外")
            return False

        result_summary = (
            f"destination: {destination}, "
            f"poi_search_city: {ctx.poi_search_city}, "
            f"province: {ctx.poi_search_province}, "
            f"district: {ctx.poi_search_district}, "
            f"geo_level: {ctx.geo_level}, "
            f"is_specific_poi: {ctx.is_specific_poi}, "
            f"center: ({ctx.center.get('lng')}, {ctx.center.get('lat')})"
        )
        ctx.log_stage_end("resolve_destination", result_summary)
        return True

    except Exception as e:
        ctx.log_stage_error("resolve_destination", str(e))
        return False


    # 经纬度范围判断（中国大致范围）
    lng = geo.get("lng", 0)
    lat = geo.get("lat", 0)
    return 73.0 <= lng <= 135.0 and 18.0 <= lat <= 54.0


# ---------------- 阶段3：POI检索 ----------------

async def stage_fetch_pois(ctx: PlanContext) -> bool:
    """
    阶段3：POI检索。

    包括：
    - 候选POI检索：景点、美食、购物、夜生活
    - 天气查询

    返回：
        bool: 是否成功（失败时可以继续，使用空POI）
    """
    ctx.log_stage_start("fetch_pois")

    try:
        from ..services.map import poi as amap_poi
        from ..services.map import weather as amap_weather

        # 检索候选POI
        pois = await amap_poi.search_pois(
            ctx.poi_search_city,
            ctx.center,
            ["景点", "美食", "购物", "夜生活"]
        )

        # 应用排除规则
        if ctx.request.exclude_poi:
            exclude_names = {n.strip() for n in ctx.request.exclude_poi if n.strip()}
            pois = [p for p in pois if p["name"] not in exclude_names]

        ctx.pois = pois

        # 天气查询
        try:
            weather = await amap_weather.get_weather(
                ctx.poi_search_province,
                ctx.poi_search_city,
                ctx.geo_info.get("adcode", "") if ctx.geo_info else ""
            )
            ctx.weather = weather or {}
        except Exception as e:
            ctx.log_stage_error("fetch_pois.weather", str(e))
            ctx.weather = {}

        result_summary = (
            f"pois: {len(ctx.pois)} 个, "
            f"weather: {'有' if ctx.weather else '无'}"
        )
        ctx.log_stage_end("fetch_pois", result_summary)
        return True

    except Exception as e:
        ctx.log_stage_error("fetch_pois", str(e))
        ctx.pois = []
        ctx.weather = {}
        return True  # POI检索失败可以继续，使用空POI


# ---------------- 阶段4：景点池构建 ----------------

async def stage_build_attraction_pool(ctx: PlanContext) -> bool:
    """
    阶段4：景点池构建。

    包括：
    - 行政分级枚举景点：区/县 → 市 → 省
    - 必打卡地标注入
    - 人群影响规则应用
    - 大型景区识别与权重调整

    返回：
        bool: 是否成功（失败时可以继续，使用空景点池）
    """
    ctx.log_stage_start("build_attraction_pool")

    try:
        # 行政分级枚举景点
        from .planner_helpers import _enumerate_scoped_attractions
        attrs = await _enumerate_scoped_attractions(ctx.geo_info, ctx.center)

        # 必打卡地标注入
        from .planner_helpers import _inject_must_visit_attrs
        attrs = await _inject_must_visit_attrs(ctx.request.destination, attrs)

        # 应用排除规则
        if ctx.request.exclude_poi:
            exclude_names = {n.strip() for n in ctx.request.exclude_poi if n.strip()}
            attrs = [p for p in attrs if p["name"] not in exclude_names]

        # 人群影响规则应用
        try:
            from app.skills.rule_engine import get_rule_engine
            rule_engine = get_rule_engine()
            group_type = ctx.request.group_type or '单人'
            group_config = rule_engine.group_engine.get_group_config(group_type)

            if group_config and attrs:
                # 标记景点的人群友好属性
                for p in attrs:
                    p['is_family_friendly'] = rule_engine.group_engine.is_family_friendly(p)
                    p['is_elderly_friendly'] = rule_engine.group_engine.is_elderly_friendly(p)
                    name = p.get('name', '')
                    category = p.get('category', '') or p.get('type', '')
                    p['is_couple_friendly'] = any(kw in name + category for kw in ['浪漫', '网红', '夜景', '摩天轮', '湖边', '咖啡馆', '情侣'])
                    p['is_friend_friendly'] = any(kw in name + category for kw in ['网红', '夜生活', '美食', '酒吧', '购物', '朋友'])
                    p['is_solo_friendly'] = any(kw in name + category for kw in ['小众', '文艺', '书店', '博物馆', '咖啡馆', '徒步'])

                # 按人群类型调整景点评分
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
                        p['rating'] = min(5.0, original_rating + 0.3)

        except Exception as e:
            ctx.log_stage_error("build_attraction_pool.group_influence", str(e))

        # 大型景区识别与权重调整
        try:
            from .planner_helpers import get_scenic_area_weight_factor, is_inside_large_scenic_area
            for p in attrs:
                name = p.get("name", "")
                category = p.get("category", "") or p.get("type", "")
                weight_factor = get_scenic_area_weight_factor(name, category)
                p["scenic_weight_factor"] = weight_factor
                is_inner, parent_scenic = is_inside_large_scenic_area(name, category)
                if is_inner:
                    p["is_scenic_inner"] = True
                    p["parent_scenic"] = parent_scenic
        except Exception as e:
            ctx.log_stage_error("build_attraction_pool.scenic_area", str(e))

        ctx.attractions = attrs

        result_summary = (
            f"attractions: {len(ctx.attractions)} 个, "
            f"group_type: {ctx.request.group_type}"
        )
        ctx.log_stage_end("build_attraction_pool", result_summary)
        return True

    except Exception as e:
        ctx.log_stage_error("build_attraction_pool", str(e))
        ctx.attractions = []
        return True  # 景点池构建失败可以继续，使用空景点池


# ---------------- 阶段5：聚类分组 ----------------

async def stage_cluster_and_group(ctx: PlanContext) -> bool:
    """
    阶段5：聚类分组。

    包括：
    - 地理聚类：就近优先，再向外扩散
    - 主子POI识别：大型景区作为整体，景区内小景点优先级降低
    - 必去景点分组：顶级地标单独分组

    返回：
        bool: 是否成功（失败时可以继续，使用空分组）
    """
    ctx.log_stage_start("cluster_and_group")

    try:
        # TODO: 实现聚类分组逻辑
        # 目前这部分逻辑还在planner.py中，后续逐步迁移

        result_summary = "聚类分组阶段（待实现完整迁移）"
        ctx.log_stage_end("cluster_and_group", result_summary)
        return True

    except Exception as e:
        ctx.log_stage_error("cluster_and_group", str(e))
        return True


# ---------------- 阶段6：逐日规划 ----------------

async def stage_build_daily_plan(ctx: PlanContext) -> bool:
    """
    阶段6：逐日规划。

    包括：
    - 时间分配：根据天数和节奏分配每天的景点数量
    - 行程构建：按照地理聚类结果构建每日行程
    - 住宿推荐：根据行程推荐住宿区域

    返回：
        bool: 是否成功（失败时可以继续，使用空行程）
    """
    ctx.log_stage_start("build_daily_plan")

    try:
        # TODO: 实现逐日规划逻辑
        # 目前这部分逻辑还在planner.py中，后续逐步迁移

        result_summary = "逐日规划阶段（待实现完整迁移）"
        ctx.log_stage_end("build_daily_plan", result_summary)
        return True

    except Exception as e:
        ctx.log_stage_error("build_daily_plan", str(e))
        return True


# ---------------- 阶段7：验证优化 ----------------

async def stage_validate_and_optimize(ctx: PlanContext) -> bool:
    """
    阶段7：验证优化。

    包括：
    - LLM优化：使用大模型对行程进行优化
    - 结果验证：验证行程是否符合要求
    - 预算计算：计算总预算和明细

    返回：
        bool: 是否成功（失败时可以继续，使用原始行程）
    """
    ctx.log_stage_start("validate_and_optimize")

    try:
        # TODO: 实现验证优化逻辑
        # 目前这部分逻辑还在planner.py中，后续逐步迁移

        result_summary = "验证优化阶段（待实现完整迁移）"
        ctx.log_stage_end("validate_and_optimize", result_summary)
        return True

    except Exception as e:
        ctx.log_stage_error("validate_and_optimize", str(e))
        return True


# ---------------- 主Pipeline ----------------

async def run_plan_pipeline(request: Any) -> PlanContext:
    """
    运行完整的规划Pipeline。

    参数：
        request: 规划请求（PlanRequest对象）

    返回：
        PlanContext: 规划上下文，包含各个阶段的结果
    """
    ctx = PlanContext(request=request)

    logger.info("plan_pipeline_start", extra={
        "fields": {
            "request_id": ctx.request_id,
            "destination": request.destination,
            "days": request.days,
            "travelers": request.travelers,
        }
    })

    # 阶段1：参数规范化
    success = await stage_normalize_params(ctx)
    if not success:
        logger.warning("plan_pipeline_failed_at_stage", extra={
            "fields": {
                "request_id": ctx.request_id,
                "stage": "normalize_params",
                "errors": ctx.errors,
            }
        })
        return ctx

    # 阶段2：目的地解析
    success = await stage_resolve_destination(ctx)
    if not success:
        logger.warning("plan_pipeline_failed_at_stage", extra={
            "fields": {
                "request_id": ctx.request_id,
                "stage": "resolve_destination",
                "errors": ctx.errors,
            }
        })
        return ctx

    # 阶段3：POI检索
    await stage_fetch_pois(ctx)

    # 阶段4：景点池构建
    await stage_build_attraction_pool(ctx)

    # 阶段5：聚类分组
    await stage_cluster_and_group(ctx)

    # 阶段6：逐日规划
    await stage_build_daily_plan(ctx)

    # 阶段7：验证优化
    await stage_validate_and_optimize(ctx)

    total_elapsed = ctx.get_total_elapsed()
    logger.info("plan_pipeline_end", extra={
        "fields": {
            "request_id": ctx.request_id,
            "total_elapsed_ms": round(total_elapsed * 1000, 2),
            "stage_timings": ctx.stage_timings,
            "errors": ctx.errors,
        }
    })

    return ctx
