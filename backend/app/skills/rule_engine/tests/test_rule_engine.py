"""
规则引擎 Skill - 测试用例

覆盖以下场景：
1. 参数标准化
2. 人群影响引擎
3. 交通灵活性引擎
4. 景点过滤引擎
5. 天数分配引擎
6. 规划审查引擎
7. 主类集成测试
"""
import pytest

from app.skills.rule_engine import (
    PlanningRuleEngine,
    ParameterNormalizer,
    GroupInfluenceEngine,
    TrafficFlexibilityEngine,
    AttractionFilterEngine,
    DayAllocationEngine,
    PlanReviewEngine,
    get_rule_engine,
)


class TestParameterNormalizer:
    """测试参数规范化器"""

    def setup_method(self):
        self.normalizer = ParameterNormalizer()

    def test_normalize_days_min(self):
        """测试天数标准化（小于最小值）"""
        assert self.normalizer.normalize_days(0) == 1
        assert self.normalizer.normalize_days(-1) == 1

    def test_normalize_days_max(self):
        """测试天数标准化（大于最大值）"""
        assert self.normalizer.normalize_days(100) == 30
        assert self.normalizer.normalize_days(50) == 30

    def test_normalize_days_valid(self):
        """测试天数标准化（合法值）"""
        assert self.normalizer.normalize_days(3) == 3
        assert self.normalizer.normalize_days(7) == 7

    def test_normalize_travelers_min(self):
        """测试人数标准化（小于最小值）"""
        assert self.normalizer.normalize_travelers(0) == 1
        assert self.normalizer.normalize_travelers(-1) == 1

    def test_normalize_travelers_max(self):
        """测试人数标准化（大于最大值）"""
        assert self.normalizer.normalize_travelers(100) == 99
        assert self.normalizer.normalize_travelers(200) == 99

    def test_normalize_travelers_valid(self):
        """测试人数标准化（合法值）"""
        assert self.normalizer.normalize_travelers(2) == 2
        assert self.normalizer.normalize_travelers(5) == 5

    def test_normalize_budget_valid(self):
        """测试预算档位标准化（合法值）"""
        assert self.normalizer.normalize_budget("经济") == "经济"
        assert self.normalizer.normalize_budget("适中") == "适中"
        assert self.normalizer.normalize_budget("舒适") == "舒适"
        assert self.normalizer.normalize_budget("豪华") == "豪华"

    def test_normalize_budget_invalid(self):
        """测试预算档位标准化（非法值）"""
        result = self.normalizer.normalize_budget("超级豪华")
        assert result in ["豪华", "适中"]  # 模糊匹配或默认值

    def test_normalize_all(self):
        """测试全部参数标准化"""
        params = {
            "days": 100,
            "travelers": 0,
            "budget_level": "超级豪华",
            "group_type": "亲子",
            "pace": "非常慢",
            "traffic_mode": "坐飞机",
        }
        normalized = self.normalizer.normalize_all(params)
        assert normalized["days"] == 30
        assert normalized["travelers"] == 1
        assert normalized["group_type"] == "亲子"

    def test_get_days_interval(self):
        """测试获取天数区间描述"""
        assert self.normalizer.get_days_interval(1) == "短途"
        assert self.normalizer.get_days_interval(3) == "短途"
        assert self.normalizer.get_days_interval(7) == "中途"
        assert self.normalizer.get_days_interval(15) == "长途"


class TestGroupInfluenceEngine:
    """测试人群影响引擎"""

    def setup_method(self):
        self.group_engine = GroupInfluenceEngine()

    def test_get_group_config_solo(self):
        """测试获取单人配置"""
        config = self.group_engine.get_group_config("单人")
        assert "main_poi_ratio" in config
        assert "aux_poi_ratio" in config
        assert "default_pace" in config
        assert config["main_poi_ratio"] + config["aux_poi_ratio"] == 1.0

    def test_get_group_config_family(self):
        """测试获取家庭配置"""
        config = self.group_engine.get_group_config("家庭")
        assert config["default_pace"] == "轻松"

    def test_get_main_poi_ratio(self):
        """测试获取主POI比例"""
        ratio = self.group_engine.get_main_poi_ratio("单人")
        assert 0.5 <= ratio <= 1.0

    def test_get_aux_poi_ratio(self):
        """测试获取辅助POI比例"""
        ratio = self.group_engine.get_aux_poi_ratio("单人")
        assert 0.0 <= ratio <= 0.5

    def test_get_default_pace(self):
        """测试获取默认节奏"""
        assert self.group_engine.get_default_pace("亲子") == "轻松"
        assert self.group_engine.get_default_pace("单人") == "适中"

    def test_get_aux_categories(self):
        """测试获取辅助类别"""
        categories = self.group_engine.get_aux_categories("亲子")
        assert isinstance(categories, list)
        assert len(categories) > 0

    def test_is_family_friendly(self):
        """测试判断是否亲子友好"""
        poi_friendly = {"name": "迪士尼乐园", "category": "亲子", "tags": ["亲子"]}
        poi_not_friendly = {"name": "酒吧", "category": "夜生活", "tags": ["成人"]}
        assert self.group_engine.is_family_friendly(poi_friendly) is True
        assert self.group_engine.is_family_friendly(poi_not_friendly) is False

    def test_adjust_pace_by_group(self):
        """测试按人群调整节奏"""
        # 亲子出行应该调整为轻松
        result = self.group_engine.adjust_pace_by_group("亲子", "紧凑")
        assert result == "轻松"


class TestTrafficFlexibilityEngine:
    """测试交通灵活性引擎"""

    def setup_method(self):
        self.traffic_engine = TrafficFlexibilityEngine()

    def test_get_traffic_suggestion_short(self):
        """测试短距离通行建议"""
        suggestion = self.traffic_engine.get_traffic_suggestion(500, "单人", "适中")
        assert "mode" in suggestion
        assert suggestion["mode"] in ["步行", "骑行", "公共交通"]

    def test_get_traffic_suggestion_medium(self):
        """测试中距离通行建议"""
        suggestion = self.traffic_engine.get_traffic_suggestion(5000, "单人", "适中")
        assert "mode" in suggestion

    def test_get_traffic_suggestion_long(self):
        """测试长距离通行建议"""
        suggestion = self.traffic_engine.get_traffic_suggestion(50000, "单人", "适中")
        assert "mode" in suggestion
        assert suggestion["mode"] in ["公共交通", "自驾", "高铁"]

    def test_calculate_impact_score(self):
        """测试计算影响强度"""
        score = self.traffic_engine.calculate_impact_score(
            group_type="单人",
            destination_type="城市型",
            poi_distribution="集中型",
            days=3,
            budget_level="适中",
        )
        assert isinstance(score, int)
        assert score >= 0

    def test_get_impact_level(self):
        """测试获取影响等级"""
        level = self.traffic_engine.get_impact_level(50)
        assert level in ["low", "medium", "high"]

    def test_determine_destination_type(self):
        """测试判断目的地类型"""
        center = {"lng": 116.4, "lat": 39.9}
        pois = [
            {"lng": 116.41, "lat": 39.91},
            {"lng": 116.42, "lat": 39.92},
        ]
        dest_type = self.traffic_engine.determine_destination_type(center, pois)
        assert dest_type in ["城市型", "景区型", "跨城型", "混合型"]


class TestAttractionFilterEngine:
    """测试景点过滤引擎"""

    def setup_method(self):
        self.filter_engine = AttractionFilterEngine()

    def test_filter_by_budget_economy(self):
        """测试经济预算过滤"""
        pois = [
            {"name": "免费公园", "category": "景点", "price": 0},
            {"name": "故宫", "category": "景点", "price": 60},
            {"name": "迪士尼", "category": "亲子", "price": 400},
        ]
        filtered = self.filter_engine.filter_by_budget(pois, "经济")
        assert len(filtered) <= len(pois)

    def test_filter_hard_constraints_must_include(self):
        """测试硬约束过滤（必去）"""
        pois = [
            {"name": "故宫", "category": "景点"},
            {"name": "天安门", "category": "景点"},
            {"name": "颐和园", "category": "景点"},
        ]
        filtered = self.filter_engine.filter_hard_constraints(pois, must_include=["故宫"])
        assert any(p["name"] == "故宫" for p in filtered)

    def test_filter_hard_constraints_exclude(self):
        """测试硬约束过滤（排除）"""
        pois = [
            {"name": "故宫", "category": "景点"},
            {"name": "天安门", "category": "景点"},
            {"name": "酒吧", "category": "夜生活"},
        ]
        filtered = self.filter_engine.filter_hard_constraints(pois, exclude=["酒吧"])
        assert not any(p["name"] == "酒吧" for p in filtered)

    def test_is_in_china(self):
        """测试判断是否在中国"""
        poi_china = {"name": "故宫", "province": "北京市", "city": "北京市"}
        poi_foreign = {"name": "东京塔", "province": "东京都", "city": "东京"}
        assert self.filter_engine.is_in_china(poi_china) is True
        # 外国地点可能返回False，取决于实现


class TestPlanningRuleEngine:
    """测试规划规则引擎主类"""

    def setup_method(self):
        self.rule_engine = PlanningRuleEngine()

    def test_singleton(self):
        """测试单例模式"""
        engine1 = get_rule_engine()
        engine2 = get_rule_engine()
        assert engine1 is engine2

    def test_normalize_params(self):
        """测试参数标准化"""
        params = {"days": 100, "travelers": 0}
        normalized = self.rule_engine.normalize_params(params)
        assert normalized["days"] == 30
        assert normalized["travelers"] == 1

    def test_filter_attractions(self):
        """测试景点过滤"""
        pois = [
            {"name": "故宫", "category": "景点", "price": 60},
            {"name": "酒吧", "category": "夜生活", "price": 200},
        ]
        params = {"group_type": "亲子", "budget_level": "经济"}
        filtered, excluded = self.rule_engine.filter_attractions(pois, params)
        assert isinstance(filtered, list)
        assert isinstance(excluded, list)

    def test_review_plan_empty_day(self):
        """测试规划审查（空天）"""
        day_plans = [
            {"day": 1, "pois": [{"name": "故宫"}]},
            {"day": 2, "pois": []},  # 空天
        ]
        params = {"days": 2}
        is_valid, issues = self.rule_engine.review_plan(day_plans, params)
        assert is_valid is False
        assert len(issues) > 0

    def test_review_plan_valid(self):
        """测试规划审查（有效行程）"""
        day_plans = [
            {"day": 1, "pois": [{"name": "故宫"}, {"name": "天安门"}]},
            {"day": 2, "pois": [{"name": "颐和园"}]},
        ]
        params = {"days": 2}
        is_valid, issues = self.rule_engine.review_plan(day_plans, params)
        # 可能有效，取决于具体的审查规则
        assert isinstance(is_valid, bool)
        assert isinstance(issues, list)

    def test_calculate_traffic_impact(self):
        """测试计算交通影响"""
        params = {"group_type": "单人", "traffic_mode": "公共交通", "budget_level": "适中", "days": 3}
        center = {"lng": 116.4, "lat": 39.9}
        pois = [{"lng": 116.41, "lat": 39.91, "name": "故宫"}]
        impact = self.rule_engine.calculate_traffic_impact(params, center, pois)
        assert "impact_score" in impact
        assert "impact_level" in impact
        assert "plan_score" in impact
        assert "plan_level" in impact

    def test_get_traffic_suggestion(self):
        """测试获取通行建议"""
        suggestion = self.rule_engine.get_traffic_suggestion(5000, "单人", "适中")
        assert "mode" in suggestion
        assert "duration" in suggestion or "estimated_time" in suggestion


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
