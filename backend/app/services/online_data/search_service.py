"""
搜索服务 - 封装公开网页搜索，支持多关键词策略

核心功能：
1. 多关键词搜索策略（攻略、景点、避坑、美食、住宿、官方信息）
2. 搜索结果过滤（优先来源、过滤广告、过滤过时信息）
3. 搜索结果聚合和去重
4. 集成搜索缓存（避免重复搜索）

设计理念：
- 以在线数据为依托，为规划引擎提供真实、经过验证的攻略和景点信息
- 搜索结果经过提纯后，作为规划引擎的基础数据
"""
import asyncio
import hashlib
import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """搜索结果条目"""
    title: str
    url: str
    content: str
    source: str = ""  # 来源网站
    publish_time: str = ""  # 发布时间
    relevance_score: float = 0.0  # 相关度评分

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "content": self.content,
            "source": self.source,
            "publish_time": self.publish_time,
            "relevance_score": self.relevance_score,
        }


@dataclass
class SearchQuery:
    """搜索查询"""
    keyword: str
    category: str = "general"  # general/guide/attraction/tips/food/hotel/official
    max_results: int = 10
    priority_sources: List[str] = field(default_factory=list)


class SearchService:
    """搜索服务"""

    # 优先来源（高质量旅游内容平台）
    PRIORITY_SOURCES = [
        "mafengwo.cn",  # 马蜂窝
        "ctrip.com",  # 携程
        "qunar.com",  # 去哪儿
        "zhihu.com",  # 知乎
        "xiaohongshu.com",  # 小红书
        "bendibao.com",  # 本地宝
        "dianping.com",  # 大众点评
        "meituan.com",  # 美团
    ]

    # 过滤来源（广告、低质量内容）
    BLOCKED_SOURCES = [
        "广告",
        "推广",
        "sponsor",
    ]

    # 搜索关键词模板
    KEYWORD_TEMPLATES = {
        "guide": [
            "{destination}{days}天攻略",
            "{destination}旅游攻略",
            "{destination}自由行攻略",
            "{destination}必去景点",
            "{destination}景点排名",
        ],
        "attraction": [
            "{destination}必去景点",
            "{destination}景点推荐",
            "{destination}旅游景点大全",
            "{destination}打卡景点",
        ],
        "tips": [
            "{destination}旅游避坑",
            "{destination}注意事项",
            "{destination}旅游防骗",
            "{destination}踩坑经验",
        ],
        "food": [
            "{destination}美食推荐",
            "{destination}必吃美食",
            "{destination}特色小吃",
            "{destination}美食街",
        ],
        "hotel": [
            "{destination}住哪里方便",
            "{destination}住宿区域推荐",
            "{destination}酒店推荐",
        ],
        "official": [
            "{attraction}官方 预约 开放时间 票价",
            "{attraction}官网 门票 闭馆",
        ],
    }

    def __init__(self, cache_enabled: bool = True):
        self.cache_enabled = cache_enabled
        self._cache = None
        self._initialized = False

    async def _initialize(self):
        """初始化（懒加载）"""
        if self._initialized:
            return
        try:
            if self.cache_enabled:
                from .search_cache import get_search_cache
                self._cache = get_search_cache()
        except Exception as e:
            logger.warning(f"搜索缓存初始化失败: {e}")
            self._cache = None
        self._initialized = True

    async def search(self, query: SearchQuery) -> List[SearchResult]:
        """
        执行搜索

        Args:
            query: 搜索查询

        Returns:
            搜索结果列表
        """
        await self._initialize()

        # 1. 检查缓存
        if self._cache:
            cached = await self._cache.get(query.keyword)
            if cached:
                logger.info(f"搜索缓存命中: {query.keyword}")
                return [SearchResult(**item) for item in cached]

        # 2. 执行搜索
        results = await self._do_search(query)

        # 3. 过滤和排序
        results = self._filter_results(results, query)
        results = self._rank_results(results)

        # 4. 写入缓存
        if self._cache and results:
            await self._cache.set(
                query.keyword,
                [r.to_dict() for r in results[:query.max_results]],
            )

        return results[:query.max_results]

    async def _do_search(self, query: SearchQuery) -> List[SearchResult]:
        """执行实际搜索"""
        try:
            # 使用 general_search 工具进行搜索
            # 注意：这里需要调用搜索工具，实际实现时根据项目的搜索工具封装
            # 这里先实现基础版本，后续可以集成具体的搜索API
            results = await self._search_with_general_search(query)
            return results
        except Exception as e:
            logger.error(f"搜索失败: {query.keyword}, 错误: {e}")
            return []

    async def _search_with_general_search(self, query: SearchQuery) -> List[SearchResult]:
        """使用通用搜索工具进行搜索

        支持多种搜索API：
        - 必应搜索API（Bing Search API）
        - 百度搜索API（Baidu Search API）
        - 谷歌自定义搜索API（Google Custom Search API）
        - 或者项目已有的搜索工具

        配置方式：
        - SEARCH_PROVIDER: 搜索服务提供商（bing/baidu/google/custom）
        - SEARCH_API_KEY: 搜索API密钥
        - SEARCH_API_URL: 自定义搜索API URL（可选）
        - SEARCH_ENABLED: 是否启用搜索（默认false）
        """
        import os

        # 检查是否启用搜索
        search_enabled = os.getenv("SEARCH_ENABLED", "false").lower() == "true"
        if not search_enabled:
            logger.info(f"search_disabled: {query.keyword}")
            return []

        search_provider = os.getenv("SEARCH_PROVIDER", "custom").lower()
        api_key = os.getenv("SEARCH_API_KEY", "")
        custom_api_url = os.getenv("SEARCH_API_URL", "")

        if not api_key and search_provider != "custom":
            logger.warning(f"search_api_key_not_configured: provider={search_provider}")
            return []

        logger.info(f"执行搜索: provider={search_provider}, keyword={query.keyword}")

        try:
            import httpx

            results = []

            if search_provider == "bing" and api_key:
                # 必应搜索API
                url = "https://api.bing.microsoft.com/v7.0/search"
                headers = {"Ocp-Apim-Subscription-Key": api_key}
                params = {
                    "q": query.keyword,
                    "count": query.max_results,
                    "mkt": "zh-CN",
                    "setLang": "zh-CN",
                }

                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(url, headers=headers, params=params)
                    if response.status_code == 200:
                        data = response.json()
                        web_pages = data.get("webPages", {}).get("value", [])
                        for page in web_pages:
                            result = SearchResult(
                                title=page.get("name", ""),
                                url=page.get("url", ""),
                                content=page.get("snippet", ""),
                                source=self._extract_source(page.get("url", "")),
                                publish_time=page.get("dateLastCrawled", ""),
                                relevance_score=0.5,
                            )
                            results.append(result)

            elif search_provider == "baidu" and api_key:
                # 百度搜索API（需要百度开发者平台的搜索API）
                url = "https://sp0.baidu.com/8aQDcjqpAAV3otqbppnN2DJv/api.php"
                params = {
                    "resource_id": "5300",
                    "query": query.keyword,
                    "pn": 0,
                    "rn": query.max_results,
                    "ie": "utf-8",
                    "oe": "utf-8",
                    "format": "json",
                }

                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(url, params=params)
                    if response.status_code == 200:
                        data = response.json()
                        items = data.get("data", [])
                        for item in items:
                            result = SearchResult(
                                title=item.get("title", ""),
                                url=item.get("url", ""),
                                content=item.get("abstract", ""),
                                source=self._extract_source(item.get("url", "")),
                                publish_time="",
                                relevance_score=0.5,
                            )
                            results.append(result)

            elif search_provider == "google" and api_key:
                # 谷歌自定义搜索API
                cx = os.getenv("GOOGLE_CSE_ID", "")
                if not cx:
                    logger.warning("google_cse_id_not_configured")
                    return []

                url = "https://www.googleapis.com/customsearch/v1"
                params = {
                    "key": api_key,
                    "cx": cx,
                    "q": query.keyword,
                    "num": min(query.max_results, 10),
                    "lr": "lang_zh-CN",
                }

                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(url, params=params)
                    if response.status_code == 200:
                        data = response.json()
                        items = data.get("items", [])
                        for item in items:
                            result = SearchResult(
                                title=item.get("title", ""),
                                url=item.get("link", ""),
                                content=item.get("snippet", ""),
                                source=self._extract_source(item.get("link", "")),
                                publish_time="",
                                relevance_score=0.5,
                            )
                            results.append(result)

            elif search_provider == "custom" and custom_api_url:
                # 自定义搜索API
                headers = {}
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"

                params = {
                    "q": query.keyword,
                    "count": query.max_results,
                }

                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(custom_api_url, headers=headers, params=params)
                    if response.status_code == 200:
                        data = response.json()
                        items = data.get("results", data.get("items", []))
                        for item in items:
                            result = SearchResult(
                                title=item.get("title", ""),
                                url=item.get("url", item.get("link", "")),
                                content=item.get("content", item.get("snippet", "")),
                                source=self._extract_source(item.get("url", item.get("link", ""))),
                                publish_time=item.get("publish_time", ""),
                                relevance_score=item.get("relevance_score", 0.5),
                            )
                            results.append(result)

            else:
                logger.warning(f"unknown_search_provider: {search_provider}")
                return []

            logger.info(f"search_results_count: {len(results)}")
            return results

        except Exception as e:
            logger.warning(f"搜索工具调用失败: {e}")
            return []

    def _filter_results(self, results: List[SearchResult], query: SearchQuery) -> List[SearchResult]:
        """过滤搜索结果"""
        filtered = []
        for result in results:
            # 过滤 blocked 来源
            if any(blocked in result.url or blocked in result.title for blocked in self.BLOCKED_SOURCES):
                continue

            # 过滤过时内容（超过2年的内容降低权重，不直接过滤）
            # 这里可以根据 publish_time 做更精细的过滤

            # 优先来源加权
            if any(source in result.url for source in query.priority_sources or self.PRIORITY_SOURCES):
                result.relevance_score += 0.3
                result.source = self._extract_source(result.url)

            filtered.append(result)

        return filtered

    def _rank_results(self, results: List[SearchResult]) -> List[SearchResult]:
        """对搜索结果排序"""
        # 按相关度评分排序
        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results

    def _extract_source(self, url: str) -> str:
        """从URL提取来源网站"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc
            # 移除www前缀
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        except Exception:
            return ""

    async def search_destination_guides(
        self,
        destination: str,
        days: int = 3,
        max_results: int = 10,
    ) -> List[SearchResult]:
        """
        搜索目的地攻略

        Args:
            destination: 目的地
            days: 天数
            max_results: 最大结果数

        Returns:
            搜索结果列表
        """
        # 生成多个关键词进行搜索
        keywords = [
            template.format(destination=destination, days=days)
            for template in self.KEYWORD_TEMPLATES["guide"]
        ]

        all_results = []
        for keyword in keywords[:3]:  # 只搜索前3个关键词，避免过多调用
            query = SearchQuery(
                keyword=keyword,
                category="guide",
                max_results=max_results,
            )
            results = await self.search(query)
            all_results.extend(results)

        # 去重
        all_results = self._deduplicate(all_results)
        return all_results[:max_results]

    async def search_attraction_info(
        self,
        attraction: str,
        max_results: int = 5,
    ) -> List[SearchResult]:
        """
        搜索景点官方信息（预约规则、开放时间、票价等）

        Args:
            attraction: 景点名称
            max_results: 最大结果数

        Returns:
            搜索结果列表
        """
        keywords = [
            template.format(attraction=attraction)
            for template in self.KEYWORD_TEMPLATES["official"]
        ]

        all_results = []
        for keyword in keywords[:2]:
            query = SearchQuery(
                keyword=keyword,
                category="official",
                max_results=max_results,
            )
            results = await self.search(query)
            all_results.extend(results)

        return self._deduplicate(all_results)[:max_results]

    async def search_travel_tips(
        self,
        destination: str,
        max_results: int = 10,
    ) -> List[SearchResult]:
        """
        搜索旅游避坑提示

        Args:
            destination: 目的地
            max_results: 最大结果数

        Returns:
            搜索结果列表
        """
        keywords = [
            template.format(destination=destination)
            for template in self.KEYWORD_TEMPLATES["tips"]
        ]

        all_results = []
        for keyword in keywords[:2]:
            query = SearchQuery(
                keyword=keyword,
                category="tips",
                max_results=max_results,
            )
            results = await self.search(query)
            all_results.extend(results)

        return self._deduplicate(all_results)[:max_results]

    def _deduplicate(self, results: List[SearchResult]) -> List[SearchResult]:
        """去重搜索结果"""
        seen_urls = set()
        seen_titles = set()
        unique = []

        for result in results:
            # URL去重
            if result.url in seen_urls:
                continue
            seen_urls.add(result.url)

            # 标题去重（简化标题后比较）
            simple_title = re.sub(r'[^\w\u4e00-\u9fff]', '', result.title)
            if simple_title in seen_titles:
                continue
            seen_titles.add(simple_title)

            unique.append(result)

        return unique


# 单例
_search_service: Optional[SearchService] = None


def get_search_service() -> SearchService:
    """获取搜索服务单例"""
    global _search_service
    if _search_service is None:
        _search_service = SearchService(cache_enabled=True)
    return _search_service
