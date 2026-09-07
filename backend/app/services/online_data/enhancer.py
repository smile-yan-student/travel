"""
在线数据增强器 - 在规划引擎的各个阶段注入在线数据

核心功能：
1. 获取目的地的在线数据（攻略、景点、避坑提示、预约规则）
2. 从攻略中提取结构化信息（景点列表、游览顺序、耗时估算）
3. 在POI搜索阶段合并在线数据的景点列表
4. 在地理聚类阶段参考在线数据的游览顺序
5. 在逐日构建阶段参考在线数据的耗时估算
6. 在输出阶段添加避坑提示和预约规则

设计理念：
- 不修改规划引擎的核心逻辑，而是通过"增强器"在关键节点注入在线数据
- 在线数据作为"参考依据"和"补充数据"，规划引擎仍然保留最终决策权
- 支持开关控制，可以随时启用或禁用在线数据增强
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class OnlineDataContext:
    """在线数据上下文 - 存储一次规划过程中的所有在线数据"""
    destination: str = ""
    days: int = 0

    # 从攻略中提取的结构化数据
    extracted_attractions: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # 景点名 -> {frequency, duration, area, is_must_visit}
    extracted_itineraries: List[Dict[str, Any]] = field(default_factory=list)  # 每日行程参考
    extracted_tips: List[Dict[str, Any]] = field(default_factory=list)  # 避坑提示

    # 从数据库获取的结构化数据
    attraction_rules: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # 景点名 -> 预约规则
    travel_tips: List[Dict[str, Any]] = field(default_factory=list)  # 避坑提示

    # 状态
    is_loaded: bool = False
    load_time: float = 0
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "destination": self.destination,
            "days": self.days,
            "extracted_attractions_count": len(self.extracted_attractions),
            "extracted_itineraries_count": len(self.extracted_itineraries),
            "extracted_tips_count": len(self.extracted_tips),
            "attraction_rules_count": len(self.attraction_rules),
            "travel_tips_count": len(self.travel_tips),
            "is_loaded": self.is_loaded,
            "load_time": self.load_time,
            "confidence": self.confidence,
        }


class OnlineDataEnhancer:
    """在线数据增强器"""

    # 开关：是否启用在线数据增强
    ENABLED = True

    # 在线数据的权重（0-1，越高表示越依赖在线数据）
    ONLINE_DATA_WEIGHT = 0.6

    def __init__(self):
        self._initialized = False
        self._search_service = None
        self._search_cache = None
        self._data_extractor = None
        self._attraction_rules = None
        self._travel_tips = None

    async def _initialize(self):
        """初始化（懒加载）"""
        if self._initialized:
            return
        try:
            from app.services.online_data import (
                get_search_service,
                get_search_cache,
                get_data_extractor,
                get_attraction_rules,
                get_travel_tips,
            )
            self._search_service = get_search_service()
            self._search_cache = get_search_cache()
            self._data_extractor = get_data_extractor()
            self._attraction_rules = get_attraction_rules()
            self._travel_tips = get_travel_tips()
            logger.info("在线数据增强器初始化成功")
        except Exception as e:
            logger.warning(f"在线数据增强器初始化失败: {e}")
        self._initialized = True

    async def load_online_data(
        self,
        destination: str,
        days: int = 3,
        enable_search: bool = False,
    ) -> OnlineDataContext:
        """
        加载目的地的在线数据

        Args:
            destination: 目的地
            days: 天数
            enable_search: 是否启用在线搜索（默认关闭，使用数据库缓存数据）

        Returns:
            在线数据上下文
        """
        await self._initialize()

        context = OnlineDataContext(
            destination=destination,
            days=days,
        )

        if not self.ENABLED:
            logger.info("在线数据增强已禁用，跳过加载")
            return context

        start_time = time.time()

        try:
            # 1. 从数据库获取预约规则
            await self._load_attraction_rules(context, destination)

            # 2. 从数据库获取避坑提示
            await self._load_travel_tips(context, destination)

            # 3. 如果启用搜索，从在线搜索获取攻略数据
            if enable_search and self._search_service:
                await self._load_from_search(context, destination, days)

            context.is_loaded = True
            context.load_time = time.time() - start_time

            # 计算置信度
            context.confidence = self._calculate_confidence(context)

            logger.info(
                f"在线数据加载完成: {destination}, "
                f"预约规则: {len(context.attraction_rules)}, "
                f"避坑提示: {len(context.travel_tips)}, "
                f"提取景点: {len(context.extracted_attractions)}, "
                f"置信度: {context.confidence:.2f}, "
                f"耗时: {context.load_time:.2f}s"
            )

        except Exception as e:
            logger.warning(f"在线数据加载失败: {destination}, 错误: {e}")
            context.is_loaded = False

        return context

    async def _load_attraction_rules(self, context: OnlineDataContext, destination: str):
        """从数据库加载预约规则"""
        if not self._attraction_rules:
            return

        try:
            rules = await self._attraction_rules.get_by_destination(destination)
            for rule in rules:
                context.attraction_rules[rule.attraction_name] = rule.to_dict()
            logger.debug(f"加载预约规则: {len(rules)}条")
        except Exception as e:
            logger.warning(f"加载预约规则失败: {e}")

    async def _load_travel_tips(self, context: OnlineDataContext, destination: str):
        """从数据库加载避坑提示"""
        if not self._travel_tips:
            return

        try:
            tips = await self._travel_tips.get_by_destination(destination, limit=20)
            context.travel_tips = [tip.to_dict() for tip in tips]
            logger.debug(f"加载避坑提示: {len(tips)}条")
        except Exception as e:
            logger.warning(f"加载避坑提示失败: {e}")

    async def _load_from_search(self, context: OnlineDataContext, destination: str, days: int):
        """从在线搜索加载攻略数据"""
        if not self._search_service or not self._data_extractor:
            return

        try:
            # 搜索目的地攻略
            search_results = await self._search_service.search_destination_guides(
                destination=destination,
                days=days,
                max_results=5,
            )

            if not search_results:
                logger.debug(f"未搜索到攻略: {destination}")
                return

            # 转换搜索结果格式
            results_dict = [
                {
                    "title": r.title,
                    "url": r.url,
                    "content": r.content,
                    "source": r.source,
                }
                for r in search_results
            ]

            # 数据提纯
            extracted = await self._data_extractor.extract(destination, results_dict)

            # 存储提取结果
            context.extracted_attractions = {
                name: info.to_dict()
                for name, info in extracted.attractions.items()
            }
            context.extracted_itineraries = [
                itinerary.to_dict()
                for itinerary in extracted.daily_itineraries
            ]
            context.extracted_tips = [
                tip.to_dict()
                for tip in extracted.tips
            ]

            logger.debug(
                f"从搜索提取数据: 景点={len(context.extracted_attractions)}, "
                f"行程={len(context.extracted_itineraries)}, "
                f"提示={len(context.extracted_tips)}"
            )

        except Exception as e:
            logger.warning(f"从搜索加载数据失败: {e}")

    def _calculate_confidence(self, context: OnlineDataContext) -> float:
        """计算在线数据置信度"""
        score = 0.0

        # 预约规则（30%）
        if context.attraction_rules:
            score += min(len(context.attraction_rules) / 5, 1.0) * 0.3

        # 避坑提示（20%）
        if context.travel_tips:
            score += min(len(context.travel_tips) / 10, 1.0) * 0.2

        # 提取的景点（30%）
        if context.extracted_attractions:
            must_visit_count = sum(
                1 for attr in context.extracted_attractions.values()
                if attr.get("is_must_visit")
            )
            score += min(must_visit_count / 3, 1.0) * 0.3

        # 提取的行程（20%）
        if context.extracted_itineraries:
            score += min(len(context.extracted_itineraries) / context.days, 1.0) * 0.2

        return min(score, 1.0)

    def enhance_poi_list(
        self,
        poi_list: List[Dict[str, Any]],
        context: OnlineDataContext,
    ) -> List[Dict[str, Any]]:
        """
        增强POI列表 - 合并在线数据中的景点

        Args:
            poi_list: 原始POI列表
            context: 在线数据上下文

        Returns:
            增强后的POI列表
        """
        if not context.is_loaded or not context.extracted_attractions:
            return poi_list

        try:
            # 获取现有POI的名称集合
            existing_names = set()
            for poi in poi_list:
                name = poi.get("name", "") or poi.get("title", "")
                if name:
                    existing_names.add(name)
                    # 也添加简化名称（去掉后缀）
                    simple_name = self._simplify_name(name)
                    if simple_name:
                        existing_names.add(simple_name)

            # 从在线数据中添加缺失的景点
            added_count = 0
            for attr_name, attr_info in context.extracted_attractions.items():
                # 检查是否已存在
                if attr_name in existing_names:
                    continue
                simple_name = self._simplify_name(attr_name)
                if simple_name and simple_name in existing_names:
                    continue

                # 只添加必去或可选景点
                if not attr_info.get("is_must_visit") and not attr_info.get("is_optional"):
                    continue

                # 创建POI对象
                new_poi = {
                    "name": attr_name,
                    "title": attr_name,
                    "source": "online_data",
                    "is_must_visit": attr_info.get("is_must_visit", False),
                    "is_optional": attr_info.get("is_optional", False),
                    "frequency": attr_info.get("frequency", 0),
                    "avg_duration": attr_info.get("avg_duration", 0),
                    "area": attr_info.get("area", ""),
                    "lng": 0,  # 需要后续地理编码
                    "lat": 0,
                }

                # 如果有预约规则，添加预约信息
                if attr_name in context.attraction_rules:
                    rule = context.attraction_rules[attr_name]
                    new_poi["reservation"] = {
                        "channel": rule.get("reservation_channel", ""),
                        "ticket_release_time": rule.get("ticket_release_time", ""),
                        "opening_hours": rule.get("opening_hours", ""),
                        "closing_days": rule.get("closing_days", ""),
                        "ticket_price": rule.get("ticket_price", ""),
                        "visitor_route": rule.get("visitor_route", ""),
                    }

                poi_list.append(new_poi)
                added_count += 1

            if added_count > 0:
                logger.info(
                    f"在线数据增强POI列表: 添加{added_count}个景点, "
                    f"总数: {len(poi_list)}"
                )

        except Exception as e:
            logger.warning(f"增强POI列表失败: {e}")

        return poi_list

    def enhance_itinerary_order(
        self,
        daily_attractions: Dict[int, List[str]],
        context: OnlineDataContext,
    ) -> Dict[int, List[str]]:
        """
        增强每日行程顺序 - 参考在线数据的游览顺序

        Args:
            daily_attractions: 原始每日行程 {day: [景点名列表]}
            context: 在线数据上下文

        Returns:
            增强后的每日行程
        """
        if not context.is_loaded or not context.extracted_itineraries:
            return daily_attractions

        try:
            # 构建在线数据的游览顺序参考
            order_reference = {}  # 景点名 -> (day, index)
            for itinerary in context.extracted_itineraries:
                day = itinerary.get("day", 0)
                attractions = itinerary.get("attractions", [])
                for idx, attr_name in enumerate(attractions):
                    if attr_name not in order_reference:
                        order_reference[attr_name] = (day, idx)

            # 对每天的景点进行排序优化
            enhanced = {}
            for day, attractions in daily_attractions.items():
                # 计算每个景点的排序分数
                scored = []
                for idx, attr_name in enumerate(attractions):
                    score = idx  # 原始顺序作为基础分数
                    # 如果在线数据中有参考顺序，调整分数
                    if attr_name in order_reference:
                        ref_day, ref_idx = order_reference[attr_name]
                        # 如果参考天数相同，使用参考索引
                        if ref_day == day:
                            score = ref_idx * 0.7 + idx * 0.3
                        # 如果参考天数不同，轻微调整
                        else:
                            score = idx * 0.8 + ref_idx * 0.2
                    scored.append((attr_name, score))

                # 按分数排序
                scored.sort(key=lambda x: x[1])
                enhanced[day] = [name for name, _ in scored]

            logger.debug(f"在线数据增强行程顺序: {len(enhanced)}天")

        except Exception as e:
            logger.warning(f"增强行程顺序失败: {e}")
            enhanced = daily_attractions

        return enhanced

    def enhance_duration_estimation(
        self,
        attraction_name: str,
        default_duration: int,
        context: OnlineDataContext,
    ) -> int:
        """
        增强耗时估算 - 参考在线数据的平均耗时

        Args:
            attraction_name: 景点名称
            default_duration: 默认耗时（分钟）
            context: 在线数据上下文

        Returns:
            增强后的耗时（分钟）
        """
        if not context.is_loaded:
            return default_duration

        try:
            # 从提取的景点中获取耗时
            if attraction_name in context.extracted_attractions:
                online_duration = context.extracted_attractions[attraction_name].get("avg_duration", 0)
                if online_duration > 0:
                    # 加权平均：在线数据60% + 默认值40%
                    enhanced = int(online_duration * self.ONLINE_DATA_WEIGHT + default_duration * (1 - self.ONLINE_DATA_WEIGHT))
                    return max(enhanced, 30)  # 最少30分钟

        except Exception as e:
            logger.debug(f"增强耗时估算失败: {attraction_name}, {e}")

        return default_duration

    def get_enhanced_output(
        self,
        context: OnlineDataContext,
    ) -> Dict[str, Any]:
        """
        获取增强输出 - 预约提醒、避坑提示等

        Args:
            context: 在线数据上下文

        Returns:
            增强输出数据
        """
        if not context.is_loaded:
            return {}

        output = {}

        try:
            # 预约提醒
            if context.attraction_rules:
                reservation_alerts = []
                for attr_name, rule in context.attraction_rules.items():
                    alert = {
                        "attraction": attr_name,
                        "channel": rule.get("reservation_channel", ""),
                        "ticket_release_time": rule.get("ticket_release_time", ""),
                        "opening_hours": rule.get("opening_hours", ""),
                        "closing_days": rule.get("closing_days", ""),
                        "ticket_price": rule.get("ticket_price", ""),
                        "visitor_route": rule.get("visitor_route", ""),
                        "tips": rule.get("tips", ""),
                    }
                    reservation_alerts.append(alert)
                output["reservation_alerts"] = reservation_alerts

            # 避坑提示
            if context.travel_tips:
                travel_tips = []
                for tip in context.travel_tips:
                    travel_tips.append({
                        "tip": tip.get("tip", ""),
                        "category": tip.get("category", "general"),
                        "severity": tip.get("severity", "info"),
                    })
                output["travel_tips"] = travel_tips

            # 从攻略提取的避坑提示
            if context.extracted_tips:
                extracted_tips = []
                for tip in context.extracted_tips[:10]:  # 最多10条
                    extracted_tips.append({
                        "tip": tip.get("tip", ""),
                        "category": tip.get("category", "general"),
                        "frequency": tip.get("frequency", 0),
                    })
                output["extracted_tips"] = extracted_tips

            # 在线数据元信息
            output["online_data_meta"] = {
                "is_loaded": context.is_loaded,
                "confidence": context.confidence,
                "load_time": context.load_time,
                "attraction_rules_count": len(context.attraction_rules),
                "travel_tips_count": len(context.travel_tips),
                "extracted_attractions_count": len(context.extracted_attractions),
            }

        except Exception as e:
            logger.warning(f"获取增强输出失败: {e}")

        return output

    def _simplify_name(self, name: str) -> str:
        """简化景点名称（去掉后缀）"""
        suffixes = [
            "景区", "风景区", "景点", "公园", "博物馆", "纪念馆",
            "寺", "庙", "塔", "湖", "山", "岛", "湾", "滩",
            "古镇", "古城", "古街", "老街", "步行街", "广场",
            "大学", "学院", "图书馆", "美术馆", "展览馆",
            "动物园", "植物园", "海洋馆", "游乐园",
        ]
        for suffix in suffixes:
            if name.endswith(suffix) and len(name) > len(suffix) + 1:
                return name[:-len(suffix)]
        return name


# 单例
_online_data_enhancer: Optional[OnlineDataEnhancer] = None


def get_online_data_enhancer() -> OnlineDataEnhancer:
    """获取在线数据增强器单例"""
    global _online_data_enhancer
    if _online_data_enhancer is None:
        _online_data_enhancer = OnlineDataEnhancer()
    return _online_data_enhancer
