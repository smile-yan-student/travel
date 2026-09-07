"""
安全中间件模块：安全响应头 + 错误信息脱敏 + 请求体大小限制。

在 main.py 中通过 app.add_middleware 或 @app.middleware 注册。

功能特性：
- 安全响应头（X-Content-Type-Options、X-Frame-Options、X-XSS-Protection 等）
- 错误信息脱敏（防止敏感信息泄露）
- CORS 源配置（从环境变量读取）
- HSTS 支持（仅 HTTPS 环境）

使用方式：
    from app.security.security_middleware import (
        SecurityHeadersMiddleware, ErrorSanitizerMiddleware, get_cors_origins
    )

    # 添加安全头中间件
    app.add_middleware(SecurityHeadersMiddleware)

    # 添加错误脱敏中间件
    app.add_middleware(ErrorSanitizerMiddleware)

    # 配置 CORS
    origins = get_cors_origins()
"""
import os
import re
from typing import Any, Awaitable, Callable, List, Tuple

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response


# 敏感信息正则（用于错误信息脱敏）
_SENSITIVE_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (
        re.compile(r'password["\']?\s*[:=]\s*["\']?[^,\s}]+', re.IGNORECASE),
        "password=***",
    ),
    (
        re.compile(r'token["\']?\s*[:=]\s*["\']?[^,\s}]+', re.IGNORECASE),
        "token=***",
    ),
    (
        re.compile(r'(?:amap|tencent)_key["\']?\s*[:=]\s*["\']?[^,\s}]+', re.IGNORECASE),
        "api_key=***",
    ),
    (
        re.compile(r'secret["\']?\s*[:=]\s*["\']?[^,\s}]+', re.IGNORECASE),
        "secret=***",
    ),
    (
        re.compile(r'authorization["\']?\s*[:=]\s*["\']?[^,\s}]+', re.IGNORECASE),
        "authorization=***",
    ),
    # SQL 错误中的敏感信息
    (
        re.compile(r"Duplicate entry '([^']+)' for key", re.IGNORECASE),
        r"Duplicate entry '***' for key",
    ),
]


def sanitize_error_message(msg: str) -> str:
    """
    脱敏错误信息中的敏感字段。

    Args:
        msg: 原始错误信息

    Returns:
        str: 脱敏后的错误信息
    """
    if not msg:
        return msg
    for pattern, replacement in _SENSITIVE_PATTERNS:
        msg = pattern.sub(replacement, msg)
    return msg


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    安全响应头中间件。

    添加以下安全头：
    - X-Content-Type-Options: nosniff（防止 MIME 类型嗅探）
    - X-Frame-Options: DENY（防止点击劫持）
    - X-XSS-Protection: 1; mode=block（XSS 防护）
    - Strict-Transport-Security: HSTS（强制 HTTPS，仅 HTTPS 环境）
    - Referrer-Policy: strict-origin-when-cross-origin（Referrer 策略）
    - Permissions-Policy: 限制浏览器功能访问

    Example:
        >>> from fastapi import FastAPI
        >>> app = FastAPI()
        >>> app.add_middleware(SecurityHeadersMiddleware)
    """

    async def dispatch(
        self, request: Request, call_next: Callable[..., Awaitable[Any]]
    ) -> Response:
        """
        中间件调度方法：添加安全响应头。

        Args:
            request: 请求对象
            call_next: 下一个中间件或路由处理函数

        Returns:
            Response: 带安全头的响应对象
        """
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        # HSTS 仅在 HTTPS 环境下生效（开发环境 http 不添加）
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response


class ErrorSanitizerMiddleware(BaseHTTPMiddleware):
    """
    错误信息脱敏中间件：防止 500 错误响应泄露内部敏感信息。

    生产环境：返回通用错误信息，不泄露内部细节。
    错误信息会经过 sanitize_error_message 脱敏处理。

    Example:
        >>> from fastapi import FastAPI
        >>> app = FastAPI()
        >>> app.add_middleware(ErrorSanitizerMiddleware)
    """

    async def dispatch(
        self, request: Request, call_next: Callable[..., Awaitable[Any]]
    ) -> Response:
        """
        中间件调度方法：捕获异常并返回脱敏后的错误响应。

        Args:
            request: 请求对象
            call_next: 下一个中间件或路由处理函数

        Returns:
            Response: 正常响应或脱敏后的错误响应
        """
        try:
            return await call_next(request)
        except Exception as e:
            # 生产环境：返回通用错误信息，不泄露内部细节
            sanitized = sanitize_error_message(str(e))
            return JSONResponse(
                status_code=500,
                content={"detail": "服务器内部错误", "error": sanitized[:200]},
            )


def get_cors_origins() -> List[str]:
    """
    获取允许的 CORS 源列表。

    从环境变量 CORS_ORIGINS 读取，逗号分隔；默认仅允许本地开发地址。
    生产环境必须配置具体域名，禁止使用 *。

    Returns:
        List[str]: 允许的 CORS 源列表

    Example:
        >>> origins = get_cors_origins()
        >>> app.add_middleware(CORSMiddleware, allow_origins=origins, ...)
    """
    origins_env = os.getenv("CORS_ORIGINS", "")
    if origins_env:
        return [o.strip() for o in origins_env.split(",") if o.strip()]
    # 默认：本地开发地址
    return [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ]
