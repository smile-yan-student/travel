"""
意图识别Skill - 测试用例

覆盖以下场景：
1. 行程规划意图识别
2. 天气查询意图识别
3. POI搜索意图识别
4. 普通对话意图识别
5. 只有目的地没有天数的情况
6. 调整指令识别
7. 参数提取准确性
8. 置信度校验
9. 规则兜底功能
10. 异常处理
"""
import pytest
import asyncio

from app.skills.intent_recognition import (
    IntentRecognizer,
    RuleIntentRecognizer,
    LLMIntentRecognizer,
    IntentType,
    IntentResult,
    get_intent_recognizer,
)


class TestIntentType:
    """测试意图类型枚举"""

    def test_intent_type_values(self):
        """测试意图类型枚举值"""
        assert IntentType.PLAN.value == "plan"
        assert IntentType.WEATHER.value == "weather"
        assert IntentType.POI.value == "poi"
        assert IntentType.CHAT.value == "chat"

    def test_from_string_valid(self):
        """测试从字符串创建意图类型（合法值）"""
        assert IntentType.from_string("plan") == IntentType.PLAN
        assert IntentType.from_string("weather") == IntentType.WEATHER
        assert IntentType.from_string("poi") == IntentType.POI
        assert IntentType.from_string("chat") == IntentType.CHAT

    def test_from_string_invalid(self):
        """测试从字符串创建意图类型（非法值）"""
        assert IntentType.from_string("invalid") == IntentType.CHAT
        assert IntentType.from_string("") == IntentType.CHAT
        assert IntentType.from_string(None) == IntentType.CHAT


class TestIntentResult:
    """测试意图识别结果"""

    def test_create_result(self):
        """测试创建意图识别结果"""
        result = IntentResult(
            intent=IntentType.PLAN,
            params={"destination": "杭州", "days": 3},
            reply="",
            confidence=0.9,
            source="test",
        )
        assert result.intent == IntentType.PLAN
        assert result.params["destination"] == "杭州"
        assert result.params["days"] == 3
        assert result.confidence == 0.9
        assert result.source == "test"

    def test_to_dict(self):
        """测试转换为字典"""
        result = IntentResult(
            intent=IntentType.PLAN,
            params={"destination": "杭州"},
            confidence=0.9,
        )
        data = result.to_dict()
        assert data["intent"] == "plan"
        assert data["args"]["destination"] == "杭州"
        assert data["confidence"] == 0.9

    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            "intent": "weather",
            "args": {"city": "济南"},
            "reply": "",
            "confidence": 0.85,
        }
        result = IntentResult.from_dict(data)
        assert result.intent == IntentType.WEATHER
        assert result.params["city"] == "济南"
        assert result.confidence == 0.85


class TestRuleIntentRecognizer:
    """测试规则兜底意图识别器"""

    def setup_method(self):
        """每个测试方法前初始化"""
        self.recognizer = RuleIntentRecognizer()

    def test_plan_intent_with_days(self):
        """测试规划意图（带天数）"""
        result = self.recognizer.recognize(["我想去杭州玩3天"])
        assert result.intent == IntentType.PLAN
        assert result.params["destination"] == "杭州"
        assert result.params["days"] == 3
        assert result.confidence >= 0.8

    def test_plan_intent_without_days(self):
        """测试规划意图（不带天数）"""
        result = self.recognizer.recognize(["我想去休宁"])
        assert result.intent == IntentType.PLAN
        assert result.params["destination"] == "休宁"
        assert result.params["days"] == 3  # 默认值

    def test_weather_intent(self):
        """测试天气查询意图"""
        result = self.recognizer.recognize(["济南天气如何"])
        assert result.intent == IntentType.WEATHER
        assert result.params["city"] == "济南"

    def test_poi_intent_attractions(self):
        """测试POI搜索意图（景点）"""
        result = self.recognizer.recognize(["杭州有什么好玩的"])
        assert result.intent == IntentType.POI
        assert result.params["city"] == "杭州"
        assert result.params["category"] == "景点"

    def test_poi_intent_food(self):
        """测试POI搜索意图（美食）"""
        result = self.recognizer.recognize(["成都有什么好吃的"])
        assert result.intent == IntentType.POI
        assert result.params["city"] == "成都"
        assert result.params["category"] == "美食"

    def test_chat_intent_greeting(self):
        """测试普通对话意图（寒暄）"""
        result = self.recognizer.recognize(["你好"])
        assert result.intent == IntentType.CHAT

    def test_chat_intent_thanks(self):
        """测试普通对话意图（感谢）"""
        result = self.recognizer.recognize(["谢谢"])
        assert result.intent == IntentType.CHAT

    def test_extract_days(self):
        """测试天数提取"""
        result = self.recognizer.recognize(["去北京玩5天"])
        assert result.params["days"] == 5

    def test_extract_travelers(self):
        """测试人数提取"""
        result = self.recognizer.recognize(["去杭州玩3天，2个人"])
        assert result.params["travelers"] == 2

    def test_extract_budget(self):
        """测试预算档位提取"""
        result = self.recognizer.recognize(["去杭州玩3天，预算经济一点"])
        assert result.params["budget_level"] == "经济"

    def test_extract_traffic_mode(self):
        """测试出行方式提取"""
        result = self.recognizer.recognize(["去杭州玩3天，自驾"])
        assert result.params["traffic_mode"] == "自驾"

    def test_empty_messages(self):
        """测试空消息"""
        result = self.recognizer.recognize([])
        assert result is None or result.intent == IntentType.CHAT

    def test_whitespace_messages(self):
        """测试空白消息"""
        result = self.recognizer.recognize(["   "])
        assert result is None or result.intent == IntentType.CHAT


class TestIntentRecognizer:
    """测试意图识别主类"""

    def test_singleton(self):
        """测试单例模式"""
        recognizer1 = get_intent_recognizer()
        recognizer2 = get_intent_recognizer()
        assert recognizer1 is recognizer2

    def test_create_with_config(self):
        """测试带配置创建"""
        recognizer = IntentRecognizer(
            llm_model="test-model",
            llm_temperature=0.5,
            use_llm=False,
            use_rule_fallback=True,
        )
        assert recognizer.use_llm is False
        assert recognizer.use_rule_fallback is True

    def test_rule_fallback_when_llm_disabled(self):
        """测试LLM禁用时使用规则兜底"""
        recognizer = IntentRecognizer(use_llm=False, use_rule_fallback=True)
        result = asyncio.run(recognizer.recognize(["我想去杭州玩3天"]))
        assert result.intent == IntentType.PLAN
        assert result.source == "rule"

    def test_default_chat_when_all_disabled(self):
        """测试所有识别器都禁用时返回默认chat"""
        recognizer = IntentRecognizer(use_llm=False, use_rule_fallback=False)
        result = asyncio.run(recognizer.recognize(["我想去杭州玩3天"]))
        assert result.intent == IntentType.CHAT
        assert result.source == "default"

    def test_empty_messages_returns_default(self):
        """测试空消息返回默认回复"""
        recognizer = IntentRecognizer(use_llm=False, use_rule_fallback=True)
        result = asyncio.run(recognizer.recognize([]))
        assert result.intent == IntentType.CHAT
        assert result.reply != ""


class TestLLMIntentRecognizer:
    """测试LLM意图识别器（需要LLM可用）"""

    def test_llm_not_available(self):
        """测试LLM不可用时返回None"""
        # 这个测试需要模拟LLM不可用的情况
        # 实际测试时需要根据环境调整
        pass

    def test_parse_json_direct(self):
        """测试直接解析JSON"""
        recognizer = LLMIntentRecognizer()
        content = '{"intent": "plan", "args": {"destination": "杭州"}, "confidence": 0.9}'
        result = recognizer._parse_json(content)
        assert result is not None
        assert result["intent"] == "plan"

    def test_parse_json_with_markdown(self):
        """测试解析带markdown的JSON"""
        recognizer = LLMIntentRecognizer()
        content = '```json\n{"intent": "plan", "args": {"destination": "杭州"}}\n```'
        result = recognizer._parse_json(content)
        assert result is not None
        assert result["intent"] == "plan"

    def test_parse_json_with_extra_text(self):
        """测试解析带额外文本的JSON"""
        recognizer = LLMIntentRecognizer()
        content = '这是回复内容\n{"intent": "plan", "args": {}}\n这是更多内容'
        result = recognizer._parse_json(content)
        assert result is not None
        assert result["intent"] == "plan"

    def test_parse_json_invalid(self):
        """测试解析无效JSON"""
        recognizer = LLMIntentRecognizer()
        content = '这不是JSON'
        result = recognizer._parse_json(content)
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
