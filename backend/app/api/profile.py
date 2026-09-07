"""
用户画像API路由模块。

提供用户画像相关的接口：
- 获取用户画像
- 用户偏好学习（从规划/修改行为中学习）
- 获取带偏好的规划参数

功能特性：
- 获取当前用户画像（出行偏好、历史行为、个性化推荐）
- 获取用户偏好详情（风格、预算、节奏、出行方式等）
- 从规划行为中学习用户偏好
- 从修改行为中学习用户偏好
- 获取带偏好的规划参数（基于用户历史行为自动填充参数）
- 登录鉴权（所有用户画像接口需要登录）

使用方式：
    from app.api.profile import router

    # 在FastAPI应用中注册路由
    app.include_router(router)

    # GET /api/profile/me 获取当前用户画像
    # GET /api/profile/preferences 获取用户偏好详情
    # POST /api/profile/learn/plan 从规划行为中学习
    # POST /api/profile/learn/modification 从修改行为中学习
    # POST /api/profile/plan-params 获取带偏好的规划参数
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from ..services.user.user_profile import get_user_profile_service
from ..services.usage_limit import get_usage_limit_service
from .deps import bearer_user

router = APIRouter(prefix="/api/profile", tags=["profile"])


def _require_user(authorization: Optional[str]) -> dict:
    user = bearer_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="未登录或登录已失效")
    return user


# ========== 请求模型 ==========

class LearnFromPlanRequest(BaseModel):
    plan_params: Dict[str, Any] = Field(..., description="规划参数")


class LearnFromModificationRequest(BaseModel):
    mod_type: str = Field(..., description="修改类型")
    mod_params: Dict[str, Any] = Field(default_factory=dict, description="修改参数")


class PlanParamsRequest(BaseModel):
    base_params: Dict[str, Any] = Field(default_factory=dict, description="基础规划参数")


# ========== 用户画像查询 ==========

@router.get("/me")
async def get_my_profile(authorization: Optional[str] = Header(None)):
    """获取当前用户画像"""
    user = _require_user(authorization)
    service = get_user_profile_service()
    profile = service.get_profile(user["id"])
    profile.username = user.get("username", "")
    return {
        "code": 0,
        "data": service.get_profile_summary(user["id"])
    }


@router.get("/preferences")
async def get_my_preferences(authorization: Optional[str] = Header(None)):
    """获取用户偏好详情"""
    user = _require_user(authorization)
    service = get_user_profile_service()
    profile = service.get_profile(user["id"])
    return {
        "code": 0,
        "data": {
            "preferences": profile.preferences.__dict__,
            "profile_completeness": service._calculate_completeness(profile.preferences),
        }
    }


@router.get("/usage")
async def get_my_usage(authorization: Optional[str] = Header(None)):
    """获取用户的调用次数使用情况"""
    user = _require_user(authorization)
    usage_service = get_usage_limit_service()
    usage_info = usage_service.get_usage_info(str(user["id"]))
    return {
        "code": 0,
        "data": usage_info
    }


# ========== 偏好学习 ==========

@router.post("/learn/plan")
async def learn_from_plan(
    req: LearnFromPlanRequest,
    authorization: Optional[str] = Header(None),
):
    """从规划行为中学习用户偏好"""
    user = _require_user(authorization)
    service = get_user_profile_service()
    profile = service.learn_from_plan(user["id"], req.plan_params)
    return {
        "code": 0,
        "data": {
            "message": "偏好学习完成",
            "profile_completeness": service._calculate_completeness(profile.preferences),
        }
    }


@router.post("/learn/modification")
async def learn_from_modification(
    req: LearnFromModificationRequest,
    authorization: Optional[str] = Header(None),
):
    """从修改行为中学习用户偏好"""
    user = _require_user(authorization)
    service = get_user_profile_service()
    profile = service.learn_from_modification(user["id"], req.mod_type, req.mod_params)
    return {
        "code": 0,
        "data": {
            "message": "偏好学习完成",
            "profile_completeness": service._calculate_completeness(profile.preferences),
        }
    }


# ========== 偏好应用 ==========

@router.post("/plan-params")
async def get_plan_params_with_preferences(
    req: PlanParamsRequest,
    authorization: Optional[str] = Header(None),
):
    """获取带用户偏好的规划参数（跨行程记忆带入）"""
    user = _require_user(authorization)
    service = get_user_profile_service()
    merged_params = service.get_plan_params_with_preferences(user["id"], req.base_params)
    return {
        "code": 0,
        "data": {
            "base_params": req.base_params,
            "merged_params": merged_params,
            "preferences_applied": {
                k: v for k, v in merged_params.items()
                if k not in req.base_params or req.base_params.get(k) != v
            }
        }
    }


# ========== 画像统计 ==========

@router.get("/stats")
async def get_profile_stats(authorization: Optional[str] = Header(None)):
    """获取用户画像统计"""
    user = _require_user(authorization)
    service = get_user_profile_service()
    profile = service.get_profile(user["id"])
    prefs = profile.preferences
    return {
        "code": 0,
        "data": {
            "total_plans": prefs.total_plans,
            "total_modifications": prefs.total_modifications,
            "favorite_destinations": prefs.favorite_destinations[-5:],
            "last_plan_time": prefs.last_plan_time,
            "profile_completeness": service._calculate_completeness(prefs),
            "learned_preferences_count": sum([
                1 for v in [
                    prefs.pace_preference, prefs.budget_preference,
                    prefs.group_type, prefs.traffic_preference,
                    prefs.food_lover, prefs.physical_level,
                ] if v is not None
            ]) + len(prefs.style_preferences),
        }
    }
