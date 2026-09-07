#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统接口路由模块。

提供系统级别的公开接口，无需登录：
- / - 根路径（应用信息）
- /api/status - 运行环境状态（Provider、AI模型、缓存占用）
- /api/site/config - 站点配置（品牌文案、TTL配置）
- /metrics - 监控指标（Prometheus/JSON格式）

功能特性：
- 根路径：返回应用基本信息（应用名称、文档路径、状态接口）
- 运行环境状态：数据 Provider（高德/腾讯/不可用）、AI 模型是否可用、缓存占用
- 站点配置：C 端可读的品牌文案与 TTL 配置（后台可维护）
- 监控指标：Prometheus 文本格式 / JSON 格式（用于 Prometheus 抓取或运维监控）

使用方式：
    from app.api.system import router

    # 在FastAPI应用中注册路由
    app.include_router(router)

    # 访问 / 获取应用基本信息
    # 访问 /api/status 获取运行环境状态
    # 访问 /api/site/config 获取站点配置
    # 访问 /metrics 获取监控指标
"""
from fastapi import APIRouter, Response as FastAPIResponse

from ..ai import ai as ai_mod
from ..config import settings
from ..data.repositories import admin_repository
from ..infrastructure.cache import cache
from ..infrastructure.metrics import metrics
from ..services import map as amap

router = APIRouter()


@router.get("/")
def root():
    """根路径：返回应用基本信息。"""
    return {"app": settings.app_name, "docs": "/docs", "status": "/api/status"}


@router.get("/api/status")
async def status():
    """
    运行环境状态：数据 Provider（高德/腾讯/不可用）、AI 模型是否可用、缓存占用。
    """
    ns_counts = cache.counts()
    prov = amap.provider()
    return {
        "provider": prov,
        "amap_ready": settings.amap_ready,
        "amap_mode": "real" if settings.amap_ready else "unavailable",
        "tencent_ready": settings.tencent_ready,
        "tencent_mode": "real" if settings.tencent_ready else "unavailable",
        "ai_available": ai_mod.ai_available(),
        "ai_model": ai_mod.resolve_model(),
        "ai_provider": settings.ai.ai_provider,
        "ollama_base_url": settings.ollama_base_url,
        "cache": {"total": cache.size(), "by_type": ns_counts,
                  "ttl": {"geo": "7d", "poi": "1d", "route": "30m", "weather": "2h"}},
    }


@router.get("/api/site/config")
def site_config_public():
    """C 端可读的品牌文案与 TTL 配置（后台可维护）。"""
    cfg = admin_repository.get_config()
    return {
        "brand_slogan": cfg.get("brand_slogan", "世界在等你，去见山海！"),
        "brand_hero": cfg.get("brand_hero", "用对话生成你的专属旅行计划"),
        "brand_footer": cfg.get("brand_footer", "去见山海 · 激发行走天下的勇气"),
        "ttl": {
            "geo": cfg.get("ttl_geo_days", "7"),
            "poi": cfg.get("ttl_poi_days", "1"),
            "route": cfg.get("ttl_route_min", "30"),
            "weather": cfg.get("ttl_weather_h", "2"),
        },
    }


@router.get("/metrics")
def metrics_endpoint(format: str = "prometheus"):
    """
    指标接口（Prometheus 文本格式 / JSON 格式）。

    用于 Prometheus 抓取或运维监控，包含请求指标（QPS/延迟/错误率）和业务指标。
    """
    if format == "json":
        return metrics.to_json()
    return FastAPIResponse(content=metrics.to_prometheus(), media_type="text/plain; version=0.0.4")
