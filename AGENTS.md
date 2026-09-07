# AGENTS.md — 项目协作约定

## 变更记录（强制）

**每一次改动（功能迭代 / Bug 修复 / 性能优化 / 数据调整）完成后，必须同步更新 `CHANGELOG.md` 的「项目进展 / 变更记录」表**：
- 在表**最上方追加一行**（最新在上），不得覆盖或改写历史行；
- 列：`日期 | 类型 | 改动内容 | 涉及文件`，内容用一句话讲清「做了什么 + 为什么 + 效果」；
- 涉及新增/删除文件时，在"涉及文件"列标注（如「新增 `backend/app/cache.py`」）。

这是本项目唯一的持续变更日志，未更新记录视为改动未完成。
> 注意：原 README.md 已重命名为 CHANGELOG.md（保留完整开发历史），新 README.md 为项目介绍和使用说明。

## 常用命令

```bash
# 后端（端口 8000，uvicorn reload）
cd backend && ./.venv/bin/python run.py
# 前端（端口 5173）
cd frontend && npm run dev
# 接口文档
http://127.0.0.1:8000/docs
```

## 架构速览（改代码前先读这些）

### 目录结构（2026-08-29 重构后）

```
backend/app/
├── main.py              # 入口（FastAPI应用初始化、路由注册、中间件注册）
├── config.py            # 配置管理（环境变量、密钥、数据库配置）
├── app_context.py       # 统一调度类（服务定位器，懒加载单例，注册22个核心服务）
├── api/                 # 接口层（路由、请求模型、鉴权依赖）
│   ├── system.py        # 系统接口（根路径、状态、站点配置、指标）
│   ├── admin.py         # 管理后台路由
│   ├── auth.py          # 认证路由（注册、登录、用户信息）
│   ├── plan.py          # 行程规划路由
│   ├── explore.py       # 探索路由
│   ├── conversations.py # 会话路由
│   ├── trips.py         # 行程报告路由
│   ├── itinerary.py     # 行程详情路由
│   ├── profile.py       # 用户资料路由
│   ├── rag.py           # RAG路由
│   └── deps.py          # 路由共享依赖（请求模型、鉴权函数、常量）
├── core/                # 核心能力层
│   ├── planner.py       # 行程规划引擎（build_plan 主入口）
│   ├── intent.py        # 意图识别（LLM解析用户输入、参数提取）
│   ├── geo_local.py     # 本地地理数据（行政区域、城市坐标、缓存）
│   └── health.py        # 健康检查（服务状态、依赖检查）
├── ai/                  # AI能力层
│   └── ai.py            # LLM服务（模型管理、对话生成、行程优化）
├── data/                # 数据访问层
│   ├── database.py      # 数据库连接管理（MySQL连接池、事务）
│   ├── dict_store.py    # 字典数据存储（旅行风格、预算档位、出行方式）
│   ├── repositories/    # 数据仓库（包含数据库调用）
│   │   ├── user_repository.py # 用户数据存储（注册、登录、JWT、bcrypt）
│   │   └── admin_repository.py # 管理员数据存储
│   ├── models/          # 数据模型
│   │   └── models.py    # Pydantic模型、请求/响应模型
│   └── static/          # 静态硬编码数据
│       ├── must_visit.py    # 必打卡地标数据
│       ├── poi_hierarchy.py # POI层级数据
│       ├── poi_hierarchy_extra.py # POI层级补充数据
│       ├── famous_landmarks.py # 著名地标数据
│       └── large_scenic_areas.py # 大型景区数据
├── infrastructure/      # 基础设施层
│   ├── cache.py         # TTL缓存（地理7d / POI 1d / 路径30m / 天气2h）
│   ├── logger.py        # 日志系统（结构化日志、文件输出、日志轮转，日志存放在系统目录）
│   ├── request_logger.py # 请求日志中间件（trace_id贯穿、方法/路径/状态码/耗时）
│   ├── metrics.py       # 监控指标（请求计数、延迟、Prometheus格式）
│   ├── exceptions.py    # 异常处理（统一异常格式、异常处理器注册）
│   ├── circuit_breaker.py # 熔断器（第三方API故障保护）
│   └── redis_client.py  # Redis客户端（预留）
├── security/            # 安全层
│   ├── auth.py          # 用户鉴权（Bearer token解析、登录依赖）
│   ├── login_security.py # 登录安全（失败计数、账户锁定）
│   ├── db_security.py   # 数据库安全（SQL注入防护、字段校验、排序安全）
│   ├── rate_limiter.py  # 限流（IP限流、用户限流）
│   └── security_middleware.py # 安全头中间件（CSP、X-Frame-Options等）
├── utils/               # 工具层
│   └── responses.py     # 统一响应格式（成功、失败、分页）
└── services/            # 业务服务层
    ├── map/             # 地图服务（高德/腾讯兼容、地理编码、POI搜索、路径规划、天气）
    ├── planner/         # 规划服务（地理枚举、聚类、逐日构建、必打卡注入）
    ├── orchestrator/    # 编排服务（规划流水线、验证器、会话管理）
    ├── rag/             # RAG服务（知识库、向量检索、问答）
    ├── session/         # 会话服务（会话存储、历史记录）
    └── user/            # 用户服务（用户资料）
```

> **注意**：日志文件不存放在项目中，默认存放在系统目录：
> - macOS: `~/Library/Logs/travel-app/`
> - Linux: `~/.cache/travel-app/`
> - Windows: `%LOCALAPPDATA%/travel-app/`
> 可通过环境变量 `LOG_DIR` 覆盖。

### 核心模块说明

- `backend/app/core/planner.py` — 行程规划引擎（`build_plan` 主入口）。
  - 规划主路径：`_geo_plan`（行政分级枚举景点 → `must_visit` 地标注入 → 聚类 → 圈层分配 → 逐日构建）。
  - `_enumerate_scoped_attractions`：区县/市/省三级枚举，**含跨城污染过滤（cityname）**。
  - `_inject_must_visit_attrs`：`data/must_visit.py` 必打卡地标注入主线。
  - `_greedy_group` / `_dedup_landmark_day`：顶级地标分组、同地标词去重。
- `backend/app/services/map/` — 地图服务（高德/腾讯双Provider兼容）。
  - `client.py`：基础客户端（HTTP请求、Provider探测、距离计算、城市坐标）
  - `geocode.py`：地理编码（地名→坐标）
  - `poi.py`：POI搜索（按类别/行政分级/就近/周边探索/点位解析/酒店）
  - `route.py`：路径规划（两点间交通方案）
  - `weather.py`：天气查询
  - 所有接口**已接 TTL 缓存**（`infrastructure/cache.py`），新增检索类接口也应接入缓存。
- `backend/app/infrastructure/cache.py` — TTL缓存（地理 7d / POI 1d / 路径 30m / 天气 2h）。
- `backend/app/app_context.py` — 统一调度类（服务定位器，懒加载单例）。
  - 注册22个核心服务的工厂函数，通过 `app_context.get_service('service_name')` 获取。
  - 新服务应在此注册，避免全局变量和循环导入。
- `frontend/src/components/MapView.vue` — 地图渲染（marker 锚点居中、Polyline 平滑采样线、按天分色、卡片联动）。
- 状态接口 `GET /api/status` 含缓存占用统计，可用来验证缓存生效。

## 注意

- 高德 Web服务 Key 不可用时应用诚实降级 mock，不要假装真实数据。
- 前端地图依赖 `VITE_AMAP_WEB_KEY`（Web端 JS API）；后端依赖 `AMAP_KEY`（Web服务），两者不同。
- 地图服务统一从 `services/map/` 导入，支持高德/腾讯双Provider。
- 所有需要登录的接口应使用 `security/auth.py` 中的 `require_user` 依赖。
- 日志文件不存放在项目中，默认存放在系统目录（macOS: `~/Library/Logs/travel-app/`），可通过 `LOG_DIR` 环境变量覆盖。
