"""
知识库数据访问层（Repository）。

提供知识库分类、知识文档的CRUD操作，以及RAG检索接口。

功能特性：
- 分类管理（列表、获取、创建、更新）
- 文档管理（列表、获取、创建、更新、删除）
- RAG检索（按POI、城市、关键词、分类检索已发布文档）
- 配置管理（获取、设置、列表）
- 统计信息（文档总数、状态分布、活跃分类数）
- 默认数据初始化

使用方式：
    from app.data.repositories.knowledge_repository import KnowledgeRepository

    # 获取分类列表
    categories = KnowledgeRepository.list_categories()

    # 获取文档列表（分页）
    docs, total = KnowledgeRepository.list_docs(
        category_id=1, status="published", page=1, page_size=20
    )

    # RAG检索
    results = KnowledgeRepository.search_for_rag(
        poi_name="西湖", city="杭州", keyword="人文", limit=5
    )

    # 获取配置
    rag_enabled = KnowledgeRepository.get_config("rag_enabled", "true")

    # 获取统计
    stats = KnowledgeRepository.get_stats()
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..database import read_connection, transaction


class KnowledgeRepository:
    """
    知识库数据访问类。

    提供知识库分类、文档的CRUD操作，以及RAG检索接口。

    Example:
        >>> categories = KnowledgeRepository.list_categories()
        >>> print(len(categories))
        4
    """

    # ========== 分类管理 ==========

    @staticmethod
    def list_categories(only_active: bool = True) -> List[Dict[str, Any]]:
        """
        获取知识库分类列表。

        Args:
            only_active: 是否只返回活跃的分类

        Returns:
            List[Dict[str, Any]]: 分类列表，按 sort_order 和 id 排序

        Example:
            >>> categories = KnowledgeRepository.list_categories()
            >>> print(categories[0]["name"])
            景点人文
        """
        with read_connection() as conn:
            with conn.cursor() as cur:
                sql = "SELECT * FROM knowledge_category"
                if only_active:
                    sql += " WHERE is_active = 1"
                sql += " ORDER BY sort_order ASC, id ASC"
                cur.execute(sql)
                return cur.fetchall()

    @staticmethod
    def get_category(category_id: int) -> Optional[Dict[str, Any]]:
        """
        获取单个分类。

        Args:
            category_id: 分类ID

        Returns:
            Optional[Dict[str, Any]]: 分类信息，不存在返回 None

        Example:
            >>> category = KnowledgeRepository.get_category(1)
            >>> print(category["name"])
            景点人文
        """
        with read_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM knowledge_category WHERE id = %s", (category_id,)
                )
                return cur.fetchone()

    @staticmethod
    def create_category(
        name: str, code: str, description: str = "", sort_order: int = 0
    ) -> int:
        """
        创建分类。

        Args:
            name: 分类名称
            code: 分类编码（唯一）
            description: 分类描述
            sort_order: 排序顺序

        Returns:
            int: 新建分类的ID

        Example:
            >>> category_id = KnowledgeRepository.create_category(
            ...     "新分类", "new_category", "这是一个新分类", 10
            ... )
            >>> print(category_id)
            5
        """
        with transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO knowledge_category (name, code, description, sort_order) VALUES (%s, %s, %s, %s)",
                    (name, code, description, sort_order),
                )
                return cur.lastrowid

    @staticmethod
    def update_category(category_id: int, **kwargs: Any) -> bool:
        """
        更新分类。

        Args:
            category_id: 分类ID
            **kwargs: 要更新的字段（name, code, description, sort_order, is_active）

        Returns:
            bool: 是否更新成功

        Example:
            >>> success = KnowledgeRepository.update_category(
            ...     1, name="新名称", description="新描述"
            ... )
            >>> print(success)
            True
        """
        if not kwargs:
            return False
        with transaction() as conn:
            with conn.cursor() as cur:
                fields = ", ".join([f"{k} = %s" for k in kwargs.keys()])
                values = list(kwargs.values()) + [category_id]
                cur.execute(
                    f"UPDATE knowledge_category SET {fields} WHERE id = %s", values
                )
                return cur.rowcount > 0

    # ========== 文档管理 ==========

    @staticmethod
    def list_docs(
        category_id: Optional[int] = None,
        status: Optional[str] = None,
        related_poi: Optional[str] = None,
        related_city: Optional[str] = None,
        keyword: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        获取知识文档列表（分页）。

        支持按分类、状态、关联POI、关联城市、关键词筛选。
        排序优先级：置顶 > 权重 > 更新时间。

        Args:
            category_id: 分类ID（可选）
            status: 状态（draft/published/offline，可选）
            related_poi: 关联POI名称（模糊匹配，可选）
            related_city: 关联城市（模糊匹配，可选）
            keyword: 关键词（标题/内容/标签模糊匹配，可选）
            page: 页码（从1开始）
            page_size: 每页大小

        Returns:
            Tuple[List[Dict[str, Any]], int]: (文档列表, 总数)

        Example:
            >>> docs, total = KnowledgeRepository.list_docs(
            ...     category_id=1, status="published", page=1, page_size=10
            ... )
            >>> print(total)
            50
        """
        with read_connection() as conn:
            with conn.cursor() as cur:
                conditions = []
                params = []
                if category_id:
                    conditions.append("d.category_id = %s")
                    params.append(category_id)
                if status:
                    conditions.append("d.status = %s")
                    params.append(status)
                if related_poi:
                    conditions.append("d.related_poi LIKE %s")
                    params.append(f"%{related_poi}%")
                if related_city:
                    conditions.append("d.related_city LIKE %s")
                    params.append(f"%{related_city}%")
                if keyword:
                    conditions.append(
                        "(d.title LIKE %s OR d.content LIKE %s OR d.tags LIKE %s)"
                    )
                    params.extend(
                        [f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"]
                    )

                where = " AND ".join(conditions) if conditions else "1=1"

                # 查询总数
                cur.execute(
                    f"SELECT COUNT(*) as total FROM knowledge_doc d WHERE {where}",
                    params,
                )
                total = cur.fetchone()["total"]

                # 查询分页数据
                offset = (page - 1) * page_size
                cur.execute(
                    f"""SELECT d.*, c.name as category_name, c.code as category_code
                        FROM knowledge_doc d
                        LEFT JOIN knowledge_category c ON d.category_id = c.id
                        WHERE {where}
                        ORDER BY d.is_pinned DESC, d.weight DESC, d.updated_at DESC
                        LIMIT %s OFFSET %s""",
                    params + [page_size, offset],
                )
                docs = cur.fetchall()
                return docs, total

    @staticmethod
    def get_doc(doc_id: int) -> Optional[Dict[str, Any]]:
        """
        获取单个文档。

        Args:
            doc_id: 文档ID

        Returns:
            Optional[Dict[str, Any]]: 文档信息（含分类名称和编码），不存在返回 None

        Example:
            >>> doc = KnowledgeRepository.get_doc(1)
            >>> print(doc["title"])
            西湖人文介绍
        """
        with read_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT d.*, c.name as category_name, c.code as category_code
                       FROM knowledge_doc d
                       LEFT JOIN knowledge_category c ON d.category_id = c.id
                       WHERE d.id = %s""",
                    (doc_id,),
                )
                return cur.fetchone()

    @staticmethod
    def create_doc(
        category_id: int,
        title: str,
        content: str,
        summary: str = "",
        tags: str = "",
        related_poi: str = "",
        related_city: str = "",
        status: str = "draft",
        source: str = "manual",
        author: str = "",
    ) -> int:
        """
        创建文档。

        Args:
            category_id: 分类ID
            title: 文档标题
            content: 文档内容（富文本/Markdown）
            summary: 内容摘要
            tags: 标签（逗号分隔）
            related_poi: 关联POI名称（逗号分隔）
            related_city: 关联城市
            status: 状态（draft/published/offline）
            source: 来源（manual/import/ai_generated）
            author: 作者

        Returns:
            int: 新建文档的ID

        Example:
            >>> doc_id = KnowledgeRepository.create_doc(
            ...     category_id=1,
            ...     title="西湖人文介绍",
            ...     content="西湖是中国著名的风景名胜区...",
            ...     related_poi="西湖",
            ...     related_city="杭州",
            ...     status="published"
            ... )
            >>> print(doc_id)
            1
        """
        with transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO knowledge_doc
                       (category_id, title, content, summary, tags, related_poi, related_city, status, source, author)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        category_id,
                        title,
                        content,
                        summary,
                        tags,
                        related_poi,
                        related_city,
                        status,
                        source,
                        author,
                    ),
                )
                return cur.lastrowid

    @staticmethod
    def update_doc(doc_id: int, **kwargs: Any) -> bool:
        """
        更新文档。

        Args:
            doc_id: 文档ID
            **kwargs: 要更新的字段（title, content, summary, tags, related_poi, related_city, status, is_pinned, is_blocked, weight等）

        Returns:
            bool: 是否更新成功

        Example:
            >>> success = KnowledgeRepository.update_doc(
            ...     1, title="新标题", status="published", is_pinned=True
            ... )
            >>> print(success)
            True
        """
        if not kwargs:
            return False
        with transaction() as conn:
            with conn.cursor() as cur:
                fields = ", ".join([f"{k} = %s" for k in kwargs.keys()])
                values = list(kwargs.values()) + [doc_id]
                cur.execute(
                    f"UPDATE knowledge_doc SET {fields} WHERE id = %s", values
                )
                return cur.rowcount > 0

    @staticmethod
    def delete_doc(doc_id: int) -> bool:
        """
        删除文档。

        Args:
            doc_id: 文档ID

        Returns:
            bool: 是否删除成功

        Example:
            >>> success = KnowledgeRepository.delete_doc(1)
            >>> print(success)
            True
        """
        with transaction() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM knowledge_doc WHERE id = %s", (doc_id,))
                return cur.rowcount > 0

    # ========== RAG检索 ==========

    @staticmethod
    def search_for_rag(
        poi_name: Optional[str] = None,
        city: Optional[str] = None,
        keyword: Optional[str] = None,
        category_code: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        RAG检索：从数据库中检索已发布的知识文档。

        优先级：置顶 > 权重 > 更新时间
        过滤：已发布、未屏蔽

        Args:
            poi_name: 关联POI名称（模糊匹配，可选）
            city: 关联城市（模糊匹配，可选）
            keyword: 关键词（标题/内容/标签/摘要模糊匹配，可选）
            category_code: 分类编码（可选）
            limit: 返回数量上限

        Returns:
            List[Dict[str, Any]]: 知识文档列表（含分类名称和编码）

        Example:
            >>> results = KnowledgeRepository.search_for_rag(
            ...     poi_name="西湖", city="杭州", keyword="人文", limit=5
            ... )
            >>> print(len(results))
            3
        """
        with read_connection() as conn:
            with conn.cursor() as cur:
                conditions = ["d.status = 'published'", "d.is_blocked = 0"]
                params = []

                if poi_name:
                    conditions.append("(d.related_poi LIKE %s OR d.title LIKE %s)")
                    params.extend([f"%{poi_name}%", f"%{poi_name}%"])
                if city:
                    conditions.append("d.related_city LIKE %s")
                    params.append(f"%{city}%")
                if keyword:
                    conditions.append(
                        "(d.title LIKE %s OR d.content LIKE %s OR d.tags LIKE %s OR d.summary LIKE %s)"
                    )
                    params.extend(
                        [
                            f"%{keyword}%",
                            f"%{keyword}%",
                            f"%{keyword}%",
                            f"%{keyword}%",
                        ]
                    )
                if category_code:
                    conditions.append("c.code = %s")
                    params.append(category_code)

                where = " AND ".join(conditions)

                cur.execute(
                    f"""SELECT d.*, c.name as category_name, c.code as category_code
                        FROM knowledge_doc d
                        LEFT JOIN knowledge_category c ON d.category_id = c.id
                        WHERE {where}
                        ORDER BY d.is_pinned DESC, d.weight DESC, d.updated_at DESC
                        LIMIT %s""",
                    params + [limit],
                )
                return cur.fetchall()

    # ========== 配置管理 ==========

    @staticmethod
    def get_config(config_key: str, default: str = "") -> str:
        """
        获取知识库配置。

        Args:
            config_key: 配置键
            default: 默认值（配置不存在时返回）

        Returns:
            str: 配置值

        Example:
            >>> rag_enabled = KnowledgeRepository.get_config("rag_enabled", "true")
            >>> print(rag_enabled)
            true
        """
        with read_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT config_value FROM knowledge_config WHERE config_key = %s",
                    (config_key,),
                )
                row = cur.fetchone()
                return row["config_value"] if row else default

    @staticmethod
    def set_config(
        config_key: str, config_value: str, description: str = ""
    ) -> bool:
        """
        设置知识库配置（幂等）。

        使用 INSERT ... ON DUPLICATE KEY UPDATE 实现幂等设置。

        Args:
            config_key: 配置键
            config_value: 配置值
            description: 配置描述

        Returns:
            bool: 是否设置成功

        Example:
            >>> success = KnowledgeRepository.set_config(
            ...     "rag_enabled", "true", "是否启用RAG知识库检索"
            ... )
            >>> print(success)
            True
        """
        with transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO knowledge_config (config_key, config_value, description)
                       VALUES (%s, %s, %s)
                       ON DUPLICATE KEY UPDATE config_value = %s, description = %s""",
                    (
                        config_key,
                        config_value,
                        description,
                        config_value,
                        description,
                    ),
                )
                return True

    @staticmethod
    def list_configs() -> List[Dict[str, Any]]:
        """
        获取所有知识库配置。

        Returns:
            List[Dict[str, Any]]: 配置列表，按 config_key 排序

        Example:
            >>> configs = KnowledgeRepository.list_configs()
            >>> print(len(configs))
            4
        """
        with read_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM knowledge_config ORDER BY config_key ASC")
                return cur.fetchall()

    # ========== 统计 ==========

    @staticmethod
    def get_stats() -> Dict[str, Any]:
        """
        获取知识库统计信息。

        包括：
        - 文档总数
        - 已发布文档数
        - 草稿文档数
        - 已下架文档数
        - 活跃分类数

        Returns:
            Dict[str, Any]: 统计信息

        Example:
            >>> stats = KnowledgeRepository.get_stats()
            >>> print(stats["total_docs"])
            100
            >>> print(stats["published_docs"])
            80
        """
        with read_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) as total FROM knowledge_doc")
                total_docs = cur.fetchone()["total"]

                cur.execute(
                    "SELECT status, COUNT(*) as count FROM knowledge_doc GROUP BY status"
                )
                status_counts = {row["status"]: row["count"] for row in cur.fetchall()}

                cur.execute(
                    "SELECT COUNT(*) as total FROM knowledge_category WHERE is_active = 1"
                )
                active_categories = cur.fetchone()["total"]

                return {
                    "total_docs": total_docs,
                    "published_docs": status_counts.get("published", 0),
                    "draft_docs": status_counts.get("draft", 0),
                    "offline_docs": status_counts.get("offline", 0),
                    "active_categories": active_categories,
                }


# 初始化默认分类和配置
def init_default_knowledge() -> None:
    """
    初始化默认的知识库分类和配置。

    默认分类：
    - 景点人文（scenic）
    - 历史名人（celebrity）
    - 美食文化（food）
    - 旅行贴士（travel_tip）

    默认配置：
    - rag_enabled: 是否启用RAG知识库检索
    - rag_max_results: RAG检索最大结果数
    - rag_allow_ai_fallback: 是否允许AI生成补充内容
    - rag_auto_update: 是否自动更新知识库
    """
    repo = KnowledgeRepository()

    # 默认分类
    default_categories = [
        ("景点人文", "scenic", "景点的历史、文化、建筑等人文知识", 1),
        ("历史名人", "celebrity", "历史名人、革命先辈相关的知识和关联地点", 2),
        ("美食文化", "food", "地方美食、饮食文化、特色餐厅介绍", 3),
        ("旅行贴士", "travel_tip", "旅行注意事项、避坑指南、实用建议", 4),
    ]

    existing_codes = {c["code"] for c in repo.list_categories(only_active=False)}
    for name, code, desc, sort_order in default_categories:
        if code not in existing_codes:
            try:
                repo.create_category(name, code, desc, sort_order)
            except Exception:
                pass

    # 默认配置
    default_configs = [
        ("rag_enabled", "true", "是否启用RAG知识库检索"),
        ("rag_max_results", "5", "RAG检索最大结果数"),
        ("rag_allow_ai_fallback", "true", "是否允许AI生成补充内容（知识库无结果时）"),
        ("rag_auto_update", "false", "是否自动更新知识库（从POI层级数据导入）"),
    ]

    for key, value, desc in default_configs:
        try:
            repo.set_config(key, value, desc)
        except Exception:
            pass
