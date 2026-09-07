"""
意图识别模块 - LLM意图识别器

使用大语言模型进行意图识别，支持Function Calling机制。
"""
import json
import re
import time
from typing import List, Dict, Any, Optional

from app.infrastructure import logger as log_mod
from app.skills.intent_recognition.types import IntentResult, IntentType

_llm_logger = log_mod.get_logger("intent_llm")


class LLMIntentRecognizer:
    """LLM意图识别器"""

    def __init__(self, model: str = "", temperature: float = 0.3):
        """
        初始化LLM意图识别器

        Args:
            model: 使用的模型名称，为空时使用默认模型
            temperature: 温度参数，意图识别建议使用较低温度（0.1-0.3）
        """
        self.model = model
        self.temperature = temperature
        self._ai_module = None

    def _get_ai_module(self):
        """延迟加载AI模块，避免循环导入"""
        if self._ai_module is None:
            from app.ai import ai as ai_mod
            self._ai_module = ai_mod
        return self._ai_module

    def _get_model(self) -> str:
        """获取使用的模型名称"""
        if self.model:
            return self.model
        ai_mod = self._get_ai_module()
        return ai_mod.resolve_model() or "qwen2:7b"

    def _is_ai_available(self) -> bool:
        """检查AI是否可用"""
        try:
            ai_mod = self._get_ai_module()
            return ai_mod.ai_available()
        except Exception:
            return False

    async def recognize(self, messages: List[str]) -> Optional[IntentResult]:
        """
        使用LLM识别用户意图

        Args:
            messages: 用户消息列表（含历史）

        Returns:
            IntentResult: 意图识别结果，失败返回None
        """
        if not self._is_ai_available():
            _llm_logger.warning("ai_not_available")
            return None

        all_msgs = [m.strip() for m in messages if m and m.strip()]
        if not all_msgs:
            return None

        call_start = time.time()
        model = self._get_model()

        try:
            # 构建消息
            from app.skills.intent_recognition.prompts import get_intent_prompt
            system_prompt = get_intent_prompt()

            # 上下文窗口管理：只保留最近5轮历史消息，更早的进行摘要
            chat_messages = [{"role": "system", "content": system_prompt}]

            # 处理历史消息（只保留最近5轮，更早的只保留关键参数摘要）
            history_msgs = all_msgs[:-1]
            current_msg = all_msgs[-1]

            if len(history_msgs) > 5:
                # 对更早的历史消息进行摘要，只保留关键参数
                early_msgs = history_msgs[:-5]
                recent_msgs = history_msgs[-5:]

                # 提取早期历史消息中的关键参数（目的地、天数、人数等）
                early_summary = self._extract_history_summary(early_msgs)
                if early_summary:
                    chat_messages.append({
                        "role": "user",
                        "content": f"【历史对话摘要（更早的对话，仅作背景参考）】{early_summary}"
                    })

                # 添加最近5轮历史消息
                for i, msg in enumerate(recent_msgs):
                    chat_messages.append({
                        "role": "user",
                        "content": f"【历史消息 {i+1}】{msg}"
                    })
            else:
                # 历史消息不超过5轮，全部保留
                for i, msg in enumerate(history_msgs):
                    chat_messages.append({
                        "role": "user",
                        "content": f"【历史消息 {i+1}】{msg}"
                    })

            # 添加当前消息（明确标记，让LLM聚焦）
            chat_messages.append({
                "role": "user",
                "content": f"【当前消息（请只分析这条消息的意图）】{current_msg}"
            })

            # 调用LLM（使用统一的chat_completion函数，支持本地Ollama和线上OpenAI兼容API）
            from app.ai.ai import chat_completion

            content = await chat_completion(
                messages=chat_messages,
                temperature=self.temperature,
                max_tokens=1024,
                model=model,
            ) or ""

            if not content:
                _llm_logger.warning("empty_response")
                return None

            # 解析JSON结果
            result = self._parse_json(content)
            if not result:
                _llm_logger.warning("json_parse_failed", extra={"fields": {"content": content[:200]}})
                return None

            # 置信度校验
            confidence = result.get("confidence", 1.0)
            intent = result.get("intent", "chat")
            try:
                confidence = float(confidence)
            except (TypeError, ValueError):
                confidence = 0.0

            # 置信度低于0.6时，降级为chat
            if confidence < 0.6 and intent != "chat":
                _llm_logger.info("low_confidence_downgrade_to_chat", extra={"fields": {
                    "original_intent": intent,
                    "confidence": confidence,
                }})
                intent = "chat"
                result["intent"] = "chat"
                result["args"] = {}

            intent_result = IntentResult(
                intent=IntentType.from_string(intent),
                params=result.get("args", {}),
                reply=result.get("reply", ""),
                confidence=confidence,
                source="llm",
                raw_result=result,
            )

            latency_ms = (time.time() - call_start) * 1000
            _llm_logger.info("intent_recognized", extra={"fields": {
                "intent": intent_result.intent.value,
                "confidence": intent_result.confidence,
                "destination": intent_result.params.get("destination", ""),
                "days": intent_result.params.get("days"),
                "history_count": len(history_msgs),
                "latency_ms": round(latency_ms, 2),
                "model": model,
            }})

            return intent_result

        except Exception as e:
            _llm_logger.error("intent_recognition_error", extra={"fields": {
                "error": str(e),
                "model": model,
            }})
            return None

    def _extract_history_summary(self, messages: List[str]) -> str:
        """
        提取历史消息的关键参数摘要，减少历史消息的干扰

        Args:
            messages: 历史消息列表

        Returns:
            str: 关键参数摘要
        """
        if not messages:
            return ""

        # 简单的关键词提取（不调用LLM，避免额外延迟）
        keywords = {
            "destination": [],
            "days": [],
            "travelers": [],
            "budget": [],
            "style": [],
            "pace": [],
            "traffic": [],
        }

        # 天数关键词
        import re
        for msg in messages:
            # 提取天数
            day_match = re.search(r'(\d+)\s*[天日]', msg)
            if day_match:
                keywords["days"].append(day_match.group(1))

            # 提取人数
            traveler_match = re.search(r'(\d+)\s*[人个]', msg)
            if traveler_match:
                keywords["travelers"].append(traveler_match.group(1))

            # 提取预算
            if any(w in msg for w in ['经济', '穷游', '省钱']):
                keywords["budget"].append("经济")
            elif any(w in msg for w in ['舒适', '豪华', '高端']):
                keywords["budget"].append("舒适")

            # 提取风格
            if any(w in msg for w in ['亲子', '孩子', '小孩']):
                keywords["style"].append("亲子")
            elif any(w in msg for w in ['情侣', '浪漫', '约会']):
                keywords["style"].append("情侣")
            elif any(w in msg for w in ['美食', '吃货', '吃']):
                keywords["style"].append("美食")
            elif any(w in msg for w in ['人文', '历史', '文化', '博物馆']):
                keywords["style"].append("人文")
            elif any(w in msg for w in ['自然', '风景', '山水']):
                keywords["style"].append("自然")

            # 提取节奏
            if any(w in msg for w in ['轻松', '休闲', '慢', '不赶']):
                keywords["pace"].append("轻松")
            elif any(w in msg for w in ['紧凑', '赶', '充实']):
                keywords["pace"].append("紧凑")

            # 提取交通方式
            if any(w in msg for w in ['自驾', '开车', '租车']):
                keywords["traffic"].append("自驾")
            elif any(w in msg for w in ['公共交通', '地铁', '公交', '高铁']):
                keywords["traffic"].append("公共交通")
            elif any(w in msg for w in ['骑行', '自行车']):
                keywords["traffic"].append("骑行")
            elif any(w in msg for w in ['步行', '走路']):
                keywords["traffic"].append("步行")

        # 构建摘要
        summary_parts = []
        if keywords["days"]:
            summary_parts.append(f"天数: {keywords['days'][-1]}天")
        if keywords["travelers"]:
            summary_parts.append(f"人数: {keywords['travelers'][-1]}人")
        if keywords["budget"]:
            summary_parts.append(f"预算: {keywords['budget'][-1]}")
        if keywords["style"]:
            summary_parts.append(f"风格: {keywords['style'][-1]}")
        if keywords["pace"]:
            summary_parts.append(f"节奏: {keywords['pace'][-1]}")
        if keywords["traffic"]:
            summary_parts.append(f"交通: {keywords['traffic'][-1]}")

        if summary_parts:
            return "已确认的出行参数: " + ", ".join(summary_parts) + "（仅作背景参考，不要影响当前消息的意图判断）"

        return ""

    def _parse_json(self, content: str) -> Optional[Dict[str, Any]]:
        """
        解析LLM返回的JSON内容

        Args:
            content: LLM返回的原始内容

        Returns:
            Dict: 解析后的字典，失败返回None
        """
        if not content:
            return None

        # 尝试直接解析
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # 尝试提取JSON块（处理markdown格式）
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试提取第一个{到最后一个}之间的内容
        start = content.find('{')
        end = content.rfind('}')
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(content[start:end+1])
            except json.JSONDecodeError:
                pass

        return None
