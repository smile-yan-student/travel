"""
FastAPI 主应用（瘦身后）：仅保留 app 创建、中间件注册、lifespan、路由注册。

业务路由已拆分到 app/api/ 目录：
- system.py      系统接口（根路径、状态、站点配置、指标）
- auth.py        注册/登录/me
- plan.py        一键规划/对话规划/路线
- explore.py     POI搜索/周边探索
- trips.py       出行记录
- conversations.py 对话历史
- itinerary.py   行程详情
- profile.py     用户资料
- rag.py         RAG相关
- admin.py       管理后台
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .ai import ai as ai_mod
from .services import map as amap
from .data.repositories import admin_repository
from .infrastructure import logger as log_mod
from .infrastructure.cache import cache
from .infrastructure.exceptions import register_exception_handlers
from .infrastructure.request_logger import request_logging_middleware
from .config import settings, set_amap_effective, set_tencent_effective

# 路由导入
from .core.health import router as health_router
from .api.system import router as system_router
from .api.admin import router as admin_router
from .api.auth import router as auth_router
from .api.plan import router as plan_router
from .api.explore import router as explore_router
from .api.trips import router as trips_router
from .api.conversations import router as conversations_router
from .api.itinerary import router as itinerary_router
from .api.rag import router as rag_router
from .api.profile import router as profile_router
from .api.admin_knowledge import router as admin_knowledge_router
from .api.admin_poi_hierarchy import router as admin_poi_hierarchy_router
from .api.admin_historical_figures import router as admin_historical_figures_router
from .api.admin_major_attractions import router as admin_major_attractions_router
from .api.admin_online_data import router as admin_online_data_router
from .api.reviews import router as reviews_router
from .api.analytics import router as analytics_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    """启动时真实探测高德/腾讯 Key：类型不符/未配置则诚实标记为不可用；初始化数据库与后台数据"""
    # 初始化统一调度上下文（AppContext），不改变现有导入方式，只作为可选的统一访问入口
    from .app_context import get_app_context
    app_ctx = get_app_context()

    log_mod.setup_logging()
    _log = log_mod.get_logger("startup")
    _log.info("app_context_initialized", extra={"fields": {"services_count": len(app_ctx.list_services())}})

    from .data.database import init_db
    init_db()
    admin_repository.init_admin_data()

    # 初始化知识库默认分类和配置
    try:
        from .data.repositories.knowledge_repository import init_default_knowledge
        init_default_knowledge()
    except Exception as e:
        _log.warning("knowledge_init_failed", extra={"fields": {"error": str(e)}})

    # 若后台曾保存过高德/腾讯 Key，优先使用（覆盖环境变量），实现后台配置持久化
    try:
        cfg = admin_repository.get_config(include_secret=True)
        if cfg.get("amap_key"):
            from .config import set_amap_key
            set_amap_key(cfg["amap_key"])
        if cfg.get("tencent_key"):
            from .config import set_tencent_key
            set_tencent_key(cfg["tencent_key"])
    except Exception:
        pass

    set_amap_effective(await amap.probe_amap())
    set_tencent_effective(await amap.probe_tencent())
    yield


app = FastAPI(title=settings.app_name, version=settings.version, lifespan=lifespan)

# 注册全局异常处理器（统一错误响应格式，不泄露堆栈）
register_exception_handlers(app)

# ---------------- 中间件注册 ----------------

# CORS 中间件（生产环境通过 CORS_ORIGINS 环境变量配置具体域名）
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Trace-Id"],
)

# 安全响应头中间件（X-Content-Type-Options / X-Frame-Options / HSTS 等）
from .security.security_middleware import SecurityHeadersMiddleware
app.add_middleware(SecurityHeadersMiddleware)

# 全局限流中间件（IP 级 + 用户级，防止恶意请求打爆服务）
from .security.rate_limiter import RateLimiterMiddleware
app.add_middleware(RateLimiterMiddleware)

# 请求指标收集中间件（QPS/延迟/错误率，用于可观测性）
from .infrastructure.metrics import MetricsMiddleware
app.add_middleware(MetricsMiddleware)

# 请求日志中间件（trace_id 贯穿 + 方法/路径/状态码/耗时，异常自动记录）
app.middleware("http")(request_logging_middleware)

# ---------------- 路由注册 ----------------

app.include_router(system_router)
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(plan_router)
app.include_router(explore_router)
app.include_router(trips_router)
app.include_router(conversations_router)
app.include_router(itinerary_router)
app.include_router(rag_router)
app.include_router(profile_router)
app.include_router(admin_router)
app.include_router(admin_knowledge_router)
app.include_router(admin_poi_hierarchy_router)
app.include_router(admin_historical_figures_router)
app.include_router(admin_major_attractions_router)
app.include_router(admin_online_data_router)
app.include_router(reviews_router)
app.include_router(analytics_router)
