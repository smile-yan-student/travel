"""
规则引擎 Skill（Rule Engine Skill）

提供旅行规划的规则引擎，包含参数标准化、参数验证、人群影响、交通灵活性、景点过滤、天数分配、规划审查等功能。

使用方式：
    from app.skills.rule_engine import get_rule_engine, PlanningRuleEngine

    rule_engine = get_rule_engine()

    # 参数标准化（标准化/兜底/收束，不报错，直接修正）
    normalized_params = rule_engine.normalize_params(params_dict)

    # 参数验证（验证/纠错，记录错误、警告和纠错记录）
    validation_result = rule_engine.validate_params(params_dict)
    if validation_result.has_errors:
        # 处理错误
        pass
    corrected_params = validation_result.params

    # 人群影响配置
    group_config = rule_engine.group_engine.get_group_config(group_type)

    # 规划审查
    is_valid, issues = rule_engine.review_plan(day_plans_dict, params_dict)

    # 规划补充
    supplemented_plan = rule_engine.supplement_plan(day_plans_dict, params_dict, candidates)
"""

from .rule_engine import (
    ParameterNormalizer,
    GroupInfluenceEngine,
    TrafficFlexibilityEngine,
    AttractionFilterEngine,
    DayAllocationEngine,
    PlanReviewEngine,
    PlanningRuleEngine,
    get_rule_engine,
)
from .parameter_validator import (
    ParameterValidator,
    ValidationResult,
    get_parameter_validator,
    validate_and_correct_params,
)

__all__ = [
    # 参数处理
    "ParameterNormalizer",
    "ParameterValidator",
    "ValidationResult",
    "get_parameter_validator",
    "validate_and_correct_params",
    # 核心引擎
    "GroupInfluenceEngine",
    "TrafficFlexibilityEngine",
    "AttractionFilterEngine",
    "DayAllocationEngine",
    "PlanReviewEngine",
    # 主入口
    "PlanningRuleEngine",
    "get_rule_engine",
]

__version__ = "1.1.0"
