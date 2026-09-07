"""
主要景点库服务（Major Attractions Service）。

在规划之前，先从主要景点库中获取目的地的主要景点，
然后与高德POI数据混合，作为候选景点池。

主要景点具有更高的优先级（must_visit标记），确保被规划进行程。

数据来源：
1. 静态主要景点库（从知识库提取的28个景点）
2. 数据库must_visit表（后台管理的必去地标）
3. AI生成的主要景点（对于库中没有的城市）

性能优化：
- 内存缓存（带过期时间，默认5分钟）
- 单例模式（避免重复加载数据）
- 索引预构建（按城市、按名称索引）

功能特性：
- 加载静态主要景点库（仅作为兜底，优先从数据库获取）
- 从数据库加载主要景点（带缓存，缓存过期时间5分钟）
- 刷新缓存（后台管理数据更新后调用）
- 构建索引（按城市、按名称）
- 根据城市获取主要景点（支持带"市"后缀和不带后缀）
- 根据名称获取主要景点（支持别名）
- 获取所有有主要景点的城市
- 获取主要景点库统计信息
- 将主要景点与POI数据混合（主要景点在前，POI数据在后）
- 使用AI生成城市的主要景点列表
- 获取城市的主要景点，如果静态库中没有，使用AI生成
- 全局单例

使用方式：
    from app.services.major_attractions import get_major_attractions_service

    # 获取全局主要景点库服务单例
    service = get_major_attractions_service()

    # 根据城市获取主要景点
    attractions = service.get_major_attractions_by_city("北京")

    # 根据名称获取主要景点（支持别名）
    attraction = service.get_major_attraction_by_name("故宫")

    # 获取所有有主要景点的城市
    cities = service.get_all_cities()

    # 获取主要景点库统计信息
    stats = service.get_stats()

    # 将主要景点与POI数据混合
    mixed = await service.merge_with_poi_data("北京", poi_data)

    # 使用AI生成城市的主要景点列表
    ai_attractions = await service.generate_major_attractions_by_ai("北京")

    # 获取城市的主要景点，如果静态库中没有，使用AI生成
    attractions = await service.get_or_generate_major_attractions("北京")

    # 刷新缓存（后台管理数据更新后调用）
    service.refresh_cache()
"""
import json
import os
import re
import time
from functools import lru_cache
from typing import Any, Dict, List, Optional


# 缓存配置
CACHE_TTL = 300  # 缓存过期时间（秒），默认5分钟


class MajorAttractionsService:
    """主要景点库服务。"""

    def __init__(self) -> None:
        """初始化主要景点库服务。"""
        self._static_attractions: Optional[List[Dict[str, Any]]] = None
        self._by_city: Optional[Dict[str, List[Dict[str, Any]]]] = None
        self._by_name: Optional[Dict[str, Dict[str, Any]]] = None
        # AI生成的主要景点缓存（运行时缓存，不持久化）
        self._ai_cache: Dict[str, List[Dict[str, Any]]] = {}
        # 数据库缓存（带过期时间）
        self._db_cache: Optional[List[Dict[str, Any]]] = None
        self._db_cache_time: float = 0

    def _load_static_attractions(self) -> List[Dict[str, Any]]:
        """
        加载静态主要景点库（仅作为兜底，优先从数据库获取）。

        Returns:
            List[Dict[str, Any]]: 静态主要景点列表
        """
        if self._static_attractions is not None:
            return self._static_attractions

        static_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "data",
            "major_attractions",
            "major_attractions.json",
        )

        if os.path.exists(static_file):
            try:
                with open(static_file, "r", encoding="utf-8") as f:
                    self._static_attractions = json.load(f)
            except Exception:
                self._static_attractions = []
        else:
            self._static_attractions = []

        return self._static_attractions

    def _load_db_attractions(self) -> List[Dict[str, Any]]:
        """
        从数据库加载主要景点（带缓存，缓存过期时间5分钟）。

        Returns:
            List[Dict[str, Any]]: 数据库主要景点列表
        """
        # 检查缓存是否有效
        current_time = time.time()
        if (
            self._db_cache is not None
            and (current_time - self._db_cache_time) < CACHE_TTL
        ):
            return self._db_cache

        try:
            from ..data.repositories.major_attractions_repository import (
                search_major_attractions,
            )

            # 从数据库获取所有有效的主要景点
            db_attractions = search_major_attractions(limit=1000)
            # 转换为统一格式
            result = []
            for attr in db_attractions:
                item = {
                    "name": attr.get("name", ""),
                    "aliases": attr.get("aliases", []) or [],
                    "city": attr.get("city", ""),
                    "district": attr.get("district", ""),
                    "province": attr.get("province", ""),
                    "level": attr.get("level", ""),
                    "category": attr.get("category", "景点"),
                    "description": attr.get("description", ""),
                    "recommended_duration": attr.get("recommended_duration", 120),
                    "lng": float(attr["lng"]) if attr.get("lng") else None,
                    "lat": float(attr["lat"]) if attr.get("lat") else None,
                    "must_visit": bool(attr.get("must_visit", True)),
                    "hot": bool(attr.get("hot", False)),
                    "tags": attr.get("tags", []) or [],
                    "inner_route": attr.get("inner_route", []) or [],
                    "nearby_attractions": attr.get("nearby_attractions", []) or [],
                    "best_time": attr.get("best_time", ""),
                    "avoid_tips": attr.get("avoid_tips", []) or [],
                    "source": attr.get("source", "database"),
                    # 新增字段：开放时间、门票、评分、评论数、图片
                    "open_hours": attr.get("open_hours", ""),
                    "ticket_price": attr.get("ticket_price", ""),
                    "rating": float(attr.get("rating", 0)) if attr.get("rating") else 0,
                    "review_count": int(attr.get("review_count", 0)) if attr.get("review_count") else 0,
                    "images": attr.get("images", []) or [],
                }
                result.append(item)

            # 更新缓存
            self._db_cache = result
            self._db_cache_time = current_time
            return result
        except Exception:
            # 数据库查询失败时，如果有旧缓存则返回旧缓存
            if self._db_cache is not None:
                return self._db_cache
            return []

    def refresh_cache(self) -> None:
        """刷新缓存（后台管理数据更新后调用）。"""
        self._db_cache = None
        self._db_cache_time = 0
        self._by_city = None
        self._by_name = None

    def _build_indexes(self) -> None:
        """构建索引（按城市、按名称），优先从数据库获取，数据库没有时从静态库获取。"""
        if self._by_city is not None and self._by_name is not None:
            return

        # 优先从数据库获取
        attractions = self._load_db_attractions()

        # 如果数据库没有，从静态库获取
        if not attractions:
            attractions = self._load_static_attractions()

        self._by_city = {}
        self._by_name = {}

        for attr in attractions:
            city = attr.get("city", "")
            name = attr.get("name", "")

            if city:
                if city not in self._by_city:
                    self._by_city[city] = []
                self._by_city[city].append(attr)

            if name:
                self._by_name[name] = attr
                # 别名也建立索引
                for alias in attr.get("aliases", []):
                    if alias and alias not in self._by_name:
                        self._by_name[alias] = attr

    def get_major_attractions_by_city(self, city: str) -> List[Dict[str, Any]]:
        """
        根据城市获取主要景点。

        Args:
            city: 城市名称（支持带"市"后缀和不带后缀）

        Returns:
            List[Dict[str, Any]]: 主要景点列表
        """
        self._build_indexes()

        # 标准化城市名称（去掉"市"后缀）
        city_normalized = city.rstrip("市")

        # 尝试多种匹配方式
        for candidate in [city, city_normalized, city + "市"]:
            if candidate in self._by_city:
                return self._by_city[candidate]

        return []

    def get_major_attraction_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        根据名称获取主要景点。

        Args:
            name: 景点名称（支持别名）

        Returns:
            Optional[Dict[str, Any]]: 主要景点信息，找不到返回None
        """
        self._build_indexes()
        return self._by_name.get(name)

    def get_all_cities(self) -> List[str]:
        """
        获取所有有主要景点的城市。

        Returns:
            List[str]: 城市名称列表（排序后）
        """
        self._build_indexes()
        return sorted(self._by_city.keys())

    def get_stats(self) -> Dict[str, Any]:
        """
        获取主要景点库统计信息。

        Returns:
            Dict[str, Any]: 统计信息
        """
        attractions = self._load_static_attractions()
        self._build_indexes()
        return {
            "total_attractions": len(attractions),
            "total_cities": len(self._by_city),
            "cities": self.get_all_cities(),
        }

    async def merge_with_poi_data(
        self,
        city: str,
        poi_data: List[Dict[str, Any]],
        include_coordinates: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        将主要景点与POI数据混合。

        Args:
            city: 城市名称
            poi_data: 高德POI数据
            include_coordinates: 是否需要解析坐标（主要景点可能没有坐标）

        Returns:
            List[Dict[str, Any]]: 混合后的景点列表（主要景点在前，POI数据在后）
        """
        # 获取主要景点（静态库 + AI生成兜底）
        major_attractions = await self.get_or_generate_major_attractions(city)
        if not major_attractions:
            return poi_data

        # 已存在的景点名称集合（用于去重）
        existing_names = {poi.get("name", "") for poi in poi_data}

        # 主要景点转换为POI格式
        major_pois = []
        for attr in major_attractions:
            name = attr.get("name", "")
            if not name or name in existing_names:
                # 如果主要景点已经在POI数据中，补充must_visit和hot标记
                for poi in poi_data:
                    if poi.get("name") == name:
                        poi["must_visit"] = True
                        poi["hot"] = attr.get("hot", True)
                        poi["rating"] = max(poi.get("rating") or 0, 4.8)
                        if "description" not in poi or not poi["description"]:
                            poi["description"] = attr.get("description", "")
                continue

            # 构建POI格式的主要景点
            poi = {
                "id": f"major_{name}",
                "name": name,
                "category": attr.get("category", "景点"),
                "rating": attr.get("rating", 4.8) if attr.get("rating", 0) > 0 else 4.8,
                "address": "",
                "district": attr.get("district", ""),
                "cityname": city,
                "must_visit": True,
                "hot": attr.get("hot", True),
                "description": attr.get("description", ""),
                "recommended_duration": attr.get("recommended_duration", 120),
                "source": "major_attractions",  # 标记来源
                # 新增字段：开放时间、门票、评分、评论数、图片
                "open_hours": attr.get("open_hours", ""),
                "ticket_price": attr.get("ticket_price", ""),
                "review_count": attr.get("review_count", 0),
                "images": attr.get("images", []),
                "best_time": attr.get("best_time", ""),
                "level": attr.get("level", ""),
            }

            # 如果主要景点有坐标，直接使用
            if "lng" in attr and "lat" in attr:
                poi["lng"] = attr["lng"]
                poi["lat"] = attr["lat"]
            elif include_coordinates:
                # 如果需要坐标，尝试从地理编码服务获取
                try:
                    from .. import map as amap

                    geo = await amap.geocode(f"{city}{name}")
                    if geo:
                        poi["lng"] = float(geo["lng"])
                        poi["lat"] = float(geo["lat"])
                except Exception:
                    # 地理编码失败，使用城市中心坐标
                    try:
                        from .. import map as amap

                        geo = await amap.geocode(city)
                        if geo:
                            poi["lng"] = float(geo["lng"])
                            poi["lat"] = float(geo["lat"])
                            poi["approximate"] = True
                    except Exception:
                        pass

            major_pois.append(poi)
            existing_names.add(name)

        # 主要景点在前，POI数据在后
        return major_pois + poi_data

    async def generate_major_attractions_by_ai(
        self,
        city: str,
        count: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        使用AI生成城市的主要景点列表。

        Args:
            city: 城市名称
            count: 生成的景点数量

        Returns:
            List[Dict[str, Any]]: 主要景点列表
        """
        try:
            from ..ai import ai as ai_mod

            prompt = f"""请列出{city}的{count}个最著名、最值得游览的主要景点。

要求：
1. 只列出景点名称，不要其他解释
2. 按照知名度和推荐度排序
3. 包含5A景区、世界遗产、城市地标等
4. 不要列出美食、购物、住宿等非景点类地点
5. 输出严格JSON格式：{{"attractions": ["景点1", "景点2", ...]}}

示例：
{{"attractions": ["故宫", "天安门广场", "八达岭长城", "颐和园", "天坛"]}}"""

            messages = [{"role": "user", "content": prompt}]
            response = await ai_mod.chat_reply(messages)

            if response:
                # 解析JSON响应
                # 尝试提取JSON
                json_match = re.search(r"\{[^{}]*\}", response)
                if json_match:
                    try:
                        data = json.loads(json_match.group())
                        attractions = data.get("attractions", [])
                        if attractions:
                            # 转换为主要景点格式
                            result = []
                            for name in attractions[:count]:
                                result.append(
                                    {
                                        "name": name,
                                        "aliases": [],
                                        "city": city,
                                        "district": "",
                                        "level": "",
                                        "category": "景点",
                                        "description": f"{city}著名景点",
                                        "recommended_duration": 120,
                                        "must_visit": True,
                                        "hot": True,
                                        "tags": [],
                                        "source": "ai_generated",
                                    }
                                )
                            return result
                    except Exception:
                        pass
        except Exception:
            pass

        return []

    async def get_or_generate_major_attractions(
        self,
        city: str,
        use_ai_fallback: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        获取城市的主要景点，如果静态库中没有，使用AI生成。

        Args:
            city: 城市名称
            use_ai_fallback: 是否使用AI生成作为兜底

        Returns:
            List[Dict[str, Any]]: 主要景点列表
        """
        # 先从静态库获取
        static_attractions = self.get_major_attractions_by_city(city)
        if static_attractions:
            return static_attractions

        # 如果静态库中没有，使用AI生成
        if use_ai_fallback:
            ai_attractions = await self.generate_major_attractions_by_ai(city)
            if ai_attractions:
                # 缓存AI生成的结果（运行时缓存，不持久化）
                city_normalized = city.rstrip("市")
                if city_normalized not in self._ai_cache:
                    self._ai_cache[city_normalized] = ai_attractions
                return ai_attractions

        return []


# 单例
_major_attractions_service: Optional[MajorAttractionsService] = None


def get_major_attractions_service() -> MajorAttractionsService:
    """
    获取主要景点库服务单例。

    Returns:
        MajorAttractionsService: 全局主要景点库服务单例
    """
    global _major_attractions_service
    if _major_attractions_service is None:
        _major_attractions_service = MajorAttractionsService()
    return _major_attractions_service
