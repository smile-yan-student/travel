"""
在线数据服务模块
- SearchService: 搜索服务（封装公开网页搜索，支持多关键词策略）
- SearchCache: 搜索结果缓存（数据库持久化，避免重复搜索）
- DataExtractor: 数据提纯（从搜索结果中提取景点列表、频率统计、游览顺序、耗时估算）
- AttractionRules: 景点预约规则管理（预约渠道、放票时间、开放时间、票价、闭馆日）
- TravelTips: 旅游避坑提示管理（防骗、避坑、交通、美食等提示）

核心设计理念：以在线数据为依托，规划引擎增强。
- 在线数据提供：真实攻略、景点信息、游客经验、官方规则
- 规划引擎负责：用户偏好调整、时间容量校验、地理距离微调、多方案生成
"""
from .search_service import SearchService, get_search_service
from .search_cache import SearchCache, get_search_cache
from .data_extractor import DataExtractor, get_data_extractor, AttractionInfo, DailyItinerary, ExtractedData
from .attraction_rules import AttractionRules, get_attraction_rules, AttractionRule
from .travel_tips import TravelTips, get_travel_tips, TravelTip
from .enhancer import OnlineDataEnhancer, get_online_data_enhancer, OnlineDataContext
from .llm_extractor import LLMExtractor, get_llm_extractor, LLMExtractedData

__all__ = [
    "SearchService",
    "get_search_service",
    "SearchCache",
    "get_search_cache",
    "DataExtractor",
    "get_data_extractor",
    "AttractionInfo",
    "DailyItinerary",
    "ExtractedData",
    "AttractionRules",
    "get_attraction_rules",
    "AttractionRule",
    "TravelTips",
    "get_travel_tips",
    "TravelTip",
    "OnlineDataEnhancer",
    "get_online_data_enhancer",
    "OnlineDataContext",
    "LLMExtractor",
    "get_llm_extractor",
    "LLMExtractedData",
]
