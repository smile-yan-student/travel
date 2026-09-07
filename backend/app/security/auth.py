"""
安全认证模块。

包含用户鉴权相关的函数和依赖，从 routers/deps.py 拆分出来。
集中管理鉴权逻辑，便于维护和复用。

功能特性：
- Bearer Token 解析
- 用户登录验证（require_user）
- 可选用户登录（optional_user）
- 无效 Token 自动返回 None

使用方式：
    from fastapi import Depends
    from app.security.auth import require_user, optional_user

    # 要求登录
    @router.post("/plan")
    async def plan(req: PlanRequest, user: dict = Depends(require_user)):
        ...

    # 可选登录
    @router.get("/explore")
    async def explore(user: Optional[dict] = Depends(optional_user)):
        ...
"""
from typing import Any, Dict, Optional

from fastapi import Header, HTTPException

from ..data.repositories.user_repository import user_by_token

# 用户信息类型
UserInfo = Dict[str, Any]


def bearer_user(authorization: Optional[str]) -> Optional[UserInfo]:
    """
    从 Authorization: Bearer <token> 解析当前用户；无效返回 None。

    Args:
        authorization: Authorization 请求头，格式为 "Bearer <token>"

    Returns:
        Optional[UserInfo]: 用户信息字典，或 None（未登录/无效 token）
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return user_by_token(authorization[7:].strip())


def require_user(authorization: Optional[str] = Header(None)) -> UserInfo:
    """
    FastAPI 依赖：要求用户登录，未登录返回 401。

    用法：
        @router.post("/plan")
        async def plan(req: PlanRequest, user: dict = Depends(require_user)):
            ...

    Args:
        authorization: Authorization 请求头（自动注入）

    Returns:
        UserInfo: 用户信息字典

    Raises:
        HTTPException: 401 未登录或登录已失效
    """
    user = bearer_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="未登录或登录已失效")
    return user


def optional_user(authorization: Optional[str] = Header(None)) -> Optional[UserInfo]:
    """
    FastAPI 依赖：可选用户登录，已登录返回用户信息，未登录返回 None。

    用法：
        @router.get("/explore")
        async def explore(user: Optional[dict] = Depends(optional_user)):
            ...

    Args:
        authorization: Authorization 请求头（自动注入）

    Returns:
        Optional[UserInfo]: 用户信息字典，或 None
    """
    return bearer_user(authorization)
