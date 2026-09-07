"""
认证路由模块。

提供用户认证相关的接口：
- /api/auth/register - 用户注册
- /api/auth/check-username - 检查用户名是否可用
- /api/auth/login - 用户登录
- /api/auth/logout - 用户登出
- /api/auth/me - 获取当前用户信息
- /api/auth/change-password - 修改密码

功能特性：
- 用户注册（用户名长度6~20个字符，密码强度校验）
- 用户名实时检查（不区分大小写，避免重复注册）
- 用户登录（JWT token生成，bcrypt密码校验）
- 用户登出（Token加入黑名单，立即失效）
- 登录安全（失败计数、账户锁定、IP级限流）
- 获取当前用户信息（Bearer token解析）
- 修改密码（旧密码校验，新密码强度校验）

使用方式：
    from app.api.auth import router

    # 在FastAPI应用中注册路由
    app.include_router(router)

    # POST /api/auth/register 注册用户
    # POST /api/auth/login 登录获取token
    # POST /api/auth/logout 登出（Token失效）
    # GET /api/auth/me 获取当前用户信息
    # POST /api/auth/change-password 修改密码
"""
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from ..data.repositories import user_repository
from ..security import login_security
from .deps import AuthRequest, RegisterRequest, LoginRequest, bearer_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


@router.post("/register")
async def register(req: RegisterRequest):
    """用户注册：邮箱验证码 + 密码（自动生成用户名）"""
    from ..services.email import get_email_service
    email_service = get_email_service()

    # 邮箱格式校验
    import re
    email = (req.email or "").strip().lower()
    if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
        return {"ok": False, "message": "邮箱格式不正确"}
    # 验证码格式校验
    if not req.code or len(req.code) != 6 or not req.code.isdigit():
        return {"ok": False, "message": "验证码格式不正确"}
    # 邮箱唯一校验
    if user_repository.email_exists(email):
        return {"ok": False, "message": "该邮箱已被注册，请直接登录"}
    # 验证邮箱验证码
    success, msg = email_service.verify_code(email, req.code)
    if not success:
        return {"ok": False, "message": msg}
    # 自动生成用户名（user_ + 邮箱前缀前6位）
    email_prefix = email.split("@")[0]
    username = f"user_{email_prefix[:6]}"
    # 如果用户名已存在，添加随机后缀
    suffix = 1
    while user_repository.username_exists(username):
        username = f"user_{email_prefix[:6]}_{suffix}"
        suffix += 1
    # 注册
    user, err = user_repository.register_with_email(username, email, req.password)
    if err:
        return {"ok": False, "message": err}
    return {"ok": True, "message": "注册成功，请登录", "user": user}


@router.get("/check-email")
async def check_email(email: str = ""):
    """注册时实时检查邮箱是否可用。"""
    import re
    email = (email or "").strip().lower()
    if not email:
        return {"ok": False, "available": False, "message": "请输入邮箱"}
    if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
        return {"ok": False, "available": False, "message": "邮箱格式不正确"}
    if user_repository.email_exists(email):
        return {"ok": True, "available": False, "message": "该邮箱已被注册，请直接登录"}
    return {"ok": True, "available": True, "message": "邮箱可用"}


@router.get("/check-username")
async def check_username(username: str = ""):
    """注册时实时检查用户名是否可用（不区分大小写）。"""
    username = (username or "").strip()
    if not (6 <= len(username) <= 20):
        return {"ok": False, "available": False, "message": "用户名长度需为 6~20 个字符"}
    if user_repository.username_exists(username):
        return {"ok": True, "available": False, "message": "用户名已被占用，换一个试试吧"}
    return {"ok": True, "available": True, "message": "用户名可用"}


@router.post("/login")
async def login(req: LoginRequest, request: Request):
    """用户登录：邮箱 + 密码"""
    # 获取客户端 IP（用于 IP 级限流）
    client_ip = request.client.host if request.client else ""
    # 检查是否被锁定（使用邮箱作为标识）
    locked, lock_msg = login_security.check_login_locked(req.email, client_ip)
    if locked:
        raise HTTPException(status_code=429, detail=lock_msg)
    # 执行登录（使用邮箱登录）
    result = user_repository.login_by_email_password(req.email, req.password)
    if not result:
        _locked, fail_msg = login_security.record_login_failure(req.email, client_ip)
        status = 429 if _locked else 401
        raise HTTPException(status_code=status, detail=fail_msg)
    token, user = result
    # 登录成功，重置失败计数
    login_security.record_login_success(req.email, client_ip)
    return {"ok": True, "token": token, "user": user}


@router.post("/logout")
async def logout(authorization: Optional[str] = Header(None)):
    """用户登出：将当前Token加入黑名单，立即失效。"""
    user = bearer_user(authorization)
    if not user:
        # 未登录也返回成功，避免泄露用户状态
        return {"ok": True, "message": "已登出"}
    # 提取Token
    token = authorization.replace("Bearer ", "").strip() if authorization else ""
    if token:
        user_repository.blacklist_token(token, user["id"])
    return {"ok": True, "message": "已登出"}


@router.get("/me")
async def me(authorization: str = Header(None)):
    user = bearer_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="未登录或登录已失效")
    return {"user": user}


@router.post("/change-password")
async def change_password(req: ChangePasswordRequest, authorization: Optional[str] = Header(None)):
    """修改用户密码。"""
    user = bearer_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="未登录或登录已失效")

    success, err = user_repository.change_password(user["id"], req.old_password, req.new_password)
    if not success:
        return {"ok": False, "message": err}

    # 密码修改成功后，将当前Token加入黑名单，要求用户重新登录
    token = authorization.replace("Bearer ", "").strip() if authorization else ""
    if token:
        user_repository.blacklist_token(token, user["id"])

    return {"ok": True, "message": "密码修改成功，请重新登录"}


# ---------------- 手机号验证码登录/注册 ----------------


class SendCodeRequest(BaseModel):
    phone: str
    scene: str = "login"  # register/login/reset


class SMSLoginRequest(BaseModel):
    phone: str
    code: str


@router.post("/sms/send-code")
async def send_sms_code(req: SendCodeRequest):
    """发送短信验证码"""
    from ..services.sms import get_sms_service
    sms_service = get_sms_service()

    # 检查短信服务是否启用
    if not sms_service.enabled:
        return {"ok": False, "message": "短信验证码服务未启用"}

    # 检查是否可以发送
    can_send, msg = sms_service.can_send(req.phone)
    if not can_send:
        return {"ok": False, "message": msg}

    # 发送验证码
    success, msg = await sms_service.send_code(req.phone, req.scene)
    if not success:
        return {"ok": False, "message": msg}

    # 获取剩余发送次数
    remaining = sms_service.get_remaining_count(req.phone)

    return {
        "ok": True,
        "message": "验证码发送成功",
        "remaining_count": remaining,
        "expire_seconds": sms_service.code_expire,
    }


@router.post("/sms/login")
async def sms_login(req: SMSLoginRequest, request: Request):
    """手机号验证码登录/注册（未注册自动注册）"""
    from ..services.sms import get_sms_service
    sms_service = get_sms_service()

    # 检查短信服务是否启用
    if not sms_service.enabled:
        return {"ok": False, "message": "短信验证码服务未启用"}

    # 验证验证码
    success, msg = sms_service.verify_code(req.phone, req.code)
    if not success:
        return {"ok": False, "message": msg}

    # 登录/注册
    result = user_repository.login_by_phone(req.phone)
    if not result:
        return {"ok": False, "message": "登录失败，请稍后重试"}

    token, user = result
    return {"ok": True, "token": token, "user": user, "is_new": not user_repository.phone_exists(req.phone)}


# ---------------- 邮箱验证码登录/注册 ----------------


class SendEmailCodeRequest(BaseModel):
    email: str
    scene: str = "login"  # register/login/reset


class EmailLoginRequest(BaseModel):
    email: str
    code: str


@router.post("/email/send-code")
async def send_email_code(req: SendEmailCodeRequest):
    """发送邮箱验证码"""
    from ..services.email import get_email_service
    email_service = get_email_service()

    # 检查邮箱服务是否启用
    if not email_service.enabled:
        return {"ok": False, "message": "邮箱验证码服务未启用"}

    # 检查是否可以发送
    can_send, msg = email_service.can_send(req.email)
    if not can_send:
        return {"ok": False, "message": msg}

    # 发送验证码
    success, msg = await email_service.send_code(req.email, req.scene)
    if not success:
        return {"ok": False, "message": msg}

    # 获取剩余发送次数
    remaining = email_service.get_remaining_count(req.email)

    return {
        "ok": True,
        "message": "验证码发送成功，请注意查收邮件",
        "remaining_count": remaining,
        "expire_seconds": email_service.code_expire,
    }


@router.post("/email/login")
async def email_login(req: EmailLoginRequest, request: Request):
    """邮箱验证码登录/注册（未注册自动注册）"""
    from ..services.email import get_email_service
    email_service = get_email_service()

    # 检查邮箱服务是否启用
    if not email_service.enabled:
        return {"ok": False, "message": "邮箱验证码服务未启用"}

    # 验证验证码
    success, msg = email_service.verify_code(req.email, req.code)
    if not success:
        return {"ok": False, "message": msg}

    # 登录/注册
    result = user_repository.login_by_email(req.email)
    if not result:
        return {"ok": False, "message": "登录失败，请稍后重试"}

    token, user = result
    return {"ok": True, "token": token, "user": user, "is_new": not user_repository.email_exists(req.email)}
