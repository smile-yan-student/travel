"""
数据提纯模块 - 从搜索结果中提取结构化的行程信息

核心功能：
1. 景点列表提取（从文本中识别景点名称）
2. 频率统计（多篇攻略中景点出现的频率）
3. 游览顺序提取（每日景点顺序）
4. 耗时估算（每个景点的游览耗时）
5. 避坑提示提取
6. 预约规则提取
7. 多攻略交叉验证

设计理念：
- 从非结构化的网页文本中提取结构化的行程信息
- 多攻略交叉验证，取高频出现的景点和顺序
- 为规划引擎提供真实、经过验证的基础数据

实现方式：
- 基础版本：规则提取（正则表达式、关键词匹配）
- 进阶版本：LLM辅助提取（准确率更高，成本较高）
"""
import logging
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class AttractionInfo:
    """景点信息"""
    name: str
    frequency: int = 0  # 出现频率
    avg_duration: int = 0  # 平均游览时长（分钟）
    area: str = ""  # 区域
    is_must_visit: bool = False  # 是否必去
    is_optional: bool = False  # 是否可选
    order_count: Dict[str, int] = field(default_factory=dict)  # 出现顺序统计

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "frequency": self.frequency,
            "avg_duration": self.avg_duration,
            "area": self.area,
            "is_must_visit": self.is_must_visit,
            "is_optional": self.is_optional,
        }


@dataclass
class DailyItinerary:
    """每日行程"""
    day: int
    attractions: List[str] = field(default_factory=list)
    frequency: int = 0

    def to_dict(self) -> dict:
        return {
            "day": self.day,
            "attractions": self.attractions,
            "frequency": self.frequency,
        }


@dataclass
class TravelTip:
    """旅游提示"""
    tip: str
    category: str = "general"  # general/reservation/anti_fraud/traffic/food/accommodation
    frequency: int = 0

    def to_dict(self) -> dict:
        return {
            "tip": self.tip,
            "category": self.category,
            "frequency": self.frequency,
        }


@dataclass
class ExtractedData:
    """提纯后的数据"""
    destination: str
    attractions: Dict[str, AttractionInfo] = field(default_factory=dict)
    daily_itineraries: List[DailyItinerary] = field(default_factory=list)
    tips: List[TravelTip] = field(default_factory=list)
    total_guides: int = 0
    confidence: float = 0.0  # 数据置信度（基于攻略数量和频率）

    def to_dict(self) -> dict:
        return {
            "destination": self.destination,
            "attractions": {k: v.to_dict() for k, v in self.attractions.items()},
            "daily_itineraries": [d.to_dict() for d in self.daily_itineraries],
            "tips": [t.to_dict() for t in self.tips],
            "total_guides": self.total_guides,
            "confidence": self.confidence,
        }


class DataExtractor:
    """数据提纯器"""

    # 常见景点关键词后缀（用于识别景点名称）
    ATTRACTION_SUFFIXES = [
        "景区", "景点", "公园", "博物馆", "纪念馆", "寺", "庙", "塔",
        "湖", "山", "岛", "湾", "滩", "瀑", "泉", "洞", "峡", "谷",
        "古镇", "古城", "古街", "老街", "步行街", "广场", "大街",
        "大学", "学院", "图书馆", "美术馆", "展览馆", "科技馆",
        "动物园", "植物园", "海洋馆", "游乐园", "主题乐园",
        "长城", "故宫", "颐和园", "天坛", "圆明园", "鸟巢", "水立方",
    ]

    # 时间关键词（用于识别游览时长）
    DURATION_PATTERNS = [
        r"(\d+)\s*小时",
        r"(\d+)\s*个小时",
        r"(\d+)\s*分钟",
        r"约\s*(\d+)\s*小时",
        r"大概\s*(\d+)\s*小时",
        r"需要\s*(\d+)\s*小时",
        r"游玩\s*(\d+)\s*小时",
        r"游览\s*(\d+)\s*小时",
    ]

    # 天数关键词
    DAY_PATTERNS = [
        r"第\s*([一二三四五六七八九十\d]+)\s*天",
        r"Day\s*(\d+)",
        r"day\s*(\d+)",
        r"D(\d+)",
    ]

    # 避坑提示关键词
    TIP_KEYWORDS = {
        "reservation": ["预约", "提前", "放票", "抢票", "闭馆", "周一", "周二"],
        "anti_fraud": ["黑导游", "一日游", "被骗", "坑", "套路", "黄牛", "假的"],
        "traffic": ["地铁", "公交", "打车", "自驾", "停车", "堵车", "交通"],
        "food": ["美食", "小吃", "餐厅", "排队", "必吃", "老字号"],
        "accommodation": ["住宿", "酒店", "民宿", "住哪里", "区域"],
    }

    def __init__(self):
        self._initialized = False

    async def _initialize(self):
        """初始化（懒加载）"""
        if self._initialized:
            return
        self._initialized = True

    async def extract(
        self,
        destination: str,
        search_results: List[Dict[str, Any]],
    ) -> ExtractedData:
        """
        从搜索结果中提纯数据

        Args:
            destination: 目的地
            search_results: 搜索结果列表

        Returns:
            提纯后的数据
        """
        await self._initialize()

        extracted = ExtractedData(destination=destination)
        extracted.total_guides = len(search_results)

        if not search_results:
            logger.warning(f"没有搜索结果，无法提纯: {destination}")
            return extracted

        # 1. 提取所有文本内容
        all_texts = []
        for result in search_results:
            content = result.get("content", "")
            title = result.get("title", "")
            if content:
                all_texts.append(f"{title}\n{content}")

        if not all_texts:
            logger.warning(f"搜索结果没有文本内容: {destination}")
            return extracted

        # 2. 提取景点列表和频率
        self._extract_attractions(all_texts, extracted)

        # 3. 提取游览顺序
        self._extract_daily_itineraries(all_texts, extracted)

        # 4. 提取游览时长
        self._extract_durations(all_texts, extracted)

        # 5. 提取避坑提示
        self._extract_tips(all_texts, extracted)

        # 6. 计算置信度
        self._calculate_confidence(extracted)

        logger.info(
            f"数据提纯完成: {destination}, "
            f"景点数: {len(extracted.attractions)}, "
            f"行程数: {len(extracted.daily_itineraries)}, "
            f"提示数: {len(extracted.tips)}, "
            f"置信度: {extracted.confidence:.2f}"
        )

        return extracted

    def _extract_attractions(self, texts: List[str], extracted: ExtractedData):
        """提取景点列表和频率"""
        attraction_counter = Counter()

        for text in texts:
            # 方法1：基于后缀匹配
            for suffix in self.ATTRACTION_SUFFIXES:
                # 匹配 "XX景区"、"XX公园" 等模式
                pattern = r'([\u4e00-\u9fffA-Za-z0-9]{2,15}' + re.escape(suffix) + r')'
                matches = re.findall(pattern, text)
                for match in matches:
                    # 过滤掉一些常见的非景点词
                    if self._is_valid_attraction(match):
                        attraction_counter[match] += 1

            # 方法2：基于已知景点列表（可以从数据库或配置中加载）
            # 这里暂时只使用后缀匹配

        # 按频率排序
        for name, count in attraction_counter.most_common():
            info = AttractionInfo(
                name=name,
                frequency=count,
            )
            # 判定必去/可选
            if count >= max(3, len(texts) * 0.3):
                info.is_must_visit = True
            elif count >= max(1, len(texts) * 0.1):
                info.is_optional = True

            extracted.attractions[name] = info

        logger.debug(f"提取景点: {len(extracted.attractions)}个")

    def _is_valid_attraction(self, name: str) -> bool:
        """判断是否为有效的景点名称"""
        # 过滤掉一些常见的非景点词
        invalid_words = [
            "旅游景区", "风景区", "景区门票", "景区介绍",
            "公园门票", "公园介绍", "博物馆门票",
            "这个景区", "那个公园", "该景点",
            "必去景点", "景点推荐", "旅游景点", "景点大全",
            "打卡景点", "热门景点", "著名景点",
            "不要参加", "不要去", "建议不要",
            "游览故宫", "参观故宫", "游玩长城",
            "北京必去", "上海必去", "杭州必去",
        ]
        for word in invalid_words:
            if word in name:
                return False

        # 长度过滤
        if len(name) < 2 or len(name) > 20:
            return False

        # 不能以动词开头（如"游览"、"参观"、"游玩"、"不要"等）
        verb_prefixes = ["游览", "参观", "游玩", "不要", "建议", "推荐", "必去", "打卡"]
        for prefix in verb_prefixes:
            if name.startswith(prefix):
                return False

        # 不能包含完整句子（长度过长或包含标点）
        if any(char in name for char in "，。！？、；："):
            return False

        return True

    def _extract_daily_itineraries(self, texts: List[str], extracted: ExtractedData):
        """提取每日行程顺序"""
        day_attractions = defaultdict(Counter)

        for text in texts:
            # 按天分割文本
            day_sections = self._split_by_day(text)

            for day_num, section_text in day_sections.items():
                # 在每天的文本中提取景点
                for suffix in self.ATTRACTION_SUFFIXES:
                    pattern = r'([\u4e00-\u9fffA-Za-z0-9]{2,15}' + re.escape(suffix) + r')'
                    matches = re.findall(pattern, section_text)
                    for match in matches:
                        if self._is_valid_attraction(match) and match in extracted.attractions:
                            day_attractions[day_num][match] += 1

        # 构建每日行程
        for day_num in sorted(day_attractions.keys()):
            attractions = [
                name for name, count in day_attractions[day_num].most_common(10)
            ]
            if attractions:
                itinerary = DailyItinerary(
                    day=day_num,
                    attractions=attractions,
                    frequency=sum(day_attractions[day_num].values()),
                )
                extracted.daily_itineraries.append(itinerary)

        logger.debug(f"提取每日行程: {len(extracted.daily_itineraries)}天")

    def _split_by_day(self, text: str) -> Dict[int, str]:
        """按天分割文本"""
        sections = {}
        current_day = 0
        current_text = []

        lines = text.split("\n")
        for line in lines:
            # 检测天数标记
            day_num = self._detect_day(line)
            if day_num:
                # 保存上一天的内容
                if current_day > 0 and current_text:
                    sections[current_day] = "\n".join(current_text)
                current_day = day_num
                current_text = [line]
            else:
                if current_day > 0:
                    current_text.append(line)

        # 保存最后一天
        if current_day > 0 and current_text:
            sections[current_day] = "\n".join(current_text)

        return sections

    def _detect_day(self, text: str) -> Optional[int]:
        """检测天数标记"""
        # 中文数字映射
        chinese_numbers = {
            "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
            "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
        }

        for pattern in self.DAY_PATTERNS:
            match = re.search(pattern, text)
            if match:
                day_str = match.group(1)
                # 中文数字转换
                if day_str in chinese_numbers:
                    return chinese_numbers[day_str]
                # 阿拉伯数字
                try:
                    return int(day_str)
                except ValueError:
                    pass

        return None

    def _extract_durations(self, texts: List[str], extracted: ExtractedData):
        """提取游览时长"""
        for attraction_name, info in extracted.attractions.items():
            durations = []

            for text in texts:
                # 在景点名称附近查找时长
                # 找到景点名称的位置
                pos = text.find(attraction_name)
                if pos >= 0:
                    # 在景点名称前后200字符内查找时长
                    context = text[max(0, pos - 100):pos + len(attraction_name) + 100]

                    for pattern in self.DURATION_PATTERNS:
                        matches = re.findall(pattern, context)
                        for match in matches:
                            try:
                                duration = int(match)
                                # 如果是小时，转换为分钟
                                if "小时" in pattern or "个小时" in pattern:
                                    duration *= 60
                                # 合理范围过滤（10分钟 - 8小时）
                                if 10 <= duration <= 480:
                                    durations.append(duration)
                            except ValueError:
                                pass

            if durations:
                # 取平均值
                info.avg_duration = int(sum(durations) / len(durations))
                logger.debug(f"景点 {attraction_name} 平均时长: {info.avg_duration}分钟")

    def _extract_tips(self, texts: List[str], extracted: ExtractedData):
        """提取避坑提示"""
        tip_counter = Counter()
        tip_categories = {}

        for text in texts:
            # 按句子分割
            sentences = re.split(r'[。！？\n]', text)

            for sentence in sentences:
                sentence = sentence.strip()
                if len(sentence) < 5 or len(sentence) > 100:
                    continue

                # 检测提示类别
                category = "general"
                for cat, keywords in self.TIP_KEYWORDS.items():
                    if any(keyword in sentence for keyword in keywords):
                        category = cat
                        break

                if category != "general":
                    # 这是一个有效的提示
                    tip_counter[sentence] += 1
                    tip_categories[sentence] = category

        # 按频率排序
        for tip, count in tip_counter.most_common(20):
            if count >= 1:  # 至少出现1次
                travel_tip = TravelTip(
                    tip=tip,
                    category=tip_categories.get(tip, "general"),
                    frequency=count,
                )
                extracted.tips.append(travel_tip)

        logger.debug(f"提取避坑提示: {len(extracted.tips)}条")

    def _calculate_confidence(self, extracted: ExtractedData):
        """计算数据置信度"""
        if extracted.total_guides == 0:
            extracted.confidence = 0.0
            return

        # 基于攻略数量
        guide_score = min(extracted.total_guides / 10, 1.0) * 0.3

        # 基于景点频率（必去景点的平均频率）
        must_visit_freqs = [
            info.frequency for info in extracted.attractions.values()
            if info.is_must_visit
        ]
        if must_visit_freqs:
            avg_freq = sum(must_visit_freqs) / len(must_visit_freqs)
            freq_score = min(avg_freq / extracted.total_guides, 1.0) * 0.4
        else:
            freq_score = 0.0

        # 基于行程天数
        itinerary_score = min(len(extracted.daily_itineraries) / 3, 1.0) * 0.2

        # 基于提示数量
        tip_score = min(len(extracted.tips) / 10, 1.0) * 0.1

        extracted.confidence = guide_score + freq_score + itinerary_score + tip_score
        extracted.confidence = min(extracted.confidence, 1.0)


# 单例
_data_extractor: Optional[DataExtractor] = None


def get_data_extractor() -> DataExtractor:
    """获取数据提纯器单例"""
    global _data_extractor
    if _data_extractor is None:
        _data_extractor = DataExtractor()
    return _data_extractor
