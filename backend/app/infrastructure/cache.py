"""
轻量 TTL 缓存模块（支持双后端：内存 + Redis）。

用于高德 Web 服务调用结果的缓存，按「数据类型」配置不同 TTL，兼顾降量与时效：
- 地理编码 / 城市坐标：7 天（几乎不变）
- POI 检索 / 行政枚举 / 地标解析 / 周边搜索：1 天（慢变量，规划参考足够）
- 路径规划：30 分钟（路况会波动，短 TTL）
- 天气：2 小时（快变量，单独短 TTL）

双后端设计：
- Redis 优先（分布式缓存，支持多实例共享）
- 内存缓存兜底（Redis 不可用时自动回退）
- 读写同时写入双后端，读取优先 Redis，未命中再读内存

设计约束：
- 失败结果不写入缓存（避免把错误结果固化）
- 读取返回深拷贝，调用方修改结果不会污染缓存
- 进程内存实现，服务重启即清空，天然不会"永久过期"

使用方式：
    from app.infrastructure.cache import cache, TTL_GEO, TTL_POI

    # 写入缓存
    cache.set("geo", "北京", {"lng": 116.4, "lat": 39.9}, TTL_GEO)

    # 读取缓存
    value = cache.get("geo", "北京", TTL_GEO)

    # 清空缓存
    cache.clear("geo")  # 清空指定命名空间
    cache.clear()       # 清空全部
"""
import copy
import json
import threading
import time
from typing import Any, Dict, Optional, Tuple

# 各数据类型 TTL（秒）
TTL_GEO: int = 7 * 24 * 3600  # 地理编码 / 城市坐标
TTL_POI: int = 24 * 3600  # POI 检索 / 行政枚举 / 地标解析 / 周边搜索
TTL_ROUTE: int = 30 * 60  # 路径规划
TTL_WEATHER: int = 2 * 3600  # 天气

# 缓存命名空间常量
NAMESPACE_GEO: str = "geo"
NAMESPACE_POI: str = "poi"
NAMESPACE_ROUTE: str = "route"
NAMESPACE_WEATHER: str = "weather"

# 所有命名空间列表（用于批量清理和统计）
ALL_NAMESPACES: Tuple[str, ...] = (
    NAMESPACE_GEO,
    NAMESPACE_POI,
    NAMESPACE_ROUTE,
    NAMESPACE_WEATHER,
)

# 后台可动态覆盖的 TTL（key 为 namespace；未覆盖时回落默认常量）
_ttl_overrides: Dict[str, float] = {}


def set_ttl(namespace: str, seconds: float) -> None:
    """
    后台配置覆盖某命名空间 TTL（保存后对新缓存立即生效）。

    Args:
        namespace: 命名空间名称（如 "geo", "poi", "route", "weather"）
        seconds: TTL 秒数
    """
    _ttl_overrides[namespace] = seconds


def get_ttl(namespace: str, default: float) -> float:
    """
    读取某命名空间当前生效 TTL（覆盖值优先）。

    Args:
        namespace: 命名空间名称
        default: 默认 TTL 秒数（当没有覆盖值时返回）

    Returns:
        float: 当前生效的 TTL 秒数
    """
    return _ttl_overrides.get(namespace, default)


class TtlCache:
    """
    线程安全的 TTL 缓存（支持双后端：内存 + Redis）。

    namespace 用于分层/批量清理，支持以下命名空间：
    - geo: 地理编码 / 城市坐标（TTL 7 天）
    - poi: POI 检索 / 行政枚举 / 地标解析 / 周边搜索（TTL 1 天）
    - route: 路径规划（TTL 30 分钟）
    - weather: 天气（TTL 2 小时）

    特性：
    - 线程安全（使用 threading.Lock）
    - 双后端支持（Redis 优先，内存兜底）
    - TTL 过期自动清理
    - 深拷贝隔离（读取和写入都使用深拷贝）
    - 支持按命名空间批量清理
    - 支持缓存占用统计

    使用方式：
        cache = TtlCache()
        cache.set("geo", "北京", {"lng": 116.4}, TTL_GEO)
        value = cache.get("geo", "北京", TTL_GEO)
    """

    def __init__(self) -> None:
        """初始化 TTL 缓存。"""
        # 内存缓存数据结构：{(namespace, key): (value, timestamp)}
        self._data: Dict[Tuple[str, str], Tuple[Any, float]] = {}
        # 线程锁
        self._lock = threading.Lock()
        # Redis 可用性检查缓存（避免频繁探测）
        self._redis_checked: bool = False
        self._redis_available: bool = False

    def _check_redis(self) -> bool:
        """
        检查 Redis 是否可用（带缓存，避免频繁探测）。

        Returns:
            bool: Redis 是否可用
        """
        if self._redis_checked:
            return self._redis_available
        self._redis_checked = True
        try:
            from . import redis_client

            self._redis_available = redis_client.is_available()
        except Exception:
            self._redis_available = False
        return self._redis_available

    def _serialize(self, value: Any) -> str:
        """
        序列化值为 JSON 字符串（用于 Redis）。

        Args:
            value: 要序列化的值

        Returns:
            str: JSON 字符串
        """
        return json.dumps(value, ensure_ascii=False, default=str)

    def _deserialize(self, value: str) -> Any:
        """
        反序列化 JSON 字符串为值（用于 Redis）。

        Args:
            value: JSON 字符串

        Returns:
            Any: 反序列化后的值
        """
        return json.loads(value)

    def get(self, namespace: str, key: str, ttl: float) -> Optional[Any]:
        """
        命中且未过期返回深拷贝；未命中/过期返回 None（并清除过期项）。

        读取优先级：Redis → 内存。
        Redis 命中时，同步写入内存缓存（提升后续读取性能）。

        Args:
            namespace: 命名空间名称
            key: 缓存键
            ttl: TTL 秒数（用于判断是否过期）

        Returns:
            Optional[Any]: 缓存值（深拷贝），未命中或过期返回 None
        """
        # 1. 优先读 Redis
        if self._check_redis():
            try:
                from . import redis_client

                raw = redis_client.get(namespace, key)
                if raw is not None:
                    value = self._deserialize(raw)
                    # 同步写入内存缓存
                    with self._lock:
                        self._data[(namespace, key)] = (
                            copy.deepcopy(value),
                            time.time(),
                        )
                    return copy.deepcopy(value)
            except Exception:
                pass  # Redis 读取失败，回退到内存

        # 2. 回退到内存缓存
        with self._lock:
            item = self._data.get((namespace, key))
            if not item:
                return None
            value, ts = item
            if time.time() - ts > ttl:
                self._data.pop((namespace, key), None)
                return None
        return copy.deepcopy(value)

    def set(self, namespace: str, key: str, value: Any, ttl: float = 0) -> None:
        """
        写入缓存（内部深拷贝，隔离调用方引用）。

        双写：同时写入 Redis 和内存缓存。
        ttl > 0 时设置过期时间；ttl = 0 表示永不过期（仅内存）。

        Args:
            namespace: 命名空间名称
            key: 缓存键
            value: 缓存值
            ttl: TTL 秒数，默认 0（永不过期，仅内存）
        """
        # 1. 写入 Redis（如果可用）
        if self._check_redis() and ttl > 0:
            try:
                from . import redis_client

                redis_client.set(namespace, key, self._serialize(value), int(ttl))
            except Exception:
                pass  # Redis 写入失败，不影响内存缓存

        # 2. 写入内存缓存
        with self._lock:
            self._data[(namespace, key)] = (copy.deepcopy(value), time.time())

    def clear(self, namespace: Optional[str] = None) -> None:
        """
        清空全部或指定命名空间。

        Args:
            namespace: 命名空间名称，None 表示清空全部
        """
        # 1. 清空 Redis
        if self._check_redis():
            try:
                from . import redis_client

                if namespace:
                    redis_client.flush_namespace(namespace)
                else:
                    for ns in ALL_NAMESPACES:
                        redis_client.flush_namespace(ns)
            except Exception:
                pass

        # 2. 清空内存
        with self._lock:
            if namespace is None:
                self._data.clear()
            else:
                for k in list(self._data):
                    if k[0] == namespace:
                        self._data.pop(k, None)

    def size(self) -> int:
        """
        返回内存缓存条目数（Redis 数量通过 counts() 单独统计）。

        Returns:
            int: 内存缓存条目数
        """
        with self._lock:
            return len(self._data)

    def counts(self) -> Dict[str, int]:
        """
        各命名空间条目数统计（内存 + Redis 合并，用于监控缓存占用）。

        Returns:
            Dict[str, int]: 各命名空间的条目数，key 为命名空间，value 为条目数
        """
        with self._lock:
            out: Dict[str, int] = {}
            for (ns, _) in self._data:
                out[ns] = out.get(ns, 0) + 1

        # 合并 Redis 统计
        if self._check_redis():
            try:
                from . import redis_client

                for ns in ALL_NAMESPACES:
                    redis_count = redis_client.count_namespace(ns)
                    out[ns] = max(out.get(ns, 0), redis_count)
            except Exception:
                pass

        return out


# 全局单例
cache = TtlCache()
