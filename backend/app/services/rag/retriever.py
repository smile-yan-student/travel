"""
RAG检索器（Retriever）。

混合检索策略：向量语义检索 + 关键词精确匹配。
支持按景点、分块类型、重要性等维度过滤。
支持景点名称模糊匹配（别名、简称、全称自动归一化）。
支持结果重排序和检索缓存。

功能特性：
- 向量语义检索（基于Chroma + bge-small-zh）
- 关键词精确匹配（基于元数据过滤）
- 景点名称模糊匹配（别名、简称、全称自动归一化）
- 结果融合与重排（多维度评分：向量相似度、分块类型优先级、关键词匹配度、文档长度、景点名称匹配度）
- 检索缓存（TTL: 30分钟，最多100条）
- 景点别名映射表（覆盖北京、西安、杭州、济南、成都、南京、上海、厦门、云南、湖南、海南、广西等城市的著名景点）
- 按景点名称检索（支持模糊匹配）
- 按自然语言查询检索（支持景点名称模糊匹配）
- 获取景点的完整知识（按分块类型分组）
- 获取用于LLM生成的上下文文本
- 全局单例

使用方式：
    from app.services.rag.retriever import get_retriever

    # 获取全局检索器单例
    retriever = get_retriever()

    # 检查是否可用
    if retriever.available:
        # 按景点名称检索（支持模糊匹配）
        results = retriever.search_by_poi("故宫", n_results=10)

        # 按自然语言查询检索
        results = retriever.search_by_query(
            "故宫的历史文化",
            poi_name="故宫",
            n_results=5
        )

        # 获取景点的完整知识（按分块类型分组）
        knowledge = retriever.get_poi_knowledge("故宫")

        # 获取用于LLM生成的上下文文本
        context = retriever.get_context_for_generation(
            "故宫",
            query="历史文化",
            max_tokens=2000
        )

        # 景点名称标准化（模糊匹配）
        normalized_name = retriever.normalize_poi_name("紫禁城")
        # 返回 "故宫"
"""
import difflib
import time
from typing import Any, Dict, List, Optional

from .vector_store import get_vector_store


# 景点别名映射表：用户可能输入的名称 → 标准名称
# 持续扩展，覆盖常见的全称、简称、俗称
POI_ALIASES = {
    # 北京
    "故宫博物院": "故宫",
    "紫禁城": "故宫",
    "北京故宫": "故宫",
    "天安门": "天安门广场",
    "八达岭": "八达岭长城",
    "长城": "八达岭长城",
    "北京长城": "八达岭长城",
    "颐和园": "颐和园",
    "圆明园": "颐和园",  # 圆明园知识暂归颐和园周边
    # 西安
    "兵马俑": "秦始皇兵马俑博物馆",
    "秦始皇兵马俑": "秦始皇兵马俑博物馆",
    "西安兵马俑": "秦始皇兵马俑博物馆",
    "西安大雁塔": "大雁塔",
    "大慈恩寺": "大雁塔",
    # 杭州
    "杭州西湖": "西湖",
    "西湖风景区": "西湖",
    "杭州灵隐寺": "灵隐寺",
    "灵隐": "灵隐寺",
    # 济南
    "济南大明湖": "大明湖",
    "大明湖风景区": "大明湖",
    "济南趵突泉": "趵突泉",
    "趵突泉公园": "趵突泉",
    # 成都
    "成都宽窄巷子": "宽窄巷子",
    "宽巷子": "宽窄巷子",
    "窄巷子": "宽窄巷子",
    # 南京
    "南京中山陵": "中山陵",
    "中山陵园": "中山陵",
    # 上海
    "上海夫子庙": "夫子庙",
    "南京夫子庙": "夫子庙",
    "夫子庙步行街": "夫子庙",
    # 厦门
    "厦门鼓浪屿": "鼓浪屿",
    "鼓浪屿风景区": "鼓浪屿",
    # 云南
    "丽江": "丽江古城",
    "云南丽江": "丽江古城",
    "大研古城": "丽江古城",
    # 湖南
    "张家界": "张家界国家森林公园",
    "湖南张家界": "张家界国家森林公园",
    "武陵源": "张家界国家森林公园",
    # 海南
    "三亚亚龙湾": "亚龙湾",
    "亚龙湾海滩": "亚龙湾",
    # 广西
    "桂林漓江": "漓江",
    "漓江风景区": "漓江",
    "桂林山水": "漓江",
}


class Retriever:
    """
    RAG检索器。

    - 向量语义检索（基于Chroma + bge-small-zh）
    - 关键词精确匹配（基于元数据过滤）
    - 景点名称模糊匹配（别名、简称、全称自动归一化）
    - 结果融合与重排
    """

    def __init__(self) -> None:
        """初始化检索器。"""
        self.vector_store = get_vector_store()
        self._all_poi_names: Optional[List[str]] = None
        # 检索结果缓存（TTL: 30分钟）
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = 1800  # 30分钟
        # 分块类型优先级（用于重排序）
        self._chunk_type_priority = {
            "summary": 10,  # 概述优先级最高
            "history": 8,  # 历史文化
            "culture": 8,  # 文化特色
            "visit_guide": 6,  # 游玩指南
            "inner_route": 5,  # 内部路线
            "nearby": 4,  # 附近景点
            "tips": 3,  # 避坑提示
            "other": 1,  # 其他
        }

    @property
    def available(self) -> bool:
        """
        检索器是否可用。

        Returns:
            bool: 是否可用
        """
        return self.vector_store.available

    def _get_cache_key(self, method: str, **kwargs: Any) -> str:
        """
        生成缓存键。

        Args:
            method: 方法名
            **kwargs: 参数

        Returns:
            str: 缓存键
        """
        key_parts = [method]
        for k, v in sorted(kwargs.items()):
            if v is not None:
                key_parts.append(f"{k}={v}")
        return "|".join(key_parts)

    def _get_from_cache(self, cache_key: str) -> Optional[List[Dict[str, Any]]]:
        """
        从缓存中获取结果。

        Args:
            cache_key: 缓存键

        Returns:
            Optional[List[Dict[str, Any]]]: 缓存数据，未命中返回None
        """
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if time.time() - cached["timestamp"] < self._cache_ttl:
                return cached["data"]
            else:
                # 过期删除
                del self._cache[cache_key]
        return None

    def _set_to_cache(self, cache_key: str, data: List[Dict[str, Any]]) -> None:
        """
        将结果存入缓存。

        Args:
            cache_key: 缓存键
            data: 数据
        """
        self._cache[cache_key] = {
            "data": data,
            "timestamp": time.time(),
        }
        # 缓存大小限制（最多100条）
        if len(self._cache) > 100:
            # 删除最旧的缓存
            oldest_key = min(
                self._cache.keys(), key=lambda k: self._cache[k]["timestamp"]
            )
            del self._cache[oldest_key]

    def _rerank_results(
        self,
        results: List[Dict[str, Any]],
        query: str = "",
        poi_name: str = "",
    ) -> List[Dict[str, Any]]:
        """
        结果重排序（基于多维度评分）。

        评分维度：
        1. 向量相似度（原始分数，权重40%）
        2. 分块类型优先级（权重20%）
        3. 关键词匹配度（权重20%）
        4. 文档长度（适中长度优先，权重10%）
        5. 景点名称匹配度（权重10%）

        Args:
            results: 检索结果列表
            query: 查询文本
            poi_name: 景点名称

        Returns:
            List[Dict[str, Any]]: 重排序后的结果列表
        """
        if not results:
            return results

        query_words = set(query.lower().split()) if query else set()
        poi_words = set(poi_name.lower()) if poi_name else set()

        scored_results = []
        for doc in results:
            content = doc.get("document", "") or doc.get("text", "")
            metadata = doc.get("metadata", {})
            original_score = doc.get("score", 0.5)  # 原始向量相似度
            chunk_type = metadata.get("chunk_type", "other")
            poi_name = metadata.get("poi_name", "")

            # 添加title字段（从poi_name和chunk_type构建）
            if "title" not in doc or not doc.get("title"):
                chunk_type_names = {
                    "summary": "景点概述",
                    "history": "历史文化",
                    "culture": "文化特色",
                    "visit_guide": "游玩指南",
                    "inner_route": "内部路线",
                    "nearby": "附近景点",
                    "tips": "避坑提示",
                    "other": "相关知识",
                }
                type_name = chunk_type_names.get(chunk_type, "相关知识")
                doc["title"] = (
                    f"{poi_name} - {type_name}" if poi_name else type_name
                )

            # 1. 向量相似度（权重40%）
            vector_score = float(original_score) * 0.4

            # 2. 分块类型优先级（权重20%）
            type_priority = self._chunk_type_priority.get(chunk_type, 1)
            type_score = (type_priority / 10) * 0.2

            # 3. 关键词匹配度（权重20%）
            keyword_score = 0.0
            if query_words and content:
                content_lower = content.lower()
                matched = sum(1 for word in query_words if word in content_lower)
                keyword_score = (
                    (matched / len(query_words)) * 0.2 if query_words else 0
                )

            # 4. 文档长度（权重10%，适中长度优先：200-800字）
            content_len = len(content)
            if 200 <= content_len <= 800:
                length_score = 0.1
            elif 100 <= content_len < 200 or 800 < content_len <= 1500:
                length_score = 0.05
            else:
                length_score = 0.02

            # 5. 景点名称匹配度（权重10%）
            poi_score = 0.0
            if poi_words and content:
                content_lower = content.lower()
                matched = sum(1 for char in poi_words if char in content_lower)
                poi_score = (matched / len(poi_words)) * 0.1 if poi_words else 0

            # 综合评分
            total_score = (
                vector_score + type_score + keyword_score + length_score + poi_score
            )

            # 在文档元数据中记录重排序分数
            doc["metadata"]["rerank_score"] = round(total_score, 4)
            doc["metadata"]["rerank_details"] = {
                "vector": round(vector_score, 4),
                "type": round(type_score, 4),
                "keyword": round(keyword_score, 4),
                "length": round(length_score, 4),
                "poi": round(poi_score, 4),
            }

            scored_results.append((total_score, doc))

        # 按综合评分降序排序
        scored_results.sort(key=lambda x: x[0], reverse=True)

        return [doc for _, doc in scored_results]

    def normalize_poi_name(self, poi_name: str) -> str:
        """
        景点名称标准化（模糊匹配）。

        优先级：1.别名精确匹配 2.包含关系匹配 3.字符串相似度匹配

        Args:
            poi_name: 用户输入的景点名称

        Returns:
            str: 标准化后的景点名称（如果匹配到）
        """
        if not poi_name:
            return poi_name

        poi_name = poi_name.strip()

        # 1. 别名精确匹配
        if poi_name in POI_ALIASES:
            return POI_ALIASES[poi_name]

        # 2. 获取所有已知景点名称（懒加载）
        if self._all_poi_names is None:
            self._all_poi_names = self._get_all_poi_names()

        if not self._all_poi_names:
            return poi_name

        # 3. 包含关系匹配（用户输入包含标准名，或标准名包含用户输入）
        for standard_name in self._all_poi_names:
            if poi_name in standard_name or standard_name in poi_name:
                # 确保长度差异合理（避免"湖"匹配到"西湖"和"大明湖"等多个）
                if abs(len(poi_name) - len(standard_name)) <= 4:
                    return standard_name

        # 4. 字符串相似度匹配（编辑距离）
        matches = difflib.get_close_matches(
            poi_name, self._all_poi_names, n=1, cutoff=0.6
        )
        if matches:
            return matches[0]

        # 5. 未匹配到，返回原名
        return poi_name

    def _get_all_poi_names(self) -> List[str]:
        """
        从向量库中获取所有已知景点名称。

        Returns:
            List[str]: 景点名称列表
        """
        try:
            # 从POI_ALIASES的值中获取标准名称
            standard_names = list(set(POI_ALIASES.values()))
            # 也可以从向量库中获取，但暂时用别名表中的标准名
            return standard_names
        except Exception:
            return list(set(POI_ALIASES.values()))

    def search_by_poi(
        self,
        poi_name: str,
        chunk_types: Optional[List[str]] = None,
        n_results: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        按景点名称检索（支持模糊匹配）。

        Args:
            poi_name: 景点名称（支持别名、简称、全称）
            chunk_types: 分块类型过滤
            n_results: 返回结果数量

        Returns:
            List[Dict[str, Any]]: 检索结果列表
        """
        # 缓存键
        cache_key = self._get_cache_key(
            "search_by_poi",
            poi_name=poi_name,
            chunk_types=",".join(chunk_types) if chunk_types else "",
            n_results=n_results,
        )

        # 尝试从缓存获取
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        # 名称标准化（模糊匹配）
        normalized_name = self.normalize_poi_name(poi_name)

        filter_meta = {"poi_name": normalized_name}
        if chunk_types:
            filter_meta["chunk_type"] = {"$in": chunk_types}

        # 优化查询构造：使用更精准的查询
        query = f"{normalized_name} 景点介绍 历史文化 游玩攻略 开放时间 门票"
        results = self.vector_store.search(
            query, n_results=n_results * 2, filter_metadata=filter_meta
        )

        # 结果重排序
        results = self._rerank_results(results, query=query, poi_name=normalized_name)

        # 截断到请求的数量
        results = results[:n_results]

        # 如果标准化名称与原名称不同，在结果元数据中标记
        if normalized_name != poi_name:
            for doc in results:
                doc["metadata"]["matched_alias"] = poi_name
                doc["metadata"]["standard_name"] = normalized_name

        # 存入缓存
        self._set_to_cache(cache_key, results)

        return results

    def search_by_query(
        self,
        query: str,
        poi_name: Optional[str] = None,
        chunk_types: Optional[List[str]] = None,
        n_results: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        按自然语言查询检索（支持景点名称模糊匹配）。

        Args:
            query: 用户查询
            poi_name: 限定景点（可选，支持别名、简称）
            chunk_types: 分块类型过滤（可选）
            n_results: 返回结果数量

        Returns:
            List[Dict[str, Any]]: 检索结果列表
        """
        # 缓存键
        cache_key = self._get_cache_key(
            "search_by_query",
            query=query,
            poi_name=poi_name or "",
            chunk_types=",".join(chunk_types) if chunk_types else "",
            n_results=n_results,
        )

        # 尝试从缓存获取
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        filter_meta = {}
        normalized_name = ""
        if poi_name:
            # 名称标准化（模糊匹配）
            normalized_name = self.normalize_poi_name(poi_name)
            filter_meta["poi_name"] = normalized_name
        if chunk_types:
            filter_meta["chunk_type"] = {"$in": chunk_types}

        # 查询扩展：增加相关关键词
        expanded_query = query
        if "历史" in query or "文化" in query:
            expanded_query += " 历史背景 文化特色 典故"
        elif "游玩" in query or "攻略" in query:
            expanded_query += " 游玩攻略 开放时间 门票 路线"
        elif "介绍" in query or "简介" in query:
            expanded_query += " 景点介绍 概述 特色"

        results = self.vector_store.search(
            expanded_query,
            n_results=n_results * 2,
            filter_metadata=filter_meta if filter_meta else None,
        )

        # 结果重排序
        results = self._rerank_results(results, query=query, poi_name=normalized_name)

        # 截断到请求的数量
        results = results[:n_results]

        # 存入缓存
        self._set_to_cache(cache_key, results)

        return results

    def get_poi_knowledge(
        self,
        poi_name: str,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        获取景点的完整知识（按分块类型分组，支持名称模糊匹配）。

        Args:
            poi_name: 景点名称（支持别名、简称、全称）

        Returns:
            Dict[str, List[Dict[str, Any]]]: 按分块类型分组的知识字典
        """
        all_docs = self.search_by_poi(poi_name, n_results=50)
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for doc in all_docs:
            chunk_type = doc.get("metadata", {}).get("chunk_type", "unknown")
            if chunk_type not in grouped:
                grouped[chunk_type] = []
            grouped[chunk_type].append(doc)
        return grouped

    def get_context_for_generation(
        self,
        poi_name: str,
        query: str = "",
        max_tokens: int = 2000,
    ) -> str:
        """
        获取用于LLM生成的上下文文本（支持名称模糊匹配）。

        Args:
            poi_name: 景点名称（支持别名、简称）
            query: 用户查询（用于相关性排序）
            max_tokens: 最大token数（粗略控制）

        Returns:
            str: 格式化的上下文文本
        """
        # 名称标准化（模糊匹配）
        normalized_name = self.normalize_poi_name(poi_name)

        if query:
            docs = self.search_by_query(
                query, poi_name=normalized_name, n_results=8
            )
        else:
            docs = self.search_by_poi(normalized_name, n_results=8)

        if not docs:
            return ""

        context_parts = []
        current_length = 0
        for doc in docs:
            content = doc.get("document", "")
            metadata = doc.get("metadata", {})
            chunk_type = metadata.get("chunk_type", "")
            poi = metadata.get("poi_name", "")

            # 格式化每条知识
            formatted = f"【{chunk_type}】{content}"
            if current_length + len(formatted) > max_tokens * 2:  # 粗略估算：1中文≈2token
                break
            context_parts.append(formatted)
            current_length += len(formatted)

        return "\n\n".join(context_parts)

    def get_stats(self) -> Dict[str, Any]:
        """
        获取检索器统计信息。

        Returns:
            Dict[str, Any]: 统计信息
        """
        return self.vector_store.get_stats()


# 全局单例
_retriever: Optional[Retriever] = None


def get_retriever() -> Retriever:
    """
    获取全局检索器单例。

    Returns:
        Retriever: 全局检索器单例
    """
    global _retriever
    if _retriever is None:
        _retriever = Retriever()
    return _retriever
