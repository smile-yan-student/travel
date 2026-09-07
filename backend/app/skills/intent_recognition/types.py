"""
意图识别模块 - 类型定义

定义意图识别相关的数据类型和枚举。
"""
from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


class IntentType(str, Enum):
    """意图类型枚举"""
    PLAN = "plan"           # 行程规划
    WEATHER = "weather"     # 天气查询
    POI = "poi"             # 景点/美食/购物搜索
    CHAT = "chat"           # 普通对话/闲聊

    @classmethod
    def from_string(cls, value: str) -> "IntentType":
        """从字符串创建意图类型，不合法时返回CHAT"""
        try:
            return cls(value)
        except ValueError:
            return cls.CHAT


class SpanUnit(str, Enum):
    """时间跨度单位枚举"""
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"


class BudgetLevel(str, Enum):
    """预算档位枚举"""
    ECONOMY = "经济"
    MODERATE = "适中"
    COMFORT = "舒适"
    LUXURY = "豪华"


class TravelStyle(str, Enum):
    """旅行风格枚举"""
    COMPREHENSIVE = "综合"
    CULTURE = "人文"
    NATURE = "自然"
    FOOD = "美食"
    SHOPPING = "购物"
    FAMILY = "亲子"
    CHECKIN = "打卡"
    PHOTOGRAPHY = "摄影"
    OUTDOOR = "户外"
    HISTORY = "历史"


class Pace(str, Enum):
    """节奏枚举"""
    RELAXED = "轻松"
    MODERATE = "适中"
    COMPACT = "紧凑"


class TrafficMode(str, Enum):
    """出行方式枚举"""
    PUBLIC_TRANSPORT = "公共交通"
    SELF_DRIVING = "自驾"
    CYCLING = "骑行"
    WALKING = "步行"
    MIXED = "混合"


class GroupType(str, Enum):
    """人群类型枚举"""
    SOLO = "单人"
    COUPLE = "情侣"
    FRIENDS = "朋友"
    FAMILY = "家庭"
    PARENT_CHILD = "亲子"
    BUSINESS = "商务"
    OTHER = "其他"


@dataclass
class PlanParams:
    """规划参数"""
    destination: str = ""
    province: str = ""
    city: str = ""
    district: str = ""
    days: int = 3
    travelers: int = 1
    budget_level: str = "适中"
    style: str = "综合"
    pace: str = "适中"
    traffic_mode: str = "公共交通"
    group_type: str = "单人"
    span_unit: str = "day"
    span_value: int = 3
    origin: str = ""
    return_point: str = ""
    interests: List[str] = field(default_factory=list)
    must_include_poi: List[str] = field(default_factory=list)
    exclude_poi: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "destination": self.destination,
            "province": self.province,
            "city": self.city,
            "district": self.district,
            "days": self.days,
            "travelers": self.travelers,
            "budget_level": self.budget_level,
            "style": self.style,
            "pace": self.pace,
            "traffic_mode": self.traffic_mode,
            "group_type": self.group_type,
            "span_unit": self.span_unit,
            "span_value": self.span_value,
            "origin": self.origin,
            "return_point": self.return_point,
            "interests": self.interests,
            "must_include_poi": self.must_include_poi,
            "exclude_poi": self.exclude_poi,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlanParams":
        """从字典创建"""
        return cls(
            destination=data.get("destination", ""),
            province=data.get("province", ""),
            city=data.get("city", ""),
            district=data.get("district", ""),
            days=data.get("days", 3),
            travelers=data.get("travelers", 1),
            budget_level=data.get("budget_level", "适中"),
            style=data.get("style", "综合"),
            pace=data.get("pace", "适中"),
            traffic_mode=data.get("traffic_mode", "公共交通"),
            group_type=data.get("group_type", "单人"),
            span_unit=data.get("span_unit", "day"),
            span_value=data.get("span_value", 3),
            origin=data.get("origin", ""),
            return_point=data.get("return_point", ""),
            interests=data.get("interests", []),
            must_include_poi=data.get("must_include_poi", []),
            exclude_poi=data.get("exclude_poi", []),
        )


@dataclass
class IntentResult:
    """意图识别结果"""
    intent: IntentType = IntentType.CHAT
    params: Dict[str, Any] = field(default_factory=dict)
    reply: str = ""
    confidence: float = 0.0
    source: str = ""  # llm / rule / hybrid
    raw_result: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "intent": self.intent.value,
            "args": self.params,
            "reply": self.reply,
            "confidence": self.confidence,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IntentResult":
        """从字典创建"""
        return cls(
            intent=IntentType.from_string(data.get("intent", "chat")),
            params=data.get("args", data.get("params", {})),
            reply=data.get("reply", ""),
            confidence=data.get("confidence", 0.0),
            source=data.get("source", ""),
            raw_result=data,
        )


@dataclass
class RecognitionContext:
    """意图识别上下文"""
    session_id: str = ""
    user_id: str = ""
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    current_params: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
