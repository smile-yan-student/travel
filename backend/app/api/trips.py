"""
出行记录路由模块。

提供出行记录相关的接口：
- /api/trips - 记录出行足迹
- /api/trips - 查看足迹汇总

功能特性：
- 记录出行足迹（目的地、天数、风格、坐标、距离）
- 查看足迹汇总（出行次数、总天数、总距离、最近出行）
- 地理编码（目的地→坐标）
- 距离计算（出发点到目的地的距离）
- 登录鉴权（所有出行记录接口需要登录）

使用方式：
    from app.api.trips import router

    # 在FastAPI应用中注册路由
    app.include_router(router)

    # POST /api/trips 记录出行足迹
    # GET /api/trips 查看足迹汇总
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Header, HTTPException

from ..data.repositories import user_repository
from ..services import map as amap
from .deps import HOME_CENTER, TripReport, bearer_user

router = APIRouter(prefix="/api/trips", tags=["trips"])


def _require_user(authorization: Optional[str]) -> dict:
    user = bearer_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="未登录或登录已失效")
    return user


@router.post("")
async def report_trip(req: TripReport, authorization: Optional[str] = Header(None)):
    """登录用户记录一次出行（需登录）。"""
    user = _require_user(authorization)
    geo = await amap.geocode(req.destination)
    if not geo:
        # 地理编码失败时使用默认坐标，避免报错
        geo = {"lng": HOME_CENTER["lng"], "lat": HOME_CENTER["lat"]}
    dist_km = round(amap.haversine(HOME_CENTER["lng"], HOME_CENTER["lat"], geo["lng"], geo["lat"]) / 1000, 1)
    user_repository.add_trip(
        user["id"], req.destination, req.days, req.style,
        geo["lng"], geo["lat"], dist_km, req.conversation_id
    )
    return {"ok": True, "recorded": True}


@router.get("")
async def get_trips(authorization: Optional[str] = Header(None)):
    """登录用户查看本人足迹（需登录）。"""
    user = _require_user(authorization)
    return {"user": user, "summary": user_repository.trips_summary(user["id"])}
