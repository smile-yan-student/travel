"""
探索路由模块。

提供探索相关的接口：
- /api/poi/search - POI搜索
- /api/explore - 周边探索（放射状可视化）

功能特性：
- POI检索（按城市和类别检索POI，供前端手动选点）
- 周边探索（以地图选点为中心，检索周围可去POI，放射状可视化用）
- 双Provider兼容（高德/腾讯）
- 登录鉴权（所有探索接口需要登录）

使用方式：
    from app.api.explore import router

    # 在FastAPI应用中注册路由
    app.include_router(router)

    # POST /api/poi/search POI搜索
    # POST /api/explore 周边探索
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Header, HTTPException

from ..config import settings
from ..data.models.models import ExploreRequest, ExploreResponse
from ..services import map as amap
from .deps import bearer_user

router = APIRouter(prefix="/api", tags=["explore"])


def _require_user(authorization: Optional[str]) -> dict:
    user = bearer_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="未登录或登录已失效")
    return user


@router.post("/poi/search")
async def poi_search(city: str = "杭州", categories: str = "景点,美食",
                     authorization: Optional[str] = Header(None)):
    """POI 检索（供前端手动选点，需登录）"""
    _require_user(authorization)
    center = await amap.geocode(city)
    cats = [c.strip() for c in categories.split(",") if c.strip()]
    pois = await amap.search_pois(city, center, cats)
    return {"city": city, "center": center, "count": len(pois), "pois": pois}


@router.post("/explore", response_model=ExploreResponse)
async def explore(req: ExploreRequest, authorization: Optional[str] = Header(None)):
    """周边探索：以地图选点为中心，检索周围可去 POI（放射状可视化用，需登录）"""
    _require_user(authorization)
    pois = await amap.explore_around(req.lng, req.lat, req.categories, req.radius, 40)
    return ExploreResponse(
        center={"lng": req.lng, "lat": req.lat},
        radius=req.radius,
        count=len(pois),
        pois=pois,
        source="amap" if settings.amap_ready else "tencent",
    )
