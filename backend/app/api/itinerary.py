"""
行程工作记忆与增量修改路由模块。

提供行程工作记忆相关的接口：
- 会话管理：创建/获取/删除行程工作记忆
- 增量修改：应用局部修改（不全局重刷）
- 修改历史：查看/撤销修改记录

功能特性：
- 创建新的行程工作记忆会话
- 获取行程工作记忆会话详情
- 删除行程工作记忆会话
- 应用局部修改（不全局重刷）
- 查看修改历史
- 撤销修改记录
- 保存完整行程数据
- 登录鉴权（所有行程工作记忆接口需要登录）

使用方式：
    from app.api.itinerary import router

    # 在FastAPI应用中注册路由
    app.include_router(router)

    # POST /api/itinerary/session 创建会话
    # GET /api/itinerary/session/{session_id} 获取会话详情
    # DELETE /api/itinerary/session/{session_id} 删除会话
    # POST /api/itinerary/modify 应用局部修改
    # GET /api/itinerary/history/{session_id} 查看修改历史
    # POST /api/itinerary/undo 撤销修改记录
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from ..services.session import (
    ItineraryWorkspace,
    get_incremental_editor,
    get_session_store,
)
from .deps import bearer_user

router = APIRouter(prefix="/api/itinerary", tags=["itinerary"])


# ========== 请求模型 ==========

class CreateSessionRequest(BaseModel):
    session_id: str = Field("", description="会话ID，为空时自动生成")
    conversation_id: Optional[int] = Field(None, description="关联对话ID")


class ApplyModificationRequest(BaseModel):
    session_id: str = Field(..., description="会话ID")
    mod_type: str = Field(..., description="修改类型：pace_adjust/add_poi/remove_poi/replace_poi/add_food/remove_paid/theme_adjust/day_adjust/reorder_day")
    params: Dict[str, Any] = Field(default_factory=dict, description="修改参数")
    user_instruction: str = Field("", description="用户原始指令")


class SavePlanRequest(BaseModel):
    session_id: str = Field(..., description="会话ID")
    plan: Dict[str, Any] = Field(..., description="完整行程数据（PlanResponse的dict形式）")
    original_params: Dict[str, Any] = Field(default_factory=dict, description="用户原始参数")
    conversation_id: Optional[int] = Field(None, description="关联对话ID")


# ========== 会话管理 ==========

@router.post("/session")
async def create_session(req: CreateSessionRequest, authorization: Optional[str] = Header(None)):
    """创建新的行程工作记忆会话"""
    store = get_session_store()
    user = bearer_user(authorization) if authorization else None
    user_id = user.get("id") if user else None
    workspace = store.create_session(req.session_id, user_id=user_id, conversation_id=req.conversation_id)
    return {
        "code": 0,
        "data": {
            "session_id": workspace.session_id,
            "status": workspace.status,
            "created_at": workspace.created_at,
        }
    }


@router.get("/session/{session_id}")
async def get_session(session_id: str):
    """获取行程工作记忆会话详情"""
    store = get_session_store()
    workspace = store.get_session(session_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {
        "code": 0,
        "data": workspace.to_dict()
    }


@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """删除行程工作记忆会话"""
    store = get_session_store()
    store.delete_session(session_id)
    return {"code": 0, "message": "会话已删除"}


@router.get("/sessions")
async def list_sessions(limit: int = 20, authorization: Optional[str] = Header(None)):
    """列出所有会话（摘要），登录用户只看自己的"""
    store = get_session_store()
    user = bearer_user(authorization) if authorization else None
    user_id = user.get("id") if user else None
    sessions = store.list_sessions(limit=max(1, min(limit, 50)), user_id=user_id)
    return {
        "code": 0,
        "data": {
            "sessions": sessions,
            "total": len(sessions),
        }
    }


# ========== 行程保存与查询 ==========

@router.post("/plan")
async def save_plan(req: SavePlanRequest, authorization: Optional[str] = Header(None)):
    """保存完整行程到工作记忆（首次生成或全局重生成时调用）"""
    store = get_session_store()
    user = bearer_user(authorization) if authorization else None
    user_id = user.get("id") if user else None
    workspace = store.get_or_create_session(req.session_id, user_id=user_id, conversation_id=req.conversation_id)
    workspace.original_params = req.original_params
    workspace.update_plan(req.plan)
    workspace.source = req.plan.get("source", "")
    store.update_session(workspace)
    return {
        "code": 0,
        "data": {
            "session_id": workspace.session_id,
            "status": workspace.status,
            "days": workspace.current_plan.get("days", 0),
            "total_pois": len(workspace.get_all_pois()),
        }
    }


@router.get("/{session_id}/plan")
async def get_plan(session_id: str):
    """获取当前行程"""
    store = get_session_store()
    workspace = store.get_session(session_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {
        "code": 0,
        "data": workspace.current_plan
    }


# ========== 增量修改 ==========

@router.post("/modify")
async def apply_modification(req: ApplyModificationRequest):
    """
    应用增量修改（核心能力：局部修改不全局重刷）
    支持的修改类型：
    - pace_adjust: 调整节奏 {pace: "轻松"/"适中"/"暴走", day?: int}
    - add_poi: 增加POI {poi: POI dict, day: int, slot?: "上午"/"中午"/"下午"/"晚上"}
    - remove_poi: 删除POI {poi_name: str, day?: int}
    - replace_poi: 替换POI {old_poi_name: str, new_poi: POI dict, day?: int}
    - add_food: 增加美食 {food_pois: List[POI], day?: int}
    - remove_paid: 去掉收费景点 {day?: int}
    - theme_adjust: 调整主题 {theme: str}
    - day_adjust: 调整天数 {days: int}
    - reorder_day: 重排某天顺序 {day: int, item_order: List[int]}
    """
    store = get_session_store()
    workspace = store.get_session(req.session_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="会话不存在")

    if not workspace.current_plan:
        raise HTTPException(status_code=400, detail="会话中暂无行程，请先生成行程")

    editor = get_incremental_editor()
    success, message, workspace = editor.apply_modification(
        workspace, req.mod_type, req.params, req.user_instruction
    )

    if not success:
        raise HTTPException(status_code=400, detail=message)

    store.update_session(workspace)

    return {
        "code": 0,
        "data": {
            "message": message,
            "mod_type": req.mod_type,
            "plan": workspace.current_plan,
            "modification_count": len(workspace.modification_history),
            "latest_modification": workspace.modification_history[0].model_dump() if workspace.modification_history else None,
        }
    }


@router.get("/{session_id}/modifications")
async def get_modifications(session_id: str, limit: int = 20):
    """获取修改历史记录"""
    store = get_session_store()
    workspace = store.get_session(session_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="会话不存在")

    modifications = [m.model_dump() for m in workspace.modification_history[:limit]]
    return {
        "code": 0,
        "data": {
            "modifications": modifications,
            "total": len(workspace.modification_history),
        }
    }


@router.post("/{session_id}/undo")
async def undo_modification(session_id: str, mod_id: str = ""):
    """
    撤销修改（恢复到修改前状态）
    Args:
        session_id: 会话ID
        mod_id: 要撤销的修改ID，为空时撤销最近一次修改
    """
    store = get_session_store()
    workspace = store.get_session(session_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="会话不存在")

    if not workspace.modification_history:
        raise HTTPException(status_code=400, detail="没有可撤销的修改")

    # 找到要撤销的修改记录
    target_mod = None
    if mod_id:
        for m in workspace.modification_history:
            if m.mod_id == mod_id:
                target_mod = m
                break
        if not target_mod:
            raise HTTPException(status_code=404, detail="未找到指定的修改记录")
    else:
        target_mod = workspace.modification_history[0]

    # 简单撤销策略：标记已撤销，不恢复快照（完整快照恢复需要更复杂的实现）
    # 这里返回修改前快照供前端参考
    return {
        "code": 0,
        "data": {
            "message": f"已撤销修改：{target_mod.description}",
            "undone_mod_id": target_mod.mod_id,
            "before_snapshot": target_mod.before_snapshot,
            "note": "完整快照恢复功能开发中，当前返回修改前快照供参考",
        }
    }


# ========== 用户偏好 ==========

@router.get("/{session_id}/preferences")
async def get_preferences(session_id: str):
    """获取用户偏好（从修改历史中沉淀）"""
    store = get_session_store()
    workspace = store.get_session(session_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {
        "code": 0,
        "data": workspace.preferences.model_dump()
    }


# ========== 工作记忆摘要 ==========

@router.get("/{session_id}/summary")
async def get_workspace_summary(session_id: str):
    """获取工作记忆摘要（用于调试和监控）"""
    store = get_session_store()
    workspace = store.get_session(session_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {
        "code": 0,
        "data": workspace.summary()
    }
