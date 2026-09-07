"""
请求日志中间件模块。

提供 HTTP 请求日志记录功能，包括：
- trace_id 贯穿整个请求生命周期
- 方法、路径、状态码、耗时
- 客户端 IP
- 异常自动记录

使用方式：
    from fastapi import FastAPI
    from app.infrastructure.request_logger import request_logging_middleware

    app = FastAPI()
    app.middleware("http")(request_logging_middleware)
"""
import time
from typing import Awaitable, Callable

from fastapi import Request, Response

from .logger import get_logger, new_trace_id

# 请求日志记录器
_req_logger = get_logger("request")


async def request_logging_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """
    请求日志中间件：trace_id 贯穿 + 方法/路径/状态码/耗时，异常自动记录。

    功能特性：
    1. 从请求头获取或生成 trace_id，贯穿整个请求生命周期
    2. 记录请求方法、路径、客户端 IP
    3. 记录响应状态码和处理耗时（毫秒）
    4. 根据状态码自动选择日志级别（<400 INFO, <500 WARNING, >=500 ERROR）
    5. 异常自动记录错误日志和堆栈信息
    6. 将 trace_id 添加到响应头，便于客户端追踪

    Args:
        request: FastAPI 请求对象
        call_next: 下一个中间件或路由处理函数

    Returns:
        Response: 响应对象（包含 X-Trace-Id 响应头）

    Raises:
        Exception: 处理过程中的异常（会被记录后重新抛出）

    Example:
        >>> from fastapi import FastAPI
        >>> app = FastAPI()
        >>> app.middleware("http")(request_logging_middleware)
    """
    start = time.time()
    trace_id = request.headers.get("X-Trace-Id") or new_trace_id()
    client_ip = request.client.host if request.client else ""
    method, path = request.method, request.url.path

    try:
        response = await call_next(request)
        duration_ms = round((time.time() - start) * 1000, 2)
        response.headers["X-Trace-Id"] = trace_id

        # 根据状态码选择日志级别
        # <400: INFO, <500: WARNING, >=500: ERROR
        level = 20 if response.status_code < 400 else (30 if response.status_code < 500 else 40)

        _req_logger.log(
            level,
            "http_request",
            extra={
                "fields": {
                    "trace_id": trace_id,
                    "method": method,
                    "path": path,
                    "status": response.status_code,
                    "duration_ms": duration_ms,
                    "client_ip": client_ip,
                }
            },
        )
        return response
    except Exception as e:
        duration_ms = round((time.time() - start) * 1000, 2)
        _req_logger.error(
            "http_request_error",
            extra={
                "fields": {
                    "trace_id": trace_id,
                    "method": method,
                    "path": path,
                    "duration_ms": duration_ms,
                    "client_ip": client_ip,
                    "error": str(e),
                }
            },
            exc_info=True,
        )
        raise
