"""
规则引擎 - 参数验证与纠错模块（Parameter Validation & Correction）

全面校验规划参数的有效性，自动纠正不正确的参数，标准化参数格式。

与 ParameterNormalizer 的职责划分：
- ParameterNormalizer（标准化/兜底/收束）：将参数标准化为合法值，当参数缺失或超出范围时提供兜底值，不报错，直接修正
- ParameterValidator（验证/纠错）：验证参数的有效性，发现并纠正不正确的参数，记录错误、警告和纠错记录，提供详细的验证结果

核心功能：
1. 参数校验：校验所有参数的有效性（目的地、天数、人数、预算、风格、节奏、出行方式等）
2. 参数纠错：自动纠正不正确的参数（如天数超出范围、预算档位不正确等）
3. 参数清洗：清洗参数格式（如目的地名称清洗、兴趣标签过滤等）
4. 结果记录：记录参数校验和纠错的过程，便于排查问题

使用方式：
    from app.skills.rule_engine import ParameterValidator, ValidationResult
    
    validator = ParameterValidator()
    result = validator.validate_and_correct(params)
    if result.has_errors:
        # 处理错误
        pass
    corrected_params = result.params
"""
import re
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

from app.infrastructure import logger as log_mod

_param_logger = log_mod.get_logger("param_validator")


# 合法的参数值定义
VALID_BUDGET_LEVELS = ["经济", "适中", "舒适", "豪华"]
VALID_STYLES = ["综合", "人文", "自然", "美食", "购物", "亲子", "打卡", "摄影", "户外", "历史"]
VALID_PACES = ["轻松", "适中", "紧凑"]
VALID_TRAFFIC_MODES = ["公共交通", "自驾", "骑行", "步行", "混合"]
VALID_GROUP_TYPES = ["单人", "情侣", "朋友", "家庭", "亲子", "商务", "其他"]
VALID_SPAN_UNITS = ["day", "week", "month", "year"]

# 参数范围定义
MIN_DAYS = 1
MAX_DAYS = 30
MIN_TRAVELERS = 1
MAX_TRAVELERS = 99


@dataclass
class ValidationResult:
    """参数校验结果"""
    params: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    corrections: List[str] = field(default_factory=list)
    has_errors: bool = False
    has_corrections: bool = False

    def add_error(self, error: str):
        """添加错误"""
        self.errors.append(error)
        self.has_errors = True

    def add_warning(self, warning: str):
        """添加警告"""
        self.warnings.append(warning)

    def add_correction(self, correction: str):
        """添加纠错记录"""
        self.corrections.append(correction)
        self.has_corrections = True


class ParameterValidator:
    """参数验证与纠错引擎

    职责：验证参数的有效性，发现并纠正不正确的参数，记录验证和纠错过程
    与 ParameterNormalizer 的区别：
    - ParameterNormalizer：标准化/兜底/收束，不报错，直接修正
    - ParameterValidator：验证/纠错，记录错误、警告和纠错记录，提供详细的验证结果
    """

    def __init__(self):
        self.logger = _param_logger

    def validate_and_correct(self, params: Dict[str, Any]) -> ValidationResult:
        """
        校验和纠正规划参数

        Args:
            params: 原始参数字典

        Returns:
            ValidationResult: 校验结果，包含纠正后的参数、错误、警告和纠错记录
        """
        result = ValidationResult(params=params.copy())

        # 依次校验各个参数
        self._validate_destination(result.params, result)
        self._validate_days(result.params, result)
        self._validate_travelers(result.params, result)
        self._validate_budget_level(result.params, result)
        self._validate_style(result.params, result)
        self._validate_pace(result.params, result)
        self._validate_traffic_mode(result.params, result)
        self._validate_group_type(result.params, result)
        self._validate_span_unit(result.params, result)
        self._validate_interests(result.params, result)
        self._validate_poi_lists(result.params, result)

        # 记录校验结果
        if result.has_corrections:
            self.logger.info("params_corrected", extra={"fields": {
                "corrections": result.corrections,
                "original_params": {k: params.get(k) for k in ["destination", "days", "travelers", "budget_level", "style", "pace", "traffic_mode", "group_type"]},
                "corrected_params": {k: result.params.get(k) for k in ["destination", "days", "travelers", "budget_level", "style", "pace", "traffic_mode", "group_type"]},
            }})

        if result.warnings:
            self.logger.warning("params_warnings", extra={"fields": {
                "warnings": result.warnings,
                "params": result.params,
            }})

        if result.has_errors:
            self.logger.error("params_errors", extra={"fields": {
                "errors": result.errors,
                "params": result.params,
            }})

        return result

    def _clean_place_name(self, name: str) -> str:
        """清洗地点名称，去除多余的后缀和空格"""
        if not name:
            return ""
        name = name.strip()
        # 去除常见的后缀（如果是行政区域，保留后缀；如果是景点，去除多余后缀）
        # 这里只做基本的清洗，不做过度处理
        name = re.sub(r"\s+", "", name)
        return name

    def _validate_destination(self, params: Dict[str, Any], result: ValidationResult):
        """校验目的地"""
        destination = params.get("destination", "")
        if not destination or not str(destination).strip():
            result.add_error("目的地不能为空")
            return
        # 清洗目的地名称
        cleaned = self._clean_place_name(str(destination))
        if cleaned != destination:
            params["destination"] = cleaned
            result.add_correction(f"目的地名称清洗: '{destination}' -> '{cleaned}'")
        # 检查目的地长度
        if len(cleaned) > 50:
            result.add_warning(f"目的地名称过长: {len(cleaned)}字符，可能不正确")
        # 检查目的地是否包含无效字符
        if re.search(r"[^\u4e00-\u9fa5A-Za-z0-9·\s]", cleaned):
            result.add_warning(f"目的地名称包含特殊字符: {cleaned}")

    def _validate_days(self, params: Dict[str, Any], result: ValidationResult):
        """校验天数"""
        days = params.get("days")
        if days is None:
            params["days"] = 3
            result.add_correction("天数为空，使用默认值3")
            return
        try:
            days = int(days)
            if days < MIN_DAYS:
                params["days"] = MIN_DAYS
                result.add_correction(f"天数{days}小于最小值{MIN_DAYS}，已修正为{MIN_DAYS}")
            elif days > MAX_DAYS:
                params["days"] = MAX_DAYS
                result.add_correction(f"天数{days}大于最大值{MAX_DAYS}，已修正为{MAX_DAYS}")
            else:
                params["days"] = days
        except (TypeError, ValueError):
            params["days"] = 3
            result.add_correction(f"天数值无效: {days}，使用默认值3")

    def _validate_travelers(self, params: Dict[str, Any], result: ValidationResult):
        """校验人数"""
        travelers = params.get("travelers")
        if travelers is None:
            params["travelers"] = 1
            result.add_correction("人数为空，使用默认值1")
            return
        try:
            travelers = int(travelers)
            if travelers < MIN_TRAVELERS:
                params["travelers"] = MIN_TRAVELERS
                result.add_correction(f"人数{travelers}小于最小值{MIN_TRAVELERS}，已修正为{MIN_TRAVELERS}")
            elif travelers > MAX_TRAVELERS:
                params["travelers"] = MAX_TRAVELERS
                result.add_correction(f"人数{travelers}大于最大值{MAX_TRAVELERS}，已修正为{MAX_TRAVELERS}")
            else:
                params["travelers"] = travelers
        except (TypeError, ValueError):
            params["travelers"] = 1
            result.add_correction(f"人数值无效: {travelers}，使用默认值1")

    def _validate_budget_level(self, params: Dict[str, Any], result: ValidationResult):
        """校验预算档位"""
        budget_level = params.get("budget_level", "")
        if not budget_level:
            params["budget_level"] = "适中"
            result.add_correction("预算档位为空，使用默认值'适中'")
            return
        if budget_level not in VALID_BUDGET_LEVELS:
            # 尝试模糊匹配
            matched = self._fuzzy_match(budget_level, VALID_BUDGET_LEVELS)
            if matched:
                params["budget_level"] = matched
                result.add_correction(f"预算档位'{budget_level}'不合法，模糊匹配为'{matched}'")
            else:
                params["budget_level"] = "适中"
                result.add_correction(f"预算档位'{budget_level}'不合法，使用默认值'适中'")

    def _validate_style(self, params: Dict[str, Any], result: ValidationResult):
        """校验旅行风格"""
        style = params.get("style", "")
        if not style:
            params["style"] = "综合"
            result.add_correction("旅行风格为空，使用默认值'综合'")
            return
        if style not in VALID_STYLES:
            # 尝试模糊匹配
            matched = self._fuzzy_match(style, VALID_STYLES)
            if matched:
                params["style"] = matched
                result.add_correction(f"旅行风格'{style}'不合法，模糊匹配为'{matched}'")
            else:
                params["style"] = "综合"
                result.add_correction(f"旅行风格'{style}'不合法，使用默认值'综合'")

    def _validate_pace(self, params: Dict[str, Any], result: ValidationResult):
        """校验节奏"""
        pace = params.get("pace", "")
        if not pace:
            params["pace"] = "适中"
            result.add_correction("节奏为空，使用默认值'适中'")
            return
        if pace not in VALID_PACES:
            # 尝试模糊匹配
            matched = self._fuzzy_match(pace, VALID_PACES)
            if matched:
                params["pace"] = matched
                result.add_correction(f"节奏'{pace}'不合法，模糊匹配为'{matched}'")
            else:
                params["pace"] = "适中"
                result.add_correction(f"节奏'{pace}'不合法，使用默认值'适中'")

    def _validate_traffic_mode(self, params: Dict[str, Any], result: ValidationResult):
        """校验出行方式"""
        traffic_mode = params.get("traffic_mode", "")
        if not traffic_mode:
            params["traffic_mode"] = "公共交通"
            result.add_correction("出行方式为空，使用默认值'公共交通'")
            return
        if traffic_mode not in VALID_TRAFFIC_MODES:
            # 尝试模糊匹配
            matched = self._fuzzy_match(traffic_mode, VALID_TRAFFIC_MODES)
            if matched:
                params["traffic_mode"] = matched
                result.add_correction(f"出行方式'{traffic_mode}'不合法，模糊匹配为'{matched}'")
            else:
                params["traffic_mode"] = "公共交通"
                result.add_correction(f"出行方式'{traffic_mode}'不合法，使用默认值'公共交通'")

    def _validate_group_type(self, params: Dict[str, Any], result: ValidationResult):
        """校验人群类型"""
        group_type = params.get("group_type", "")
        if not group_type:
            # 根据人数推断人群类型
            travelers = params.get("travelers", 1)
            if travelers == 1:
                group_type = "单人"
            elif travelers == 2:
                group_type = "情侣"  # 默认2人为情侣，用户可以调整
            else:
                group_type = "朋友"
            params["group_type"] = group_type
            result.add_correction(f"人群类型为空，根据人数{travelers}推断为'{group_type}'")
            return
        if group_type not in VALID_GROUP_TYPES:
            # 尝试模糊匹配
            matched = self._fuzzy_match(group_type, VALID_GROUP_TYPES)
            if matched:
                params["group_type"] = matched
                result.add_correction(f"人群类型'{group_type}'不合法，模糊匹配为'{matched}'")
            else:
                params["group_type"] = "其他"
                result.add_correction(f"人群类型'{group_type}'不合法，使用默认值'其他'")

    def _validate_span_unit(self, params: Dict[str, Any], result: ValidationResult):
        """校验时间跨度单位"""
        span_unit = params.get("span_unit", "")
        if not span_unit:
            params["span_unit"] = "day"
            result.add_correction("时间跨度单位为空，使用默认值'day'")
            return
        if span_unit not in VALID_SPAN_UNITS:
            params["span_unit"] = "day"
            result.add_correction(f"时间跨度单位'{span_unit}'不合法，使用默认值'day'")

    def _validate_interests(self, params: Dict[str, Any], result: ValidationResult):
        """校验兴趣标签"""
        interests = params.get("interests", [])
        if not interests:
            params["interests"] = []
            return
        if not isinstance(interests, list):
            params["interests"] = []
            result.add_correction(f"兴趣标签不是列表类型，已重置为空列表")
            return
        # 过滤掉无效的兴趣标签
        valid_interests = []
        for interest in interests:
            if isinstance(interest, str) and 1 <= len(interest) <= 20:
                valid_interests.append(interest.strip())
        if len(valid_interests) != len(interests):
            params["interests"] = valid_interests
            result.add_correction(f"过滤了{len(interests) - len(valid_interests)}个无效的兴趣标签")

    def _validate_poi_lists(self, params: Dict[str, Any], result: ValidationResult):
        """校验必去和排除的POI列表"""
        for param_name in ["must_include_poi", "exclude_poi"]:
            pois = params.get(param_name, [])
            if not pois:
                params[param_name] = []
                continue
            if not isinstance(pois, list):
                params[param_name] = []
                result.add_correction(f"{param_name}不是列表类型，已重置为空列表")
                continue
            # 过滤掉无效的POI名称
            valid_pois = []
            for poi in pois:
                if isinstance(poi, str) and 1 <= len(poi) <= 50:
                    valid_pois.append(poi.strip())
            if len(valid_pois) != len(pois):
                params[param_name] = valid_pois
                result.add_correction(f"过滤了{len(pois) - len(valid_pois)}个无效的POI名称（{param_name}）")

    def _fuzzy_match(self, value: str, valid_values: List[str]) -> Optional[str]:
        """
        模糊匹配：尝试在合法值列表中找到匹配的值

        Args:
            value: 待匹配的值
            valid_values: 合法值列表

        Returns:
            Optional[str]: 匹配到的值，如果没有匹配到则返回None
        """
        if not value:
            return None
        value_str = str(value)
        for valid in valid_values:
            if valid in value_str or value_str in valid:
                return valid
        return None


# 全局单例
_validator = None


def get_parameter_validator() -> ParameterValidator:
    """获取参数验证器单例"""
    global _validator
    if _validator is None:
        _validator = ParameterValidator()
    return _validator


# 兼容函数：保持与原param_validator.py的接口兼容
def validate_and_correct_params(params: Dict[str, Any]) -> ValidationResult:
    """
    校验和纠正规划参数（兼容函数）

    Args:
        params: 原始参数字典

    Returns:
        ValidationResult: 校验结果
    """
    return get_parameter_validator().validate_and_correct(params)
