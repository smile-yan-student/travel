"""
健康检查模块。

提供 /health 和 /health/detailed 接口，检查应用、数据库、缓存、外部依赖状态。
用于容器健康探针、负载均衡健康检查、运维监控。

功能特性：
- 轻量级健康检查（仅检查应用自身，快速响应）
- 详细健康检查（检查所有依赖）
- 数据库连接状态检查
- 缓存状态检查
- 地图服务状态检查（高德/腾讯双Provider）
- AI服务状态检查（Ollama本地模型）
- 总体状态计算（任一依赖 unhealthy 则总体 unhealthy，degraded 则总体 degraded）

使用方式：
    from app.core.health import router

    # 在FastAPI应用中注册路由
    app.include_router(router)

    # 访问 /health 获取轻量级健康检查
    # 访问 /health/detailed 获取详细健康检查
"""
import time
from typing import Any, Dict

from fastapi import APIRouter

from ..ai import ai as ai_mod
from ..config import settings
from ..infrastructure.cache import cache
from ..services import map as amap

router = APIRouter(tags=["health"])


def _check_database() -> Dict[str, Any]:
    """检查数据库连接状态。"""
    start = time.time()
    try:
        from ..data.database import get_conn
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
            return {
                "status": "healthy",
                "latency_ms": round((time.time() - start) * 1000, 2),
            }
        finally:
            conn.close()
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "latency_ms": round((time.time() - start) * 1000, 2),
        }


def _check_cache() -> Dict[str, Any]:
    """检查缓存状态。"""
    start = time.time()
    try:
        # 尝试写入和读取一个测试键（TTL 60秒）
        cache.set("health", "test", "ping", ttl=60)
        val = cache.get("health", "test", ttl=60)
        return {
            "status": "healthy" if val == "ping" else "degraded",
            "size": cache.size(),
            "latency_ms": round((time.time() - start) * 1000, 2),
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "latency_ms": round((time.time() - start) * 1000, 2),
        }


def _check_map_service() -> Dict[str, Any]:
    """检查地图服务状态。"""
    prov = amap.provider()
    return {
        "status": "healthy" if prov != "none" else "degraded",
        "provider": prov,
        "amap_ready": settings.amap_ready,
        "tencent_ready": settings.tencent_ready,
    }


def _check_ai_service() -> Dict[str, Any]:
    """检查 AI 服务状态。"""
    available = ai_mod.ai_available()
    return {
        "status": "healthy" if available else "unhealthy",
        "model": settings.ollama_model,
        "base_url": settings.ollama_base_url,
        "available": available,
    }


@router.get("/health")
async def health_check():
    """轻量级健康检查（仅检查应用自身，快速响应）。

    用于容器 liveness probe，不应包含耗时的依赖检查。
    """
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.version,
        "timestamp": int(time.time()),
    }


@router.get("/health/detailed")
async def detailed_health_check():
    """详细健康检查（检查所有依赖）。

    用于容器 readiness probe、负载均衡健康检查、运维监控。
    返回各依赖的详细状态，总体状态由各依赖状态决定。
    """
    checks = {
        "database": _check_database(),
        "cache": _check_cache(),
        "map_service": _check_map_service(),
        "ai_service": _check_ai_service(),
    }

    # 计算总体状态：任一依赖 unhealthy 则总体 unhealthy，degraded 则总体 degraded
    statuses = [c["status"] for c in checks.values()]
    if "unhealthy" in statuses:
        overall = "unhealthy"
    elif "degraded" in statuses:
        overall = "degraded"
    else:
        overall = "healthy"

    return {
        "status": overall,
        "app": settings.app_name,
        "version": settings.version,
        "timestamp": int(time.time()),
        "checks": checks,
    }
