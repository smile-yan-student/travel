# -*- coding: utf-8 -*-
"""
Prompt管理模块。

统一管理项目中所有的Prompt，支持：
1. 从配置文件加载Prompt（JSON格式）
2. Prompt版本管理
3. 运行时动态修改Prompt
4. Prompt模板渲染（支持变量替换）
5. 保留原有的Prompt作为默认值，确保兼容性

设计原则：
- 所有Prompt统一管理，避免散落在各个文件中
- 支持配置文件覆盖默认值，便于调优
- 支持版本管理，便于回滚
- 支持模板渲染，便于动态生成Prompt

功能特性：
- DEFAULT_PROMPTS：默认Prompt配置（从原代码中提取，作为默认值）
- PromptManager：Prompt管理器（统一管理所有Prompt）
- 从配置文件加载Prompt
- Prompt版本管理
- 运行时动态修改Prompt
- Prompt模板渲染（支持变量替换）
- 保留原有的Prompt作为默认值，确保兼容性

使用方式：
    from app.ai.prompt_manager import PromptManager, get_prompt_manager

    # 获取Prompt管理器单例
    manager = get_prompt_manager()

    # 获取指定名称的Prompt
    prompt = manager.get_prompt("intent_extraction")

    # 渲染Prompt模板（支持变量替换）
    rendered = manager.render_prompt("intent_extraction", {"destination": "杭州"})

    # 动态修改Prompt
    manager.set_prompt("intent_extraction", "新的Prompt内容")
"""
import json
import os
import threading
from typing import Any, Dict, Optional

from ..infrastructure.logger import get_logger

logger = get_logger("prompt_manager")


# 默认Prompt配置（从原代码中提取，作为默认值）
DEFAULT_PROMPTS: Dict[str, str] = {
    # 意图识别Prompt（app/core/intent.py）
    "intent_extraction": """你是旅行规划对话助手，负责判断用户意图并从对话中提取结构化行程参数。
先判断用户最新消息的意图类型：
- 若用户在规划/调整行程（想去某地玩、生成/重做行程、改天数/预算/风格/节奏/交通/人群、增删景点点位等）→ intent 为 "plan"；
- 若用户只是普通对话或咨询（闲聊寒暄、问天气/美食/门票/交通/最佳时间、询问当前行程内容等，不要求生成或改动行程）→ intent 为 "chat"。
根据对话内容输出严格 JSON（不要 markdown、不要多余文字、不要注释）：
{
  "intent": "plan 或 chat，二选一",
  "destination": "目的地，可以是省/市/区县等任何具体可旅行地名；用户明确说出“去X玩/到X游玩/想去X”时，X 就是目的地，务必提取不要留空；整段对话完全没提到地点才给空字符串",
  "province": "省份（行政区域补全）",
  "city": "城市（行政区域补全）",
  "district": "区县（行政区域补全）",
  "days": 3,
  "origin": "出发点",
  "travelers": 1,
  "return_point": "返回点",
  "group_type": "单人/情侣/亲子/家庭/朋友/老人",
  "budget_level": "经济/适中/舒适/奢华",
  "style": "美食/人文/网红/小众/亲子/自然",
  "pace": "轻松/适中/暴走",
  "traffic_mode": "自驾/公共交通/骑行/步行/混合",
  "interests": [],
  "must_include_poi": [],
  "exclude_poi": []
}
规则：
1. 未提到的字段给默认值或空；days 未提给 3。
2. 最后一条用户消息是最新的、最权威的表述：目的地、天数等一律以它为准。
3. 目的地必须是用户明确想去的地点，从"去X/到X/在X玩/规划X的行程"等表述中提取。
4. 出发点/返回点/人数只在用户明确提到时填写，不要臆测。
5. 意图判断示例：问"杭州有什么好吃的"虽提到杭州但只是咨询 → chat；说"带爸妈去杭州玩3天，预算适中" → plan。
""",

    # 系统Prompt（app/ai/ai.py）
    "system": """你是「去见山海」的资深旅行规划师，也是用户最真诚的旅行伙伴。
你的使命是帮助更多人走出去，去旅行，去探索，激发大家行走天下的勇气。
请用温暖、真诚、博学的语气与用户交流，在规划行程的同时，也分享旅行的意义和人文故事。
""",

    # 对话系统Prompt（app/ai/ai.py）
    "chat_system": """你是「去见山海」的旅行伙伴，一名温暖真诚、博学多识的旅行向导。
你的使命是帮助更多人走出去，去旅行，去探索，激发大家行走天下的勇气。
在对话中，你可以：
1. 回答用户关于旅行的各种问题（景点、美食、天气、交通等）
2. 分享人文故事、历史背景、名人轶事
3. 推荐适合用户的旅行目的地和行程
4. 用温暖、真诚的语气与用户交流
请记住，你不仅是一个旅行规划工具，更是用户的旅行伙伴。
""",

    # 工具调用系统Prompt（app/ai/ai.py）
    "function_calling_system": """你是「去见山海」的旅行伙伴，一名温暖真诚、博学多识的旅行向导。
你可以调用以下工具来帮助用户：
1. plan_trip：规划旅行行程
2. get_weather：查询天气
3. search_poi：搜索景点
请根据用户的需求，选择合适的工具进行调用。如果不需要调用工具，请直接回答用户的问题。
""",

    # 工具回复系统Prompt（app/ai/ai.py）
    "tool_reply_system": """你是「去见山海」的旅行伙伴，一名温暖真诚、博学多识的旅行向导。
请基于工具返回的结果，用温暖、真诚的语气回答用户的问题。
如果工具返回的是行程规划结果，请简要介绍行程的亮点，并引导用户查看详细行程。
""",

    # 规划回复系统Prompt（app/ai/ai.py）
    "plan_reply_system": """你是「去见山海」的旅行伙伴，一名温暖真诚、博学多识的旅行向导。
请基于行程规划结果，用温暖、真诚的语气向用户介绍行程。
请包含以下内容：
1. 行程的总体概况（天数、目的地、适合人群）
2. 行程的亮点（必去景点、特色体验）
3. 温馨提示（注意事项、最佳游览时间）
4. 鼓励用户出发的话语
请记住，你的使命是激发大家行走天下的勇气。
""",

    # 行程优化系统Prompt（app/ai/ai.py）
    "optimize_system": """你是「去见山海」的资深旅行规划专家。
你的任务是从候选景点中筛选最适合用户的景点，并为每个景点分配主题标签和建议游览时长。
请根据用户的需求（目的地、天数、人群、预算、风格、节奏等），从候选景点中筛选最合适的景点。
请确保：
1. 景点的地理分布合理，避免来回奔波
2. 景点的类型多样，满足不同的游览需求
3. 景点的数量与天数匹配，避免过于紧凑或过于松散
4. 必去的著名景点优先安排
请输出严格的JSON格式，包含筛选后的景点列表、主题标签和建议游览时长。
""",

    # RAG景点讲解系统Prompt（app/services/rag/generator.py）
    "rag_poi_explain": """你是一位专业的旅行文化讲解员。
请基于以下知识库内容，为「{poi_name}」生成一份结构化的景点讲解。
请包含以下部分：
1. 景点概述（地理位置、历史背景、文化价值）
2. 主要看点（必去景点、特色体验）
3. 人文故事（历史名人、传说故事、文化内涵）
4. 游览建议（最佳游览时间、游览路线、注意事项）
请用温暖、生动的语言，让用户感受到景点的魅力。
知识库内容：
{knowledge}
""",

    # RAG问答系统Prompt（app/services/rag/generator.py）
    "rag_qa": """你是一位专业的旅行文化顾问。
请基于以下知识库内容，回答用户关于「{poi_name}」的问题。
请确保回答准确、全面、生动，同时引用知识库中的内容作为依据。
如果知识库中没有相关内容，请如实告知，并给出一般性的建议。
知识库内容：
{knowledge}
用户问题：{question}
""",
}


class PromptManager:
    """Prompt管理器，统一管理所有Prompt。"""

    def __init__(self, config_path: Optional[str] = None):
        """初始化Prompt管理器。

        参数：
            config_path: Prompt配置文件路径（JSON格式），如果为None则使用默认配置
        """
        self._lock = threading.Lock()
        self._prompts: Dict[str, str] = dict(DEFAULT_PROMPTS)
        self._versions: Dict[str, int] = {name: 1 for name in DEFAULT_PROMPTS}
        self._config_path = config_path

        # 从配置文件加载Prompt
        if config_path and os.path.exists(config_path):
            self._load_from_file(config_path)

        logger.info("prompt_manager_initialized", extra={
            "fields": {
                "prompt_count": len(self._prompts),
                "config_path": config_path,
            }
        })

    def _load_from_file(self, config_path: str) -> None:
        """从配置文件加载Prompt。"""
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            prompts = config.get("prompts", {})
            versions = config.get("versions", {})

            with self._lock:
                for name, content in prompts.items():
                    if isinstance(content, str) and content.strip():
                        self._prompts[name] = content
                        self._versions[name] = versions.get(name, 1)

            logger.info("prompt_manager_loaded_from_file", extra={
                "fields": {
                    "config_path": config_path,
                    "loaded_count": len(prompts),
                }
            })
        except Exception as e:
            logger.warning("prompt_manager_load_failed", extra={
                "fields": {
                    "config_path": config_path,
                    "error": str(e),
                }
            })

    def save_to_file(self, config_path: Optional[str] = None) -> bool:
        """保存当前Prompt配置到文件。

        参数：
            config_path: 保存路径，如果为None则使用初始化时的路径

        返回：
            bool: 是否保存成功
        """
        save_path = config_path or self._config_path
        if not save_path:
            logger.warning("prompt_manager_save_no_path")
            return False

        try:
            with self._lock:
                config = {
                    "prompts": dict(self._prompts),
                    "versions": dict(self._versions),
                }

            # 确保目录存在
            os.makedirs(os.path.dirname(save_path), exist_ok=True)

            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)

            logger.info("prompt_manager_saved_to_file", extra={
                "fields": {
                    "config_path": save_path,
                    "prompt_count": len(self._prompts),
                }
            })
            return True
        except Exception as e:
            logger.warning("prompt_manager_save_failed", extra={
                "fields": {
                    "config_path": save_path,
                    "error": str(e),
                }
            })
            return False

    def get_prompt(self, name: str, **kwargs: Any) -> str:
        """获取Prompt，支持模板渲染。

        参数：
            name: Prompt名称
            **kwargs: 模板变量（用于替换Prompt中的{variable}）

        返回：
            str: 渲染后的Prompt内容
        """
        with self._lock:
            content = self._prompts.get(name, "")

        if not content:
            logger.warning("prompt_manager_prompt_not_found", extra={
                "fields": {"name": name}
            })
            return ""

        # 模板渲染
        if kwargs:
            try:
                content = content.format(**kwargs)
            except KeyError as e:
                logger.warning("prompt_manager_template_render_failed", extra={
                    "fields": {
                        "name": name,
                        "missing_key": str(e),
                    }
                })

        return content

    def set_prompt(self, name: str, content: str) -> bool:
        """设置Prompt内容。

        参数：
            name: Prompt名称
            content: Prompt内容

        返回：
            bool: 是否设置成功
        """
        if not name or not content or not content.strip():
            return False

        with self._lock:
            self._prompts[name] = content
            self._versions[name] = self._versions.get(name, 0) + 1

        logger.info("prompt_manager_prompt_updated", extra={
            "fields": {
                "name": name,
                "version": self._versions.get(name),
                "content_length": len(content),
            }
        })
        return True

    def get_version(self, name: str) -> int:
        """获取Prompt的版本号。"""
        with self._lock:
            return self._versions.get(name, 0)

    def list_prompts(self) -> Dict[str, Dict[str, Any]]:
        """列出所有Prompt的元信息（不包含完整内容）。"""
        with self._lock:
            return {
                name: {
                    "version": self._versions.get(name, 0),
                    "content_length": len(self._prompts.get(name, "")),
                }
                for name in self._prompts
            }

    def reset_prompt(self, name: str) -> bool:
        """重置Prompt为默认值。"""
        if name not in DEFAULT_PROMPTS:
            return False

        with self._lock:
            self._prompts[name] = DEFAULT_PROMPTS[name]
            self._versions[name] = 1

        logger.info("prompt_manager_prompt_reset", extra={
            "fields": {"name": name}
        })
        return True

    def reset_all(self) -> None:
        """重置所有Prompt为默认值。"""
        with self._lock:
            self._prompts = dict(DEFAULT_PROMPTS)
            self._versions = {name: 1 for name in DEFAULT_PROMPTS}

        logger.info("prompt_manager_all_reset")


# 全局Prompt管理器实例
_prompt_manager: Optional[PromptManager] = None
_prompt_manager_lock = threading.Lock()


def get_prompt_manager() -> PromptManager:
    """获取全局Prompt管理器实例（单例）。"""
    global _prompt_manager
    if _prompt_manager is None:
        with _prompt_manager_lock:
            if _prompt_manager is None:
                # 从环境变量获取配置文件路径
                config_path = os.getenv("PROMPT_CONFIG_PATH", "")
                _prompt_manager = PromptManager(config_path if config_path else None)
    return _prompt_manager


def get_prompt(name: str, **kwargs: Any) -> str:
    """便捷函数：获取Prompt。"""
    return get_prompt_manager().get_prompt(name, **kwargs)
