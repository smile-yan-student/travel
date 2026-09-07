"""
对话历史路由模块。

提供对话历史相关的接口：
- /api/conversations/stream - 统一对话流（按时间倒序返回会话）
- /api/conversations - 会话列表
- /api/conversations/{conv_id} - 获取会话详情
- /api/conversations - 保存会话
- /api/conversations/{conv_id} - 删除会话

功能特性：
- 统一对话流（按时间倒序返回会话，支持before_id游标分页拉更早历史）
- 历史会话列表（标题/时间/消息数，按时间倒序）
- 加载某条历史会话（含messages与内嵌行程）
- 保存会话（新增或更新）
- 删除会话
- 登录鉴权（所有会话接口需要登录）

使用方式：
    from app.api.conversations import router

    # 在FastAPI应用中注册路由
    app.include_router(router)

    # GET /api/conversations/stream 获取对话流
    # GET /api/conversations 获取会话列表
    # GET /api/conversations/{conv_id} 获取会话详情
    # POST /api/conversations 保存会话
    # DELETE /api/conversations/{conv_id} 删除会话
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Header, HTTPException

from ..data.repositories import user_repository
from .deps import ConversationSave, bearer_user

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


def _require_user(authorization: Optional[str]) -> dict:
    user = bearer_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="未登录或登录已失效")
    return user


@router.get("/stream")
async def conversation_stream(
    before_id: Optional[int] = None,
    limit: int = 10,
    authorization: Optional[str] = Header(None),
):
    """统一对话流：按时间倒序返回会话（含 messages），支持 before_id 游标分页拉更早历史。"""
    user = _require_user(authorization)
    convs = user_repository.get_conversation_stream(
        user["id"], before_id=before_id, limit=max(1, min(limit, 30))
    )
    return {"conversations": convs}


@router.get("")
async def list_conversations(
    before_id: Optional[int] = None,
    limit: int = 20,
    authorization: Optional[str] = Header(None),
):
    """登录用户的历史会话列表（标题/时间/消息数），按时间倒序。"""
    user = _require_user(authorization)
    convs = user_repository.list_conversations(
        user["id"], before_id=before_id, limit=max(1, min(limit, 50))
    )
    return {"conversations": convs}


@router.get("/{conv_id}")
async def get_conversation(conv_id: int, authorization: Optional[str] = Header(None)):
    """加载某条历史会话（含 messages 与内嵌行程）"""
    user = _require_user(authorization)
    conv = user_repository.get_conversation(user["id"], conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"conversation": conv}


@router.post("")
async def save_conversation(req: ConversationSave, authorization: Optional[str] = Header(None)):
    """创建或更新会话（upsert）。登录后同步未登录本地会话也走这里。"""
    user = _require_user(authorization)
    conv = user_repository.save_conversation(
        user["id"], req.id, req.title, req.messages or []
    )
    return {"conversation": conv}


@router.delete("/{conv_id}")
async def delete_conversation(conv_id: int, authorization: Optional[str] = Header(None)):
    user = _require_user(authorization)
    ok = user_repository.delete_conversation(user["id"], conv_id)
    return {"ok": ok}
