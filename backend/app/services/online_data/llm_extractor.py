"""
LLM辅助数据提纯模块

使用大语言模型从非结构化文本中提取结构化的旅行信息，
与规则提取结果合并，提升数据提纯的准确率和覆盖率。

功能特性：
- LLM辅助提取景点列表（含频率和重要性）
- LLM辅助提取游览顺序（按天分组）
- LLM辅助提取耗时估算
- LLM辅助提取避坑提示（含分类和严重程度）
- 与规则提取结果合并，去重和加权
- 支持配置开关，可随时启用或禁用

使用方式：
    from app.services.online_data.llm_extractor import get_llm_extractor

    extractor = get_llm_extractor()
    result = await extractor.extract_with_llm(
        destination="北京",
        texts=["攻略文本1", "攻略文本2"],
        rule_extracted_data=rule_data  # 可选，规则提取结果
    )
"""
import json
import re
from typing import Any, Dict, List, Optional

from ...infrastructure.logger import get_logger

_logger = get_logger("llm_extractor")


class LLMExtractedAttraction:
    """LLM提取的景点信息"""
    def __init__(
        self,
        name: str = "",
        frequency: int = 1,
        importance: str = "optional",  # must_visit / recommended / optional
        estimated_duration: int = 120,  # 分钟
        category: str = "景点",
        description: str = "",
    ):
        self.name = name
        self.frequency = frequency
        self.importance = importance
        self.estimated_duration = estimated_duration
        self.category = category
        self.description = description

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "frequency": self.frequency,
            "importance": self.importance,
            "estimated_duration": self.estimated_duration,
            "category": self.category,
            "description": self.description,
        }


class LLMExtractedItinerary:
    """LLM提取的每日行程"""
    def __init__(
        self,
        day: int = 1,
        attractions: List[str] = None,
        theme: str = "",
        notes: str = "",
    ):
        self.day = day
        self.attractions = attractions or []
        self.theme = theme
        self.notes = notes

    def to_dict(self) -> dict:
        return {
            "day": self.day,
            "attractions": self.attractions,
            "theme": self.theme,
            "notes": self.notes,
        }


class LLMExtractedTip:
    """LLM提取的避坑提示"""
    def __init__(
        self,
        tip: str = "",
        category: str = "general",
        severity: str = "info",
        confidence: float = 0.8,
    ):
        self.tip = tip
        self.category = category
        self.severity = severity
        self.confidence = confidence

    def to_dict(self) -> dict:
        return {
            "tip": self.tip,
            "category": self.category,
            "severity": self.severity,
            "confidence": self.confidence,
        }


class LLMExtractedData:
    """LLM提取的完整数据"""
    def __init__(self, destination: str = ""):
        self.destination = destination
        self.attractions: List[LLMExtractedAttraction] = []
        self.itineraries: List[LLMExtractedItinerary] = []
        self.tips: List[LLMExtractedTip] = []
        self.confidence: float = 0.0
        self.llm_used: bool = False
        self.error: str = ""

    def to_dict(self) -> dict:
        return {
            "destination": self.destination,
            "attractions": [a.to_dict() for a in self.attractions],
            "itineraries": [i.to_dict() for i in self.itineraries],
            "tips": [t.to_dict() for t in self.tips],
            "confidence": self.confidence,
            "llm_used": self.llm_used,
            "error": self.error,
        }


class LLMExtractor:
    """LLM辅助数据提纯器"""

    # 是否启用LLM辅助提取
    ENABLED = True

    # LLM提取的提示词模板
    EXTRACTION_PROMPT = """你是一个专业的旅行数据分析师。请从以下旅行攻略文本中提取结构化信息。

目的地：{destination}

攻略文本：
{texts}

请提取以下信息，并以JSON格式返回（只返回JSON，不要其他内容）：

1. 景点列表（attractions）：每个景点包含
   - name: 景点名称
   - importance: 重要性（must_visit必去/recommended推荐/optional可选）
   - estimated_duration: 推荐游览时长（分钟）
   - category: 分类（景点/美食/购物/夜生活/文化）
   - description: 简短描述（20字以内）

2. 每日行程（itineraries）：按天分组，每天包含
   - day: 第几天（数字）
   - attractions: 当天游览的景点名称列表
   - theme: 当天主题（如：老城文化/长城一日游）
   - notes: 注意事项

3. 避坑提示（tips）：每条提示包含
   - tip: 提示内容
   - category: 分类（general通用/reservation预约/anti_fraud防骗/traffic交通/food美食/accommodation住宿/weather天气/safety安全）
   - severity: 严重程度（info信息/warning警告/danger危险）

请确保提取的信息准确、完整，只提取文本中明确提到的内容，不要编造。

JSON格式示例：
{{
  "attractions": [
    {{"name": "故宫", "importance": "must_visit", "estimated_duration": 180, "category": "文化", "description": "明清皇宫"}}
  ],
  "itineraries": [
    {{"day": 1, "attractions": ["天安门", "故宫", "景山"], "theme": "老城中心", "notes": "需提前预约"}}
  ],
  "tips": [
    {{"tip": "故宫需提前7天预约", "category": "reservation", "severity": "warning"}}
  ]
}}
"""

    def __init__(self):
        self._initialized = False

    async def _initialize(self):
        """初始化（懒加载）"""
        if self._initialized:
            return
        self._initialized = True

    async def _call_llm(self, prompt: str) -> Optional[str]:
        """调用LLM获取响应"""
        try:
            from ...ai.ai import chat_completion

            messages = [
                {"role": "system", "content": "你是一个专业的旅行数据分析师，擅长从非结构化文本中提取结构化信息。"},
                {"role": "user", "content": prompt}
            ]

            response = await chat_completion(
                messages=messages,
                temperature=0.1,  # 低温度，确保输出稳定
                max_tokens=2000,
            )

            if response and isinstance(response, str):
                return response.strip()
            return None
        except Exception as e:
            _logger.warning(f"llm_call_failed: {e}")
            return None

    def _parse_json_response(self, response: str) -> Optional[Dict[str, Any]]:
        """解析LLM返回的JSON响应"""
        if not response:
            return None

        # 尝试直接解析
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # 尝试提取JSON部分（可能包含markdown代码块）
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试提取第一个{到最后一个}之间的内容
        first_brace = response.find('{')
        last_brace = response.rfind('}')
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            try:
                return json.loads(response[first_brace:last_brace + 1])
            except json.JSONDecodeError:
                pass

        _logger.warning(f"json_parse_failed: {response[:100]}")
        return None

    def _json_to_extracted_data(
        self,
        destination: str,
        data: Dict[str, Any]
    ) -> LLMExtractedData:
        """将JSON数据转换为LLMExtractedData对象"""
        result = LLMExtractedData(destination=destination)
        result.llm_used = True

        # 解析景点列表
        attractions_data = data.get("attractions", [])
        for attr in attractions_data:
            if isinstance(attr, dict) and attr.get("name"):
                attraction = LLMExtractedAttraction(
                    name=attr.get("name", "").strip(),
                    importance=attr.get("importance", "optional"),
                    estimated_duration=attr.get("estimated_duration", 120),
                    category=attr.get("category", "景点"),
                    description=attr.get("description", ""),
                )
                result.attractions.append(attraction)

        # 解析每日行程
        itineraries_data = data.get("itineraries", [])
        for itin in itineraries_data:
            if isinstance(itin, dict):
                itinerary = LLMExtractedItinerary(
                    day=itin.get("day", 1),
                    attractions=itin.get("attractions", []),
                    theme=itin.get("theme", ""),
                    notes=itin.get("notes", ""),
                )
                result.itineraries.append(itinerary)

        # 解析避坑提示
        tips_data = data.get("tips", [])
        for tip in tips_data:
            if isinstance(tip, dict) and tip.get("tip"):
                extracted_tip = LLMExtractedTip(
                    tip=tip.get("tip", "").strip(),
                    category=tip.get("category", "general"),
                    severity=tip.get("severity", "info"),
                    confidence=tip.get("confidence", 0.8),
                )
                result.tips.append(extracted_tip)

        # 计算置信度（基于提取到的数据量）
        total_items = len(result.attractions) + len(result.itineraries) + len(result.tips)
        if total_items >= 10:
            result.confidence = 0.9
        elif total_items >= 5:
            result.confidence = 0.75
        elif total_items >= 2:
            result.confidence = 0.6
        else:
            result.confidence = 0.4

        return result

    async def extract_with_llm(
        self,
        destination: str,
        texts: List[str],
        rule_extracted_data: Optional[Any] = None,
    ) -> LLMExtractedData:
        """
        使用LLM辅助提取数据

        Args:
            destination: 目的地
            texts: 攻略文本列表
            rule_extracted_data: 规则提取的数据（可选，用于合并）

        Returns:
            LLM提取的数据
        """
        await self._initialize()

        result = LLMExtractedData(destination=destination)

        if not self.ENABLED:
            _logger.info(f"llm_extractor_disabled: {destination}")
            return result

        if not texts:
            _logger.warning(f"no_texts_for_extraction: {destination}")
            return result

        # 合并文本（限制总长度，避免超出LLM上下文）
        combined_text = ""
        for i, text in enumerate(texts[:5]):  # 最多使用5篇攻略
            if combined_text:
                combined_text += "\n\n---\n\n"
            combined_text += f"攻略{i+1}：\n{text[:3000]}"  # 每篇最多3000字

        if not combined_text:
            return result

        # 构建提示词
        prompt = self.EXTRACTION_PROMPT.format(
            destination=destination,
            texts=combined_text
        )

        # 调用LLM
        _logger.info(f"llm_extraction_start: {destination}, texts_count={len(texts)}")
        response = await self._call_llm(prompt)

        if not response:
            result.error = "LLM调用失败或无响应"
            _logger.warning(f"llm_extraction_no_response: {destination}")
            return result

        # 解析JSON响应
        data = self._parse_json_response(response)
        if not data:
            result.error = "JSON解析失败"
            _logger.warning(f"llm_extraction_parse_failed: {destination}")
            return result

        # 转换为结构化数据
        result = self._json_to_extracted_data(destination, data)

        _logger.info(
            f"llm_extraction_complete: {destination}, "
            f"attractions={len(result.attractions)}, "
            f"itineraries={len(result.itineraries)}, "
            f"tips={len(result.tips)}, "
            f"confidence={result.confidence}"
        )

        return result

    def merge_with_rule_data(
        self,
        llm_data: LLMExtractedData,
        rule_data: Any,
    ) -> Dict[str, Any]:
        """
        将LLM提取数据与规则提取数据合并

        Args:
            llm_data: LLM提取的数据
            rule_data: 规则提取的数据

        Returns:
            合并后的数据
        """
        merged = {
            "destination": llm_data.destination,
            "attractions": [],
            "itineraries": [],
            "tips": [],
            "confidence": max(llm_data.confidence, 0.5),
            "llm_enhanced": llm_data.llm_used,
        }

        # 合并景点列表（LLM优先，规则补充）
        attraction_names = set()

        # 先添加LLM提取的景点
        for attr in llm_data.attractions:
            if attr.name and attr.name not in attraction_names:
                attraction_names.add(attr.name)
                merged["attractions"].append({
                    "name": attr.name,
                    "frequency": attr.frequency,
                    "importance": attr.importance,
                    "estimated_duration": attr.estimated_duration,
                    "category": attr.category,
                    "description": attr.description,
                    "source": "llm",
                })

        # 再添加规则提取的景点（去重）
        if rule_data and hasattr(rule_data, "attractions"):
            for attr in rule_data.attractions:
                name = attr.get("name", "") if isinstance(attr, dict) else getattr(attr, "name", "")
                if name and name not in attraction_names:
                    attraction_names.add(name)
                    merged["attractions"].append({
                        "name": name,
                        "frequency": attr.get("frequency", 1) if isinstance(attr, dict) else 1,
                        "importance": "optional",
                        "estimated_duration": 120,
                        "category": "景点",
                        "description": "",
                        "source": "rule",
                    })

        # 合并每日行程（LLM优先）
        if llm_data.itineraries:
            merged["itineraries"] = [i.to_dict() for i in llm_data.itineraries]
        elif rule_data and hasattr(rule_data, "itineraries"):
            merged["itineraries"] = rule_data.itineraries

        # 合并避坑提示（LLM优先，规则补充）
        tip_texts = set()

        # 先添加LLM提取的提示
        for tip in llm_data.tips:
            if tip.tip and tip.tip not in tip_texts:
                tip_texts.add(tip.tip)
                merged["tips"].append({
                    "tip": tip.tip,
                    "category": tip.category,
                    "severity": tip.severity,
                    "confidence": tip.confidence,
                    "source": "llm",
                })

        # 再添加规则提取的提示（去重）
        if rule_data and hasattr(rule_data, "tips"):
            for tip in rule_data.tips:
                tip_text = tip.get("tip", "") if isinstance(tip, dict) else getattr(tip, "tip", "")
                if tip_text and tip_text not in tip_texts:
                    tip_texts.add(tip_text)
                    merged["tips"].append({
                        "tip": tip_text,
                        "category": tip.get("category", "general") if isinstance(tip, dict) else "general",
                        "severity": tip.get("severity", "info") if isinstance(tip, dict) else "info",
                        "confidence": 0.6,
                        "source": "rule",
                    })

        return merged


# 单例
_llm_extractor: Optional[LLMExtractor] = None


def get_llm_extractor() -> LLMExtractor:
    """获取LLM数据提纯器单例"""
    global _llm_extractor
    if _llm_extractor is None:
        _llm_extractor = LLMExtractor()
    return _llm_extractor
