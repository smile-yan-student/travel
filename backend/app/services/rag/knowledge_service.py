"""
RAG知识服务（Knowledge Service）。

负责景点人文知识的录入、更新、管理和统计。

功能特性：
- 从结构化数据生成向量化文档（summary、visit_guide、tips等分块类型）
- 从poi_hierarchy导入景点知识到向量库
- 批量导入所有景点知识
- 导入自定义景点知识
- 删除景点的所有知识
- 保存景点数据到本地文件
- 知识库统计（向量库文档数、本地文件数）
- 全局单例

支持的分块类型：
- summary: 景点概述（一句话简介+详细介绍）
- visit_guide: 游玩指南（内部动线、周边推荐、最佳时间、避坑提示）
- tips: 游玩贴士（最佳时间、避坑提示）

使用方式：
    from app.services.rag.knowledge_service import get_knowledge_service

    # 获取全局知识服务单例
    knowledge_service = get_knowledge_service()

    # 检查是否可用
    if knowledge_service.available:
        # 从poi_hierarchy导入景点知识
        success = knowledge_service.import_poi_from_hierarchy("故宫")

        # 批量导入所有景点知识
        stats = knowledge_service.import_all_from_hierarchy()

        # 导入自定义景点知识
        success = knowledge_service.import_custom_poi({
            "name": "我的景点",
            "city": "北京",
            "description": "这是一个测试景点"
        })

        # 删除景点的所有知识
        success = knowledge_service.delete_poi("故宫")

        # 获取知识库统计
        stats = knowledge_service.get_stats()
"""
import json
import os
from typing import Any, Dict, List, Optional

from app.infrastructure.logger import get_logger

from .vector_store import get_vector_store

logger = get_logger("rag.knowledge_service")


class KnowledgeService:
    """
    RAG知识服务。

    负责景点人文知识的录入和管理。
    """

    def __init__(self) -> None:
        """初始化知识服务。"""
        self.vector_store = get_vector_store()
        self._data_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "data",
            "knowledge_base",
            "processed",
        )
        os.makedirs(self._data_dir, exist_ok=True)

    @property
    def available(self) -> bool:
        """
        知识服务是否可用。

        Returns:
            bool: 是否可用
        """
        return self.vector_store.available

    def _generate_documents_from_poi(
        self, poi_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        从景点结构化数据生成向量化文档。

        Args:
            poi_data: 景点数据（来自poi_hierarchy或外部）

        Returns:
            List[Dict[str, Any]]: 文档列表（含document, metadata, id）
        """
        poi_name = poi_data.get("name", "")
        city = poi_data.get("city", "")
        district = poi_data.get("district", "")
        level = poi_data.get("level", "")
        docs = []

        # 1. summary分块：一句话简介+详细介绍
        summary = poi_data.get("description", "")
        if summary:
            docs.append(
                {
                    "document": f"{poi_name}位于{city}{district}，{level}景区。{summary}",
                    "metadata": {
                        "poi_name": poi_name,
                        "city": city,
                        "chunk_type": "summary",
                        "importance": "high",
                        "source": "知识库",
                    },
                    "id": f"{poi_name}_summary",
                }
            )

        # 2. 内部动线作为visit_guide分块
        inner_route = poi_data.get("inner_route", [])
        if inner_route:
            route_text = f"{poi_name}推荐游览路线："
            for stop in inner_route:
                route_text += f"\n{stop.get('order', '')}. {stop.get('name', '')}：{stop.get('description', '')}（约{stop.get('duration_min', 30)}分钟）"
                if stop.get("highlight"):
                    route_text += f"，看点：{stop['highlight']}"
            docs.append(
                {
                    "document": route_text,
                    "metadata": {
                        "poi_name": poi_name,
                        "city": city,
                        "chunk_type": "visit_guide",
                        "importance": "high",
                        "source": "知识库",
                    },
                    "id": f"{poi_name}_inner_route",
                }
            )

        # 3. 周边附属作为visit_guide分块
        nearby = poi_data.get("nearby_attractions", [])
        if nearby:
            nearby_text = f"{poi_name}周边推荐："
            for n in nearby:
                nearby_text += f"\n- {n.get('name', '')}（{n.get('category', '')}，距{n.get('distance_m', 0)}米，推荐{n.get('recommended_slot', '')}）：{n.get('description', '')}"
            docs.append(
                {
                    "document": nearby_text,
                    "metadata": {
                        "poi_name": poi_name,
                        "city": city,
                        "chunk_type": "visit_guide",
                        "importance": "medium",
                        "source": "知识库",
                    },
                    "id": f"{poi_name}_nearby",
                }
            )

        # 4. 最佳时间和避坑提示
        best_time = poi_data.get("best_time", "")
        avoid_tips = poi_data.get("avoid_tips", [])
        if best_time or avoid_tips:
            tips_text = f"{poi_name}游玩贴士："
            if best_time:
                tips_text += f"\n最佳游玩时间：{best_time}"
            if avoid_tips:
                tips_text += "\n避坑提示："
                for tip in avoid_tips:
                    tips_text += f"\n- {tip}"
            docs.append(
                {
                    "document": tips_text,
                    "metadata": {
                        "poi_name": poi_name,
                        "city": city,
                        "chunk_type": "visit_guide",
                        "importance": "high",
                        "source": "知识库",
                    },
                    "id": f"{poi_name}_tips",
                }
            )

        return docs

    def import_poi_from_hierarchy(self, poi_name: str) -> bool:
        """
        从poi_hierarchy导入景点知识到向量库。

        Args:
            poi_name: 景点名称

        Returns:
            bool: 是否成功
        """
        if not self.available:
            return False

        # 从数据库获取POI层级数据
        try:
            from ...data.repositories.poi_hierarchy_repository import (
                PoiHierarchyRepository,
            )

            poi_dict = PoiHierarchyRepository.get_main_poi_by_name(poi_name)
        except Exception:
            poi_dict = None

        if not poi_dict:
            logger.warning(f"未找到景点: {poi_name}")
            return False

        docs = self._generate_documents_from_poi(poi_dict)

        if not docs:
            return False

        # 保存到本地文件
        self._save_poi_data(poi_name, poi_dict)

        # 录入向量库
        documents = [d["document"] for d in docs]
        metadatas = [d["metadata"] for d in docs]
        ids = [d["id"] for d in docs]

        return self.vector_store.add_documents(documents, metadatas, ids)

    def import_all_from_hierarchy(self) -> Dict[str, Any]:
        """
        从poi_hierarchy批量导入所有景点知识。

        Returns:
            Dict[str, Any]: 导入统计
        """
        if not self.available:
            return {"success": False, "message": "RAG不可用"}

        # 从数据库获取所有主POI
        try:
            from ...data.repositories.poi_hierarchy_repository import (
                PoiHierarchyRepository,
            )

            repo = PoiHierarchyRepository()
            all_main_pois, total = repo.list_main_pois(page_size=1000)
            poi_names = [poi["name"] for poi in all_main_pois]
        except Exception:
            poi_names = []
            total = 0

        success_count = 0
        failed = []
        for poi_name in poi_names:
            try:
                if self.import_poi_from_hierarchy(poi_name):
                    success_count += 1
                else:
                    failed.append(poi_name)
            except Exception as e:
                logger.error(f"导入{poi_name}失败: {e}")
                failed.append(poi_name)

        return {
            "success": True,
            "total": total,
            "success_count": success_count,
            "failed": failed,
            "document_count": self.vector_store.count(),
        }

    def import_custom_poi(self, poi_data: Dict[str, Any]) -> bool:
        """
        导入自定义景点知识。

        Args:
            poi_data: 景点数据（需包含name字段）

        Returns:
            bool: 是否成功
        """
        if not self.available:
            return False

        poi_name = poi_data.get("name", "")
        if not poi_name:
            return False

        docs = self._generate_documents_from_poi(poi_data)
        if not docs:
            return False

        self._save_poi_data(poi_name, poi_data)

        documents = [d["document"] for d in docs]
        metadatas = [d["metadata"] for d in docs]
        ids = [d["id"] for d in docs]

        return self.vector_store.add_documents(documents, metadatas, ids)

    def delete_poi(self, poi_name: str) -> bool:
        """
        删除景点的所有知识。

        Args:
            poi_name: 景点名称

        Returns:
            bool: 是否成功
        """
        if not self.available:
            return False
        # 删除该景点的所有文档（按id前缀）
        ids_to_delete = [
            f"{poi_name}_summary",
            f"{poi_name}_inner_route",
            f"{poi_name}_nearby",
            f"{poi_name}_tips",
        ]
        return self.vector_store.delete(ids_to_delete)

    def _save_poi_data(self, poi_name: str, poi_data: Dict[str, Any]) -> None:
        """
        保存景点数据到本地文件。

        Args:
            poi_name: 景点名称
            poi_data: 景点数据
        """
        try:
            file_path = os.path.join(self._data_dir, f"{poi_name}.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(poi_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存{poi_name}数据失败: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """
        获取知识库统计。

        Returns:
            Dict[str, Any]: 统计信息
        """
        stats = self.vector_store.get_stats()
        # 统计本地文件
        try:
            local_files = [
                f for f in os.listdir(self._data_dir) if f.endswith(".json")
            ]
            stats["local_poi_count"] = len(local_files)
        except Exception:
            stats["local_poi_count"] = 0
        return stats


# 全局单例
_knowledge_service: Optional[KnowledgeService] = None


def get_knowledge_service() -> KnowledgeService:
    """
    获取全局知识服务单例。

    Returns:
        KnowledgeService: 全局知识服务单例
    """
    global _knowledge_service
    if _knowledge_service is None:
        _knowledge_service = KnowledgeService()
    return _knowledge_service
