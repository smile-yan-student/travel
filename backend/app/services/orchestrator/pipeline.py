"""
终极链路编排器（Orchestrator）。

实现最终版方案的核心架构：
用户输入/多轮对话 → LLM意图解析 → 规划引擎生成合法点位池+硬约束 → LLM在约束内编排行程+人文内容 → 规划引擎二次校验修复 → 返回前端

职责边界：
- 硬规则规划引擎：只做客观、可校验、数学级正确的事情
  - 用户意图参数校验、补全、缺省
  - 目的地层级解析（省/市/区县/单点）
  - POI分层筛选：主景点、子景点、周边市井小吃街区
  - 地理聚类算法（就近优先、向外扩散）
  - 真实地图耗时、距离计算
  - 住宿=次日起点规则
  - 跨天内容去重
  - 行程体量合理性校验（防止太少/太臃肿）
  - 行程时间轴合法性校验（前后时间冲突修复）

- LLM智能语义层：只做创作、理解、润色、多轮推理
  - 自然语言多轮理解
  - 局部行程修改（增量修改，不全局重写）
  - 人文历史内容生成
  - 景点简介、典故、游玩建议
  - 结构化行程编排（在引擎给出的合法点位池内编排）

功能特性：
- 完整的终极链路编排（4个阶段）
- 行程工作记忆（每个会话一个实例，保存完整行程状态和修改历史）
- LLM意图解析（从用户自然语言中提取规划参数）
- 规划引擎生成合法点位池 + 硬约束
- LLM在约束内编排行程 + 人文内容（预留接口）
- 规划引擎二次校验修复（自动修复验证问题）
- 全局单例（获取全局编排器单例）

使用方式：
    from app.services.orchestrator.pipeline import get_orchestrator

    # 获取全局编排器单例
    orchestrator = get_orchestrator()

    # 执行完整的终极链路
    plan_response, workspace = await orchestrator.execute_full_pipeline(
        user_input="去杭州玩3天",
        session_id="abc123"
    )

    # 查看行程响应
    print(plan_response.destination)  # 杭州
    print(plan_response.days)  # 3

    # 查看行程工作记忆
    print(workspace.status)  # generated
    print(workspace.get_all_pois())  # 所有POI
"""
import asyncio
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from ... import ai as ai_mod
from ...skills.itinerary_planner import build_plan as _engine_build_plan
from ...data.models.models import PlanRequest, PlanResponse
from ...infrastructure import logger as log_mod
from ..session import (
    ItineraryWorkspace,
    get_incremental_editor,
    get_session_store,
)
from .validators import PlanValidator, ValidationResult

_logger = log_mod.get_logger("orchestrator")


class Orchestrator:
    """
    终极链路编排器。

    协调LLM意图解析、规划引擎点位池生成、LLM编排、引擎二次校验。
    """

    def __init__(self) -> None:
        """初始化编排器。"""
        self.validator = PlanValidator()
        self.session_store = get_session_store()
        self.incremental_editor = get_incremental_editor()

    async def execute_full_pipeline(
        self,
        user_input: str,
        session_id: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[PlanResponse, ItineraryWorkspace]:
        """
        执行完整的终极链路。

        Args:
            user_input: 用户自然语言输入
            session_id: 会话ID（用于行程工作记忆）
            context: 额外上下文

        Returns:
            Tuple[PlanResponse, ItineraryWorkspace]: (行程响应, 行程工作记忆)
        """
        request_id = uuid.uuid4().hex[:12]
        start_time = time.time()
        _logger.info(
            "orchestrator_pipeline_start",
            extra={
                "fields": {
                    "request_id": request_id,
                    "session_id": session_id,
                    "user_input": user_input[:100],
                }
            },
        )

        # 获取或创建行程工作记忆
        workspace = self.session_store.get_or_create_session(session_id)
        workspace.add_instruction(user_input)

        try:
            # ========== 阶段1: LLM意图解析 ==========
            _logger.info(
                "pipeline_stage_1_intent_parsing",
                extra={"fields": {"request_id": request_id}},
            )
            plan_request = await self._parse_intent(user_input, workspace, context)
            workspace.original_params = plan_request.model_dump()

            # ========== 阶段2: 规划引擎生成合法点位池 + 硬约束 ==========
            _logger.info(
                "pipeline_stage_2_engine_poi_pool",
                extra={"fields": {"request_id": request_id}},
            )
            plan_response = await self._engine_generate_poi_pool(
                plan_request, request_id
            )

            # ========== 阶段3: LLM在约束内编排行程 + 人文内容 ==========
            # 注意：现有planner.py已在build_plan内部调用了ai_mod.optimize_itinerary
            # 这里保留接口，后续可进一步拆分
            _logger.info(
                "pipeline_stage_3_llm_arrangement",
                extra={"fields": {"request_id": request_id}},
            )
            # plan_response = await self._llm_arrange_itinerary(plan_response, plan_request)

            # ========== 阶段4: 规划引擎二次校验修复 ==========
            _logger.info(
                "pipeline_stage_4_engine_validation",
                extra={"fields": {"request_id": request_id}},
            )
            validation_result = self.validator.validate(plan_response)
            if not validation_result.is_valid:
                _logger.info(
                    "pipeline_validation_issues_found",
                    extra={
                        "fields": {
                            "request_id": request_id,
                            "issues": validation_result.issues[:5],
                        }
                    },
                )
                plan_response = self.validator.auto_fix(
                    plan_response, validation_result
                )

            # 更新工作记忆
            workspace.update_plan(plan_response.model_dump())
            workspace.source = plan_response.source
            workspace.status = "generated"
            self.session_store.update_session(workspace)

            duration_ms = (time.time() - start_time) * 1000
            _logger.info(
                "orchestrator_pipeline_complete",
                extra={
                    "fields": {
                        "request_id": request_id,
                        "session_id": workspace.session_id,
                        "destination": plan_response.destination,
                        "days": plan_response.days,
                        "total_pois": len(workspace.get_all_pois()),
                        "duration_ms": round(duration_ms, 2),
                        "validation_passed": validation_result.is_valid,
                        "validation_issues": len(validation_result.issues),
                    }
                },
            )

            return plan_response, workspace

        except Exception as e:
            _logger.error(
                "orchestrator_pipeline_failed",
                extra={"fields": {"request_id": request_id, "error": str(e)}},
            )
            raise

    async def _parse_intent(
        self,
        user_input: str,
        workspace: ItineraryWorkspace,
        context: Optional[Dict[str, Any]] = None,
    ) -> PlanRequest:
        """
        阶段1: LLM意图解析。

        从用户自然语言中提取规划参数（目的地、天数、人群、预算、风格等）。

        Args:
            user_input: 用户自然语言输入
            workspace: 行程工作记忆
            context: 额外上下文

        Returns:
            PlanRequest: 规划请求
        """
        # 优先使用已有意图解析模块
        from app.skills.intent_recognition.legacy_parser import parse_intent

        try:
            intent_result = parse_intent([user_input])
            if intent_result and intent_result.get("destination"):
                params = intent_result
                # 合并工作记忆中的用户偏好
                params = self._merge_preferences(params, workspace)
                return PlanRequest(**params)
        except Exception as e:
            _logger.warning(
                "intent_parse_failed_fallback_to_default",
                extra={"fields": {"error": str(e)}},
            )

        # 兜底：使用默认参数
        return PlanRequest(destination=user_input[:50] or "杭州")

    def _merge_preferences(
        self, params: Dict[str, Any], workspace: ItineraryWorkspace
    ) -> Dict[str, Any]:
        """
        合并工作记忆中的用户偏好（隐性偏好学习的应用）。

        Args:
            params: 规划参数
            workspace: 行程工作记忆

        Returns:
            Dict[str, Any]: 合并后的规划参数
        """
        prefs = workspace.preferences
        if prefs.pace_preference and not params.get("pace"):
            params["pace"] = prefs.pace_preference
        if prefs.transport_preference and not params.get("traffic_mode"):
            params["traffic_mode"] = prefs.transport_preference
        if prefs.theme_preferences and not params.get("style"):
            params["style"] = "+".join(prefs.theme_preferences[:2])
        return params

    async def _engine_generate_poi_pool(
        self,
        plan_request: PlanRequest,
        request_id: str,
    ) -> PlanResponse:
        """
        阶段2: 规划引擎生成合法点位池 + 硬约束。

        调用现有planner.py的build_plan（已包含行政分级枚举、聚类、逐日构建等）。

        Args:
            plan_request: 规划请求
            request_id: 请求ID（用于日志追踪）

        Returns:
            PlanResponse: 规划响应
        """
        # 注入request_id用于日志追踪
        plan_request_dict = plan_request.model_dump()
        plan_request_dict["request_id"] = request_id
        return await _engine_build_plan(plan_request)

    async def _llm_arrange_itinerary(
        self,
        plan_response: PlanResponse,
        plan_request: PlanRequest,
    ) -> PlanResponse:
        """
        阶段3: LLM在约束内编排行程 + 人文内容。

        （预留接口，现有逻辑已在planner.py内部实现，后续可进一步拆分）

        Args:
            plan_response: 规划响应
            plan_request: 规划请求

        Returns:
            PlanResponse: 编排后的规划响应
        """
        # TODO: 进一步拆分LLM编排逻辑到独立模块
        return plan_response


# 全局单例
_orchestrator: Optional[Orchestrator] = None


def get_orchestrator() -> Orchestrator:
    """
    获取全局编排器单例。

    Returns:
        Orchestrator: 全局编排器单例
    """
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator
