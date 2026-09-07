"""
Redis 客户端模块。

提供 Redis 连接池和常用操作，支持分布式缓存。
当 Redis 不可用时，自动回退到内存缓存（由 cache.py 处理）。

功能特性：
- 连接池管理（懒加载单例）
- 可用性探测（带缓存，避免频繁探测）
- 常用操作：get、set、delete、exists
- 命名空间管理：flush_namespace、count_namespace
- 全局统计：total_count
- 自动故障恢复（reset_availability）

使用方式：
    from app.infrastructure import redis_client

    # 检查可用性
    if redis_client.is_available():
        # 设置缓存
        redis_client.set("geo", "北京", '{"lng": 116.4}', 3600)
        # 获取缓存
        value = redis_client.get("geo", "北京")
        # 删除缓存
        redis_client.delete("geo", "北京")
"""
from typing import Any, Optional

from app.config import settings

from . import logger as log_mod

# Redis 日志记录器
_redis_logger = log_mod.get_logger("redis")

# Redis 连接池（懒加载）
_pool: Optional[Any] = None
_client: Optional[Any] = None
_available: Optional[bool] = None  # None=未探测, True/False=探测结果


def get_redis_pool() -> Optional[Any]:
    """
    获取 Redis 连接池（单例）。

    懒加载：首次调用时创建连接池，后续调用复用。
    如果 Redis 未启用或初始化失败，返回 None。

    Returns:
        Optional[Any]: Redis 连接池对象，不可用时返回 None
    """
    global _pool
    if _pool is None and settings.redis_enabled:
        try:
            import redis

            _pool = redis.ConnectionPool(
                host=settings.redis_host,
                port=settings.redis_port,
                password=settings.redis_password or None,
                db=settings.redis_db,
                max_connections=settings.redis_max_connections,
                socket_timeout=settings.redis_socket_timeout,
                socket_connect_timeout=settings.redis_socket_connect_timeout,
                decode_responses=True,
            )
        except Exception as e:
            _redis_logger.warning(
                "redis_pool_init_failed", extra={"fields": {"error": str(e)}}
            )
            _pool = None
    return _pool


def get_redis_client() -> Optional[Any]:
    """
    获取 Redis 客户端（单例）。

    懒加载：首次调用时创建客户端，后续调用复用。
    如果连接池不可用或初始化失败，返回 None。

    Returns:
        Optional[Any]: Redis 客户端对象，不可用时返回 None
    """
    global _client
    if _client is None:
        pool = get_redis_pool()
        if pool:
            try:
                import redis

                _client = redis.Redis(connection_pool=pool)
            except Exception as e:
                _redis_logger.warning(
                    "redis_client_init_failed", extra={"fields": {"error": str(e)}}
                )
                _client = None
    return _client


def is_available() -> bool:
    """
    检测 Redis 是否可用（带缓存，避免频繁探测）。

    探测逻辑：
    1. 如果已有探测结果，直接返回
    2. 如果 Redis 未启用，返回 False
    3. 获取客户端，如果客户端不可用，返回 False
    4. 执行 ping 命令，如果成功返回 True，否则返回 False

    Returns:
        bool: Redis 是否可用
    """
    global _available
    if _available is not None:
        return _available
    if not settings.redis_enabled:
        _available = False
        return False
    client = get_redis_client()
    if client is None:
        _available = False
        return False
    try:
        client.ping()
        _available = True
        return True
    except Exception as e:
        _redis_logger.warning(
            "redis_ping_failed", extra={"fields": {"error": str(e)}}
        )
        _available = False
        return False


def reset_availability() -> None:
    """
    重置可用性缓存（用于 Redis 恢复后重新探测）。

    当 Redis 操作失败时，调用此方法重置缓存，
    下次调用 is_available() 时会重新探测 Redis 可用性。
    """
    global _available, _client, _pool
    _available = None
    _client = None
    _pool = None


def _prefixed_key(namespace: str, key: str) -> str:
    """
    添加 Redis key 前缀。

    格式：{redis_key_prefix}{namespace}:{key}

    Args:
        namespace: 命名空间名称
        key: 缓存键

    Returns:
        str: 带前缀的完整 Redis key
    """
    return f"{settings.redis_key_prefix}{namespace}:{key}"


def get(namespace: str, key: str) -> Optional[str]:
    """
    获取缓存值。

    Args:
        namespace: 命名空间名称
        key: 缓存键

    Returns:
        Optional[str]: 缓存值（字符串），不存在或失败时返回 None
    """
    if not is_available():
        return None
    client = get_redis_client()
    if client is None:
        return None
    try:
        return client.get(_prefixed_key(namespace, key))
    except Exception as e:
        _redis_logger.warning(
            "redis_get_failed", extra={"fields": {"error": str(e), "key": key}}
        )
        reset_availability()
        return None


def set(namespace: str, key: str, value: str, ttl_seconds: int = 0) -> bool:
    """
    设置缓存值，ttl_seconds=0 表示永不过期。

    Args:
        namespace: 命名空间名称
        key: 缓存键
        value: 缓存值（字符串）
        ttl_seconds: 过期时间（秒），0 表示永不过期

    Returns:
        bool: 是否设置成功
    """
    if not is_available():
        return False
    client = get_redis_client()
    if client is None:
        return False
    try:
        full_key = _prefixed_key(namespace, key)
        if ttl_seconds > 0:
            client.setex(full_key, ttl_seconds, value)
        else:
            client.set(full_key, value)
        return True
    except Exception as e:
        _redis_logger.warning(
            "redis_set_failed", extra={"fields": {"error": str(e), "key": key}}
        )
        reset_availability()
        return False


def delete(namespace: str, key: str) -> bool:
    """
    删除缓存值。

    Args:
        namespace: 命名空间名称
        key: 缓存键

    Returns:
        bool: 是否删除成功
    """
    if not is_available():
        return False
    client = get_redis_client()
    if client is None:
        return False
    try:
        client.delete(_prefixed_key(namespace, key))
        return True
    except Exception as e:
        _redis_logger.warning(
            "redis_delete_failed", extra={"fields": {"error": str(e), "key": key}}
        )
        reset_availability()
        return False


def exists(namespace: str, key: str) -> bool:
    """
    检查缓存值是否存在。

    Args:
        namespace: 命名空间名称
        key: 缓存键

    Returns:
        bool: 缓存值是否存在
    """
    if not is_available():
        return False
    client = get_redis_client()
    if client is None:
        return False
    try:
        return bool(client.exists(_prefixed_key(namespace, key)))
    except Exception as e:
        _redis_logger.warning(
            "redis_exists_failed", extra={"fields": {"error": str(e), "key": key}}
        )
        reset_availability()
        return False


def flush_namespace(namespace: str) -> int:
    """
    清空指定命名空间的所有缓存，返回删除数量。

    Args:
        namespace: 命名空间名称

    Returns:
        int: 删除的缓存数量
    """
    if not is_available():
        return 0
    client = get_redis_client()
    if client is None:
        return 0
    try:
        pattern = _prefixed_key(namespace, "*")
        keys = list(client.scan_iter(match=pattern))
        if keys:
            return client.delete(*keys)
        return 0
    except Exception as e:
        _redis_logger.warning(
            "redis_flush_failed",
            extra={"fields": {"error": str(e), "namespace": namespace}},
        )
        reset_availability()
        return 0


def count_namespace(namespace: str) -> int:
    """
    统计指定命名空间的缓存数量。

    Args:
        namespace: 命名空间名称

    Returns:
        int: 缓存数量
    """
    if not is_available():
        return 0
    client = get_redis_client()
    if client is None:
        return 0
    try:
        pattern = _prefixed_key(namespace, "*")
        return sum(1 for _ in client.scan_iter(match=pattern))
    except Exception as e:
        _redis_logger.warning(
            "redis_count_failed",
            extra={"fields": {"error": str(e), "namespace": namespace}},
        )
        reset_availability()
        return 0


def total_count() -> int:
    """
    统计所有缓存数量。

    Returns:
        int: 所有缓存数量
    """
    if not is_available():
        return 0
    client = get_redis_client()
    if client is None:
        return 0
    try:
        pattern = f"{settings.redis_key_prefix}*"
        return sum(1 for _ in client.scan_iter(match=pattern))
    except Exception as e:
        _redis_logger.warning(
            "redis_total_count_failed", extra={"fields": {"error": str(e)}}
        )
        reset_availability()
        return 0
