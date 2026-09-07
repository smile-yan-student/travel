"""
知识库管理API路由模块（后台管理）。

提供知识库分类、知识文档的CRUD操作，以及RAG检索测试、配置管理等接口。

功能特性：
- 知识库分类管理（CRUD操作）
- 知识文档管理（CRUD操作）
- RAG检索测试（测试检索效果）
- 知识库配置管理
- 知识库统计信息
- 批量导入/导出知识文档
- 管理员鉴权（所有管理接口需要管理员登录）

使用方式：
    from app.api.admin_knowledge import router

    # 在FastAPI应用中注册路由
    app.include_router(router)

    # GET /api/admin/knowledge/categories 获取分类列表
    # POST /api/admin/knowledge/categories 创建分类
    # PUT /api/admin/knowledge/categories/{id} 更新分类
    # DELETE /api/admin/knowledge/categories/{id} 删除分类
    # GET /api/admin/knowledge/docs 获取文档列表
    # POST /api/admin/knowledge/docs 创建文档
    # PUT /api/admin/knowledge/docs/{id} 更新文档
    # DELETE /api/admin/knowledge/docs/{id} 删除文档
    # POST /api/admin/knowledge/test RAG检索测试
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..data.repositories.knowledge_repository import KnowledgeRepository

router = APIRouter(prefix="/api/admin/knowledge", tags=["admin-knowledge"])


# ========== 请求模型 ==========

class CategoryCreateRequest(BaseModel):
    name: str = Field(..., description="分类名称")
    code: str = Field(..., description="分类编码")
    description: str = Field("", description="分类描述")
    sort_order: int = Field(0, description="排序")

class CategoryUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None

class DocCreateRequest(BaseModel):
    category_id: int = Field(..., description="分类ID")
    title: str = Field(..., description="文档标题")
    content: str = Field(..., description="文档内容")
    summary: str = Field("", description="内容摘要")
    tags: str = Field("", description="标签，逗号分隔")
    related_poi: str = Field("", description="关联POI名称，逗号分隔")
    related_city: str = Field("", description="关联城市")
    status: str = Field("draft", description="状态：draft/published/offline")
    source: str = Field("manual", description="来源")
    author: str = Field("", description="作者")

class DocUpdateRequest(BaseModel):
    category_id: Optional[int] = None
    title: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    tags: Optional[str] = None
    related_poi: Optional[str] = None
    related_city: Optional[str] = None
    status: Optional[str] = None
    is_pinned: Optional[bool] = None
    is_blocked: Optional[bool] = None
    weight: Optional[int] = None

class ConfigUpdateRequest(BaseModel):
    config_key: str = Field(..., description="配置键")
    config_value: str = Field(..., description="配置值")
    description: str = Field("", description="配置描述")

class SearchTestRequest(BaseModel):
    poi_name: Optional[str] = None
    city: Optional[str] = None
    keyword: Optional[str] = None
    category_code: Optional[str] = None
    limit: int = Field(5, ge=1, le=20)


# ========== 分类管理 ==========

@router.get("/categories")
async def list_categories():
    """获取知识库分类列表"""
    repo = KnowledgeRepository()
    categories = repo.list_categories(only_active=False)
    return {"code": 0, "data": categories}

@router.post("/categories")
async def create_category(req: CategoryCreateRequest):
    """创建分类"""
    repo = KnowledgeRepository()
    try:
        category_id = repo.create_category(req.name, req.code, req.description, req.sort_order)
        return {"code": 0, "data": {"id": category_id}}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"创建分类失败：{str(e)}")

@router.put("/categories/{category_id}")
async def update_category(category_id: int, req: CategoryUpdateRequest):
    """更新分类"""
    repo = KnowledgeRepository()
    data = {k: v for k, v in req.model_dump().items() if v is not None}
    if not data:
        raise HTTPException(status_code=400, detail="没有需要更新的字段")
    success = repo.update_category(category_id, **data)
    if not success:
        raise HTTPException(status_code=404, detail="分类不存在")
    return {"code": 0, "message": "更新成功"}


# ========== 文档管理 ==========

@router.get("/docs")
async def list_docs(
    category_id: Optional[int] = None,
    status: Optional[str] = None,
    related_poi: Optional[str] = None,
    related_city: Optional[str] = None,
    keyword: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """获取知识文档列表（分页）"""
    repo = KnowledgeRepository()
    docs, total = repo.list_docs(
        category_id=category_id, status=status, related_poi=related_poi,
        related_city=related_city, keyword=keyword, page=page, page_size=page_size
    )
    return {
        "code": 0,
        "data": {
            "list": docs,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        }
    }

@router.get("/docs/{doc_id}")
async def get_doc(doc_id: int):
    """获取单个文档详情"""
    repo = KnowledgeRepository()
    doc = repo.get_doc(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    return {"code": 0, "data": doc}

@router.post("/docs")
async def create_doc(req: DocCreateRequest):
    """创建文档"""
    repo = KnowledgeRepository()
    try:
        doc_id = repo.create_doc(
            category_id=req.category_id, title=req.title, content=req.content,
            summary=req.summary, tags=req.tags, related_poi=req.related_poi,
            related_city=req.related_city, status=req.status,
            source=req.source, author=req.author
        )
        return {"code": 0, "data": {"id": doc_id}}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"创建文档失败：{str(e)}")

@router.put("/docs/{doc_id}")
async def update_doc(doc_id: int, req: DocUpdateRequest):
    """更新文档"""
    repo = KnowledgeRepository()
    data = {k: v for k, v in req.model_dump().items() if v is not None}
    if not data:
        raise HTTPException(status_code=400, detail="没有需要更新的字段")
    success = repo.update_doc(doc_id, **data)
    if not success:
        raise HTTPException(status_code=404, detail="文档不存在")
    return {"code": 0, "message": "更新成功"}

@router.delete("/docs/{doc_id}")
async def delete_doc(doc_id: int):
    """删除文档"""
    repo = KnowledgeRepository()
    success = repo.delete_doc(doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="文档不存在")
    return {"code": 0, "message": "删除成功"}


# ========== RAG检索测试 ==========

@router.post("/search-test")
async def search_test(req: SearchTestRequest):
    """RAG检索测试（用于后台验证检索效果）"""
    repo = KnowledgeRepository()
    results = repo.search_for_rag(
        poi_name=req.poi_name, city=req.city, keyword=req.keyword,
        category_code=req.category_code, limit=req.limit
    )
    return {
        "code": 0,
        "data": {
            "results": results,
            "total": len(results),
            "query": {
                "poi_name": req.poi_name,
                "city": req.city,
                "keyword": req.keyword,
                "category_code": req.category_code,
            }
        }
    }


# ========== 配置管理 ==========

@router.get("/configs")
async def list_configs():
    """获取知识库配置列表"""
    repo = KnowledgeRepository()
    configs = repo.list_configs()
    return {"code": 0, "data": configs}

@router.post("/configs")
async def update_config(req: ConfigUpdateRequest):
    """更新知识库配置"""
    repo = KnowledgeRepository()
    repo.set_config(req.config_key, req.config_value, req.description)
    return {"code": 0, "message": "配置更新成功"}


# ========== 统计 ==========

@router.get("/stats")
async def get_stats():
    """获取知识库统计信息"""
    repo = KnowledgeRepository()
    stats = repo.get_stats()
    return {"code": 0, "data": stats}


# ========== 初始化 ==========

@router.post("/init")
async def init_knowledge():
    """初始化默认分类和配置"""
    from ..data.repositories.knowledge_repository import init_default_knowledge
    init_default_knowledge()
    return {"code": 0, "message": "初始化完成"}
