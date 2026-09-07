"""
地图服务 - 基础客户端模块。

基础功能：
- 基础常量（API地址、城市中心坐标）
- 工具函数（haversine距离计算）
- HTTP请求（高德/腾讯GET请求，含重试和签名）
- Provider探测（当前生效的数据Provider）

功能特性：
- 高德/腾讯双Provider兼容
- 全局信号量（限制高德并发 ≤3，避免高频并行调用触发限流/丢批次）
- 慢请求日志（超过阈值才记录，避免成功请求日志爆炸）
- 失败重试（默认2次重试，指数退避）
- 腾讯签名（MD5签名）
- Provider探测（启动时真实探测高德/腾讯 Key 是否可用）

使用方式：
    from app.services.map.client import (
        AMAP_BASE, TENCENT_BASE, CITY_CENTERS,
        haversine, amap_get, tencent_get, provider,
        probe_amap, probe_tencent
    )

    # 获取当前Provider
    prov = provider()  # "amap" / "tencent" / "none"

    # 高德GET请求
    data = await amap_get(f"{AMAP_BASE}/geocode/geo", {"address": "北京"})

    # 腾讯GET请求
    data = await tencent_get(f"{TENCENT_BASE}/geocoder/v1/", {"address": "北京"})

    # 计算两点距离
    distance = haversine(116.407, 39.904, 120.155, 30.274)

    # 获取城市中心坐标
    center = CITY_CENTERS.get("杭州")  # [120.155, 30.274]
"""
import asyncio
import hashlib
import math
import time
from typing import Any, Dict, Optional
from urllib.parse import urlsplit

import httpx

from ...config import settings
from ...infrastructure import logger as log_mod
from ...infrastructure.cache import (
    TTL_GEO,
    TTL_POI,
    TTL_ROUTE,
    TTL_WEATHER,
    cache,
    get_ttl,
)

_amap_logger = log_mod.get_logger("amap")
_SLOW_THRESHOLD_MS = 3000  # 地图 API 慢请求阈值

# 熔断机制：当检测到不可重试错误（如调用量已达上限）时，立即熔断，停止后续调用
_circuit_breaker = {
    "amap_open": True,
    "tencent_open": True,
    "amap_reason": "",
    "tencent_reason": "",
}

# 不可重试的错误码/消息（遇到这些错误立即熔断，不再重试或继续调用）
_NON_RETRYABLE_MESSAGES = (
    "调用量已达到上限",
    "调用量已达上限",
    "key不存在",
    "key无效",
    "签名错误",
    "权限不足",
    "账号已被封禁",
)
_NON_RETRYABLE_STATUS = {
    "tencent": {110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121},
    "amap": {"10001", "10002", "10003", "10004", "10005", "10006", "10007", "10008", "10009", "10010"},
}

AMAP_BASE = "https://restapi.amap.com/v3"
TENCENT_BASE = "https://apis.map.qq.com/ws"

# 常用城市中心坐标（真实/演示双模式兜底）
CITY_CENTERS = {
    "北京": [116.407, 39.904],
    "上海": [121.473, 31.230],
    "广州": [113.264, 23.129],
    "深圳": [114.057, 22.543],
    "杭州": [120.155, 30.274],
    "成都": [104.066, 30.572],
    "重庆": [106.551, 29.563],
    "西安": [108.940, 34.341],
    "南京": [118.796, 32.060],
    "苏州": [120.585, 31.298],
    "武汉": [114.305, 30.593],
    "长沙": [112.938, 28.228],
    "厦门": [118.089, 24.479],
    "青岛": [120.383, 36.067],
    "济南": [117.120, 36.651],
    "天津": [117.200, 39.085],
    "郑州": [113.625, 34.746],
    "昆明": [102.832, 24.880],
    "三亚": [109.511, 18.252],
    "大理": [100.230, 25.592],
    "丽江": [100.229, 26.855],
    "桂林": [110.290, 25.274],
    "洛阳": [112.454, 34.620],
    "哈尔滨": [126.535, 45.803],
    "沈阳": [123.432, 41.808],
}


def log_slow(provider: str, api_name: str, start: float) -> None:
    """
    地图 API 慢请求日志（超过阈值才记录，避免成功请求日志爆炸）。

    Args:
        provider: Provider名称（amap/tencent）
        api_name: API名称
        start: 开始时间戳
    """
    duration_ms = round((time.time() - start) * 1000, 2)
    if duration_ms > _SLOW_THRESHOLD_MS:
        _amap_logger.warning(
            f"{provider}_api_slow",
            extra={"fields": {"api": api_name, "duration_ms": duration_ms}},
        )


def haversine(lng1: float, lat1: float, lng2: float, lat2: float) -> int:
    """
    两点球面距离（米）。

    Args:
        lng1: 点1经度
        lat1: 点1纬度
        lng2: 点2经度
        lat2: 点2纬度

    Returns:
        int: 距离（米）
    """
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = (
        math.sin(dp / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    )
    return int(2 * r * math.asin(math.sqrt(a)))


def _http() -> httpx.AsyncClient:
    """
    创建HTTP客户端。

    Returns:
        httpx.AsyncClient: HTTP客户端实例
    """
    return httpx.AsyncClient(timeout=8.0)


_AMAP_SEM: Optional[asyncio.Semaphore] = None


def amap_sem() -> asyncio.Semaphore:
    """
    全局信号量：限制高德并发 ≤3，避免高频并行调用触发限流/丢批次。

    Returns:
        asyncio.Semaphore: 信号量实例
    """
    global _AMAP_SEM
    if _AMAP_SEM is None:
        _AMAP_SEM = asyncio.Semaphore(3)
    return _AMAP_SEM


async def amap_get(
    url: str,
    params: Dict[str, Any],
    retry: int = 1,
    retry_empty: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    带 Key 的 GET（异步），失败返回 None。

    Args:
        url: 请求URL
        params: 请求参数
        retry: 重试次数（默认1次，即不重试，失败直接走下一步）
        retry_empty: 是否重试空结果（默认False）

    Returns:
        Optional[Dict[str, Any]]: 响应数据，失败返回 None
    """
    start = time.time()
    api_name = url.replace(AMAP_BASE, "").split("?")[0]

    # 熔断检查：如果高德已熔断，直接返回None
    if not _circuit_breaker["amap_open"]:
        return None

    params["key"] = settings.amap_key
    data = None
    last_err = None
    for attempt in range(retry):
        try:
            async with amap_sem():
                async with _http() as client:
                    resp = await client.get(url, params=params)
                    data = resp.json()
        except Exception as e:
            last_err = str(e)
            data = None
        if data and data.get("status") == "1":
            pois = data.get("pois")
            if not (retry_empty and (pois is None or len(pois) == 0)):
                log_slow("amap", api_name, start)
                return data
        # 检查是否是不可重试错误，如果是则立即熔断
        if data:
            status = str(data.get("status", ""))
            message = (data.get("info") or data.get("message") or "").strip()
            is_non_retryable = (
                status in _NON_RETRYABLE_STATUS.get("amap", set())
                or any(msg in message for msg in _NON_RETRYABLE_MESSAGES)
            )
            if is_non_retryable:
                _circuit_breaker["amap_open"] = False
                _circuit_breaker["amap_reason"] = f"status={status}, message={message}"
                _amap_logger.warning(
                    "amap_circuit_breaker_open",
                    extra={
                        "fields": {
                            "api": api_name,
                            "status": status,
                            "message": message,
                            "reason": _circuit_breaker["amap_reason"],
                        }
                    },
                )
                return None
        if attempt < retry - 1:
            await asyncio.sleep(0.35 * (attempt + 1))
    duration_ms = round((time.time() - start) * 1000, 2)
    status = data.get("status") if data else None
    _amap_logger.warning(
        "amap_api_failed",
        extra={
            "fields": {
                "api": api_name,
                "status": status,
                "duration_ms": duration_ms,
                "retry": retry,
                "error": last_err,
            }
        },
    )
    return data if data and data.get("status") == "1" else None


def tencent_sign(method_path: str, params: Dict[str, Any], sk: str) -> str:
    """
    腾讯 WebService 签名（MD5）。

    Args:
        method_path: 方法路径
        params: 请求参数
        sk: 签名密钥

    Returns:
        str: MD5签名
    """
    qs = "&".join(f"{k}={params[k]}" for k in sorted(params))
    raw = f"{method_path}?{qs}{sk}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


async def tencent_get(
    url: str,
    params: Dict[str, Any],
    retry: int = 1,
    retry_empty: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    腾讯地图 WebService GET（status=0 视为成功），失败/非 0 返回 None。

    Args:
        url: 请求URL
        params: 请求参数
        retry: 重试次数（默认1次，即不重试，失败直接走下一步）
        retry_empty: 是否重试空结果（默认False）

    Returns:
        Optional[Dict[str, Any]]: 响应数据，失败返回 None
    """
    start = time.time()
    api_name = url.replace(TENCENT_BASE, "").split("?")[0]

    # 熔断检查：如果腾讯已熔断，直接返回None
    if not _circuit_breaker["tencent_open"]:
        return None

    params["key"] = settings.tencent_key
    sk = settings.tencent_sk
    if not sk:
        return None  # 未配置签名密钥，腾讯无法调用，诚实降级
    path = urlsplit(url).path or "/"
    params["sig"] = tencent_sign(path, params, sk)
    data = None
    last_err = None
    for attempt in range(retry):
        try:
            async with amap_sem():
                async with _http() as client:
                    resp = await client.get(url, params=params)
                    data = resp.json()
        except Exception as e:
            last_err = str(e)
            data = None
        if data and data.get("status") == 0:
            arr = data.get("data")
            if not (retry_empty and (arr is None or len(arr) == 0)):
                log_slow("tencent", api_name, start)
                return data
        # 检查是否是不可重试错误，如果是则立即熔断
        if data:
            status = data.get("status")
            message = (data.get("message") or "").strip()
            is_non_retryable = (
                status in _NON_RETRYABLE_STATUS.get("tencent", set())
                or any(msg in message for msg in _NON_RETRYABLE_MESSAGES)
            )
            if is_non_retryable:
                _circuit_breaker["tencent_open"] = False
                _circuit_breaker["tencent_reason"] = f"status={status}, message={message}"
                _amap_logger.warning(
                    "tencent_circuit_breaker_open",
                    extra={
                        "fields": {
                            "api": api_name,
                            "status": status,
                            "message": message,
                            "reason": _circuit_breaker["tencent_reason"],
                        }
                    },
                )
                return None
        if attempt < retry - 1:
            await asyncio.sleep(0.35 * (attempt + 1))
    duration_ms = round((time.time() - start) * 1000, 2)
    status = data.get("status") if data else None
    _amap_logger.warning(
        "tencent_api_failed",
        extra={
            "fields": {
                "api": api_name,
                "status": status,
                "duration_ms": duration_ms,
                "retry": retry,
                "error": last_err,
                "message": (data or {}).get("message", "") if data else "",
            }
        },
    )
    return data if data and data.get("status") == 0 else None


def provider() -> str:
    """
    当前生效的数据 Provider：高德优先 → 腾讯兜底 → none（无可用Provider）。

    Returns:
        str: Provider名称（amap/tencent/none）
    """
    if settings.amap_ready:
        return "amap"
    if settings.tencent_ready:
        return "tencent"
    return "none"


async def probe_amap() -> bool:
    """
    启动时真实探测高德 Key 是否可用。

    Returns:
        bool: 是否可用
    """
    if not settings.amap_key:
        return False
    data = await amap_get(f"{AMAP_BASE}/geocode/geo", {"address": "北京"})
    if data and data.get("geocodes"):
        return True
    data = await amap_get(
        f"{AMAP_BASE}/place/text",
        {"city": "北京", "keywords": "景区", "offset": 1, "page": 1},
    )
    return bool(data and data.get("pois"))


async def probe_tencent() -> bool:
    """
    启动时真实探测腾讯 Key 是否可用（高德不可用时的兼容 Provider）。

    Returns:
        bool: 是否可用
    """
    if not settings.tencent_key or not settings.tencent_sk:
        return False
    data = await tencent_get(f"{TENCENT_BASE}/geocoder/v1/", {"address": "北京"})
    if data and data.get("result"):
        return True
    data = await tencent_get(
        f"{TENCENT_BASE}/place/v1/search",
        {
            "keyword": "北京",
            "boundary": "region(北京,0)",
            "page_size": 1,
            "page_index": 1,
        },
    )
    return bool(data and data.get("data"))
