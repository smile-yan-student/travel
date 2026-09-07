"""
搜索结果缓存 - 数据库持久化，避免重复搜索

核心功能：
1. 搜索结果缓存（关键词 -> 结果列表）
2. 缓存过期机制（热门目的地7天，普通目的地3天，官方信息30天）
3. 缓存查询和写入接口
4. 缓存清理机制（定期清理过期缓存）

设计理念：
- 减少搜索API调用成本
- 提升响应速度
- 热门目的地数据定期更新，保证数据新鲜度
"""
import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """缓存条目"""
    keyword: str
    keyword_hash: str
    category: str
    results: List[Dict[str, Any]]
    expire_at: float  # 过期时间戳
    created_at: float
    updated_at: float

    def is_expired(self) -> bool:
        """是否已过期"""
        return time.time() > self.expire_at


class SearchCache:
    """搜索结果缓存"""

    # 缓存过期时间（秒）
    CACHE_TTL = {
        "guide": 7 * 24 * 3600,  # 攻略：7天
        "attraction": 7 * 24 * 3600,  # 景点：7天
        "tips": 15 * 24 * 3600,  # 避坑：15天
        "food": 15 * 24 * 3600,  # 美食：15天
        "hotel": 30 * 24 * 3600,  # 住宿：30天
        "official": 30 * 24 * 3600,  # 官方信息：30天
        "general": 3 * 24 * 3600,  # 通用：3天
    }

    # 热门目的地列表（这些目的地的缓存会定期更新）
    HOT_DESTINATIONS = [
        "北京", "上海", "杭州", "成都", "西安", "重庆", "厦门", "三亚",
        "丽江", "大理", "桂林", "苏州", "南京", "武汉", "长沙", "青岛",
        "大连", "哈尔滨", "长春", "沈阳", "天津", "济南", "郑州", "合肥",
        "福州", "南昌", "广州", "深圳", "珠海", "昆明", "贵阳", "拉萨",
        "乌鲁木齐", "兰州", "西宁", "银川", "呼和浩特", "石家庄", "太原",
    ]

    def __init__(self):
        self._initialized = False
        self._db_available = False

    async def _initialize(self):
        """初始化（懒加载）"""
        if self._initialized:
            return
        try:
            # 检查数据库是否可用
            from app.data.database import execute_query
            # 尝试查询，确认表存在
            execute_query(
                "SELECT COUNT(*) as cnt FROM search_cache",
                fetch="one",
            )
            self._db_available = True
            logger.info("搜索缓存数据库初始化成功")
        except Exception as e:
            logger.warning(f"搜索缓存数据库不可用: {e}")
            self._db_available = False
        self._initialized = True

    def _get_cache_ttl(self, category: str, keyword: str = "") -> int:
        """获取缓存过期时间"""
        # 基础TTL
        ttl = self.CACHE_TTL.get(category, self.CACHE_TTL["general"])

        # 热门目的地的攻略和景点信息，TTL减半（更频繁更新）
        if category in ("guide", "attraction"):
            for dest in self.HOT_DESTINATIONS:
                if dest in keyword:
                    ttl = ttl // 2
                    break

        return ttl

    def _hash_keyword(self, keyword: str) -> str:
        """计算关键词的哈希值"""
        return hashlib.md5(keyword.encode("utf-8")).hexdigest()

    async def get(self, keyword: str, category: str = "general") -> Optional[List[Dict[str, Any]]]:
        """
        获取缓存

        Args:
            keyword: 搜索关键词
            category: 搜索类别

        Returns:
            缓存的搜索结果列表，未命中或已过期返回 None
        """
        await self._initialize()

        if not self._db_available:
            return None

        try:
            from app.data.database import execute_query

            keyword_hash = self._hash_keyword(keyword)
            result = execute_query(
                """
                SELECT results, expire_at FROM search_cache
                WHERE keyword_hash = %s AND category = %s
                LIMIT 1
                """,
                (keyword_hash, category),
                fetch="one",
            )

            if result:
                # 检查是否过期
                if time.time() < float(result["expire_at"]):
                    # 未过期，返回结果
                    results = json.loads(result["results"])
                    logger.info(f"缓存命中: {keyword}")
                    return results
                else:
                    logger.info(f"缓存已过期: {keyword}")

            return None
        except Exception as e:
            logger.warning(f"缓存查询失败: {e}")
            return None

    async def set(
        self,
        keyword: str,
        results: List[Dict[str, Any]],
        category: str = "general",
    ) -> bool:
        """
        设置缓存

        Args:
            keyword: 搜索关键词
            results: 搜索结果列表
            category: 搜索类别

        Returns:
            是否设置成功
        """
        await self._initialize()

        if not self._db_available:
            return False

        try:
            from app.data.database import execute_update
            from datetime import datetime

            keyword_hash = self._hash_keyword(keyword)
            ttl = self._get_cache_ttl(category, keyword)
            expire_at = time.time() + ttl
            results_json = json.dumps(results, ensure_ascii=False)
            now = datetime.now()

            # 使用 INSERT ... ON DUPLICATE KEY UPDATE
            execute_update(
                """
                INSERT INTO search_cache
                (keyword, keyword_hash, category, results, expire_at, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                results = VALUES(results),
                expire_at = VALUES(expire_at),
                updated_at = VALUES(updated_at)
                """,
                (
                    keyword[:500],  # 限制关键词长度
                    keyword_hash,
                    category,
                    results_json,
                    expire_at,
                    now,
                    now,
                ),
            )

            logger.info(f"缓存已设置: {keyword}, 过期时间: {ttl}秒")
            return True
        except Exception as e:
            logger.warning(f"缓存设置失败: {e}")
            return False

    async def delete(self, keyword: str, category: str = "general") -> bool:
        """
        删除缓存

        Args:
            keyword: 搜索关键词
            category: 搜索类别

        Returns:
            是否删除成功
        """
        await self._initialize()

        if not self._db_available:
            return False

        try:
            from app.data.database import execute_update

            keyword_hash = self._hash_keyword(keyword)
            execute_update(
                "DELETE FROM search_cache WHERE keyword_hash = %s AND category = %s",
                (keyword_hash, category),
            )
            return True
        except Exception as e:
            logger.warning(f"缓存删除失败: {e}")
            return False

    async def clean_expired(self) -> int:
        """
        清理过期缓存

        Returns:
            清理的缓存条目数
        """
        await self._initialize()

        if not self._db_available:
            return 0

        try:
            from app.data.database import execute_update

            now = time.time()
            result = execute_update(
                "DELETE FROM search_cache WHERE expire_at < %s",
                (now,),
            )
            logger.info(f"清理过期缓存: {result}条")
            return result
        except Exception as e:
            logger.warning(f"清理过期缓存失败: {e}")
            return 0

    async def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            缓存统计信息
        """
        await self._initialize()

        if not self._db_available:
            return {"available": False}

        try:
            from app.data.database import execute_query

            # 总缓存数
            total = execute_query(
                "SELECT COUNT(*) as cnt FROM search_cache",
                fetch="one",
            )["cnt"]

            # 已过期缓存数
            expired = execute_query(
                "SELECT COUNT(*) as cnt FROM search_cache WHERE expire_at < %s",
                (time.time(),),
                fetch="one",
            )["cnt"]

            # 按类别统计
            by_category = execute_query(
                "SELECT category, COUNT(*) as cnt FROM search_cache GROUP BY category",
                fetch="all",
            )

            return {
                "available": True,
                "total": total,
                "expired": expired,
                "active": total - expired,
                "by_category": {item["category"]: item["cnt"] for item in by_category},
            }
        except Exception as e:
            logger.warning(f"获取缓存统计失败: {e}")
            return {"available": False, "error": str(e)}


# 单例
_search_cache: Optional[SearchCache] = None


def get_search_cache() -> SearchCache:
    """获取搜索缓存单例"""
    global _search_cache
    if _search_cache is None:
        _search_cache = SearchCache()
    return _search_cache
