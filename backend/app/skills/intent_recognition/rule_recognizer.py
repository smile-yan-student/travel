"""
意图识别模块 - 规则兜底意图识别器

当LLM不可用或识别失败时，使用规则进行意图识别的兜底。
"""
import re
from typing import List, Dict, Any, Optional

from app.infrastructure import logger as log_mod
from app.skills.intent_recognition.types import IntentResult, IntentType

_rule_logger = log_mod.get_logger("intent_rule")


class RuleIntentRecognizer:
    """规则兜底意图识别器"""

    def __init__(self):
        """初始化规则意图识别器"""
        # 天气关键词
        self.weather_keywords = [
            "天气", "气温", "温度", "冷不丁", "热不热", "下雨", "下雪",
            "降温", "几度", "穿衣", "防晒", "台风", "雾霾", "穿什么",
            "天气预报", "天气怎么样", "天气如何",
        ]

        # POI搜索关键词
        self.poi_keywords = [
            "有什么好玩的", "有什么好吃的", "景点推荐", "美食推荐",
            "购物推荐", "夜生活", "好玩的地方", "好吃的地方",
            "推荐景点", "推荐美食", "哪里好玩", "哪里好吃",
        ]

        # 规划意图强关键词
        self.strong_plan_keywords = [
            "玩几天", "玩多少天", "旅游几天", "旅行几天",
            "天行程", "天攻略", "天规划", "天旅游",
            "规划行程", "规划攻略", "规划旅游",
            "帮我规划", "给我规划", "帮我做",
        ]

        # 规划意图模式
        self.plan_patterns = [
            r"去\s*[\u4e00-\u9fa5A-Za-z0-9]{2,15}?\s*(?:玩|旅游|旅行|度假|逛逛|耍|打卡)",
            r"去\s*[\u4e00-\u9fa5A-Za-z0-9]{2,15}?\s*(?:\d+\s*天|\d+\s*日|\d+\s*晚)",
            r"(?:我想去|我要去|我打算去|我准备去)\s*[\u4e00-\u9fa5A-Za-z0-9]{2,15}",
            r"(?:帮我|给我|替我)\s*规划\s*[\u4e00-\u9fa5A-Za-z0-9]{2,15}",
            r"^[\u4e00-\u9fa5A-Za-z0-9]{2,15}?\s*(?:\d+\s*天)?\s*(?:规划|攻略|行程|旅游|旅行)",
        ]

        # 调整指令关键词
        self.adjust_keywords = [
            "改成", "改为", "加个", "增加", "去掉", "不要",
            "预算", "节奏", "风格", "天数", "天",
            "太满", "太赶", "减少", "放慢",
        ]

    def recognize(self, messages: List[str]) -> Optional[IntentResult]:
        """
        使用规则识别用户意图

        Args:
            messages: 用户消息列表（含历史）

        Returns:
            IntentResult: 意图识别结果，失败返回None
        """
        all_msgs = [m.strip() for m in messages if m and m.strip()]
        if not all_msgs:
            return None

        latest_msg = all_msgs[-1]

        # 1. 检查是否是天气查询
        weather_result = self._check_weather(latest_msg)
        if weather_result:
            return weather_result

        # 2. 检查是否是POI搜索
        poi_result = self._check_poi(latest_msg)
        if poi_result:
            return poi_result

        # 3. 检查是否是行程规划
        plan_result = self._check_plan(latest_msg, all_msgs)
        if plan_result:
            return plan_result

        # 4. 都不匹配，返回chat
        return IntentResult(
            intent=IntentType.CHAT,
            params={},
            reply="",
            confidence=0.5,
            source="rule",
        )

    def _check_weather(self, message: str) -> Optional[IntentResult]:
        """检查是否是天气查询"""
        if not any(kw in message for kw in self.weather_keywords):
            return None

        # 提取城市名
        city = self._extract_city(message)
        if not city:
            return None

        _rule_logger.info("weather_intent_recognized", extra={"fields": {
            "city": city,
            "message": message[:100],
        }})

        return IntentResult(
            intent=IntentType.WEATHER,
            params={"city": city},
            reply="",
            confidence=0.85,
            source="rule",
        )

    def _check_poi(self, message: str) -> Optional[IntentResult]:
        """检查是否是POI搜索"""
        if not any(kw in message for kw in self.poi_keywords):
            return None

        # 提取城市名（POI搜索模式）
        city = self._extract_city_for_poi(message)
        if not city:
            return None

        # 判断类别
        category = "景点"
        if any(kw in message for kw in ["好吃", "美食", "吃什么"]):
            category = "美食"
        elif any(kw in message for kw in ["购物", "买什么", "商场"]):
            category = "购物"
        elif any(kw in message for kw in ["夜生活", "酒吧", "夜市"]):
            category = "夜生活"

        _rule_logger.info("poi_intent_recognized", extra={"fields": {
            "city": city,
            "category": category,
            "message": message[:100],
        }})

        return IntentResult(
            intent=IntentType.POI,
            params={"city": city, "category": category, "keyword": ""},
            reply="",
            confidence=0.85,
            source="rule",
        )

    def _check_plan(self, message: str, all_msgs: List[str]) -> Optional[IntentResult]:
        """检查是否是行程规划"""
        # 检查是否是调整指令（需要参考历史消息）
        if self._is_adjust_command(message):
            # 从历史消息中提取目的地
            destination = self._extract_destination_from_history(all_msgs)
            if destination:
                params = self._extract_params(message)
                params["destination"] = destination
                _rule_logger.info("plan_adjust_intent_recognized", extra={"fields": {
                    "destination": destination,
                    "message": message[:100],
                }})
                return IntentResult(
                    intent=IntentType.PLAN,
                    params=params,
                    reply="",
                    confidence=0.8,
                    source="rule",
                )

        # 检查是否包含强规划关键词
        has_strong_keyword = any(kw in message for kw in self.strong_plan_keywords)

        # 检查是否匹配规划模式
        matched_pattern = None
        for pattern in self.plan_patterns:
            if re.search(pattern, message):
                matched_pattern = pattern
                break

        # 提取目的地
        destination = self._extract_destination(message)

        # 如果有强关键词且有目的地，或者匹配规划模式且有目的地
        if (has_strong_keyword and destination) or (matched_pattern and destination):
            params = self._extract_params(message)
            params["destination"] = destination
            _rule_logger.info("plan_intent_recognized", extra={"fields": {
                "destination": destination,
                "days": params.get("days"),
                "message": message[:100],
            }})
            return IntentResult(
                intent=IntentType.PLAN,
                params=params,
                reply="",
                confidence=0.85,
                source="rule",
            )

        # 如果只有"我想去X"模式
        if destination and ("我想去" in message or "我要去" in message):
            params = self._extract_params(message)
            params["destination"] = destination
            _rule_logger.info("plan_intent_recognized_simple", extra={"fields": {
                "destination": destination,
                "message": message[:100],
            }})
            return IntentResult(
                intent=IntentType.PLAN,
                params=params,
                reply="",
                confidence=0.75,
                source="rule",
            )

        return None

    def _is_adjust_command(self, message: str) -> bool:
        """检查是否是调整指令"""
        return any(kw in message for kw in self.adjust_keywords)

    def _extract_city(self, message: str) -> str:
        """从消息中提取城市名（简单实现）"""
        # 匹配"X的天气"、"X天气"模式
        patterns = [
            r"([\u4e00-\u9fa5]{2,10}?)\s*的?\s*天气",
            r"([\u4e00-\u9fa5]{2,10}?)\s*的?\s*气温",
            r"([\u4e00-\u9fa5]{2,10}?)\s*的?\s*温度",
        ]
        for pattern in patterns:
            match = re.search(pattern, message)
            if match:
                city = match.group(1).strip()
                # 过滤掉常见的非城市词汇
                if city not in ["今天", "现在", "这里", "那里", "最近", "本地", "明天", "后天"]:
                    return city
        return ""

    def _extract_city_for_poi(self, message: str) -> str:
        """从POI搜索消息中提取城市名"""
        # 匹配"X有什么好玩的"、"X有什么好吃的"、"X景点推荐"等模式
        patterns = [
            r"([\u4e00-\u9fa5]{2,10}?)\s*有什么(?:好玩|好吃|好逛|好买)",
            r"([\u4e00-\u9fa5]{2,10}?)\s*(?:景点|美食|购物|夜生活)\s*推荐",
            r"([\u4e00-\u9fa5]{2,10}?)\s*(?:好玩的|好吃的|好逛的)\s*地方",
            r"([\u4e00-\u9fa5]{2,10}?)\s*哪里(?:好玩|好吃|好逛)",
            r"推荐\s*([\u4e00-\u9fa5]{2,10}?)\s*(?:景点|美食|购物)",
        ]
        for pattern in patterns:
            match = re.search(pattern, message)
            if match:
                city = match.group(1).strip()
                # 过滤掉常见的非城市词汇
                if city not in ["今天", "现在", "这里", "那里", "最近", "本地", "明天", "后天", "什么", "怎么", "如何", "为什么"]:
                    return city
        return ""

    def _extract_destination(self, message: str) -> str:
        """从消息中提取目的地"""
        dest_patterns = [
            r"去\s*([\u4e00-\u9fa5A-Za-z0-9]{2,15}?)\s*(?:玩|旅游|旅行|度假|逛逛|耍|打卡)",
            r"去\s*([\u4e00-\u9fa5A-Za-z0-9]{2,15}?)\s*(?:\d+\s*天|\d+\s*日|\d+\s*晚)",
            r"(?:我想去|我要去|我打算去|我准备去)\s*([\u4e00-\u9fa5A-Za-z0-9]{2,15})",
            r"(?:帮我|给我|替我)\s*规划\s*([\u4e00-\u9fa5A-Za-z0-9]{2,15})",
            r"^([\u4e00-\u9fa5A-Za-z0-9]{2,15}?)\s*(?:\d+\s*天)?\s*(?:规划|攻略|行程|旅游|旅行)",
        ]
        for pattern in dest_patterns:
            match = re.search(pattern, message)
            if match:
                destination = match.group(1).strip()
                # 去掉目的地后面的常见后缀
                for suffix in ["行程", "攻略", "规划", "旅游", "旅行", "游玩", "度假", "打卡", "之旅"]:
                    if destination.endswith(suffix):
                        destination = destination[:-len(suffix)]
                        break
                # 过滤掉常见的非目的地词汇
                if destination not in ["哪里", "哪儿", "什么", "怎么", "如何", "为什么", "多少", "几", "帮我", "给我", "替我"]:
                    return destination
        return ""

    def _extract_destination_from_history(self, messages: List[str]) -> str:
        """从历史消息中提取目的地"""
        # 从最近的历史消息中提取
        for msg in reversed(messages[:-1]):
            destination = self._extract_destination(msg)
            if destination:
                return destination
        return ""

    def _extract_params(self, message: str) -> Dict[str, Any]:
        """从消息中提取规划参数"""
        params = {
            "days": 3,
            "travelers": 1,
            "budget_level": "适中",
            "style": "综合",
            "pace": "适中",
            "traffic_mode": "公共交通",
            "interests": [],
        }

        # 提取天数
        days_patterns = [
            r"(\d+)\s*天",
            r"(\d+)\s*日",
            r"(\d+)\s*晚",
            r"玩\s*(\d+)",
            r"旅游\s*(\d+)",
            r"旅行\s*(\d+)",
        ]
        for pattern in days_patterns:
            match = re.search(pattern, message)
            if match:
                try:
                    days = int(match.group(1))
                    if 1 <= days <= 30:
                        params["days"] = days
                        break
                except (ValueError, IndexError):
                    pass

        # 提取人数
        travelers_patterns = [
            r"(\d+)\s*人",
            r"(\d+)\s*个",
            r"我们\s*(\d+)",
            r"(\d+)\s*位",
        ]
        for pattern in travelers_patterns:
            match = re.search(pattern, message)
            if match:
                try:
                    travelers = int(match.group(1))
                    if 1 <= travelers <= 99:
                        params["travelers"] = travelers
                        break
                except (ValueError, IndexError):
                    pass

        # 提取预算档位
        budget_keywords = {
            "经济": ["经济", "穷游", "省钱", "便宜", "性价比"],
            "舒适": ["舒适", "享受", "品质", "高端"],
            "豪华": ["豪华", "奢侈", "顶级", "奢华"],
        }
        for budget, keywords in budget_keywords.items():
            if any(kw in message for kw in keywords):
                params["budget_level"] = budget
                break

        # 提取出行方式
        traffic_keywords = {
            "自驾": ["自驾", "开车", "自驾游"],
            "骑行": ["骑行", "自行车", "骑车"],
            "步行": ["步行", "走路", "徒步"],
            "公共交通": ["公共交通", "地铁", "公交", "高铁", "火车", "飞机"],
        }
        for traffic, keywords in traffic_keywords.items():
            if any(kw in message for kw in keywords):
                params["traffic_mode"] = traffic
                break

        # 提取节奏
        pace_keywords = {
            "轻松": ["轻松", "慢", "休闲", "不赶"],
            "紧凑": ["紧凑", "赶", "充实", "满"],
        }
        for pace, keywords in pace_keywords.items():
            if any(kw in message for kw in keywords):
                params["pace"] = pace
                break

        return params
