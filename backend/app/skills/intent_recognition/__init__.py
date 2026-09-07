"""
意图识别模块

提供统一的意图识别接口，支持LLM识别和规则兜底。

使用方式：
    from app.services.intent import get_intent_recognizer, IntentResult, IntentType
    
    recognizer = get_intent_recognizer()
    result = await recognizer.recognize(messages)
    
    if result.intent == IntentType.PLAN:
        # 处理规划意图
        params = result.params
    elif result.intent == IntentType.WEATHER:
        # 处理天气查询
        city = result.params.get("city")
    elif result.intent == IntentType.POI:
        # 处理POI搜索
        city = result.params.get("city")
        category = result.params.get("category")
    else:
        # 处理普通对话
        reply = result.reply
"""

from app.skills.intent_recognition.types import (
    IntentType,
    SpanUnit,
    BudgetLevel,
    TravelStyle,
    Pace,
    TrafficMode,
    GroupType,
    PlanParams,
    IntentResult,
    RecognitionContext,
)
from app.skills.intent_recognition.recognizer import IntentRecognizer, get_intent_recognizer
from app.skills.intent_recognition.llm_recognizer import LLMIntentRecognizer
from app.skills.intent_recognition.rule_recognizer import RuleIntentRecognizer
from app.skills.intent_recognition.prompts import get_intent_prompt, INTENT_SYSTEM_PROMPT
from app.skills.intent_recognition.utils import DEFAULT_PARAMS, clean_place, extract_city

__all__ = [
    # 类型
    "IntentType",
    "SpanUnit",
    "BudgetLevel",
    "TravelStyle",
    "Pace",
    "TrafficMode",
    "GroupType",
    "PlanParams",
    "IntentResult",
    "RecognitionContext",
    # 识别器
    "IntentRecognizer",
    "LLMIntentRecognizer",
    "RuleIntentRecognizer",
    "get_intent_recognizer",
    # 提示词
    "get_intent_prompt",
    "INTENT_SYSTEM_PROMPT",
    # 工具函数
    "DEFAULT_PARAMS",
    "clean_place",
    "extract_city",
]

__version__ = "1.1.0"
