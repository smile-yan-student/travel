"""
全局限流中间件模块。

支持 IP 级和用户级限流，防止恶意请求打爆服务。
使用滑动窗口算法，内存实现（Redis 可用时可扩展）。

限流维度：
- IP 级：每个 IP 每分钟最多 N 次请求（默认 120 次/分钟）
- 用户级：每个登录用户每分钟最多 N 次请求（默认 60 次/分钟）
- 接口级：可对特定接口设置更严格的限流

使用方式：
    from app.security.rate_limiter import RateLimiterMiddleware
    app.add_middleware(RateLimiterMiddleware)

响应头：
- X-RateLimit-Limit: 限流上限
- X-RateLimit-Remaining: 剩余请求数
- X-RateLimit-Reset: 限流重置时间戳
- Retry-After: 重试等待时间（秒）
"""
import time
from collections import defaultdict, deque
from typing import Any, Awaitable, Callable, Deque, Dict, Optional, Set, Tuple

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from ..config import settings
from ..infrastructure import logger as log_mod

# 限流日志记录器
_rl_logger = log_mod.get_logger("rate_limiter")

# 不需要限流的路径（健康检查、静态资源等）
_SKIP_PATHS: Set[str] = {
    "/health",
    "/health/detailed",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/favicon.ico",
}

# 限流配置
DEFAULT_IP_RATE: int = 120  # 每 IP 每分钟最大请求数
DEFAULT_USER_RATE: int = 60  # 每用户每分钟最大请求数
WINDOW_SECONDS: int = 60  # 限流窗口（秒）

# 限流命中时的响应内容
RATE_LIMIT_RESPONSE = (
    '{"code":"10005","message":"请求过于频繁，请稍后再试","data":null}'
)


class RateLimiter:
    """
    滑动窗口限流器（内存实现）。

    使用滑动窗口算法统计每个 IP/用户在时间窗口内的请求数。
    时间窗口外的请求记录会被自动清理。

    Example:
        >>> limiter = RateLimiter()
        >>> allowed, remaining = limiter.check_ip("127.0.0.1")
        >>> print(allowed, remaining)
        True 119
    """

    def __init__(self) -> None:
        """初始化限流器。"""
        self._ip_requests: Dict[str, Deque[float]] = defaultdict(deque)
        self._user_requests: Dict[str, Deque[float]] = defaultdict(deque)
        self._ip_limit = DEFAULT_IP_RATE
        self._user_limit = DEFAULT_USER_RATE

    def _clean_old(self, dq: Deque[float], now: float) -> None:
        """
        清理窗口外的旧请求记录。

        Args:
            dq: 请求时间戳队列
            now: 当前时间戳
        """
        cutoff = now - WINDOW_SECONDS
        while dq and dq[0] < cutoff:
            dq.popleft()

    def check_ip(self, ip: str) -> Tuple[bool, int]:
        """
        检查 IP 是否超限，返回 (是否允许, 剩余请求数)。

        Args:
            ip: 客户端 IP 地址

        Returns:
            Tuple[bool, int]: (是否允许, 剩余请求数)
        """
        now = time.time()
        dq = self._ip_requests[ip]
        self._clean_old(dq, now)
        if len(dq) >= self._ip_limit:
            return False, 0
        dq.append(now)
        return True, self._ip_limit - len(dq)

    def check_user(self, user_id: str) -> Tuple[bool, int]:
        """
        检查用户是否超限，返回 (是否允许, 剩余请求数)。

        Args:
            user_id: 用户 ID

        Returns:
            Tuple[bool, int]: (是否允许, 剩余请求数)
        """
        now = time.time()
        dq = self._user_requests[user_id]
        self._clean_old(dq, now)
        if len(dq) >= self._user_limit:
            return False, 0
        dq.append(now)
        return True, self._user_limit - len(dq)

    def get_stats(self) -> Dict[str, int]:
        """
        获取限流统计（当前活跃的 IP 和用户数）。

        Returns:
            Dict[str, int]: 限流统计字典，包含 active_ips 和 active_users
        """
        now = time.time()
        active_ips = sum(
            1
            for dq in self._ip_requests.values()
            if any(t > now - WINDOW_SECONDS for t in dq)
        )
        active_users = sum(
            1
            for dq in self._user_requests.values()
            if any(t > now - WINDOW_SECONDS for t in dq)
        )
        return {"active_ips": active_ips, "active_users": active_users}


# 全局限流器实例
_rate_limiter = RateLimiter()


def get_client_ip(request: Request) -> str:
    """
    获取客户端真实 IP（考虑反向代理）。

    优先级：
    1. X-Forwarded-For 请求头（取第一个 IP）
    2. X-Real-IP 请求头
    3. request.client.host

    Args:
        request: 请求对象

    Returns:
        str: 客户端 IP 地址
    """
    # 优先从 X-Forwarded-For 获取
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    # 其次从 X-Real-IP 获取
    xri = request.headers.get("x-real-ip")
    if xri:
        return xri.strip()
    # 最后从 request.client 获取
    return request.client.host if request.client else "unknown"


def get_user_id(request: Request) -> Optional[str]:
    """
    从请求中获取用户 ID（从 JWT token 解析）。

    Args:
        request: 请求对象

    Returns:
        Optional[str]: 用户 ID，未登录或解析失败返回 None
    """
    auth = request.headers.get("authorization")
    if not auth or not auth.startswith("Bearer "):
        return None
    token = auth[7:]
    try:
        import jwt as pyjwt

        payload = pyjwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        return str(payload.get("sub", ""))
    except Exception:
        return None


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """
    全局限流中间件。

    限流策略：
    - 未登录用户：IP 级限流（默认 120 次/分钟）
    - 已登录用户：用户级限流（默认 60 次/分钟）+ IP 级限流
    - 限流命中时返回 429 Too Many Requests
    - 响应头包含 X-RateLimit-Limit / X-RateLimit-Remaining / X-RateLimit-Reset

    跳过路径：健康检查、API 文档、静态资源等。

    Example:
        >>> from fastapi import FastAPI
        >>> app = FastAPI()
        >>> app.add_middleware(RateLimiterMiddleware)
    """

    async def dispatch(
        self, request: Request, call_next: Callable[..., Awaitable[Any]]
    ) -> Response:
        """
        中间件调度方法：检查限流并处理请求。

        Args:
            request: 请求对象
            call_next: 下一个中间件或路由处理函数

        Returns:
            Response: 响应对象
        """
        path = request.url.path

        # 跳过不需要限流的路径
        if path in _SKIP_PATHS or path.startswith("/static"):
            return await call_next(request)

        client_ip = get_client_ip(request)
        user_id = get_user_id(request)

        # IP 级限流（所有请求都检查）
        allowed_ip, remaining_ip = _rate_limiter.check_ip(client_ip)
        if not allowed_ip:
            _rl_logger.warning(
                "rate_limit_ip_blocked",
                extra={
                    "fields": {
                        "ip": client_ip,
                        "path": path,
                        "method": request.method,
                    }
                },
            )
            return Response(
                status_code=429,
                content=RATE_LIMIT_RESPONSE,
                media_type="application/json",
                headers={
                    "X-RateLimit-Limit": str(DEFAULT_IP_RATE),
                    "X-RateLimit-Remaining": "0",
                    "Retry-After": str(WINDOW_SECONDS),
                },
            )

        # 用户级限流（仅已登录用户）
        if user_id:
            allowed_user, remaining_user = _rate_limiter.check_user(user_id)
            if not allowed_user:
                _rl_logger.warning(
                    "rate_limit_user_blocked",
                    extra={
                        "fields": {
                            "user_id": user_id,
                            "ip": client_ip,
                            "path": path,
                            "method": request.method,
                        }
                    },
                )
                return Response(
                    status_code=429,
                    content=RATE_LIMIT_RESPONSE,
                    media_type="application/json",
                    headers={
                        "X-RateLimit-Limit": str(DEFAULT_USER_RATE),
                        "X-RateLimit-Remaining": "0",
                        "Retry-After": str(WINDOW_SECONDS),
                    },
                )

        # 正常处理请求
        response = await call_next(request)

        # 添加限流响应头
        limit = DEFAULT_USER_RATE if user_id else DEFAULT_IP_RATE
        remaining = remaining_user if user_id else remaining_ip
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(time.time() + WINDOW_SECONDS))

        return response


def get_rate_limiter_stats() -> Dict[str, int]:
    """
    获取限流统计信息（用于监控接口）。

    Returns:
        Dict[str, int]: 限流统计字典，包含 active_ips 和 active_users
    """
    return _rate_limiter.get_stats()
