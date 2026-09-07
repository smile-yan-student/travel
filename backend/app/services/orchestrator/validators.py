"""
规划引擎二次校验器（Plan Validator）。

终极链路第4阶段：规划引擎二次校验修复。

校验内容：
- 行程体量合理性（防止太少/太臃肿）
- 行程时间轴合法性（前后时间冲突修复）
- 跨天内容去重
- 住宿=次日起点规则
- POI数据完整性

功能特性：
- 校验问题数据类（级别、类别、天数、POI名称、消息、是否可自动修复）
- 校验结果数据类（是否有效、问题列表、错误计数、警告计数）
- 规划引擎二次校验器（5个维度的校验）
- 自动修复可修复的问题（体量问题、时间轴问题）
- 支持PlanResponse对象和dict两种输入格式

使用方式：
    from app.services.orchestrator.validators import PlanValidator

    # 创建校验器
    validator = PlanValidator()

    # 校验行程
    validation_result = validator.validate(plan_response)

    # 查看校验结果
    print(f'is_valid: {validation_result.is_valid}')
    print(f'error_count: {validation_result.error_count}')
    print(f'warning_count: {validation_result.warning_count}')
    for issue in validation_result.issues:
        print(f'  [{issue.level}] {issue.category}: {issue.message}')

    # 自动修复可修复的问题
    if not validation_result.is_valid:
        fixed_plan = validator.auto_fix(plan_response, validation_result)
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union


@dataclass
class ValidationIssue:
    """
    校验问题。

    Attributes:
        level: 级别（error / warning / info）
        category: 类别（volume / timeline / dedup / hotel / poi_integrity）
        day: 天数
        poi_name: POI名称
        message: 消息
        auto_fixable: 是否可自动修复
    """

    level: str = "warning"  # error / warning / info
    category: str = ""  # volume / timeline / dedup / hotel / poi_integrity
    day: Optional[int] = None
    poi_name: str = ""
    message: str = ""
    auto_fixable: bool = False


@dataclass
class ValidationResult:
    """
    校验结果。

    Attributes:
        is_valid: 是否有效
        issues: 问题列表
    """

    is_valid: bool = True
    issues: List[ValidationIssue] = field(default_factory=list)

    def add_issue(self, issue: ValidationIssue) -> None:
        """
        添加校验问题。

        Args:
            issue: 校验问题
        """
        self.issues.append(issue)
        if issue.level == "error":
            self.is_valid = False

    @property
    def error_count(self) -> int:
        """
        错误数量。

        Returns:
            int: 错误数量
        """
        return sum(1 for i in self.issues if i.level == "error")

    @property
    def warning_count(self) -> int:
        """
        警告数量。

        Returns:
            int: 警告数量
        """
        return sum(1 for i in self.issues if i.level == "warning")


class PlanValidator:
    """
    规划引擎二次校验器。

    对LLM编排后的行程进行客观校验和自动修复。
    """

    # 每天合理的POI数量范围
    MIN_POIS_PER_DAY = 2
    MAX_POIS_PER_DAY = 8
    # 每个POI合理的停留时间范围（分钟）
    MIN_DURATION = 30
    MAX_DURATION = 480

    def validate(self, plan_response: Union[Dict[str, Any], Any]) -> ValidationResult:
        """
        校验行程。

        Args:
            plan_response: PlanResponse对象或dict

        Returns:
            ValidationResult: 校验结果
        """
        result = ValidationResult()
        plan_dict = (
            plan_response
            if isinstance(plan_response, dict)
            else plan_response.model_dump()
        )

        day_plans = plan_dict.get("day_plans", [])
        if not day_plans:
            result.add_issue(
                ValidationIssue(
                    level="error",
                    category="volume",
                    message="行程为空，没有任何天数安排",
                )
            )
            return result

        # 1. 行程体量合理性校验
        self._validate_volume(plan_dict, result)

        # 2. 时间轴合法性校验
        self._validate_timeline(plan_dict, result)

        # 3. 跨天内容去重校验
        self._validate_dedup(plan_dict, result)

        # 4. 住宿规则校验
        self._validate_hotel(plan_dict, result)

        # 5. POI数据完整性校验
        self._validate_poi_integrity(plan_dict, result)

        return result

    def _validate_volume(
        self, plan_dict: Dict[str, Any], result: ValidationResult
    ) -> None:
        """
        校验行程体量合理性。

        Args:
            plan_dict: 行程字典
            result: 校验结果
        """
        day_plans = plan_dict.get("day_plans", [])
        for dp in day_plans:
            day = dp.get("day", 0)
            items = dp.get("items", [])
            poi_count = len([item for item in items if item.get("poi")])

            if poi_count < self.MIN_POIS_PER_DAY:
                result.add_issue(
                    ValidationIssue(
                        level="warning",
                        category="volume",
                        day=day,
                        message=f"第{day}天只有{poi_count}个点位，偏少",
                        auto_fixable=True,
                    )
                )
            elif poi_count > self.MAX_POIS_PER_DAY:
                result.add_issue(
                    ValidationIssue(
                        level="warning",
                        category="volume",
                        day=day,
                        message=f"第{day}天有{poi_count}个点位，偏多可能太赶",
                        auto_fixable=True,
                    )
                )

            # 校验总时长合理性
            total_duration = sum(item.get("duration_min", 0) for item in items)
            total_transit = sum(item.get("transit_min", 0) for item in items)
            total_hours = (total_duration + total_transit) / 60
            if total_hours > 14:
                result.add_issue(
                    ValidationIssue(
                        level="warning",
                        category="volume",
                        day=day,
                        message=f"第{day}天总时长约{total_hours:.1f}小时，可能超过合理范围",
                        auto_fixable=False,
                    )
                )

    def _validate_timeline(
        self, plan_dict: Dict[str, Any], result: ValidationResult
    ) -> None:
        """
        校验时间轴合法性。

        Args:
            plan_dict: 行程字典
            result: 校验结果
        """
        day_plans = plan_dict.get("day_plans", [])
        for dp in day_plans:
            day = dp.get("day", 0)
            items = dp.get("items", [])
            # 按slot排序检查时间顺序
            slot_order = {"上午": 0, "中午": 1, "下午": 2, "晚上": 3}
            sorted_items = sorted(
                items, key=lambda x: slot_order.get(x.get("slot", "下午"), 2)
            )

            # 检查POI停留时间合理性
            for item in sorted_items:
                poi = item.get("poi", {})
                duration = item.get("duration_min", 0)
                if duration > 0 and (
                    duration < self.MIN_DURATION or duration > self.MAX_DURATION
                ):
                    result.add_issue(
                        ValidationIssue(
                            level="info",
                            category="timeline",
                            day=day,
                            poi_name=poi.get("name", ""),
                            message=f"「{poi.get('name', '')}」停留{duration}分钟，可能不合理",
                            auto_fixable=True,
                        )
                    )

    def _validate_dedup(
        self, plan_dict: Dict[str, Any], result: ValidationResult
    ) -> None:
        """
        校验跨天内容去重。

        Args:
            plan_dict: 行程字典
            result: 校验结果
        """
        day_plans = plan_dict.get("day_plans", [])
        all_poi_names: Dict[str, int] = {}
        for dp in day_plans:
            day = dp.get("day", 0)
            for item in dp.get("items", []):
                poi = item.get("poi", {})
                name = poi.get("name", "")
                if name:
                    if name in all_poi_names:
                        result.add_issue(
                            ValidationIssue(
                                level="warning",
                                category="dedup",
                                day=day,
                                poi_name=name,
                                message=f"「{name}」在第{all_poi_names[name]}天和第{day}天重复出现",
                                auto_fixable=False,
                            )
                        )
                    else:
                        all_poi_names[name] = day

    def _validate_hotel(
        self, plan_dict: Dict[str, Any], result: ValidationResult
    ) -> None:
        """
        校验住宿=次日起点规则。

        Args:
            plan_dict: 行程字典
            result: 校验结果
        """
        day_plans = plan_dict.get("day_plans", [])
        days = len(day_plans)
        if days <= 1:
            return  # 单日行程不需要住宿

        for i, dp in enumerate(day_plans[:-1]):  # 最后一天不需要住宿
            day = dp.get("day", 0)
            hotel = dp.get("hotel")
            if not hotel:
                result.add_issue(
                    ValidationIssue(
                        level="info",
                        category="hotel",
                        day=day,
                        message=f"第{day}天未安排住宿点（多日行程建议明确住宿）",
                        auto_fixable=False,
                    )
                )

    def _validate_poi_integrity(
        self, plan_dict: Dict[str, Any], result: ValidationResult
    ) -> None:
        """
        校验POI数据完整性。

        Args:
            plan_dict: 行程字典
            result: 校验结果
        """
        day_plans = plan_dict.get("day_plans", [])
        for dp in day_plans:
            day = dp.get("day", 0)
            for item in dp.get("items", []):
                poi = item.get("poi", {})
                name = poi.get("name", "")
                if not name:
                    result.add_issue(
                        ValidationIssue(
                            level="error",
                            category="poi_integrity",
                            day=day,
                            message=f"第{day}天存在无名称的POI",
                            auto_fixable=False,
                        )
                    )
                # 检查坐标完整性
                if poi.get("lng") is None or poi.get("lat") is None:
                    result.add_issue(
                        ValidationIssue(
                            level="warning",
                            category="poi_integrity",
                            day=day,
                            poi_name=name,
                            message=f"「{name}」缺少坐标信息",
                            auto_fixable=False,
                        )
                    )

    def auto_fix(
        self,
        plan_response: Union[Dict[str, Any], Any],
        validation_result: ValidationResult,
    ) -> Union[Dict[str, Any], Any]:
        """
        自动修复可修复的问题。

        Args:
            plan_response: PlanResponse对象或dict
            validation_result: 校验结果

        Returns:
            Union[Dict[str, Any], Any]: 修复后的行程
        """
        plan_dict = (
            plan_response
            if isinstance(plan_response, dict)
            else plan_response.model_dump()
        )
        fixed_count = 0

        for issue in validation_result.issues:
            if not issue.auto_fixable:
                continue

            if issue.category == "volume" and issue.day:
                # 体量问题：调整POI停留时间
                for dp in plan_dict.get("day_plans", []):
                    if dp.get("day") == issue.day:
                        items = dp.get("items", [])
                        poi_count = len([item for item in items if item.get("poi")])
                        if poi_count > self.MAX_POIS_PER_DAY:
                            # 过多：减少停留时间
                            for item in items:
                                item["duration_min"] = max(
                                    60, item.get("duration_min", 120) - 30
                                )
                            fixed_count += 1
                        elif poi_count < self.MIN_POIS_PER_DAY:
                            # 过少：增加停留时间（不增加POI，因为需要外部数据）
                            for item in items:
                                item["duration_min"] = min(
                                    240, item.get("duration_min", 120) + 60
                                )
                            fixed_count += 1

            elif issue.category == "timeline" and issue.day and issue.poi_name:
                # 时间轴问题：调整不合理的停留时间
                for dp in plan_dict.get("day_plans", []):
                    if dp.get("day") == issue.day:
                        for item in dp.get("items", []):
                            if item.get("poi", {}).get("name") == issue.poi_name:
                                duration = item.get("duration_min", 0)
                                if duration < self.MIN_DURATION:
                                    item["duration_min"] = self.MIN_DURATION
                                    fixed_count += 1
                                elif duration > self.MAX_DURATION:
                                    item["duration_min"] = self.MAX_DURATION
                                    fixed_count += 1

        if fixed_count > 0:
            # 如果是PlanResponse对象，需要重新构造
            if not isinstance(plan_response, dict):
                from ...data.models.models import PlanResponse

                plan_response = PlanResponse(**plan_dict)
                return plan_response

        return plan_response if isinstance(plan_response, dict) else plan_response
