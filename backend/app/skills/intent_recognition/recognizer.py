"""
意图识别模块 - 主类（对外接口）

协调LLM识别器和规则识别器，提供统一的意图识别接口。
"""
from typing import List, Dict, Any, Optional

from app.infrastructure import logger as log_mod
from app.skills.intent_recognition.types import IntentResult, IntentType, RecognitionContext
from app.skills.intent_recognition.llm_recognizer import LLMIntentRecognizer
from app.skills.intent_recognition.rule_recognizer import RuleIntentRecognizer

_recognizer_logger = log_mod.get_logger("intent_recognizer")


class IntentRecognizer:
    """意图识别器（对外接口）"""

    def __init__(
        self,
        llm_model: str = "",
        llm_temperature: float = 0.3,
        use_llm: bool = True,
        use_rule_fallback: bool = True,
    ):
        """
        初始化意图识别器

        Args:
            llm_model: LLM模型名称，为空时使用默认模型
            llm_temperature: LLM温度参数
            use_llm: 是否使用LLM识别
            use_rule_fallback: 是否使用规则兜底
        """
        self.use_llm = use_llm
        self.use_rule_fallback = use_rule_fallback

        # 初始化识别器
        self.llm_recognizer = LLMIntentRecognizer(
            model=llm_model,
            temperature=llm_temperature,
        ) if use_llm else None

        self.rule_recognizer = RuleIntentRecognizer() if use_rule_fallback else None

    async def recognize(
        self,
        messages: List[str],
        context: Optional[RecognitionContext] = None,
    ) -> IntentResult:
        """
        识别用户意图

        Args:
            messages: 用户消息列表（含历史）
            context: 识别上下文

        Returns:
            IntentResult: 意图识别结果
        """
        all_msgs = [m.strip() for m in messages if m and m.strip()]
        if not all_msgs:
            return IntentResult(
                intent=IntentType.CHAT,
                params={},
                reply="你好呀，我是你的旅行伙伴！世界很大，而我们正从一次出发开始。想去哪儿？哪怕只是心里一个模糊的方向，也可以说给我听。",
                confidence=0.9,
                source="default",
            )

        # 1. 优先使用LLM识别
        if self.llm_recognizer:
            try:
                llm_result = await self.llm_recognizer.recognize(all_msgs)
                if llm_result:
                    _recognizer_logger.info("llm_recognition_success", extra={"fields": {
                        "intent": llm_result.intent.value,
                        "confidence": llm_result.confidence,
                        "destination": llm_result.params.get("destination", ""),
                    }})
                    return llm_result
                else:
                    _recognizer_logger.warning("llm_recognition_returned_none")
            except Exception as e:
                _recognizer_logger.error("llm_recognition_error", extra={"fields": {
                    "error": str(e),
                }})

        # 2. LLM失败，使用规则兜底
        if self.rule_recognizer:
            try:
                rule_result = self.rule_recognizer.recognize(all_msgs)
                if rule_result:
                    _recognizer_logger.info("rule_fallback_success", extra={"fields": {
                        "intent": rule_result.intent.value,
                        "confidence": rule_result.confidence,
                        "destination": rule_result.params.get("destination", ""),
                    }})
                    return rule_result
            except Exception as e:
                _recognizer_logger.error("rule_recognition_error", extra={"fields": {
                    "error": str(e),
                }})

        # 3. 都失败，返回默认chat
        _recognizer_logger.warning("all_recognition_failed")
        return IntentResult(
            intent=IntentType.CHAT,
            params={},
            reply="我在呢～无论是景点、美食还是天气，都乐意陪你聊。要是想把某个地方变成一场真正的行程，直接告诉我「去X玩几天」就行。",
            confidence=0.5,
            source="default",
        )

    async def recognize_plan_params(
        self,
        message: str,
        context: Optional[RecognitionContext] = None,
    ) -> Dict[str, Any]:
        """
        专门识别规划参数（用于参数提取场景）

        Args:
            message: 用户消息
            context: 识别上下文

        Returns:
            Dict: 提取的参数字典
        """
        result = await self.recognize([message], context)
        if result.intent == IntentType.PLAN:
            return result.params
        return {}


# 单例
_singleton_instance: Optional[IntentRecognizer] = None


def get_intent_recognizer() -> IntentRecognizer:
    """获取意图识别器单例"""
    global _singleton_instance
    if _singleton_instance is None:
        _singleton_instance = IntentRecognizer()
    return _singleton_instance
