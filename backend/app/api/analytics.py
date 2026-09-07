"""
数据智能 API

功能：
- 用户画像查询和更新
- 个性化推荐（目的地、景点）
- 趋势统计（目的地趋势、景点趋势）
- 行程效果分析
- 数据看板概览
- 用户行为记录
"""

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import json

from app.security.auth import require_user
from app.utils.responses import ok, fail
from app.services.analytics.user_profile import (
    get_user_profile,
    update_user_profile,
    log_behavior,
)
from app.services.analytics.recommendation import (
    recommend_destinations,
    recommend_pois,
)
from app.services.analytics.trends import (
    get_destination_trends,
    get_poi_trends,
    get_plan_effect_analysis,
    get_dashboard_overview,
)

router = APIRouter(prefix="/api/analytics", tags=["数据智能"])


# ==================== 请求模型 ====================

class BehaviorLogRequest(BaseModel):
    """用户行为记录请求"""
    behavior_type: str = Field(..., description="行为类型(search/view/plan/review/share/click)")
    target_type: Optional[str] = Field(None, description="目标类型(destination/poi/trip)")
    target_id: Optional[str] = Field(None, description="目标ID")
    target_name: Optional[str] = Field(None, description="目标名称")
    metadata: Optional[Dict[str, Any]] = Field(None, description="行为元数据")
    duration: Optional[int] = Field(None, description="停留时长(秒)")


# ==================== 用户画像 ====================

@router.get("/profile")
async def get_profile(user: dict = Depends(require_user)):
    """获取当前用户画像"""
    profile = get_user_profile(user['id'])
    if profile:
        return ok(profile)
    return fail("获取用户画像失败")


@router.post("/profile/refresh")
async def refresh_profile(user: dict = Depends(require_user)):
    """刷新当前用户画像（重新计算）"""
    profile = update_user_profile(user['id'])
    if profile:
        return ok(profile, "画像更新成功")
    return fail("更新用户画像失败")


# ==================== 个性化推荐 ====================

@router.get("/recommendations/destinations")
async def get_destination_recommendations(
    limit: int = Query(10, ge=1, le=50),
    algorithm: str = Query("hybrid", description="推荐算法(popular/content/collaborative/hybrid)"),
    user: dict = Depends(require_user),
):
    """获取个性化目的地推荐"""
    recommendations = recommend_destinations(
        user_id=user['id'],
        limit=limit,
        algorithm=algorithm,
    )
    return ok({
        "algorithm": algorithm,
        "count": len(recommendations),
        "items": recommendations,
    })


@router.get("/recommendations/pois")
async def get_poi_recommendations(
    destination: Optional[str] = Query(None, description="目的地筛选"),
    limit: int = Query(10, ge=1, le=50),
    algorithm: str = Query("hybrid", description="推荐算法"),
    user: dict = Depends(require_user),
):
    """获取个性化景点推荐"""
    recommendations = recommend_pois(
        user_id=user['id'],
        destination=destination,
        limit=limit,
        algorithm=algorithm,
    )
    return ok({
        "algorithm": algorithm,
        "destination": destination,
        "count": len(recommendations),
        "items": recommendations,
    })


@router.get("/recommendations/popular/destinations")
async def get_popular_destinations(
    limit: int = Query(10, ge=1, le=50),
):
    """获取热门目的地推荐（无需登录）"""
    recommendations = recommend_destinations(
        user_id=None,
        limit=limit,
        algorithm='popular',
    )
    return ok({
        "count": len(recommendations),
        "items": recommendations,
    })


# ==================== 趋势统计 ====================

@router.get("/trends/destinations")
async def get_destinations_trends(
    period_type: str = Query("weekly", description="统计周期(daily/weekly/monthly/yearly)"),
    limit: int = Query(20, ge=1, le=100),
):
    """获取目的地趋势"""
    trends = get_destination_trends(
        period_type=period_type,
        limit=limit,
    )
    return ok({
        "period_type": period_type,
        "count": len(trends),
        "items": trends,
    })


@router.get("/trends/pois")
async def get_pois_trends(
    destination: Optional[str] = Query(None, description="目的地筛选"),
    category: Optional[str] = Query(None, description="类别筛选"),
    period_type: str = Query("monthly", description="统计周期(daily/weekly/monthly)"),
    limit: int = Query(20, ge=1, le=100),
):
    """获取景点趋势"""
    trends = get_poi_trends(
        destination=destination,
        category=category,
        period_type=period_type,
        limit=limit,
    )
    return ok({
        "period_type": period_type,
        "destination": destination,
        "category": category,
        "count": len(trends),
        "items": trends,
    })


# ==================== 行程效果分析 ====================

@router.get("/analysis/plan-effect")
async def get_plan_analysis(
    period_days: int = Query(30, ge=1, le=365, description="统计天数"),
    user: dict = Depends(require_user),
):
    """获取行程效果分析（需要管理员权限）"""
    # TODO: 检查管理员权限
    analysis = get_plan_effect_analysis(period_days=period_days)
    return ok(analysis)


# ==================== 数据看板 ====================

@router.get("/dashboard/overview")
async def get_dashboard(user: dict = Depends(require_user)):
    """获取数据看板概览（需要管理员权限）"""
    # TODO: 检查管理员权限
    overview = get_dashboard_overview()
    return ok(overview)


# ==================== 用户行为记录 ====================

@router.post("/behavior/log")
async def log_user_behavior(
    req: BehaviorLogRequest,
    request: Request,
    user: dict = Depends(require_user),
):
    """记录用户行为"""
    # 获取客户端IP
    client_ip = request.client.host if request.client else None

    # 获取会话ID（从header或生成）
    session_id = request.headers.get("X-Session-ID") or None

    log_id = log_behavior(
        user_id=user['id'],
        session_id=session_id,
        behavior_type=req.behavior_type,
        target_type=req.target_type,
        target_id=req.target_id,
        target_name=req.target_name,
        metadata=req.metadata,
        duration=req.duration,
        ip=client_ip,
        user_agent=request.headers.get("user-agent"),
    )

    if log_id > 0:
        return ok({"id": log_id}, "行为记录成功")
    return fail("行为记录失败")
