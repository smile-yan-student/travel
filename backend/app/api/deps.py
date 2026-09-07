"""
路由共享依赖模块。

包含请求模型、常量和鉴权函数。
鉴权逻辑已拆分到 app/security/auth.py，本模块只保留请求模型和常量。

功能特性：
- AuthRequest：认证请求模型（用户名、密码）
- TripReport：行程报告模型（目的地、天数、风格）
- ConversationSave：会话保存模型（ID、标题、消息列表）
- HOME_CENTER：参考出发地（当前用户所在地）用于估算探索里程
- 鉴权函数从 security/auth.py 导入，保持向后兼容（bearer_user、require_user、optional_user）

使用方式：
    from app.api.deps import AuthRequest, require_user

    # 在路由中使用请求模型
    @router.post("/login")
    async def login(request: AuthRequest):
        ...

    # 在路由中使用鉴权依赖
    @router.get("/profile")
    async def profile(user: dict = Depends(require_user)):
        ...
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

# 鉴权函数从 security/auth.py 导入，保持向后兼容
from ..security.auth import bearer_user, optional_user, require_user


# 参考出发地（当前用户所在地）用于估算探索里程
HOME_CENTER = {"lng": 117.12, "lat": 36.651}  # 济南


# ---------------- 请求模型 ----------------

class AuthRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    code: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class TripReport(BaseModel):
    destination: str
    days: int = 1
    style: str = ""
    conversation_id: Optional[int] = None  # 关联的会话ID


class ConversationSave(BaseModel):
    id: Optional[int] = None  # 传入则更新，否则创建
    title: str = ""
    messages: list = []
