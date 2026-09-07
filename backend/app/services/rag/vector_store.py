"""
RAG向量存储（Vector Store）。

基于Chroma的本地向量存储，支持景点人文知识的向量化存储和检索。

功能特性：
- 使用Chroma作为本地向量数据库
- 使用bge-small-zh作为Embedding模型（中文优化）
- 支持景点人文知识的存储、检索、更新
- 离线模式（强制使用本地缓存的模型，避免网络请求超时）
- 模型加载超时保护（120秒超时，避免网络问题阻塞后端服务）
- RAG服务可通过环境变量控制（RAG_ENABLED=true/false）
- 全局单例

使用方式：
    from app.services.rag.vector_store import get_vector_store

    # 获取全局向量存储单例
    vector_store = get_vector_store()

    # 检查是否可用
    if vector_store.available:
        # 添加文档
        vector_store.add_documents(
            documents=["西湖是中国著名的风景名胜区"],
            metadatas=[{"poi_id": "1", "poi_name": "西湖"}],
            ids=["doc_001"]
        )

        # 语义检索
        results = vector_store.search("杭州有什么好玩的", n_results=5)

        # 删除文档
        vector_store.delete(["doc_001"])

        # 获取文档总数
        count = vector_store.count()

        # 清空集合
        vector_store.clear()

        # 获取统计信息
        stats = vector_store.get_stats()
"""
import os
import threading
from typing import Any, Dict, List, Optional

from app.infrastructure.logger import get_logger

logger = get_logger("rag.vector_store")

# 设置离线模式，强制使用本地缓存的模型，避免网络请求超时
# 必须在导入sentence_transformers之前设置
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

try:
    import chromadb
    from chromadb.config import Settings

    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer

    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False


class VectorStore:
    """
    RAG向量存储。

    - 使用Chroma作为本地向量数据库
    - 使用bge-small-zh作为Embedding模型（中文优化）
    - 支持景点人文知识的存储、检索、更新
    """

    def __init__(
        self, persist_dir: str = "", collection_name: str = "poi_knowledge"
    ) -> None:
        """
        初始化向量存储。

        Args:
            persist_dir: 持久化目录（默认为 data/knowledge_base/chroma）
            collection_name: 集合名称（默认为 poi_knowledge）
        """
        self.persist_dir = persist_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "data",
            "knowledge_base",
            "chroma",
        )
        self.collection_name = collection_name
        self._client = None
        self._collection = None
        self._embedding_model = None
        self._available = False

        # 初始化
        self._init()

    def _init(self) -> None:
        """初始化向量存储和Embedding模型。"""
        # 检查环境变量，控制是否启用RAG服务（默认禁用，避免网络问题阻塞后端服务）
        rag_enabled = os.environ.get("RAG_ENABLED", "false").lower() == "true"
        if not rag_enabled:
            logger.warning("RAG服务已禁用（设置环境变量 RAG_ENABLED=true 启用）")
            return

        if not CHROMA_AVAILABLE:
            logger.warning("chromadb未安装，RAG功能不可用")
            return
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            logger.warning("sentence-transformers未安装，RAG功能不可用")
            return

        try:
            os.makedirs(self.persist_dir, exist_ok=True)
            self._client = chromadb.PersistentClient(path=self.persist_dir)
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name, metadata={"hnsw:space": "cosine"}
            )

            # 检查模型是否已经缓存到本地，避免网络下载超时
            model_name = "BAAI/bge-small-zh-v1.5"
            cache_dir = os.environ.get(
                "HF_HOME", os.path.expanduser("~/.cache/huggingface")
            )
            model_cache_path = os.path.join(
                cache_dir, "hub", "models--BAAI--bge-small-zh-v1.5"
            )

            if not os.path.exists(model_cache_path):
                logger.warning(
                    f"模型未缓存到本地（{model_cache_path}），跳过加载以避免网络超时"
                )
                logger.warning(
                    "如需启用RAG，请先手动下载模型：python -c \"from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-zh-v1.5')\""
                )
                self._available = False
                return

            # 加载中文Embedding模型（轻量版）
            # 使用线程超时机制，避免网络问题阻塞后端服务
            # 注意：离线模式环境变量已在文件顶部设置
            result: Dict[str, Any] = {}

            def load_model() -> None:
                """加载Embedding模型（在线程中执行，支持超时）。"""
                try:
                    result["model"] = SentenceTransformer(model_name)
                    result["success"] = True
                except Exception as e:
                    result["error"] = e
                    result["success"] = False

            load_thread = threading.Thread(target=load_model, daemon=True)
            load_thread.start()
            load_thread.join(timeout=120)  # 120秒超时（模型首次加载可能需要较长时间）

            if load_thread.is_alive():
                logger.warning("模型加载超时（120秒），RAG功能不可用")
                self._available = False
                return

            if not result.get("success", False):
                logger.warning(f"模型加载失败: {result.get('error', '未知错误')}")
                self._available = False
                return

            self._embedding_model = result["model"]
            self._available = True
            logger.info(
                f"初始化成功，集合: {self.collection_name}, 文档数: {self.count()}"
            )
        except Exception as e:
            logger.error(f"初始化失败: {e}")
            self._available = False

    @property
    def available(self) -> bool:
        """
        RAG是否可用。

        Returns:
            bool: 是否可用
        """
        return self._available

    def _embed(self, texts: List[str]) -> List[List[float]]:
        """
        文本向量化。

        Args:
            texts: 文本列表

        Returns:
            List[List[float]]: 向量列表
        """
        if not self._available:
            return []
        return self._embedding_model.encode(texts, normalize_embeddings=True).tolist()

    def add_documents(
        self,
        documents: List[str],
        metadatas: List[Dict[str, Any]],
        ids: List[str],
    ) -> bool:
        """
        添加文档到向量库。

        Args:
            documents: 文档文本列表
            metadatas: 元数据列表（poi_id, poi_name, chunk_type等）
            ids: 文档ID列表

        Returns:
            bool: 是否成功
        """
        if not self._available:
            return False
        try:
            embeddings = self._embed(documents)
            self._collection.upsert(
                documents=documents,
                metadatas=metadatas,
                ids=ids,
                embeddings=embeddings,
            )
            return True
        except Exception as e:
            logger.error(f"添加文档失败: {e}")
            return False

    def search(
        self,
        query: str,
        n_results: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        语义检索。

        Args:
            query: 查询文本
            n_results: 返回结果数量
            filter_metadata: 元数据过滤条件

        Returns:
            List[Dict[str, Any]]: 检索结果列表（含document, metadata, distance, score）
        """
        if not self._available:
            return []
        try:
            query_embedding = self._embed([query])[0]
            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=filter_metadata,
            )
            # 格式化结果
            formatted = []
            for i in range(len(results["documents"][0])):
                formatted.append(
                    {
                        "document": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "id": results["ids"][0][i],
                        "distance": (
                            results["distances"][0][i]
                            if results.get("distances")
                            else 0
                        ),
                        "score": 1
                        - (
                            results["distances"][0][i]
                            if results.get("distances")
                            else 0
                        ),
                    }
                )
            return formatted
        except Exception as e:
            logger.error(f"检索失败: {e}")
            return []

    def delete(self, ids: List[str]) -> bool:
        """
        删除文档。

        Args:
            ids: 文档ID列表

        Returns:
            bool: 是否成功
        """
        if not self._available:
            return False
        try:
            self._collection.delete(ids=ids)
            return True
        except Exception as e:
            logger.error(f"删除失败: {e}")
            return False

    def count(self) -> int:
        """
        获取文档总数。

        Returns:
            int: 文档总数
        """
        if not self._available:
            return 0
        try:
            return self._collection.count()
        except Exception:
            return 0

    def clear(self) -> bool:
        """
        清空集合。

        Returns:
            bool: 是否成功
        """
        if not self._available:
            return False
        try:
            self._client.delete_collection(self.collection_name)
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name, metadata={"hnsw:space": "cosine"}
            )
            return True
        except Exception as e:
            logger.error(f"清空失败: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        获取向量库统计信息。

        Returns:
            Dict[str, Any]: 统计信息
        """
        return {
            "available": self._available,
            "collection": self.collection_name,
            "document_count": self.count(),
            "persist_dir": self.persist_dir,
            "embedding_model": (
                "BAAI/bge-small-zh-v1.5" if self._available else "未加载"
            ),
        }


# 全局单例
_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """
    获取全局向量存储单例。

    Returns:
        VectorStore: 全局向量存储单例
    """
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
