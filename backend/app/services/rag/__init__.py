"""
RAG知识库服务模块
- VectorStore: 向量存储（Chroma + bge-small-zh）
- Retriever: 检索器（混合检索+按景点/类型过滤）
- RAGGenerator: 内容生成器（AI讲解+知识问答+人文短句）
- KnowledgeService: 知识服务（数据录入+管理+统计）
"""
from .vector_store import VectorStore, get_vector_store
from .retriever import Retriever, get_retriever
from .generator import RAGGenerator, get_rag_generator
from .knowledge_service import KnowledgeService, get_knowledge_service

__all__ = [
    "VectorStore",
    "get_vector_store",
    "Retriever",
    "get_retriever",
    "RAGGenerator",
    "get_rag_generator",
    "KnowledgeService",
    "get_knowledge_service",
]
