"""
参数校验与纠错模块（兼容层）。

本模块已迁移到规则引擎Skill（app.skills.rule_engine.parameter_validator）。
此文件保留为兼容层，从规则引擎Skill导入，保持向后兼容性。

新代码请直接从规则引擎Skill导入：
    from app.skills.rule_engine import ParameterValidator, ValidationResult, validate_and_correct_params

或通过规则引擎主类使用：
    from app.skills.rule_engine import get_rule_engine
    rule_engine = get_rule_engine()
    result = rule_engine.validate_params(params)

功能特性：
- 参数校验（验证参数是否符合规则）
- 参数纠错（自动纠正不符合规则的参数）
- 预算档位校验（经济/适中/舒适/豪华）
- 旅行风格校验（美食+人文/自然风光/历史文化/亲子/情侣/摄影等）
- 节奏校验（轻松/适中/紧凑）
- 出行方式校验（自驾/公共交通/骑行/步行/混合）
- 人群类型校验（单人/情侣/家庭/朋友/亲子/老人）
- 时间跨度单位校验（天/周/月/年）
- 天数范围校验（最小1天，最大365天）
- 人数范围校验（最小1人，最大50人）

使用方式：
    from app.services.planner.param_validator import (
        ParameterValidator, ValidationResult, validate_and_correct_params
    )

    # 直接使用函数
    result = validate_and_correct_params(params)
    if result.is_valid:
        corrected_params = result.params
    else:
        errors = result.errors

    # 使用类
    validator = ParameterValidator()
    result = validator.validate(params)

    # 通过规则引擎主类
    from app.skills.rule_engine import get_rule_engine
    rule_engine = get_rule_engine()
    result = rule_engine.validate_params(params)
"""
from app.skills.rule_engine.parameter_validator import (
    MAX_DAYS,
    MAX_TRAVELERS,
    MIN_DAYS,
    MIN_TRAVELERS,
    VALID_BUDGET_LEVELS,
    VALID_GROUP_TYPES,
    VALID_PACES,
    VALID_SPAN_UNITS,
    VALID_STYLES,
    VALID_TRAFFIC_MODES,
    ParameterValidator,
    ValidationResult,
    get_parameter_validator,
    validate_and_correct_params,
)

__all__ = [
    "ParameterValidator",
    "ValidationResult",
    "get_parameter_validator",
    "validate_and_correct_params",
    "VALID_BUDGET_LEVELS",
    "VALID_STYLES",
    "VALID_PACES",
    "VALID_TRAFFIC_MODES",
    "VALID_GROUP_TYPES",
    "VALID_SPAN_UNITS",
    "MIN_DAYS",
    "MAX_DAYS",
    "MIN_TRAVELERS",
    "MAX_TRAVELERS",
]
