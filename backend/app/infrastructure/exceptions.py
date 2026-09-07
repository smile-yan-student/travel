"""
统一异常处理模块。

定义业务异常类、错误码常量，以及全局异常处理器。
所有业务异常应继承 AppException，由全局处理器统一转换为标准响应格式。

错误码规则：
- 1xxxx：通用错误
- 2xxxx：认证/授权错误
- 3xxxx：业务逻辑错误（规划/对话等）
- 4xxxx：第三方服务错误（地图/AI等）
- 5xxxx：数据/存储错误

使用方式：
    from app.infrastructure.exceptions import (
        AppException, AuthException, BusinessException,
        ThirdPartyException, DataException, ErrorCode,
        register_exception_handlers
    )

    # 抛出业务异常
    raise BusinessException(code=ErrorCode.DESTINATION_REQUIRED, message="目的地不能为空")

    # 注册全局异常处理器
    register_exception_handlers(app)
"""
from enum import Enum
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ErrorCode(str, Enum):
    """
    统一错误码定义。

    错误码规则：
    - 1xxxx：通用错误
    - 2xxxx：认证/授权错误
    - 3xxxx：业务逻辑错误（规划/对话等）
    - 4xxxx：第三方服务错误（地图/AI等）
    - 5xxxx：数据/存储错误
    """

    # 通用错误 1xxxx
    SUCCESS = "0"
    UNKNOWN_ERROR = "10000"
    BAD_REQUEST = "10001"
    VALIDATION_ERROR = "10002"
    NOT_FOUND = "10003"
    METHOD_NOT_ALLOWED = "10004"
    TOO_MANY_REQUESTS = "10005"
    SERVICE_UNAVAILABLE = "10006"

    # 认证/授权错误 2xxxx
    UNAUTHORIZED = "20001"
    TOKEN_EXPIRED = "20002"
    TOKEN_INVALID = "20003"
    FORBIDDEN = "20004"
    USER_NOT_FOUND = "20005"
    USER_ALREADY_EXISTS = "20006"
    PASSWORD_INCORRECT = "20007"
    PASSWORD_WEAK = "20008"

    # 业务逻辑错误 3xxxx
    PLAN_GENERATION_FAILED = "30001"
    DESTINATION_REQUIRED = "30002"
    INVALID_DESTINATION = "30003"
    CHAT_GENERATION_FAILED = "30004"
    INTENT_PARSE_FAILED = "30005"

    # 第三方服务错误 4xxxx
    MAP_SERVICE_ERROR = "40001"
    MAP_SERVICE_UNAVAILABLE = "40002"
    AI_SERVICE_ERROR = "40003"
    AI_SERVICE_UNAVAILABLE = "40004"
    THIRD_PARTY_TIMEOUT = "40005"

    # 数据/存储错误 5xxxx
    DATABASE_ERROR = "50001"
    DATA_NOT_FOUND = "50002"
    CACHE_ERROR = "50003"


# 错误码 → HTTP 状态码 映射
ERROR_HTTP_STATUS: Dict[ErrorCode, int] = {
    ErrorCode.SUCCESS: 200,
    ErrorCode.UNKNOWN_ERROR: 500,
    ErrorCode.BAD_REQUEST: 400,
    ErrorCode.VALIDATION_ERROR: 422,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.METHOD_NOT_ALLOWED: 405,
    ErrorCode.TOO_MANY_REQUESTS: 429,
    ErrorCode.SERVICE_UNAVAILABLE: 503,
    ErrorCode.UNAUTHORIZED: 401,
    ErrorCode.TOKEN_EXPIRED: 401,
    ErrorCode.TOKEN_INVALID: 401,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.USER_NOT_FOUND: 404,
    ErrorCode.USER_ALREADY_EXISTS: 409,
    ErrorCode.PASSWORD_INCORRECT: 401,
    ErrorCode.PASSWORD_WEAK: 400,
    ErrorCode.PLAN_GENERATION_FAILED: 500,
    ErrorCode.DESTINATION_REQUIRED: 400,
    ErrorCode.INVALID_DESTINATION: 400,
    ErrorCode.CHAT_GENERATION_FAILED: 500,
    ErrorCode.INTENT_PARSE_FAILED: 400,
    ErrorCode.MAP_SERVICE_ERROR: 502,
    ErrorCode.MAP_SERVICE_UNAVAILABLE: 503,
    ErrorCode.AI_SERVICE_ERROR: 502,
    ErrorCode.AI_SERVICE_UNAVAILABLE: 503,
    ErrorCode.THIRD_PARTY_TIMEOUT: 504,
    ErrorCode.DATABASE_ERROR: 500,
    ErrorCode.DATA_NOT_FOUND: 404,
    ErrorCode.CACHE_ERROR: 500,
}


class AppException(Exception):
    """
    业务异常基类。

    所有业务异常应继承此类，由全局异常处理器统一处理。

    属性：
        code: 错误码（ErrorCode 枚举）
        message: 错误消息
        data: 附加数据
        http_status: HTTP 状态码

    Example:
        >>> raise AppException(code=ErrorCode.BAD_REQUEST, message="参数错误")
    """

    def __init__(
        self,
        code: ErrorCode = ErrorCode.UNKNOWN_ERROR,
        message: str = "",
        data: Any = None,
        http_status: Optional[int] = None,
    ) -> None:
        """
        初始化业务异常。

        Args:
            code: 错误码，默认 UNKNOWN_ERROR
            message: 错误消息，为空时自动从错误码名称生成
            data: 附加数据，默认 None
            http_status: HTTP 状态码，为空时从 ERROR_HTTP_STATUS 映射获取
        """
        self.code = code
        self.message = message or code.name.replace("_", " ").title()
        self.data = data
        self.http_status = http_status or ERROR_HTTP_STATUS.get(code, 500)
        super().__init__(self.message)


class AuthException(AppException):
    """
    认证异常。

    用于认证/授权相关的错误，如未登录、token 过期、权限不足等。

    Example:
        >>> raise AuthException(code=ErrorCode.UNAUTHORIZED, message="请先登录")
    """

    def __init__(
        self, code: ErrorCode = ErrorCode.UNAUTHORIZED, message: str = ""
    ) -> None:
        """
        初始化认证异常。

        Args:
            code: 错误码，默认 UNAUTHORIZED
            message: 错误消息
        """
        super().__init__(code=code, message=message)


class BusinessException(AppException):
    """
    业务逻辑异常。

    用于业务逻辑相关的错误，如参数校验失败、目的地不能为空等。

    Example:
        >>> raise BusinessException(code=ErrorCode.DESTINATION_REQUIRED, message="目的地不能为空")
    """

    def __init__(
        self, code: ErrorCode = ErrorCode.BAD_REQUEST, message: str = ""
    ) -> None:
        """
        初始化业务逻辑异常。

        Args:
            code: 错误码，默认 BAD_REQUEST
            message: 错误消息
        """
        super().__init__(code=code, message=message)


class ThirdPartyException(AppException):
    """
    第三方服务异常。

    用于第三方服务相关的错误，如地图服务不可用、AI 服务超时等。

    Example:
        >>> raise ThirdPartyException(code=ErrorCode.MAP_SERVICE_ERROR, message="地图服务调用失败")
    """

    def __init__(
        self, code: ErrorCode = ErrorCode.MAP_SERVICE_ERROR, message: str = ""
    ) -> None:
        """
        初始化第三方服务异常。

        Args:
            code: 错误码，默认 MAP_SERVICE_ERROR
            message: 错误消息
        """
        super().__init__(code=code, message=message)


class DataException(AppException):
    """
    数据/存储异常。

    用于数据/存储相关的错误，如数据库连接失败、数据不存在等。

    Example:
        >>> raise DataException(code=ErrorCode.DATABASE_ERROR, message="数据库连接失败")
    """

    def __init__(
        self, code: ErrorCode = ErrorCode.DATABASE_ERROR, message: str = ""
    ) -> None:
        """
        初始化数据/存储异常。

        Args:
            code: 错误码，默认 DATABASE_ERROR
            message: 错误消息
        """
        super().__init__(code=code, message=message)


def register_exception_handlers(app: FastAPI) -> None:
    """
    注册全局异常处理器到 FastAPI 应用。

    处理顺序：
    1. AppException（业务异常）→ 统一格式响应
    2. RequestValidationError（请求参数校验失败）→ 422 统一格式
    3. HTTPException（FastAPI 内置 HTTP 异常）→ 统一格式
    4. Exception（未捕获异常）→ 500 统一格式，不泄露堆栈

    Args:
        app: FastAPI 应用实例

    Example:
        >>> from fastapi import FastAPI
        >>> app = FastAPI()
        >>> register_exception_handlers(app)
    """
    from . import logger as log_mod

    _err_logger = log_mod.get_logger("exception")

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        """
        业务异常处理器：返回统一格式，记录 warn 日志。

        Args:
            request: 请求对象
            exc: 业务异常对象

        Returns:
            JSONResponse: 统一格式的 JSON 响应
        """
        trace_id = request.headers.get("X-Trace-Id", "")
        _err_logger.warning(
            "business_exception",
            extra={
                "fields": {
                    "trace_id": trace_id,
                    "code": exc.code.value,
                    "message": exc.message,
                    "path": request.url.path,
                    "method": request.method,
                }
            },
        )
        return JSONResponse(
            status_code=exc.http_status,
            content={
                "code": exc.code.value,
                "message": exc.message,
                "data": exc.data,
                "trace_id": trace_id,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """
        请求参数校验失败处理器：返回 422 统一格式，包含字段级错误详情。

        Args:
            request: 请求对象
            exc: 请求参数校验异常对象

        Returns:
            JSONResponse: 统一格式的 JSON 响应（422 状态码）
        """
        trace_id = request.headers.get("X-Trace-Id", "")
        errors: List[Dict[str, str]] = []
        for err in exc.errors():
            errors.append(
                {
                    "field": ".".join(str(loc) for loc in err.get("loc", [])),
                    "message": err.get("msg", ""),
                    "type": err.get("type", ""),
                }
            )
        _err_logger.warning(
            "validation_error",
            extra={
                "fields": {
                    "trace_id": trace_id,
                    "path": request.url.path,
                    "errors": errors,
                }
            },
        )
        return JSONResponse(
            status_code=422,
            content={
                "code": ErrorCode.VALIDATION_ERROR.value,
                "message": "请求参数校验失败",
                "data": {"errors": errors},
                "trace_id": trace_id,
            },
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request, exc: HTTPException
    ) -> JSONResponse:
        """
        FastAPI HTTPException 处理器：统一格式。

        Args:
            request: 请求对象
            exc: HTTP 异常对象

        Returns:
            JSONResponse: 统一格式的 JSON 响应
        """
        trace_id = request.headers.get("X-Trace-Id", "")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": str(exc.status_code),
                "message": exc.detail if isinstance(exc.detail, str) else "请求失败",
                "data": None,
                "trace_id": trace_id,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """
        未捕获异常处理器：返回 500 统一格式，记录 error 日志，不泄露堆栈信息。

        Args:
            request: 请求对象
            exc: 未捕获的异常对象

        Returns:
            JSONResponse: 统一格式的 JSON 响应（500 状态码）
        """
        trace_id = request.headers.get("X-Trace-Id", "")
        _err_logger.error(
            "unhandled_exception",
            extra={
                "fields": {
                    "trace_id": trace_id,
                    "path": request.url.path,
                    "method": request.method,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                }
            },
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={
                "code": ErrorCode.UNKNOWN_ERROR.value,
                "message": "服务器内部错误，请稍后重试",
                "data": None,
                "trace_id": trace_id,
            },
        )
