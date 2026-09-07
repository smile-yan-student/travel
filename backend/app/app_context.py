#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
应用统一调度上下文（AppContext）。

作为整个应用的服务定位器（ServiceLocator），统一管理所有核心服务的实例化、
生命周期和访问入口，避免代码中到处散落的直接导入和实例化。

本阶段不改变现有目录结构，只增加 AppContext 作为可选的统一访问入口。
后续阶段逐步将代码中的直接导入改为通过 AppContext 访问。

使用方式：
    from app.app_context import get_app_context

    ctx = get_app_context()
    # 访问服务
    planner = ctx.planner          # 行程规划引擎
    llm = ctx.llm                  # AI大模型
    amap = ctx.map_client          # 地图服务
    db = ctx.db                    # 数据库连接
    cache = ctx.cache              # 缓存
    logger = ctx.logger            # 日志

设计原则：
1. 懒加载：服务只在首次访问时实例化，避免启动时加载所有依赖
2. 单例：每个服务在AppContext中只实例化一次
3. 可替换：服务可以通过set_xxx()方法替换，便于测试和mock
4. 统一入口：所有服务通过ctx访问，代码中不再散落直接导入
"""
import threading
from typing import Optional, Any, Dict, Callable


class AppContext:
    """
    应用统一调度上下文。

    管理所有核心服务的实例化和访问，提供统一的调用入口。
    """

    _instance: Optional['AppContext'] = None
    _lock = threading.Lock()

    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._factories: Dict[str, Callable] = {}
        self._initialized = False

    @classmethod
    def get_instance(cls) -> 'AppContext':
        """获取AppContext单例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register_factory(self, name: str, factory: Callable):
        """
        注册服务工厂函数。

        Args:
            name: 服务名称
            factory: 工厂函数，调用时返回服务实例
        """
        self._factories[name] = factory

    def get_service(self, name: str) -> Any:
        """
        获取服务实例（懒加载）。

        Args:
            name: 服务名称

        Returns:
            服务实例
        """
        if name not in self._services:
            with self._lock:
                if name not in self._services:
                    if name in self._factories:
                        self._services[name] = self._factories[name]()
                    else:
                        raise ValueError(f"服务 '{name}' 未注册，请先调用 register_factory()")
        return self._services[name]

    def set_service(self, name: str, instance: Any):
        """
        直接设置服务实例（用于测试或覆盖默认实现）。

        Args:
            name: 服务名称
            instance: 服务实例
        """
        self._services[name] = instance

    def has_service(self, name: str) -> bool:
        """检查服务是否已注册或已实例化"""
        return name in self._services or name in self._factories

    # ==================== 常用服务快捷属性 ====================

    @property
    def config(self):
        """应用配置"""
        return self.get_service('config')

    @property
    def db(self):
        """数据库连接"""
        return self.get_service('db')

    @property
    def cache(self):
        """缓存服务"""
        return self.get_service('cache')

    @property
    def logger(self):
        """日志服务"""
        return self.get_service('logger')

    @property
    def planner(self):
        """行程规划引擎"""
        return self.get_service('planner')

    @property
    def llm(self):
        """AI大模型服务"""
        return self.get_service('llm')

    @property
    def intent(self):
        """意图识别服务"""
        return self.get_service('intent')

    @property
    def map_client(self):
        """地图服务客户端"""
        return self.get_service('map_client')

    @property
    def geocode(self):
        """地理编码服务"""
        return self.get_service('geocode')

    @property
    def poi_search(self):
        """POI搜索服务"""
        return self.get_service('poi_search')

    @property
    def route_planner(self):
        """路径规划服务"""
        return self.get_service('route_planner')

    @property
    def weather(self):
        """天气服务"""
        return self.get_service('weather')

    @property
    def rag_retriever(self):
        """RAG检索服务"""
        return self.get_service('rag_retriever')

    @property
    def rag_generator(self):
        """RAG生成服务"""
        return self.get_service('rag_generator')

    @property
    def knowledge_service(self):
        """知识库服务"""
        return self.get_service('knowledge_service')

    @property
    def user_store(self):
        """用户存储"""
        return self.get_service('user_store')

    @property
    def admin_repository(self):
        """管理员存储"""
        return self.get_service('admin_repository')

    @property
    def dict_store(self):
        """字典数据存储"""
        return self.get_service('dict_store')

    @property
    def session_store(self):
        """会话存储"""
        return self.get_service('session_store')

    @property
    def security(self):
        """安全服务"""
        return self.get_service('security')

    @property
    def rate_limiter(self):
        """限流服务"""
        return self.get_service('rate_limiter')

    @property
    def circuit_breaker(self):
        """熔断器"""
        return self.get_service('circuit_breaker')

    @property
    def metrics(self):
        """监控指标"""
        return self.get_service('metrics')

    # ==================== 初始化 ====================

    def initialize(self, config=None):
        """
        初始化AppContext，注册所有默认服务工厂。

        本阶段不改变现有目录结构，只注册服务工厂。
        后续阶段逐步将代码中的直接导入改为通过 AppContext 访问。

        Args:
            config: 应用配置（可选，默认从app.config读取）
        """
        if self._initialized:
            return

        if config is None:
            from .config import settings
            config = settings

        self.set_service('config', config)

        # 注册基础设施服务工厂
        self.register_factory('logger', self._create_logger)
        self.register_factory('cache', self._create_cache)
        self.register_factory('db', self._create_db)
        self.register_factory('metrics', self._create_metrics)
        self.register_factory('circuit_breaker', self._create_circuit_breaker)

        # 注册安全服务工厂
        self.register_factory('rate_limiter', self._create_rate_limiter)

        # 注册数据访问服务工厂
        self.register_factory('user_store', self._create_user_store)
        self.register_factory('admin_repository', self._create_admin_store)
        self.register_factory('dict_store', self._create_dict_store)
        self.register_factory('session_store', self._create_session_store)

        # 注册地图服务工厂
        self.register_factory('map_client', self._create_map_client)
        self.register_factory('geocode', self._create_geocode)
        self.register_factory('poi_search', self._create_poi_search)
        self.register_factory('route_planner', self._create_route_planner)
        self.register_factory('weather', self._create_weather)

        # 注册AI服务工厂
        self.register_factory('llm', self._create_llm)
        self.register_factory('intent', self._create_intent)
        self.register_factory('rag_retriever', self._create_rag_retriever)
        self.register_factory('rag_generator', self._create_rag_generator)
        self.register_factory('knowledge_service', self._create_knowledge_service)

        # 注册核心服务工厂
        self.register_factory('planner', self._create_planner)

        self._initialized = True

    # ==================== 服务工厂方法 ====================

    def _create_logger(self):
        from .infrastructure.logger import setup_logging, get_logger
        setup_logging()
        return get_logger('app')

    def _create_cache(self):
        from .infrastructure.cache import cache
        return cache

    def _create_db(self):
        from .data.database import get_conn
        return get_conn

    def _create_metrics(self):
        from .infrastructure.metrics import MetricsRegistry
        return MetricsRegistry()

    def _create_circuit_breaker(self):
        from .infrastructure.circuit_breaker import get_circuit_breaker
        return get_circuit_breaker()

    def _create_rate_limiter(self):
        from .security.rate_limiter import RateLimiter
        return RateLimiter()

    def _create_user_store(self):
        from .data.repositories.user_repository import UserStore
        return UserStore()

    def _create_admin_store(self):
        from .data.repositories.admin_repository import AdminStore
        return AdminStore()

    def _create_dict_store(self):
        from .data.dict_store import DictStore
        return DictStore()

    def _create_session_store(self):
        from .services.session.session_store import SessionStore
        return SessionStore()

    def _create_map_client(self):
        # 注意：amap.py是兼容层，真正的实现在services/map/client.py
        from .services.map.client import MapClient
        return MapClient()

    def _create_geocode(self):
        from .services.map.geocode import GeocodeService
        return GeocodeService()

    def _create_poi_search(self):
        from .services.map.poi import PoiSearchService
        return PoiSearchService()

    def _create_route_planner(self):
        from .services.map.route import RoutePlannerService
        return RoutePlannerService()

    def _create_weather(self):
        from .services.map.weather import WeatherService
        return WeatherService()

    def _create_llm(self):
        from .ai.ai import LLMService
        return LLMService()

    def _create_intent(self):
        # IntentService 已迁移到意图识别Skill
        from app.skills.intent_recognition import get_intent_recognizer
        return get_intent_recognizer()

    def _create_rag_retriever(self):
        from .services.rag.retriever import Retriever
        return Retriever()

    def _create_rag_generator(self):
        from .services.rag.generator import RAGGenerator
        return RAGGenerator()

    def _create_knowledge_service(self):
        from .services.rag.knowledge_service import KnowledgeService
        return KnowledgeService()

    def _create_planner(self):
        # planner.py是主入口，提供build_plan等函数
        # 这里返回模块本身，因为planner.py使用函数式设计
        from .skills.itinerary_planner import planner
        return planner

    def list_services(self) -> Dict[str, bool]:
        """列出所有已注册的服务及其实例化状态"""
        result = {}
        all_names = set(list(self._services.keys()) + list(self._factories.keys()))
        for name in sorted(all_names):
            result[name] = name in self._services
        return result


def get_app_context() -> AppContext:
    """
    获取应用统一调度上下文（全局单例）。

    Returns:
        AppContext实例
    """
    ctx = AppContext.get_instance()
    if not ctx._initialized:
        ctx.initialize()
    return ctx
