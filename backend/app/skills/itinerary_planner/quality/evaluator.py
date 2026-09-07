"""
规划质量评估体系（Plan Quality Evaluation System）。

量化评估规划结果的质量，找出问题所在，为持续优化提供数据支撑。

评估维度：
1. 景点覆盖率（Attraction Coverage）：目的地的主要景点是否都在规划中
2. 行程合理性（Itinerary Reasonableness）：每天的景点数量、游览时间、交通时间是否合理
3. 地理聚类质量（Geo Clustering Quality）：同一天的景点是否地理上接近
4. 时间安排合理性（Time Scheduling Reasonableness）：开放时间、用餐时间、休息时间是否考虑
5. 用户需求匹配度（User Demand Matching）：是否符合用户的出行风格、预算、人群等需求

功能特性：
- 质量维度评估结果数据类（QualityDimension）：名称、得分、权重、问题列表、详细信息
- 规划质量评估报告数据类（QualityReport）：综合得分、各维度得分、问题汇总、优化建议、评估时间
- 规划质量评估器（PlanQualityEvaluator）：五个维度的评估、综合得分计算、优化建议生成
- 景点覆盖率评估：主要景点覆盖、景点数量、重复景点检测
- 行程合理性评估：每天景点数量、多天之间的平衡性
- 地理聚类质量评估：同一天内景点之间的距离
- 时间安排合理性评估：时间段安排、游览时长、用餐安排
- 用户需求匹配度评估：天数匹配、目的地匹配、预算匹配、出行风格匹配
- 优化建议生成：根据评估结果生成针对性的优化建议
- Haversine距离计算：计算两个经纬度坐标之间的距离（公里）

使用方式：
    from app.services.planner.quality.evaluator import PlanQualityEvaluator

    # 创建评估器
    evaluator = PlanQualityEvaluator()

    # 评估规划结果的质量
    report = evaluator.evaluate(plan_response, plan_request, major_attractions)

    # 打印摘要
    print(report.summary())

    # 转换为字典
    report_dict = report.to_dict()
"""
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class QualityDimension:
    """质量维度评估结果"""
    name: str
    score: float  # 0-100分
    weight: float  # 权重，总和为1
    issues: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "score": round(self.score, 2),
            "weight": self.weight,
            "issues": self.issues,
            "details": self.details,
        }


@dataclass
class QualityReport:
    """规划质量评估报告"""
    overall_score: float  # 综合得分，0-100分
    dimensions: List[QualityDimension] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)  # 所有问题汇总
    suggestions: List[str] = field(default_factory=list)  # 优化建议
    evaluated_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def summary(self) -> str:
        """生成摘要文本"""
        lines = [
            f"=== 规划质量评估报告 ===",
            f"综合得分: {self.overall_score:.1f}/100",
            f"评估时间: {self.evaluated_at}",
            "",
            "各维度得分:",
        ]
        for dim in self.dimensions:
            lines.append(f"  - {dim.name}: {dim.score:.1f}分 (权重{dim.weight*100:.0f}%)")
            for issue in dim.issues[:3]:
                lines.append(f"    ⚠️  {issue}")

        if self.suggestions:
            lines.append("")
            lines.append("优化建议:")
            for i, sug in enumerate(self.suggestions[:5], 1):
                lines.append(f"  {i}. {sug}")

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_score": round(self.overall_score, 2),
            "dimensions": [d.to_dict() for d in self.dimensions],
            "issues": self.issues,
            "suggestions": self.suggestions,
            "evaluated_at": self.evaluated_at,
        }


class PlanQualityEvaluator:
    """规划质量评估器"""

    def __init__(self):
        # 各维度权重（总和为1）
        self.weights = {
            "attraction_coverage": 0.25,  # 景点覆盖率
            "itinerary_reasonableness": 0.20,  # 行程合理性
            "geo_clustering": 0.20,  # 地理聚类质量
            "time_scheduling": 0.15,  # 时间安排合理性
            "user_demand_matching": 0.20,  # 用户需求匹配度
        }

    def evaluate(
        self,
        plan: Dict[str, Any],
        request: Optional[Dict[str, Any]] = None,
        major_attractions: Optional[List[Dict[str, Any]]] = None,
    ) -> QualityReport:
        """
        评估规划结果的质量

        Args:
            plan: 规划结果（PlanResponse的dict形式）
            request: 规划请求参数
            major_attractions: 目的地的主要景点列表（用于覆盖率评估）

        Returns:
            QualityReport: 质量评估报告
        """
        dimensions = []

        # 1. 景点覆盖率评估
        coverage_dim = self._evaluate_attraction_coverage(plan, major_attractions)
        dimensions.append(coverage_dim)

        # 2. 行程合理性评估
        itinerary_dim = self._evaluate_itinerary_reasonableness(plan)
        dimensions.append(itinerary_dim)

        # 3. 地理聚类质量评估
        clustering_dim = self._evaluate_geo_clustering(plan)
        dimensions.append(clustering_dim)

        # 4. 时间安排合理性评估
        time_dim = self._evaluate_time_scheduling(plan)
        dimensions.append(time_dim)

        # 5. 用户需求匹配度评估
        demand_dim = self._evaluate_user_demand_matching(plan, request)
        dimensions.append(demand_dim)

        # 计算综合得分（加权平均）
        overall_score = sum(
            dim.score * self.weights.get(dim.name, 0)
            for dim in dimensions
        )

        # 汇总所有问题
        all_issues = []
        for dim in dimensions:
            all_issues.extend(dim.issues)

        # 生成优化建议
        suggestions = self._generate_suggestions(dimensions, plan, request)

        return QualityReport(
            overall_score=overall_score,
            dimensions=dimensions,
            issues=all_issues,
            suggestions=suggestions,
        )

    def _evaluate_attraction_coverage(
        self,
        plan: Dict[str, Any],
        major_attractions: Optional[List[Dict[str, Any]]] = None,
    ) -> QualityDimension:
        """评估景点覆盖率：目的地的主要景点是否都在规划中"""
        issues = []
        details = {}

        # 获取规划中的所有景点名称
        plan_pois = plan.get("all_pois", []) or []
        plan_names = {p.get("name", "") for p in plan_pois if p.get("name")}

        # 统计景点类POI数量
        attraction_pois = [p for p in plan_pois if p.get("category") == "景点"]
        details["total_pois"] = len(plan_pois)
        details["attraction_pois"] = len(attraction_pois)

        score = 50.0  # 基础分

        # 如果有主要景点列表，计算覆盖率
        if major_attractions:
            major_names = {a.get("name", "") for a in major_attractions if a.get("name")}
            covered = major_names & plan_names
            coverage_rate = len(covered) / len(major_names) if major_names else 0
            score = coverage_rate * 100
            details["major_attractions_count"] = len(major_names)
            details["covered_count"] = len(covered)
            details["coverage_rate"] = round(coverage_rate, 2)

            missing = major_names - plan_names
            if missing:
                issues.append(f"主要景点未覆盖: {', '.join(list(missing)[:5])}")
                if len(missing) > 5:
                    issues.append(f"还有{len(missing)-5}个主要景点未覆盖")
        else:
            # 没有主要景点列表，根据景点数量评估
            if len(attraction_pois) == 0:
                score = 0
                issues.append("规划中没有景点类POI")
            elif len(attraction_pois) < 3:
                score = 30
                issues.append(f"景点数量过少: 只有{len(attraction_pois)}个景点")
            elif len(attraction_pois) < 5:
                score = 60
                issues.append(f"景点数量偏少: {len(attraction_pois)}个景点")
            else:
                score = 80

        # 检查是否有重复景点
        name_counts = {}
        for p in plan_pois:
            name = p.get("name", "")
            if name:
                name_counts[name] = name_counts.get(name, 0) + 1
        duplicates = {name: count for name, count in name_counts.items() if count > 1}
        if duplicates:
            score -= 10
            issues.append(f"存在重复景点: {', '.join(list(duplicates.keys())[:3])}")
            details["duplicate_attractions"] = duplicates

        return QualityDimension(
            name="attraction_coverage",
            score=max(0, min(100, score)),
            weight=self.weights["attraction_coverage"],
            issues=issues,
            details=details,
        )

    def _evaluate_itinerary_reasonableness(self, plan: Dict[str, Any]) -> QualityDimension:
        """评估行程合理性：每天的景点数量、游览时间是否合理"""
        issues = []
        details = {}

        day_plans = plan.get("day_plans", []) or []
        details["total_days"] = len(day_plans)

        if not day_plans:
            return QualityDimension(
                name="itinerary_reasonableness",
                score=0,
                weight=self.weights["itinerary_reasonableness"],
                issues=["没有行程安排"],
                details=details,
            )

        score = 80.0
        day_item_counts = []

        for i, day in enumerate(day_plans, 1):
            items = day.get("items", []) or []
            item_count = len(items)
            day_item_counts.append(item_count)
            day_label = day.get("date_label", f"第{i}天")

            # 每天景点数量评估：3-5个为合理
            if item_count == 0:
                score -= 20
                issues.append(f"{day_label}没有安排任何景点")
            elif item_count < 2:
                score -= 10
                issues.append(f"{day_label}景点过少: 只有{item_count}个")
            elif item_count > 6:
                score -= 10
                issues.append(f"{day_label}景点过多: {item_count}个，可能过于紧凑")

        # 多天之间的平衡性评估
        if len(day_item_counts) > 1:
            max_count = max(day_item_counts)
            min_count = min(day_item_counts)
            balance_diff = max_count - min_count
            details["max_day_items"] = max_count
            details["min_day_items"] = min_count
            details["balance_diff"] = balance_diff

            if balance_diff > 3:
                score -= 10
                issues.append(f"行程安排不均衡: 最多{max_count}个，最少{min_count}个，相差{balance_diff}个")

        details["day_item_counts"] = day_item_counts
        details["avg_items_per_day"] = round(sum(day_item_counts) / len(day_item_counts), 1)

        return QualityDimension(
            name="itinerary_reasonableness",
            score=max(0, min(100, score)),
            weight=self.weights["itinerary_reasonableness"],
            issues=issues,
            details=details,
        )

    def _evaluate_geo_clustering(self, plan: Dict[str, Any]) -> QualityDimension:
        """评估地理聚类质量：同一天的景点是否地理上接近"""
        issues = []
        details = {}

        day_plans = plan.get("day_plans", []) or []

        if not day_plans:
            return QualityDimension(
                name="geo_clustering",
                score=0,
                weight=self.weights["geo_clustering"],
                issues=["没有行程安排，无法评估聚类质量"],
                details=details,
            )

        score = 70.0
        all_day_distances = []

        for i, day in enumerate(day_plans, 1):
            items = day.get("items", []) or []
            day_label = day.get("date_label", f"第{i}天")

            # 计算同一天内景点之间的距离
            if len(items) >= 2:
                coords = []
                for item in items:
                    poi = item.get("poi", {}) or item
                    lng = poi.get("lng") or poi.get("longitude")
                    lat = poi.get("lat") or poi.get("latitude")
                    if lng and lat:
                        coords.append((float(lng), float(lat)))

                if len(coords) >= 2:
                    day_distances = []
                    for j in range(len(coords) - 1):
                        dist = self._haversine_distance(coords[j], coords[j + 1])
                        day_distances.append(dist)

                    avg_dist = sum(day_distances) / len(day_distances)
                    max_dist = max(day_distances)
                    all_day_distances.extend(day_distances)

                    details[f"day_{i}_avg_distance_km"] = round(avg_dist, 2)
                    details[f"day_{i}_max_distance_km"] = round(max_dist, 2)

                    # 同一天内平均距离评估：5公里以内为合理
                    if avg_dist > 20:
                        score -= 10
                        issues.append(f"{day_label}景点过于分散: 平均距离{avg_dist:.1f}公里")
                    elif avg_dist > 10:
                        score -= 5
                        issues.append(f"{day_label}景点稍显分散: 平均距离{avg_dist:.1f}公里")

        if all_day_distances:
            details["overall_avg_distance_km"] = round(sum(all_day_distances) / len(all_day_distances), 2)
            details["overall_max_distance_km"] = round(max(all_day_distances), 2)

        return QualityDimension(
            name="geo_clustering",
            score=max(0, min(100, score)),
            weight=self.weights["geo_clustering"],
            issues=issues,
            details=details,
        )

    def _evaluate_time_scheduling(self, plan: Dict[str, Any]) -> QualityDimension:
        """评估时间安排合理性：开放时间、用餐时间、休息时间是否考虑"""
        issues = []
        details = {}

        day_plans = plan.get("day_plans", []) or []

        if not day_plans:
            return QualityDimension(
                name="time_scheduling",
                score=0,
                weight=self.weights["time_scheduling"],
                issues=["没有行程安排，无法评估时间安排"],
                details=details,
            )

        score = 60.0  # 基础分，时间安排通常需要更多信息才能准确评估

        has_time_slots = False
        has_duration = False
        has_meal_times = False

        for i, day in enumerate(day_plans, 1):
            items = day.get("items", []) or []
            day_label = day.get("date_label", f"第{i}天")

            for item in items:
                # 检查是否有时间段安排
                if item.get("start_time") or item.get("time_slot") or item.get("period"):
                    has_time_slots = True
                # 检查是否有游览时长
                if item.get("duration") or item.get("visit_duration") or item.get("stay_time"):
                    has_duration = True
                # 检查是否有用餐安排
                category = item.get("category", "") or (item.get("poi", {}) or {}).get("category", "")
                if category in ["美食", "餐饮", "餐厅"]:
                    has_meal_times = True

        details["has_time_slots"] = has_time_slots
        details["has_duration"] = has_duration
        details["has_meal_times"] = has_meal_times

        if has_time_slots:
            score += 15
        else:
            issues.append("缺少具体的时间段安排（上午/下午/晚上）")

        if has_duration:
            score += 15
        else:
            issues.append("缺少景点游览时长建议")

        if has_meal_times:
            score += 10
        else:
            issues.append("缺少用餐时间安排")

        return QualityDimension(
            name="time_scheduling",
            score=max(0, min(100, score)),
            weight=self.weights["time_scheduling"],
            issues=issues,
            details=details,
        )

    def _evaluate_user_demand_matching(
        self,
        plan: Dict[str, Any],
        request: Optional[Dict[str, Any]] = None,
    ) -> QualityDimension:
        """评估用户需求匹配度：是否符合用户的出行风格、预算、人群等需求"""
        issues = []
        details = {}

        if not request:
            return QualityDimension(
                name="user_demand_matching",
                score=50,
                weight=self.weights["user_demand_matching"],
                issues=["缺少请求参数，无法评估需求匹配度"],
                details=details,
            )

        score = 70.0

        # 1. 天数匹配
        requested_days = request.get("days", 0)
        actual_days = len(plan.get("day_plans", []))
        details["requested_days"] = requested_days
        details["actual_days"] = actual_days

        if requested_days and actual_days:
            if actual_days < requested_days:
                score -= 20
                issues.append(f"天数不匹配: 请求{requested_days}天，实际只规划了{actual_days}天")
            elif actual_days > requested_days + 1:
                score -= 10
                issues.append(f"天数超出: 请求{requested_days}天，实际规划了{actual_days}天")

        # 2. 目的地匹配
        requested_destination = request.get("destination", "")
        actual_destination = plan.get("destination", "")
        details["requested_destination"] = requested_destination
        details["actual_destination"] = actual_destination

        if requested_destination and actual_destination:
            if requested_destination not in actual_destination and actual_destination not in requested_destination:
                score -= 30
                issues.append(f"目的地不匹配: 请求「{requested_destination}」，实际「{actual_destination}」")

        # 3. 预算匹配（粗略评估）
        requested_budget = request.get("budget_level", "")
        actual_budget = plan.get("total_budget", 0)
        details["requested_budget_level"] = requested_budget
        details["actual_total_budget"] = actual_budget

        if requested_budget and actual_budget and actual_days:
            avg_daily_budget = actual_budget / actual_days
            details["avg_daily_budget"] = round(avg_daily_budget, 0)

            # 粗略的预算区间评估
            if requested_budget == "经济" and avg_daily_budget > 500:
                score -= 10
                issues.append(f"预算偏高: 经济档请求，日均预算{avg_daily_budget:.0f}元")
            elif requested_budget == "舒适" and avg_daily_budget < 300:
                score -= 5
                issues.append(f"预算偏低: 舒适档请求，日均预算{avg_daily_budget:.0f}元")

        # 4. 出行风格匹配（需要更多信息才能准确评估）
        requested_style = request.get("style", "")
        details["requested_style"] = requested_style
        if requested_style:
            # 这里可以根据风格评估景点类型的匹配度
            # 暂时只记录，不扣分
            pass

        return QualityDimension(
            name="user_demand_matching",
            score=max(0, min(100, score)),
            weight=self.weights["user_demand_matching"],
            issues=issues,
            details=details,
        )

    def _generate_suggestions(
        self,
        dimensions: List[QualityDimension],
        plan: Dict[str, Any],
        request: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """根据评估结果生成优化建议"""
        suggestions = []

        # 按得分排序，找出最需要优化的维度
        sorted_dims = sorted(dimensions, key=lambda d: d.score)

        for dim in sorted_dims[:3]:
            if dim.score < 60:
                if dim.name == "attraction_coverage":
                    suggestions.append("增加主要景点库的覆盖范围，确保目的地的知名景点都在规划中")
                    suggestions.append("优化POI搜索策略，扩大搜索范围到所属的地级市")
                elif dim.name == "itinerary_reasonableness":
                    suggestions.append("优化逐日分配算法，确保每天的景点数量在3-5个之间")
                    suggestions.append("增加多天之间的平衡性调整，避免一天太多一天太少")
                elif dim.name == "geo_clustering":
                    suggestions.append("改进聚类算法，考虑景点之间的实际交通时间")
                    suggestions.append("以主POI为聚类中心，子POI自动归入主POI的簇")
                elif dim.name == "time_scheduling":
                    suggestions.append("增加景点的开放时间和建议游览时长信息")
                    suggestions.append("优化时间安排算法，合理分配上午、下午、晚上的景点")
                elif dim.name == "user_demand_matching":
                    suggestions.append("确保规划天数与用户请求天数一致，景点不足时从周边城市补充")
                    suggestions.append("增加预算控制算法，根据用户的预算档位调整行程")

        # 通用建议
        if not suggestions:
            suggestions.append("规划质量良好，可以继续优化细节体验")

        return suggestions

    @staticmethod
    def _haversine_distance(coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
        """计算两个经纬度坐标之间的距离（公里）"""
        R = 6371  # 地球半径（公里）

        lng1, lat1 = coord1
        lng2, lat2 = coord2

        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lng = math.radians(lng2 - lng1)

        a = math.sin(delta_lat / 2) ** 2 + \
            math.cos(lat1_rad) * math.cos(lat2_rad) * \
            math.sin(delta_lng / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c
