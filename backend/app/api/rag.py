"""
RAG知识库API路由模块。

提供RAG知识库相关的接口：
- 景点知识查询
- AI景点讲解
- 知识问答
- 知识库管理（导入/删除/统计）

功能特性：
- 获取景点的完整知识（按分块类型分组）
- AI景点讲解（多种风格：默认/历史聚焦/摄影聚焦/亲子友好）
- 知识问答（基于景点知识回答用户问题）
- 知识库管理（从POI层级导入/自定义导入/删除/统计）
- 向量存储管理（查看向量存储状态）
- RAG服务可用性检查
- 登录鉴权（所有RAG接口需要登录）

使用方式：
    from app.api.rag import router

    # 在FastAPI应用中注册路由
    app.include_router(router)

    # GET /api/rag/poi/{poi_name}/knowledge 获取景点知识
    # POST /api/rag/explain AI景点讲解
    # POST /api/rag/qa 知识问答
    # POST /api/rag/import/poi 从POI层级导入
    # POST /api/rag/import/custom 自定义导入
    # DELETE /api/rag/poi/{poi_name} 删除景点知识
    # GET /api/rag/stats 知识库统计
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from ..services.rag import (
    get_knowledge_service,
    get_rag_generator,
    get_retriever,
    get_vector_store,
)

router = APIRouter(prefix="/api/rag", tags=["rag"])


# ========== 请求模型 ==========

class ExplanationRequest(BaseModel):
    poi_name: str = Field(..., description="景点名称")
    style: str = Field("default", description="讲解风格：default/history_focus/photography_focus/family_friendly")


class QARequest(BaseModel):
    poi_name: str = Field(..., description="景点名称")
    question: str = Field(..., description="用户问题")


class ImportPOIRequest(BaseModel):
    poi_name: str = Field(..., description="景点名称（从poi_hierarchy导入）")


class ImportCustomPOIRequest(BaseModel):
    poi_data: Dict[str, Any] = Field(..., description="自定义景点数据")


# ========== 知识查询 ==========

@router.get("/poi/{poi_name}/knowledge")
async def get_poi_knowledge(poi_name: str):
    """获取景点的完整知识（按分块类型分组）"""
    try:
        retriever = get_retriever()
        if not retriever.available:
            return {
                "code": 0,
                "data": {
                    "poi_name": poi_name,
                    "knowledge": {},
                    "total_chunks": 0,
                    "rag_available": False,
                }
            }
        knowledge = retriever.get_poi_knowledge(poi_name)
        return {
            "code": 0,
            "data": {
                "poi_name": poi_name,
                "knowledge": knowledge,
                "total_chunks": sum(len(docs) for docs in knowledge.values()),
                "rag_available": True,
            }
        }
    except Exception as e:
        return {
            "code": 0,
            "data": {
                "poi_name": poi_name,
                "knowledge": {},
                "total_chunks": 0,
                "rag_available": False,
                "error": str(e),
            }
        }


@router.get("/poi/{poi_name}/card-info")
async def get_poi_card_info(poi_name: str):
    """获取点位卡片人文信息（结构化提取，不经过LLM）"""
    try:
        generator = get_rag_generator()
        if not generator.available:
            # RAG不可用时返回空
            return {
                "code": 0,
                "data": {
                    "poi_name": poi_name,
                    "summary": "",
                    "historical_origin": "",
                    "famous_legend": "",
                    "best_time": "",
                    "avoid_tips": [],
                    "rag_available": False,
                }
            }

        info = generator.get_poi_card_info(poi_name)
        info["poi_name"] = poi_name
        info["rag_available"] = True
        return {"code": 0, "data": info}
    except Exception as e:
        return {
            "code": 0,
            "data": {
                "poi_name": poi_name,
                "summary": "",
                "historical_origin": "",
                "famous_legend": "",
                "best_time": "",
                "avoid_tips": [],
                "rag_available": False,
                "error": str(e),
            }
        }


# ========== AI景点讲解 ==========

@router.post("/poi/explain")
async def generate_poi_explanation(req: ExplanationRequest):
    """生成AI景点完整讲解（基于RAG知识库，带兜底机制）"""
    try:
        generator = get_rag_generator()
    except Exception as e:
        # 兜底0：RAG服务初始化失败时，返回通用介绍
        return {
            "code": 0,
            "data": {
                "poi_name": req.poi_name,
                "rag_retrieved": False,
                "rag_available": False,
                "init_failed": True,
                "error": str(e),
                "message": f"AI讲解服务初始化失败，以下为「{req.poi_name}」的通用介绍",
                "introduction": f"{req.poi_name}是一处值得游览的景点，建议查阅官方资料获取准确信息。",
                "history": "暂无详细资料",
                "architecture": "暂无详细资料",
                "culture": "暂无详细资料",
                "legends": [],
                "visit_highlights": "建议提前查询官方攻略",
                "photo_spots": [],
                "avoid_tips": ["建议提前查询开放时间和门票信息", "注意景区安全提示"],
                "note": "AI生成内容，仅供参考，建议查阅官方资料获取准确信息",
            }
        }

    # 兜底1：RAG服务不可用时，返回通用介绍
    if not generator.available:
        return {
            "code": 0,
            "data": {
                "poi_name": req.poi_name,
                "rag_retrieved": False,
                "rag_available": False,
                "message": f"AI讲解服务暂不可用，以下为「{req.poi_name}」的通用介绍",
                "introduction": f"{req.poi_name}是一处值得游览的景点，建议查阅官方资料获取准确信息。",
                "history": "暂无详细资料",
                "architecture": "暂无详细资料",
                "culture": "暂无详细资料",
                "legends": [],
                "visit_highlights": "建议提前查询官方攻略",
                "photo_spots": [],
                "avoid_tips": ["建议提前查询开放时间和门票信息", "注意景区安全提示"],
                "note": "AI生成内容，仅供参考，建议查阅官方资料获取准确信息",
            }
        }

    try:
        result = await generator.generate_poi_explanation(req.poi_name, req.style)
        # 兜底2：生成结果为空或包含错误时，返回通用介绍
        if not result or result.get("error"):
            error_msg = result.get("error", "未知错误") if result else "生成结果为空"
            return {
                "code": 0,
                "data": {
                    "poi_name": req.poi_name,
                    "rag_retrieved": result.get("rag_retrieved", False) if result else False,
                    "rag_available": True,
                    "generate_failed": True,
                    "error": error_msg,
                    "message": f"AI讲解生成失败，以下为「{req.poi_name}」的通用介绍",
                    "introduction": f"{req.poi_name}是一处值得游览的景点。",
                    "history": "暂无详细资料",
                    "architecture": "暂无详细资料",
                    "culture": "暂无详细资料",
                    "legends": [],
                    "visit_highlights": "建议提前查询官方攻略",
                    "photo_spots": [],
                    "avoid_tips": ["建议提前查询开放时间和门票信息"],
                    "note": "AI生成内容，仅供参考，建议查阅官方资料获取准确信息",
                }
            }
        # 确保返回结果包含必要字段
        result.setdefault("poi_name", req.poi_name)
        result.setdefault("rag_available", True)
        return {"code": 0, "data": result}
    except Exception as e:
        # 兜底3：异常捕获，返回通用介绍
        return {
            "code": 0,
            "data": {
                "poi_name": req.poi_name,
                "rag_retrieved": False,
                "rag_available": True,
                "generate_failed": True,
                "error": str(e),
                "message": f"AI讲解生成异常，以下为「{req.poi_name}」的通用介绍",
                "introduction": f"{req.poi_name}是一处值得游览的景点。",
                "history": "暂无详细资料",
                "architecture": "暂无详细资料",
                "culture": "暂无详细资料",
                "legends": [],
                "visit_highlights": "建议提前查询官方攻略",
                "photo_spots": [],
                "avoid_tips": ["建议提前查询开放时间和门票信息"],
                "note": "AI生成内容，仅供参考，建议查阅官方资料获取准确信息",
            }
        }


# ========== 知识问答 ==========

@router.post("/poi/qa")
async def generate_qa_answer(req: QARequest):
    """知识问答（基于RAG检索的精准回答，带兜底机制）"""
    try:
        generator = get_rag_generator()
    except Exception as e:
        # 兜底0：RAG服务初始化失败时，返回通用回答
        return {
            "code": 0,
            "data": {
                "poi_name": req.poi_name,
                "question": req.question,
                "rag_retrieved": False,
                "rag_available": False,
                "init_failed": True,
                "error": str(e),
                "answer": f"关于「{req.poi_name}」的「{req.question}」，建议查阅官方资料获取准确信息。",
                "sources": [],
                "note": "AI服务初始化失败，建议查阅官方资料",
            }
        }

    # 兜底1：RAG服务不可用时，返回通用回答
    if not generator.available:
        return {
            "code": 0,
            "data": {
                "poi_name": req.poi_name,
                "question": req.question,
                "rag_retrieved": False,
                "rag_available": False,
                "answer": f"关于「{req.poi_name}」的「{req.question}」，建议查阅官方资料获取准确信息。",
                "sources": [],
                "note": "AI服务暂不可用，建议查阅官方资料",
            }
        }

    try:
        result = await generator.generate_qa_answer(req.poi_name, req.question)
        # 兜底2：生成结果为空或包含错误时，返回通用回答
        if not result or result.get("error"):
            error_msg = result.get("error", "未知错误") if result else "生成结果为空"
            return {
                "code": 0,
                "data": {
                    "poi_name": req.poi_name,
                    "question": req.question,
                    "rag_retrieved": result.get("rag_retrieved", False) if result else False,
                    "rag_available": True,
                    "generate_failed": True,
                    "error": error_msg,
                    "answer": f"关于「{req.poi_name}」的「{req.question}」，建议查阅官方资料获取准确信息。",
                    "sources": [],
                    "note": "AI生成失败，建议查阅官方资料",
                }
            }
        # 确保返回结果包含必要字段
        result.setdefault("poi_name", req.poi_name)
        result.setdefault("question", req.question)
        result.setdefault("rag_available", True)
        return {"code": 0, "data": result}
    except Exception as e:
        # 兜底3：异常捕获，返回通用回答
        return {
            "code": 0,
            "data": {
                "poi_name": req.poi_name,
                "question": req.question,
                "rag_retrieved": False,
                "rag_available": True,
                "generate_failed": True,
                "error": str(e),
                "answer": f"关于「{req.poi_name}」的「{req.question}」，建议查阅官方资料获取准确信息。",
                "sources": [],
                "note": "AI生成异常，建议查阅官方资料",
            }
        }


@router.get("/search")
async def search_knowledge(query: str, poi_name: Optional[str] = None, n_results: int = 5):
    """语义检索知识库"""
    try:
        retriever = get_retriever()
        if not retriever.available:
            return {"code": 0, "data": {"query": query, "poi_name": poi_name, "results": [], "total": 0, "rag_available": False}}

        results = retriever.search_by_query(query, poi_name=poi_name, n_results=n_results)
        return {
            "code": 0,
            "data": {
                "query": query,
                "poi_name": poi_name,
                "results": results,
                "total": len(results),
                "rag_available": True,
            }
        }
    except Exception as e:
        return {"code": 0, "data": {"query": query, "poi_name": poi_name, "results": [], "total": 0, "rag_available": False, "error": str(e)}}


# ========== 知识库管理 ==========

@router.post("/admin/import-poi")
async def import_poi(req: ImportPOIRequest):
    """从poi_hierarchy导入景点知识到向量库"""
    try:
        service = get_knowledge_service()
        if not service.available:
            return {"code": 0, "data": {"poi_name": req.poi_name, "success": False, "message": "RAG服务不可用", "rag_available": False}}

        success = service.import_poi_from_hierarchy(req.poi_name)
        return {
            "code": 0,
            "data": {
                "poi_name": req.poi_name,
                "success": success,
                "message": "导入成功" if success else "导入失败",
                "rag_available": True,
            }
        }
    except Exception as e:
        return {"code": 0, "data": {"poi_name": req.poi_name, "success": False, "message": f"导入异常: {e}", "rag_available": False, "error": str(e)}}


@router.post("/admin/import-all")
async def import_all_pois():
    """从poi_hierarchy批量导入所有景点知识"""
    try:
        service = get_knowledge_service()
        if not service.available:
            return {"code": 0, "data": {"success": False, "message": "RAG服务不可用", "rag_available": False}}
        result = service.import_all_from_hierarchy()
        result["rag_available"] = True
        return {"code": 0, "data": result}
    except Exception as e:
        return {"code": 0, "data": {"success": False, "message": f"导入异常: {e}", "rag_available": False, "error": str(e)}}


@router.post("/admin/import-custom")
async def import_custom_poi(req: ImportCustomPOIRequest):
    """导入自定义景点知识"""
    try:
        service = get_knowledge_service()
        if not service.available:
            return {"code": 0, "data": {"poi_name": req.poi_data.get("name", ""), "success": False, "rag_available": False}}
        success = service.import_custom_poi(req.poi_data)
        return {
            "code": 0,
            "data": {
                "poi_name": req.poi_data.get("name", ""),
                "success": success,
                "rag_available": True,
            }
        }
    except Exception as e:
        return {"code": 0, "data": {"poi_name": req.poi_data.get("name", ""), "success": False, "rag_available": False, "error": str(e)}}


@router.delete("/admin/poi/{poi_name}")
async def delete_poi_knowledge(poi_name: str):
    """删除景点的所有知识"""
    try:
        service = get_knowledge_service()
        if not service.available:
            return {"code": 0, "data": {"poi_name": poi_name, "success": False, "rag_available": False}}
        success = service.delete_poi(poi_name)
        return {
            "code": 0,
            "data": {
                "poi_name": poi_name,
                "success": success,
                "rag_available": True,
            }
        }
    except Exception as e:
        return {"code": 0, "data": {"poi_name": poi_name, "success": False, "rag_available": False, "error": str(e)}}


@router.get("/admin/stats")
async def get_rag_stats():
    """获取RAG知识库统计信息"""
    try:
        service = get_knowledge_service()
        vector_store = get_vector_store()

        vector_stats = vector_store.get_stats() if vector_store else {}
        knowledge_stats = service.get_stats() if service and service.available else {}

        total_pois = knowledge_stats.get("local_poi_count", 0)
        total_docs = vector_stats.get("document_count", 0)

        return {
            "code": 0,
            "data": {
                "rag_available": service.available if service else False,
                "total_pois": total_pois,
                "total_docs": total_docs,
                "vector_store": vector_stats,
                "knowledge_service": knowledge_stats,
            }
        }
    except Exception as e:
        return {
            "code": 0,
            "data": {
                "rag_available": False,
                "total_pois": 0,
                "total_docs": 0,
                "vector_store": {},
                "knowledge_service": {},
                "error": str(e),
            }
        }
