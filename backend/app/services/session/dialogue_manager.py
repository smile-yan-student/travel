"""
多轮对话管理模块（Multi-turn Dialogue Manager）。

维护对话状态，检测参数缺失，智能追问缺失的关键参数，支持多轮参数补充。

核心功能：
1. 对话状态维护：记录已收集的规划参数
2. 参数缺失检测：检测哪些关键参数缺失
3. 智能追问：根据已有的参数，智能地追问缺失的关键参数
4. 多轮补充：支持用户在多轮对话中逐步补充参数
5. 状态重置：当用户开始新的规划时，重置对话状态

功能特性：
- 关键参数定义（按优先级排序，目的地、天数）
- 可选参数定义（出行人数、预算、风格、节奏、出行方式等）
- 对话状态数据类（参数、已收集参数、缺失参数、追问计数、最后追问参数）
- 对话处理结果数据类（是否需要追问、追问消息、追问参数、参数、状态）
- 多轮对话管理器（处理用户消息、维护对话状态、判断是否需要追问）
- 新规划意图检测（自动重置对话状态）
- 智能追问消息生成（根据追问次数选择不同模板）
- 默认值兜底（追问3次后使用默认值）
- 会话超时清理（默认30分钟）
- 全局单例

使用方式：
    from app.services.session.dialogue_manager import get_dialogue_manager

    # 获取全局对话管理器单例
    manager = get_dialogue_manager()

    # 处理用户消息，返回是否需要追问以及追问内容
    result = manager.process_message(
        session_id="abc123",
        user_message="我想去杭州玩",
        extracted_params={"destination": "杭州"},
        intent="plan"
    )

    if result.need_clarification:
        # 需要追问
        print(f"追问: {result.clarification_message}")
        print(f"追问参数: {result.clarification_param}")
    else:
        # 参数完整，可以开始规划
        print(f"参数: {result.params}")
        print(f"已收集参数: {result.newly_collected}")
"""
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ...infrastructure import logger as log_mod

_dialogue_logger = log_mod.get_logger("dialogue_manager")


# 关键参数定义（按优先级排序）
CRITICAL_PARAMS = [
    {
        "key": "destination",
        "name": "目的地",
        "required": True,
        "clarification_templates": [
            "你心里已经有想去的远方了吗？告诉我一个名字，我替你把它变成出发的理由——比如「去成都玩4天，节奏慢一点」。",
            "世界很大，而我们正从一次出发开始。你想去哪儿？哪怕只是一个城市的名字，比如「杭州」「西安」。",
            "每一次远行，都始于一个名字。你想去哪里？告诉我目的地，我来帮你规划剩下的一切。",
        ],
    },
    {
        "key": "days",
        "name": "天数",
        "required": True,
        "default": 3,
        "clarification_templates": [
            "打算在{destination}玩几天呢？比如3天2夜、5天4晚，告诉我天数，我帮你安排得刚刚好。",
            "在{destination}停留多久比较合适？告诉我你的时间，比如「3天」或「5天」，我来规划节奏。",
            "时间是旅行的画布。你打算在{destination}画几天？告诉我天数，我来填充风景。",
        ],
    },
]

# 可选参数（不需要主动追问，但用户提到时会记录）
OPTIONAL_PARAMS = [
    "travelers",
    "budget_level",
    "style",
    "pace",
    "traffic_mode",
    "origin",
    "return_point",
    "interests",
    "must_include_poi",
    "exclude_poi",
]


@dataclass
class DialogueState:
    """
    对话状态。

    Attributes:
        session_id: 会话ID
        params: 已收集的参数
        collected_params: 已收集的参数列表
        missing_params: 缺失的参数列表
        clarification_count: 追问计数
        last_clarification_param: 最后追问的参数
        last_update_time: 最后更新时间
        created_time: 创建时间
    """

    session_id: str
    params: Dict[str, Any] = field(default_factory=dict)
    collected_params: List[str] = field(default_factory=list)
    missing_params: List[str] = field(default_factory=list)
    clarification_count: int = 0
    last_clarification_param: str = ""
    last_update_time: float = field(default_factory=time.time)
    created_time: float = field(default_factory=time.time)

    def is_complete(self) -> bool:
        """
        检查是否所有关键参数都已收集。

        Returns:
            bool: 是否完整
        """
        for param in CRITICAL_PARAMS:
            if param["required"] and not self.params.get(param["key"]):
                return False
        return True

    def get_missing_params(self) -> List[str]:
        """
        获取缺失的关键参数。

        Returns:
            List[str]: 缺失的参数列表
        """
        missing = []
        for param in CRITICAL_PARAMS:
            if param["required"] and not self.params.get(param["key"]):
                missing.append(param["key"])
        return missing

    def update_params(self, new_params: Dict[str, Any]) -> List[str]:
        """
        更新参数，返回新收集的参数列表。

        Args:
            new_params: 新参数

        Returns:
            List[str]: 新收集的参数列表
        """
        newly_collected = []
        for key, value in new_params.items():
            if value and (key not in self.params or not self.params[key]):
                self.params[key] = value
                newly_collected.append(key)
                if key not in self.collected_params:
                    self.collected_params.append(key)
        self.last_update_time = time.time()
        self.missing_params = self.get_missing_params()
        return newly_collected

    def reset(self) -> None:
        """重置对话状态。"""
        self.params = {}
        self.collected_params = []
        self.missing_params = []
        self.clarification_count = 0
        self.last_clarification_param = ""
        self.last_update_time = time.time()


@dataclass
class DialogueResult:
    """
    对话处理结果。

    Attributes:
        need_clarification: 是否需要追问
        clarification_message: 追问消息
        clarification_param: 追问参数
        params: 已收集的参数
        state: 对话状态
        is_new_session: 是否是新会话
        newly_collected: 新收集的参数列表
    """

    need_clarification: bool = False
    clarification_message: str = ""
    clarification_param: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    state: Optional[DialogueState] = None
    is_new_session: bool = False
    newly_collected: List[str] = field(default_factory=list)


class DialogueManager:
    """多轮对话管理器。"""

    def __init__(self, max_sessions: int = 1000, session_timeout: int = 1800) -> None:
        """
        初始化对话管理器。

        Args:
            max_sessions: 最大会话数
            session_timeout: 会话超时时间（秒），默认30分钟
        """
        self.sessions: Dict[str, DialogueState] = {}
        self.max_sessions = max_sessions
        self.session_timeout = session_timeout

    def _cleanup_expired_sessions(self) -> None:
        """清理过期的会话。"""
        now = time.time()
        expired = [
            sid
            for sid, state in self.sessions.items()
            if now - state.last_update_time > self.session_timeout
        ]
        for sid in expired:
            del self.sessions[sid]
        if expired:
            _dialogue_logger.info(
                "cleanup_expired_sessions",
                extra={
                    "fields": {
                        "expired_count": len(expired),
                        "remaining_count": len(self.sessions),
                    }
                },
            )

    def _get_or_create_session(self, session_id: str) -> Tuple[DialogueState, bool]:
        """
        获取或创建会话状态。

        Args:
            session_id: 会话ID

        Returns:
            Tuple[DialogueState, bool]: (对话状态, 是否是新会话)
        """
        # 清理过期会话
        if len(self.sessions) >= self.max_sessions:
            self._cleanup_expired_sessions()

        is_new = session_id not in self.sessions
        if is_new:
            self.sessions[session_id] = DialogueState(session_id=session_id)
            _dialogue_logger.info(
                "create_session",
                extra={
                    "fields": {
                        "session_id": session_id,
                        "total_sessions": len(self.sessions),
                    }
                },
            )

        return self.sessions[session_id], is_new

    def _detect_new_plan_intent(self, message: str) -> bool:
        """
        检测是否是新的规划意图（需要重置对话状态）。

        Args:
            message: 用户消息

        Returns:
            bool: 是否是新的规划意图
        """
        new_plan_keywords = [
            "重新规划",
            "重新来",
            "换个地方",
            "换个目的地",
            "我想去",
            "我要去",
            "帮我规划",
            "给我规划",
            "去.*玩",
            "去.*旅游",
            "去.*旅行",
        ]
        for pattern in new_plan_keywords:
            if re.search(pattern, message):
                return True
        return False

    def _generate_clarification_message(
        self, param_key: str, params: Dict[str, Any]
    ) -> str:
        """
        生成追问消息。

        Args:
            param_key: 参数键
            params: 已收集的参数

        Returns:
            str: 追问消息
        """
        for param in CRITICAL_PARAMS:
            if param["key"] == param_key:
                templates = param["clarification_templates"]
                # 根据追问次数选择不同的模板
                idx = min(params.get("clarification_count", 0), len(templates) - 1)
                template = templates[idx]
                # 替换占位符
                message = template.format(**params)
                return message
        return "请告诉我更多信息，我来帮你规划。"

    def process_message(
        self,
        session_id: str,
        user_message: str,
        extracted_params: Dict[str, Any],
        intent: str = "plan",
    ) -> DialogueResult:
        """
        处理用户消息，维护对话状态，判断是否需要追问。

        Args:
            session_id: 会话ID
            user_message: 用户消息
            extracted_params: 从用户消息中提取的参数
            intent: 意图类型（plan/chat/weather/poi）

        Returns:
            DialogueResult: 对话处理结果
        """
        # 获取或创建会话状态
        state, is_new = self._get_or_create_session(session_id)

        # 如果是新的规划意图，重置对话状态
        if (
            intent == "plan"
            and self._detect_new_plan_intent(user_message)
            and not is_new
        ):
            _dialogue_logger.info(
                "reset_session_new_plan",
                extra={
                    "fields": {
                        "session_id": session_id,
                        "old_params": state.params,
                    }
                },
            )
            state.reset()
            is_new = True

        # 更新参数
        newly_collected = state.update_params(extracted_params)

        # 如果是chat意图，不需要追问
        if intent == "chat":
            return DialogueResult(
                need_clarification=False,
                params=state.params.copy(),
                state=state,
                is_new_session=is_new,
                newly_collected=newly_collected,
            )

        # 检查是否需要追问
        missing_params = state.get_missing_params()
        if missing_params:
            # 选择第一个缺失的关键参数进行追问
            param_to_clarify = missing_params[0]

            # 避免重复追问同一个参数（除非用户没有回答）
            if (
                state.last_clarification_param == param_to_clarify
                and state.clarification_count > 2
            ):
                # 已经追问3次，使用默认值
                for param in CRITICAL_PARAMS:
                    if param["key"] == param_to_clarify and param.get("default"):
                        state.params[param_to_clarify] = param["default"]
                        _dialogue_logger.info(
                            "use_default_param",
                            extra={
                                "fields": {
                                    "session_id": session_id,
                                    "param": param_to_clarify,
                                    "default_value": param["default"],
                                }
                            },
                        )
                        # 重新检查缺失参数
                        missing_params = state.get_missing_params()
                        if not missing_params:
                            return DialogueResult(
                                need_clarification=False,
                                params=state.params.copy(),
                                state=state,
                                is_new_session=is_new,
                                newly_collected=newly_collected,
                            )
                        param_to_clarify = missing_params[0]
                        break

            # 生成追问消息
            clarification_params = state.params.copy()
            clarification_params["clarification_count"] = state.clarification_count
            clarification_message = self._generate_clarification_message(
                param_to_clarify, clarification_params
            )

            # 更新追问计数
            state.clarification_count += 1
            state.last_clarification_param = param_to_clarify

            _dialogue_logger.info(
                "need_clarification",
                extra={
                    "fields": {
                        "session_id": session_id,
                        "param": param_to_clarify,
                        "clarification_count": state.clarification_count,
                        "collected_params": state.collected_params,
                        "missing_params": missing_params,
                    }
                },
            )

            return DialogueResult(
                need_clarification=True,
                clarification_message=clarification_message,
                clarification_param=param_to_clarify,
                params=state.params.copy(),
                state=state,
                is_new_session=is_new,
                newly_collected=newly_collected,
            )

        # 所有关键参数都已收集，不需要追问
        _dialogue_logger.info(
            "params_complete",
            extra={
                "fields": {
                    "session_id": session_id,
                    "params": state.params,
                    "collected_params": state.collected_params,
                }
            },
        )

        return DialogueResult(
            need_clarification=False,
            params=state.params.copy(),
            state=state,
            is_new_session=is_new,
            newly_collected=newly_collected,
        )

    def get_session(self, session_id: str) -> Optional[DialogueState]:
        """
        获取会话状态。

        Args:
            session_id: 会话ID

        Returns:
            Optional[DialogueState]: 对话状态，不存在返回None
        """
        return self.sessions.get(session_id)

    def reset_session(self, session_id: str) -> None:
        """
        重置会话状态。

        Args:
            session_id: 会话ID
        """
        if session_id in self.sessions:
            self.sessions[session_id].reset()
            _dialogue_logger.info(
                "reset_session",
                extra={"fields": {"session_id": session_id}},
            )

    def delete_session(self, session_id: str) -> None:
        """
        删除会话。

        Args:
            session_id: 会话ID
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
            _dialogue_logger.info(
                "delete_session",
                extra={"fields": {"session_id": session_id}},
            )


# 单例
_singleton_instance: Optional[DialogueManager] = None


def get_dialogue_manager() -> DialogueManager:
    """
    获取对话管理器单例。

    Returns:
        DialogueManager: 全局对话管理器单例
    """
    global _singleton_instance
    if _singleton_instance is None:
        _singleton_instance = DialogueManager()
    return _singleton_instance
