"""
熔断器模块（轻量级实现，无外部依赖）。

用于保护第三方 API 调用（高德/腾讯/AI），避免故障雪崩。

熔断器状态机：
- CLOSED（关闭）：正常请求，统计失败次数
- OPEN（打开）：拒绝请求，快速失败，等待冷却时间
- HALF_OPEN（半开）：冷却时间后，允许少量探测请求
  - 探测成功 → CLOSED
  - 探测失败 → OPEN（重新计时）

使用方式：
    from app.infrastructure.circuit_breaker import circuit_breaker, CircuitBreaker

    # 方式1：装饰器
    @circuit_breaker(name="amap", failure_threshold=5, recovery_timeout=30)
    async def call_amap_api():
        ...

    # 方式2：手动使用
    cb = CircuitBreaker(name="amap")
    if cb.can_execute():
        try:
            result = await call_api()
            cb.on_success()
        except Exception as e:
            cb.on_failure(e)
            raise
"""
import asyncio
import time
from enum import Enum
from functools import wraps
from typing import Any, Awaitable, Callable, Dict, Optional, Union

from . import logger as log_mod

# 熔断器日志记录器
_cb_logger = log_mod.get_logger("circuit_breaker")


class CircuitState(str, Enum):
    """
    熔断器状态枚举。

    状态说明：
    - CLOSED: 正常请求，统计失败次数
    - OPEN: 拒绝请求，快速失败，等待冷却时间
    - HALF_OPEN: 冷却时间后，允许少量探测请求
    """

    CLOSED = "closed"  # 正常请求
    OPEN = "open"  # 拒绝请求
    HALF_OPEN = "half_open"  # 探测请求


class CircuitBreakerOpenError(Exception):
    """
    熔断器打开时抛出的异常（快速失败）。

    属性：
        name: 熔断器名称
        recovery_remaining: 剩余恢复时间（秒）
    """

    def __init__(self, name: str, recovery_remaining: float) -> None:
        """
        初始化熔断器打开异常。

        Args:
            name: 熔断器名称
            recovery_remaining: 剩余恢复时间（秒）
        """
        self.name = name
        self.recovery_remaining = recovery_remaining
        super().__init__(
            f"Circuit breaker '{name}' is open, retry in {recovery_remaining:.1f}s"
        )


class CircuitBreaker:
    """
    熔断器实例。

    参数：
    - name: 熔断器名称（用于日志和统计）
    - failure_threshold: 连续失败次数阈值（达到后打开熔断器）
    - recovery_timeout: 冷却时间（秒，打开后等待多久进入半开状态）
    - half_open_max_calls: 半开状态允许的最大探测请求数

    状态转换：
    - CLOSED → OPEN: 连续失败次数达到阈值
    - OPEN → HALF_OPEN: 冷却时间结束
    - HALF_OPEN → CLOSED: 探测请求成功
    - HALF_OPEN → OPEN: 探测请求失败

    Example:
        >>> cb = CircuitBreaker(name="amap", failure_threshold=5, recovery_timeout=30)
        >>> if cb.can_execute():
        ...     try:
        ...         result = await call_api()
        ...         cb.on_success()
        ...     except Exception as e:
        ...         cb.on_failure(e)
        ...         raise
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
    ) -> None:
        """
        初始化熔断器。

        Args:
            name: 熔断器名称（用于日志和统计）
            failure_threshold: 连续失败次数阈值，默认 5
            recovery_timeout: 冷却时间（秒），默认 30.0
            half_open_max_calls: 半开状态允许的最大探测请求数，默认 3
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        # 内部状态
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """
        当前状态（自动检查是否需要从 OPEN 转为 HALF_OPEN）。

        Returns:
            CircuitState: 当前熔断器状态
        """
        if self._state == CircuitState.OPEN:
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
                _cb_logger.info(
                    "circuit_breaker_half_open", extra={"fields": {"name": self.name}}
                )
        return self._state

    def can_execute(self) -> bool:
        """
        是否可以执行请求。

        Returns:
            bool: 是否可以执行请求
        """
        s = self.state
        if s == CircuitState.CLOSED:
            return True
        if s == CircuitState.OPEN:
            return False
        if s == CircuitState.HALF_OPEN:
            return self._half_open_calls < self.half_open_max_calls
        return False

    def on_success(self) -> None:
        """
        请求成功回调。

        根据当前状态进行状态转换：
        - HALF_OPEN → CLOSED: 探测成功，恢复正常
        - CLOSED: 重置失败计数
        """
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._half_open_calls = 0
            _cb_logger.info(
                "circuit_breaker_closed", extra={"fields": {"name": self.name}}
            )
        elif self._state == CircuitState.CLOSED:
            self._failure_count = 0

    def on_failure(self, error: Optional[Exception] = None) -> None:
        """
        请求失败回调。

        根据当前状态进行状态转换：
        - HALF_OPEN → OPEN: 探测失败，重新打开熔断器
        - CLOSED: 增加失败计数，达到阈值时打开熔断器

        Args:
            error: 失败的异常对象（可选，用于日志）
        """
        self._last_failure_time = time.time()
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
            self._half_open_calls = 0
            _cb_logger.warning(
                "circuit_breaker_opened",
                extra={
                    "fields": {
                        "name": self.name,
                        "error": str(error) if error else "",
                    }
                },
            )
        elif self._state == CircuitState.CLOSED:
            self._failure_count += 1
            if self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                _cb_logger.warning(
                    "circuit_breaker_opened",
                    extra={
                        "fields": {
                            "name": self.name,
                            "failure_count": self._failure_count,
                            "error": str(error) if error else "",
                        }
                    },
                )

    async def execute(
        self, func: Callable[..., Union[Any, Awaitable[Any]]], *args: Any, **kwargs: Any
    ) -> Any:
        """
        执行受熔断器保护的函数。

        支持同步和异步函数。

        Args:
            func: 要执行的函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            Any: 函数执行结果

        Raises:
            CircuitBreakerOpenError: 熔断器打开时抛出
            Exception: 函数执行失败时抛出
        """
        if not self.can_execute():
            remaining = self.recovery_timeout - (time.time() - self._last_failure_time)
            raise CircuitBreakerOpenError(self.name, max(0, remaining))

        if self._state == CircuitState.HALF_OPEN:
            self._half_open_calls += 1

        try:
            result = (
                await func(*args, **kwargs)
                if asyncio.iscoroutinefunction(func)
                else func(*args, **kwargs)
            )
            self.on_success()
            return result
        except Exception as e:
            self.on_failure(e)
            raise

    def get_stats(self) -> Dict[str, Any]:
        """
        获取熔断器统计信息（用于监控）。

        Returns:
            Dict[str, Any]: 熔断器统计信息
        """
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "last_failure_time": self._last_failure_time,
        }


# 全局熔断器注册表
_breakers: Dict[str, CircuitBreaker] = {}


def get_circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: float = 30.0,
) -> CircuitBreaker:
    """
    获取或创建全局熔断器（单例）。

    Args:
        name: 熔断器名称
        failure_threshold: 连续失败次数阈值，默认 5
        recovery_timeout: 冷却时间（秒），默认 30.0

    Returns:
        CircuitBreaker: 熔断器实例
    """
    if name not in _breakers:
        _breakers[name] = CircuitBreaker(name, failure_threshold, recovery_timeout)
    return _breakers[name]


def circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: float = 30.0,
    fallback: Optional[Callable[..., Any]] = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    熔断器装饰器。

    参数：
    - name: 熔断器名称
    - failure_threshold: 连续失败次数阈值
    - recovery_timeout: 冷却时间（秒）
    - fallback: 熔断时的降级回调（接收相同参数，返回降级结果）

    用法：
        @circuit_breaker(name="amap", failure_threshold=5, recovery_timeout=30)
        async def call_amap():
            ...

        # 带降级
        @circuit_breaker(name="amap", fallback=lambda: mock_data)
        async def call_amap():
            ...

    Args:
        name: 熔断器名称
        failure_threshold: 连续失败次数阈值，默认 5
        recovery_timeout: 冷却时间（秒），默认 30.0
        fallback: 熔断时的降级回调，默认 None

    Returns:
        Callable: 装饰器函数
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        cb = get_circuit_breaker(name, failure_threshold, recovery_timeout)

        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            """异步函数包装器。"""
            if not cb.can_execute():
                if fallback:
                    return fallback(*args, **kwargs)
                remaining = recovery_timeout - (time.time() - cb._last_failure_time)
                raise CircuitBreakerOpenError(name, max(0, remaining))

            if cb.state == CircuitState.HALF_OPEN:
                cb._half_open_calls += 1

            try:
                result = await func(*args, **kwargs)
                cb.on_success()
                return result
            except Exception as e:
                cb.on_failure(e)
                if fallback:
                    return fallback(*args, **kwargs)
                raise

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            """同步函数包装器。"""
            if not cb.can_execute():
                if fallback:
                    return fallback(*args, **kwargs)
                remaining = recovery_timeout - (time.time() - cb._last_failure_time)
                raise CircuitBreakerOpenError(name, max(0, remaining))

            if cb.state == CircuitState.HALF_OPEN:
                cb._half_open_calls += 1

            try:
                result = func(*args, **kwargs)
                cb.on_success()
                return result
            except Exception as e:
                cb.on_failure(e)
                if fallback:
                    return fallback(*args, **kwargs)
                raise

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator


def get_all_stats() -> Dict[str, Dict[str, Any]]:
    """
    获取所有熔断器统计信息（用于监控接口）。

    Returns:
        Dict[str, Dict[str, Any]]: 所有熔断器的统计信息，key 为熔断器名称
    """
    return {name: cb.get_stats() for name, cb in _breakers.items()}
