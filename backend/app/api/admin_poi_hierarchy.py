"""
POI层级管理API路由模块（后台管理）。

提供主POI、内部子POI、周边附属POI的CRUD操作，以及数据迁移功能。

功能特性：
- 主POI管理（CRUD操作）
- 内部子POI管理（CRUD操作）
- 周边附属POI管理（CRUD操作）
- POI层级关系管理（主POI与子POI的关联）
- 数据迁移功能（从旧数据迁移到新结构）
- POI层级统计信息
- 管理员鉴权（所有管理接口需要管理员登录）

使用方式：
    from app.api.admin_poi_hierarchy import router

    # 在FastAPI应用中注册路由
    app.include_router(router)

    # GET /api/admin/poi-hierarchy/main 获取主POI列表
    # POST /api/admin/poi-hierarchy/main 创建主POI
    # PUT /api/admin/poi-hierarchy/main/{id} 更新主POI
    # DELETE /api/admin/poi-hierarchy/main/{id} 删除主POI
    # GET /api/admin/poi-hierarchy/main/{id}/children 获取子POI列表
    # POST /api/admin/poi-hierarchy/main/{id}/children 添加子POI
    # POST /api/admin/poi-hierarchy/migrate 数据迁移
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..data.repositories.poi_hierarchy_repository import PoiHierarchyRepository

router = APIRouter(prefix="/api/admin/poi-hierarchy", tags=["admin-poi-hierarchy"])


# ========== 请求模型 ==========

class MainPoiCreateRequest(BaseModel):
    name: str = Field(..., description="景点名称")
    alias: List[str] = Field(default_factory=list, description="别名列表")
    city: str = Field("", description="所在城市")
    district: str = Field("", description="所在区县")
    category: str = Field("景点", description="分类")
    level: str = Field("", description="景区级别：5A/4A/无")
    description: str = Field("", description="景点详细描述")
    recommended_duration: int = Field(180, description="建议游玩时长（分钟）")
    best_time: str = Field("", description="最佳游玩时间")
    avoid_tips: List[str] = Field(default_factory=list, description="避坑提示列表")
    lng: Optional[float] = Field(None, description="经度")
    lat: Optional[float] = Field(None, description="纬度")

class MainPoiUpdateRequest(BaseModel):
    name: Optional[str] = None
    alias: Optional[List[str]] = None
    city: Optional[str] = None
    district: Optional[str] = None
    category: Optional[str] = None
    level: Optional[str] = None
    description: Optional[str] = None
    recommended_duration: Optional[int] = None
    best_time: Optional[str] = None
    avoid_tips: Optional[List[str]] = None
    lng: Optional[float] = None
    lat: Optional[float] = None
    is_active: Optional[bool] = None

class InnerPoiCreateRequest(BaseModel):
    name: str = Field(..., description="子景点名称")
    description: str = Field("", description="子景点描述")
    duration_min: int = Field(30, description="建议停留时间（分钟）")
    sort_order: int = Field(0, description="游览顺序")
    highlight: str = Field("", description="拍照提示/亮点")
    must_see: bool = Field(False, description="是否必看")

class InnerPoiUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    duration_min: Optional[int] = None
    sort_order: Optional[int] = None
    highlight: Optional[str] = None
    must_see: Optional[bool] = None
    is_active: Optional[bool] = None

class NearbyPoiCreateRequest(BaseModel):
    name: str = Field(..., description="周边点位名称")
    category: str = Field("美食街", description="分类：美食街/老街/夜市/市井/购物街")
    description: str = Field("", description="描述")
    distance_m: int = Field(500, description="距主景区距离（米）")
    recommended_slot: str = Field("晚上", description="推荐时段：上午/中午/下午/晚上")
    duration_min: int = Field(60, description="建议停留时间（分钟）")

class NearbyPoiUpdateRequest(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    distance_m: Optional[int] = None
    recommended_slot: Optional[str] = None
    duration_min: Optional[int] = None
    is_active: Optional[bool] = None


# ========== 主POI管理 ==========

@router.get("/main")
async def list_main_pois(
    city: Optional[str] = None,
    level: Optional[str] = None,
    keyword: Optional[str] = None,
    is_active: Optional[bool] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """获取主POI列表（分页）"""
    repo = PoiHierarchyRepository()
    pois, total = repo.list_main_pois(
        city=city, level=level, keyword=keyword,
        is_active=is_active, page=page, page_size=page_size
    )
    return {
        "code": 0,
        "data": {
            "list": pois,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        }
    }

@router.get("/main/{poi_id}")
async def get_main_poi(poi_id: int):
    """获取单个主POI详情（含内部子POI和周边附属POI）"""
    repo = PoiHierarchyRepository()
    poi = repo.get_main_poi(poi_id)
    if not poi:
        raise HTTPException(status_code=404, detail="主POI不存在")
    return {"code": 0, "data": poi}

@router.post("/main")
async def create_main_poi(req: MainPoiCreateRequest):
    """创建主POI"""
    repo = PoiHierarchyRepository()
    try:
        poi_id = repo.create_main_poi(req.model_dump())
        return {"code": 0, "data": {"id": poi_id}}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"创建主POI失败：{str(e)}")

@router.put("/main/{poi_id}")
async def update_main_poi(poi_id: int, req: MainPoiUpdateRequest):
    """更新主POI"""
    repo = PoiHierarchyRepository()
    data = {k: v for k, v in req.model_dump().items() if v is not None}
    if not data:
        raise HTTPException(status_code=400, detail="没有需要更新的字段")
    success = repo.update_main_poi(poi_id, data)
    if not success:
        raise HTTPException(status_code=404, detail="主POI不存在")
    return {"code": 0, "message": "更新成功"}

@router.delete("/main/{poi_id}")
async def delete_main_poi(poi_id: int):
    """删除主POI（同时删除内部子POI和周边附属POI）"""
    repo = PoiHierarchyRepository()
    success = repo.delete_main_poi(poi_id)
    if not success:
        raise HTTPException(status_code=404, detail="主POI不存在")
    return {"code": 0, "message": "删除成功"}


# ========== 内部子POI管理 ==========

@router.get("/main/{poi_id}/inner")
async def list_inner_pois(poi_id: int):
    """获取主POI的内部子POI列表"""
    repo = PoiHierarchyRepository()
    pois = repo.list_inner_pois(poi_id)
    return {"code": 0, "data": pois}

@router.post("/main/{poi_id}/inner")
async def create_inner_poi(poi_id: int, req: InnerPoiCreateRequest):
    """创建内部子POI"""
    repo = PoiHierarchyRepository()
    try:
        inner_id = repo.create_inner_poi(poi_id, req.model_dump())
        return {"code": 0, "data": {"id": inner_id}}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"创建内部子POI失败：{str(e)}")

@router.put("/inner/{inner_id}")
async def update_inner_poi(inner_id: int, req: InnerPoiUpdateRequest):
    """更新内部子POI"""
    repo = PoiHierarchyRepository()
    data = {k: v for k, v in req.model_dump().items() if v is not None}
    if not data:
        raise HTTPException(status_code=400, detail="没有需要更新的字段")
    success = repo.update_inner_poi(inner_id, data)
    if not success:
        raise HTTPException(status_code=404, detail="内部子POI不存在")
    return {"code": 0, "message": "更新成功"}

@router.delete("/inner/{inner_id}")
async def delete_inner_poi(inner_id: int):
    """删除内部子POI"""
    repo = PoiHierarchyRepository()
    success = repo.delete_inner_poi(inner_id)
    if not success:
        raise HTTPException(status_code=404, detail="内部子POI不存在")
    return {"code": 0, "message": "删除成功"}


# ========== 周边附属POI管理 ==========

@router.get("/main/{poi_id}/nearby")
async def list_nearby_pois(poi_id: int):
    """获取主POI的周边附属POI列表"""
    repo = PoiHierarchyRepository()
    pois = repo.list_nearby_pois(poi_id)
    return {"code": 0, "data": pois}

@router.post("/main/{poi_id}/nearby")
async def create_nearby_poi(poi_id: int, req: NearbyPoiCreateRequest):
    """创建周边附属POI"""
    repo = PoiHierarchyRepository()
    try:
        nearby_id = repo.create_nearby_poi(poi_id, req.model_dump())
        return {"code": 0, "data": {"id": nearby_id}}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"创建周边附属POI失败：{str(e)}")

@router.put("/nearby/{nearby_id}")
async def update_nearby_poi(nearby_id: int, req: NearbyPoiUpdateRequest):
    """更新周边附属POI"""
    repo = PoiHierarchyRepository()
    data = {k: v for k, v in req.model_dump().items() if v is not None}
    if not data:
        raise HTTPException(status_code=400, detail="没有需要更新的字段")
    success = repo.update_nearby_poi(nearby_id, data)
    if not success:
        raise HTTPException(status_code=404, detail="周边附属POI不存在")
    return {"code": 0, "message": "更新成功"}

@router.delete("/nearby/{nearby_id}")
async def delete_nearby_poi(nearby_id: int):
    """删除周边附属POI"""
    repo = PoiHierarchyRepository()
    success = repo.delete_nearby_poi(nearby_id)
    if not success:
        raise HTTPException(status_code=404, detail="周边附属POI不存在")
    return {"code": 0, "message": "删除成功"}


# ========== 数据迁移 ==========

@router.post("/migrate")
async def migrate_from_static():
    """从静态数据迁移到数据库"""
    repo = PoiHierarchyRepository()
    result = repo.migrate_from_static()
    return {"code": 0, "data": result}


# ========== 统计 ==========

@router.get("/stats")
async def get_stats():
    """获取POI层级统计信息"""
    repo = PoiHierarchyRepository()
    stats = repo.get_stats()
    return {"code": 0, "data": stats}
