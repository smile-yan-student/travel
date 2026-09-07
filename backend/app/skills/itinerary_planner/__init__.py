"""
行程规划 Skill（Itinerary Planner Skill）

这是一个独立的行程规划能力模块，提供完整的旅游行程规划功能。

核心能力：
- 行程规划引擎（build_plan）：根据用户需求生成完整的行程规划
- 地理枚举（enumerate_scoped_attractions）：按行政分级枚举景点
- 地理聚类（cluster_attractions）：按地理位置聚类分组
- 逐日构建（build_geo_day）：按天分配景点和时间
- 必去景点注入（inject_must_visit_attrs）：确保必去景点进入规划
- 时空规划器（spatial_temporal_plan）：时空联合规划
- 行程质量评估（PlanQualityEvaluator）：评估规划质量
- 大型景区识别（is_large_scenic_area / is_inside_large_scenic_area）
- 景区内部POI去重（dedup_scenic_inner_pois）

使用方式：
    from app.skills.itinerary_planner import build_plan, PlanQualityEvaluator

    # 构建行程规划
    plan = await build_plan(plan_request)

    # 评估行程质量
    evaluator = PlanQualityEvaluator()
    report = evaluator.evaluate(plan)
"""

from .planner import (
    build_plan,
    is_large_scenic_area,
    is_inside_large_scenic_area,
    get_scenic_area_weight_factor,
    dedup_scenic_inner_pois,
)
from .geo_enum import (
    is_in_china,
    is_province,
    enumerate_scoped_attractions,
    scope_attrs,
)
from .cluster import (
    cluster_attractions,
    assign_areas_to_days,
    greedy_group,
    area_label,
)
from .daily_build import (
    build_geo_day,
    geo_plan,
    reorder_day,
    dedup_landmark_day,
    day_focus,
)
from .must_visit import inject_must_visit_attrs
from .spatial_temporal import spatial_temporal_plan, build_spatial_route
from .quality.evaluator import PlanQualityEvaluator, QualityReport, QualityDimension
from .constants import (
    SCOPE_KEYWORDS,
    CLUSTER_MAX_DIST,
    SCOPE_MAX_RANGE,
    CLOSED_MARKERS,
    AUX_FOOD_BAD_NAMES,
    LANDMARK_WORDS,
)
from .utils import (
    is_closed,
    is_landmark,
    rank,
    avg_rank,
    drop_sub_venues,
    daily_inspiration,
    departure_message,
)

__all__ = [
    # 核心规划引擎
    "build_plan",
    # 地理枚举
    "is_in_china",
    "is_province",
    "enumerate_scoped_attractions",
    "scope_attrs",
    # 地理聚类
    "cluster_attractions",
    "assign_areas_to_days",
    "greedy_group",
    "area_label",
    # 逐日构建
    "build_geo_day",
    "geo_plan",
    "reorder_day",
    "dedup_landmark_day",
    "day_focus",
    # 必去景点
    "inject_must_visit_attrs",
    # 时空规划
    "spatial_temporal_plan",
    "build_spatial_route",
    # 质量评估
    "PlanQualityEvaluator",
    "QualityReport",
    "QualityDimension",
    # 大型景区
    "is_large_scenic_area",
    "is_inside_large_scenic_area",
    "get_scenic_area_weight_factor",
    "dedup_scenic_inner_pois",
    # 常量
    "SCOPE_KEYWORDS",
    "CLUSTER_MAX_DIST",
    "SCOPE_MAX_RANGE",
    "CLOSED_MARKERS",
    "AUX_FOOD_BAD_NAMES",
    "LANDMARK_WORDS",
    # 工具函数
    "is_closed",
    "is_landmark",
    "rank",
    "avg_rank",
    "drop_sub_venues",
    "daily_inspiration",
    "departure_message",
]

__version__ = "1.0.0"
__skill_name__ = "itinerary_planner"
__description__ = "行程规划 Skill - 提供完整的旅游行程规划能力"
