# 见山海 · AI 旅行规划

> 基于大语言模型 + 规则引擎的智能旅行规划应用，支持自然语言对话生成行程、地图可视化、人文知识讲解。

[![Python](https://img.shields.io/badge/Python-3.11+-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)](https://fastapi.tiangolo.com/)
[![Vue](https://img.shields.io/badge/Vue-3.4-brightgreen)](https://vuejs.org/)
[![MySQL](https://img.shields.io/badge/MySQL-8.0-orange)](https://www.mysql.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 作者唠叨
本人是一名纯前端开发工程师，对于后端项目开发能力比较弱，这个项目的由来是我的一个想法或者说一个痛点，在我选择离职后我尝试用vibecoding的方式，完全无人工干涉生成了这个项目，对于一个成熟项目的架构来说，这个项目还差许多东西没有完成，但是对于我来说这个项目提供了很好的实践来提升我对项目开发的更好的理解，至于那些没有完成的能力或者说模块，我也没有多余时间继续完成了，但是这个项目我会一直留存，并且在github开源。虽然项目本身没有什么亮点，但是希望每个人都能找到一件事情最初的实践开始，一旦选择开始这就是最佳实践！！！如果有人能将它完善也是感激不尽！！！

## 项目配置
目前项目需要配置各种能力的key才能使用，deepseek、高德、邮箱的账号密码

## 核心特性

### 智能规划
- **自然语言对话规划**：用日常对话描述出行需求，AI 自动识别意图并生成行程
- **多轮增量修改**：支持调整预算、天数、节奏、增删景点等局部修改，无需全局重刷
- **规则引擎 + LLM 协同**：LLM 负责意图理解和语义编排，规则引擎负责地理聚类、时间分配、预算计算等客观计算
- **中国区域规划**：仅支持中国境内目的地规划，确保数据准确性

### 精细点位体系
- **三层 POI 结构**：主景点 → 内部子景点 → 周边附属景点，行程从"景点跳转"升级为"真实游玩动线"
- **主/子 POI 智能处理**：大型景区作为整体规划点位，景区内小景点优先级降低，避免重复
- **必去景点保护机制**：标志性景点、用户指定必去景点在所有筛选中不被过滤
- **全量候选池构建**：一次全量检索 + 统一注入，确保知名景点在候选池中

### 人文知识体系
- **RAG 知识库**：基于 Chroma 向量数据库 + 中文 Embedding 模型，支持景点人文知识检索
- **AI 景点讲解**：8 个模块完整讲解（一句话定位/历史沿革/建筑格局/文化意义/名人典故/游玩重点/拍照机位/避坑提示）
- **历史名人关联**：对话中涉及历史名人、革命先辈时自动关联相关地名和出行推荐
- **语音介绍**：支持景点语音讲解，内容更详尽

### 用户系统
- **邮箱验证码登录**：注册使用邮箱验证码 + 密码，登录使用邮箱 + 密码
- **JWT 鉴权**：无状态 Token 认证，默认 24 小时过期
- **bcrypt 密码加密**：cost 12，旧用户登录后自动升级
- **用户画像**：自动学习用户旅行偏好（节奏/预算/人群/交通/风格等），越用越智能
- **历史会话**：登录用户按用户存储，未登录本地保留，登录后自动同步

### 管理后台
- **独立 PC 端管理后台**：用户管理、行程足迹、对话运营、内容管理、AI 管理、地图服务管理、系统配置
- **数据可视化管理**：必去地标库、景点层级关系、主要景点库、预约规则、避坑提示等数据的可视化 CRUD
- **日志监控**：结构化日志查询，支持级别筛选和关键词搜索
- **POI 测试工具**：后台内置地图 POI 搜索测试页面，便于排查数据问题

### 在线数据增强
- **在线搜索服务**：支持多种搜索 API（必应/百度/谷歌自定义搜索），获取真实攻略和游客经验
- **LLM 辅助数据提纯**：从非结构化攻略文本中提取结构化信息（景点列表/每日行程/避坑提示）
- **数据审核流程**：在线数据 → LLM 提纯 → 人工审核 → 规划引擎使用，形成数据质量保障闭环
- **预约规则管理**：景点预约渠道、放票时间、开放时间、闭馆日、票价等信息的管理和展示

## 技术栈

### 后端
- **框架**：FastAPI 0.115 + Uvicorn
- **数据库**：MySQL 8.0（pymysql 连接池）
- **AI 模型**：DeepSeek Chat（OpenAI 兼容 API），支持本地 Ollama 模型
- **向量数据库**：Chroma（RAG 知识库）
- **嵌入模型**：BAAI/bge-small-zh-v1.5（中文优化）
- **地图服务**：腾讯地图 WebService API（主），高德地图（备用）
- **认证**：JWT (HS256) + bcrypt
- **缓存**：内存 TTL 缓存（地理 7d / POI 1d / 路径 30m / 天气 2h），支持 Redis
- **部署**：Docker + Docker Compose + Nginx

### 前端
- **用户端**：Vue 3 + Vite + Vue Router + Pinia
- **管理后台**：Vue 3 + Vite（独立 PC 端项目）
- **地图**：高德地图 JS API（前端展示）
- **UI**：自定义组件库（BaseCard/BaseButton/BaseTag 等）

## 项目结构

```
travel/
├── backend/                    # 后端服务
│   ├── app/
│   │   ├── main.py            # 入口（FastAPI 应用初始化、路由注册、中间件）
│   │   ├── config.py          # 配置管理（环境变量、密钥、数据库配置）
│   │   ├── app_context.py     # 统一调度类（服务定位器，懒加载单例）
│   │   ├── constants.py       # 全局常量
│   │   ├── db_constants.py    # 数据库常量
│   │   ├── api/               # 接口层（路由、请求模型、鉴权依赖）
│   │   │   ├── auth.py        # 认证路由（注册、登录、用户信息）
│   │   │   ├── plan.py        # 行程规划路由
│   │   │   ├── explore.py     # 探索路由
│   │   │   ├── conversations.py # 会话路由
│   │   │   ├── trips.py       # 行程报告路由
│   │   │   ├── itinerary.py   # 行程详情路由
│   │   │   ├── profile.py     # 用户资料路由
│   │   │   ├── rag.py         # RAG 路由
│   │   │   ├── reviews.py     # 评价体系路由
│   │   │   ├── analytics.py   # 数据分析路由
│   │   │   ├── admin.py       # 管理后台路由
│   │   │   ├── admin_online_data.py # 在线数据管理路由
│   │   │   ├── admin_major_attractions.py # 主要景点管理路由
│   │   │   ├── admin_poi_hierarchy.py # POI 层级管理路由
│   │   │   ├── admin_knowledge.py # 知识库管理路由
│   │   │   ├── admin_historical_figures.py # 历史人物管理路由
│   │   │   ├── system.py      # 系统接口（状态、站点配置、指标）
│   │   │   └── deps.py        # 路由共享依赖
│   │   ├── core/              # 核心能力层
│   │   │   ├── geo_local.py   # 本地地理数据（行政区域、城市坐标、缓存）
│   │   │   ├── health.py      # 健康检查
│   │   │   └── pipeline_stages.py # 流水线阶段
│   │   ├── ai/                # AI 能力层
│   │   │   ├── ai.py          # LLM 服务（模型管理、对话生成、行程优化）
│   │   │   ├── model_manager.py # 模型管理器
│   │   │   └── prompt_manager.py # 提示词管理器
│   │   ├── data/              # 数据访问层
│   │   │   ├── database.py    # 数据库连接管理（MySQL 连接池、事务）
│   │   │   ├── dict_store.py  # 字典数据存储（旅行风格、预算档位、出行方式）
│   │   │   ├── repositories/  # 数据仓库
│   │   │   └── models/        # 数据模型（Pydantic 模型）
│   │   ├── infrastructure/    # 基础设施层
│   │   │   ├── cache.py       # TTL 缓存
│   │   │   ├── logger.py      # 日志系统（结构化日志、文件输出、日志轮转）
│   │   │   ├── request_logger.py # 请求日志中间件
│   │   │   ├── metrics.py     # 监控指标（Prometheus 格式）
│   │   │   ├── exceptions.py  # 异常处理
│   │   │   ├── circuit_breaker.py # 熔断器
│   │   │   └── redis_client.py # Redis 客户端（预留）
│   │   ├── security/          # 安全层
│   │   │   ├── auth.py        # 用户鉴权（Bearer token 解析、登录依赖）
│   │   │   ├── login_security.py # 登录安全（失败计数、账户锁定）
│   │   │   ├── db_security.py # 数据库安全（SQL 注入防护）
│   │   │   ├── rate_limiter.py # 限流（IP 限流、用户限流）
│   │   │   └── security_middleware.py # 安全头中间件
│   │   ├── utils/             # 工具层
│   │   │   ├── responses.py   # 统一响应格式
│   │   │   ├── poi_deduplicator.py # POI 去重工具
│   │   │   └── data_import_export.py # 数据导入导出工具
│   │   ├── services/          # 业务服务层
│   │   │   ├── map/           # 地图服务（高德/腾讯兼容、地理编码、POI 搜索、路径规划、天气）
│   │   │   ├── orchestrator/  # 编排服务（规划流水线、验证器、会话管理）
│   │   │   ├── rag/           # RAG 服务（知识库、向量检索、问答）
│   │   │   ├── session/       # 会话服务（会话存储、历史记录）
│   │   │   ├── user/          # 用户服务（用户资料、用户画像）
│   │   │   ├── email/         # 邮箱服务（验证码发送）
│   │   │   ├── online_data/   # 在线数据服务（搜索、提纯、预约规则、避坑提示）
│   │   │   └── major_attractions.py # 主要景点服务
│   │   └── skills/            # 技能模块（独立可复用能力）
│   │       ├── intent_recognition/ # 意图识别技能（LLM 解析、规则识别、参数提取）
│   │       ├── itinerary_planner/  # 行程规划技能（规划引擎、地理枚举、聚类、逐日构建）
│   │       └── rule_engine/        # 规则引擎技能（参数规范化、人群影响、出行方式、景点筛选、按天分配、行程检视）
│   ├── scripts/                # 脚本工具（数据迁移、初始化、导入导出）
│   ├── tests/                  # 测试文件
│   ├── Dockerfile              # 后端 Docker 镜像
│   ├── requirements.txt        # Python 依赖
│   ├── requirements-rag.txt    # RAG 可选依赖
│   └── run.py                  # 启动入口
│
├── frontend/                   # 用户端（移动端 H5）
│   ├── src/
│   │   ├── main.js             # 入口
│   │   ├── App.vue             # 根组件（TabBar 布局）
│   │   ├── router/             # 路由
│   │   ├── store/              # 状态管理（Pinia）
│   │   ├── api/                # API 封装
│   │   ├── views/              # 页面
│   │   │   ├── Home.vue        # 对话板块（默认）
│   │   │   ├── Explore.vue     # 探索板块
│   │   │   ├── Me.vue          # 我的板块
│   │   │   └── Plan.vue        # 行程详情页
│   │   ├── components/         # 组件
│   │   │   ├── ChatPlanner.vue # 对话规划组件
│   │   │   ├── MapView.vue     # 地图渲染组件
│   │   │   ├── DayCard.vue     # 每日行程卡片
│   │   │   ├── TripPoster.vue  # 行程海报
│   │   │   ├── SpeechPlayer.vue # 语音播放器
│   │   │   ├── ReservationAlerts.vue # 预约提醒
│   │   │   ├── TravelTips.vue  # 避坑提示
│   │   │   └── base/           # 基础组件
│   │   └── utils/              # 工具函数
│   ├── package.json
│   ├── vite.config.js
│   └── Dockerfile              # 前端 Docker 镜像
│
├── frontend-admin/             # 管理后台（PC 端）
│   ├── src/
│   │   ├── main.js
│   │   ├── App.vue
│   │   ├── router/
│   │   ├── api/
│   │   └── views/admin/
│   │       ├── AdminLogin.vue  # 登录页
│   │       ├── AdminApp.vue    # 主布局（侧边栏 + 内容区）
│   │       └── panels/         # 功能面板
│   │           ├── DashboardPanel.vue    # 仪表盘
│   │           ├── UsersPanel.vue        # 用户管理
│   │           ├── TripsPanel.vue        # 行程足迹
│   │           ├── ConversationsPanel.vue # 对话运营
│   │           ├── ContentPanel.vue      # 内容管理
│   │           ├── AiPanel.vue           # AI 管理
│   │           ├── AmapPanel.vue         # 地图服务管理
│   │           ├── LogPanel.vue          # 日志监控
│   │           ├── ConfigPanel.vue       # 系统配置
│   │           ├── DictPanel.vue         # 字典数据管理
│   │           ├── PoiHierarchyPanel.vue # POI 层级管理
│   │           ├── PoiTestPanel.vue      # POI 测试工具
│   │           ├── RagPanel.vue          # RAG 知识库管理
│   │           ├── KnowledgePanel.vue     # 知识库管理
│   │           ├── HistoricalFigurePanel.vue # 历史人物管理
│   │           ├── ReservationRulesPanel.vue # 预约规则管理
│   │           ├── TravelTipsPanel.vue   # 避坑提示管理
│   │           └── AdminsPanel.vue       # 管理员管理
│   ├── package.json
│   └── vite.config.js
│
├── docs/                       # 项目文档
│   ├── 项目资料体系/            # 产品文档（PRD、运营方案、商业计划书、竞品分析、用户旅程地图）
│   ├── DEPLOYMENT.md           # 部署文档
│   ├── code-structure.md       # 代码结构梳理
│   ├── planner-rules.md        # 规划引擎规则
│   ├── 行程规划完整数据流.md     # 规划流程数据流
│   ├── 行程规划引擎流程架构优化方案.md # 规划引擎优化方案
│   ├── 能力升级规划.md          # 能力升级路线图
│   └── RAG_KNOWLEDGE_BASE_PLAN.md # RAG 知识库建设计划
│
├── data/                       # 数据目录（运行时生成）
│   ├── mysql/                  # MySQL 数据
│   ├── logs/                   # 日志文件
│   └── rag/                    # RAG 向量数据
│
├── deploy/                     # 部署配置
│   └── nginx/                  # Nginx 配置
│
├── docker-compose.yml          # Docker Compose 编排
├── Makefile                    # 常用命令封装
├── .env.example                # 环境变量示例
├── .gitignore
├── CHANGELOG.md                # 变更记录（原 README，含完整开发历史）
└── README.md                   # 本文件
```

## 快速开始

### 环境要求

- **Python** >= 3.11
- **Node.js** >= 18
- **MySQL** >= 8.0
- **npm** >= 9

### 1. 克隆项目

```bash
git clone <repository-url>
cd travel
```

### 2. 配置环境变量

```bash
# 后端配置
cd backend
cp .env.example .env
# 编辑 .env，填写以下关键配置：
# - DATABASE_URL: MySQL 数据库连接
# - JWT_SECRET: JWT 密钥
# - OPENAI_API_KEY: DeepSeek API Key
# - TENCENT_MAP_KEY / TENCENT_MAP_SK: 腾讯地图 Key
# - SMTP_*: 邮箱服务配置（可选）
```

### 3. 安装后端依赖

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# 如需启用 RAG 功能：
pip install -r requirements-rag.txt
```

### 4. 初始化数据库

```bash
cd backend
# 数据库表会在首次启动时自动创建（CREATE TABLE IF NOT EXISTS）
# 如需初始化热门景点数据：
python scripts/init_hot_destinations.py
```

### 5. 启动后端服务

```bash
cd backend
python run.py
# 服务启动在 http://127.0.0.1:8000
# API 文档：http://127.0.0.1:8000/docs
```

### 6. 安装前端依赖并启动

```bash
# 用户端
cd frontend
npm install
npm run dev
# 启动在 http://127.0.0.1:5173

# 管理后台（新开终端）
cd frontend-admin
npm install
npm run dev
# 启动在 http://127.0.0.1:5174
```

### 7. 访问应用

- **用户端**：http://127.0.0.1:5173
- **管理后台**：http://127.0.0.1:5174
- **API 文档**：http://127.0.0.1:8000/docs

### 默认账号

- **管理后台**：`admin01` / `Admin@123456`（首次登录后请修改密码）
- **用户端**：需注册账号（邮箱验证码注册）

## Docker 部署

### 使用 Docker Compose 一键部署

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env，填写所有配置项

# 2. 构建并启动
docker-compose up -d --build

# 3. 查看日志
docker-compose logs -f

# 4. 停止服务
docker-compose down
```

### 常用 Make 命令

```bash
make build          # 构建镜像
make up             # 启动服务
make down           # 停止服务
make restart        # 重启服务
make logs           # 查看日志
make ps             # 查看服务状态
make backup         # 备份数据库
make health         # 健康检查
make clean          # 清理数据
```

详细部署说明请参考 [部署文档](docs/DEPLOYMENT.md)。

## 配置说明

### 核心环境变量

| 变量 | 说明 | 默认值 |
|---|---|---|
| `ENV` | 运行环境（dev/staging/prod） | `dev` |
| `SECRET_KEY` | 应用密钥 | - |
| `DATABASE_URL` | MySQL 数据库连接 | - |
| `JWT_SECRET` | JWT 签名密钥 | - |
| `JWT_EXPIRE_HOURS` | JWT 过期时间（小时） | `24` |

### AI 模型配置

| 变量 | 说明 | 默认值 |
|---|---|---|
| `AI_PROVIDER` | AI 提供商（openai/ollama） | `openai` |
| `OPENAI_BASE_URL` | OpenAI 兼容 API 地址 | `https://api.deepseek.com/v1` |
| `OPENAI_API_KEY` | API 密钥 | - |
| `AI_MODEL` | 模型名称 | `deepseek-chat` |

### 地图服务配置

| 变量 | 说明 | 默认值 |
|---|---|---|
| `MAP_PROVIDER` | 地图提供商（tencent/amap） | `tencent` |
| `TENCENT_MAP_KEY` | 腾讯地图 WebService Key | - |
| `TENCENT_MAP_SK` | 腾讯地图签名密钥 | - |
| `AMAP_KEY` | 高德地图 WebService Key（备用） | - |

### 邮箱服务配置

| 变量 | 说明 | 默认值 |
|---|---|---|
| `EMAIL_ENABLED` | 是否启用邮箱服务 | `false` |
| `SMTP_HOST` | SMTP 服务器地址 | `smtp.qq.com` |
| `SMTP_PORT` | SMTP 端口 | `465` |
| `SMTP_USER` | 邮箱账号 | - |
| `SMTP_PASSWORD` | 邮箱授权码 | - |

### RAG 知识库配置

| 变量 | 说明 | 默认值 |
|---|---|---|
| `RAG_ENABLED` | 是否启用 RAG | `false` |
| `RAG_DATA_DIR` | 向量数据目录 | `./data/knowledge_base` |
| `RAG_MODEL_NAME` | 嵌入模型名称 | `BAAI/bge-small-zh-v1.5` |

完整配置项请参考 [.env.example](.env.example)。

## API 文档

启动后端服务后，访问 http://127.0.0.1:8000/docs 查看完整的交互式 API 文档（Swagger UI）。

### 核心接口

| 方法 | 路径 | 说明 | 鉴权 |
|---|---|---|---|
| POST | `/api/auth/register` | 注册（邮箱验证码 + 密码） | 否 |
| POST | `/api/auth/login` | 登录（邮箱 + 密码），返回 JWT | 否 |
| POST | `/api/auth/email/send-code` | 发送邮箱验证码 | 否 |
| GET | `/api/auth/me` | 获取当前用户信息 | 是 |
| POST | `/api/chat/plan` | 对话式规划（自然语言 → 行程） | 是 |
| POST | `/api/plan` | 一键生成行程 | 是 |
| GET | `/api/conversations` | 获取会话列表 | 是 |
| GET | `/api/trips` | 获取出行记录 | 是 |
| POST | `/api/explore` | 周边探索 | 是 |
| GET | `/api/rag/{poi_name}/explain` | AI 景点讲解 | 是 |
| GET | `/api/status` | 系统状态 | 否 |

## 文档索引

| 文档 | 说明 |
|---|---|
| [CHANGELOG.md](CHANGELOG.md) | 完整变更记录（开发历史） |
| [部署文档](docs/DEPLOYMENT.md) | Docker 部署、Nginx 配置、HTTPS、数据库备份 |
| [代码结构](docs/code-structure.md) | 后端/前端模块职责、调用关系、常用命令 |
| [规划引擎规则](docs/planner-rules.md) | 规划主流程、行政分级枚举、聚类、逐日构建 |
| [规划完整数据流](docs/行程规划完整数据流.md) | 从用户输入到行程生成的 39 步数据流 |
| [规划引擎优化方案](docs/行程规划引擎流程架构优化方案.md) | 10 阶段架构优化方案 |
| [能力升级规划](docs/能力升级规划.md) | 7 大维度 30+ 升级方向，4 阶段实施路径 |
| [RAG 知识库计划](docs/RAG_KNOWLEDGE_BASE_PLAN.md) | RAG 知识库建设与落地计划 |
| [产品资料体系](docs/项目资料体系/) | PRD、运营方案、商业计划书、竞品分析、用户旅程地图 |

## 规划引擎核心流程

```
用户输入
  ↓
阶段一：意图识别（LLM 解析 + 规则兜底）
  ├─ 识别意图：plan / chat / weather / poi
  ├─ 提取参数：目的地、天数、人数、预算、风格、节奏、交通方式
  └─ 参数不完整时多轮对话补全
  ↓
阶段二：参数标准化与校验
  ├─ 时间跨度归一化（天/周/月/年）
  ├─ 人数/预算收束（最小兜底 + 最大收束）
  └─ 中国区域校验
  ↓
阶段三：地理编码与行政区域识别
  ├─ 本地行政区域库优先（6364 条，100% 覆盖）
  ├─ 同名地点消歧（上下文优先）
  └─ 第三方地图兜底（腾讯/高德）
  ↓
阶段四：全量候选池构建
  ├─ 行政分级枚举景点（省/市/区县三级）
  ├─ 主要景点库注入（450+ 热门景点）
  ├─ 必打卡地标注入（289 个知名地标）
  ├─ POI 搜索（腾讯/高德，数据库缓存优先）
  └─ 在线数据增强（预约规则、避坑提示）
  ↓
阶段五：必要景点保护与关联处理
  ├─ 标记保护景点（必打卡/主要景点/用户指定）
  ├─ 主 POI / 子 POI 统一处理（大型景区识别）
  └─ 同名景区去重（别名映射 + 坐标距离 + 包含关系）
  ↓
阶段六：景点筛选与地理聚类
  ├─ 人群影响评分（亲子/老人/情侣/朋友/单人/家庭）
  ├─ LLM 智能筛选（主题分组 + 智能时长 + 最佳时段）
  ├─ 不足补充（从候选池补充）
  ├─ 辅助 POI 限制（美食/购物/夜生活占比）
  └─ 地理聚类（就近优先 + 向外扩散）
  ↓
阶段七：时间规划与时间线管理
  ├─ 游览时长估算（景点类型/规模/人群/推荐时长）
  ├─ 开放时间检查（避免闭馆时间安排景点）
  ├─ 交通时间计算（Haversine 距离 + 出行方式速度）
  └─ 时间线模板（轻松/适中/紧凑，用餐时间、休息间隔）
  ↓
阶段八：时间跨度切分与行程构建
  ├─ 按天分配（旅行体验曲线：第1天轻松 → 核心景点 → 轻松收尾）
  ├─ 住宿锚点（前晚住宿 = 次日起点）
  ├─ 跨天地域去重
  └─ 预算拆解（餐饮/门票/交通/住宿）
  ↓
阶段九：兜底处理与辅助 POI 填充
  ├─ 天数不足时从候选池补充
  ├─ 极端兜底（城市地标 + 本地美食街）
  └─ 辅助 POI 最后填充
  ↓
阶段十：行程完善与返回
  ├─ 行程检视（8 维度校验，不符合时补充）
  ├─ 在线数据增强（预约提醒、避坑提示）
  ├─ 品牌化文案（出发宣言、每日寄语）
  └─ 返回完整行程
```

## 贡献指南

欢迎贡献代码、文档或提出建议！

### 开发流程

1. Fork 本仓库
2. 创建特性分支：`git checkout -b feature/your-feature`
3. 提交更改：`git commit -m 'Add some feature'`
4. 推送到分支：`git push origin feature/your-feature`
5. 提交 Pull Request

### 代码规范

- **后端**：遵循 PEP 8，使用类型注解，模块级文档字符串
- **前端**：Vue 3 Composition API，组件命名 PascalCase
- **提交信息**：使用 Conventional Commits 格式（feat/fix/docs/style/refactor/test/chore）

### 项目约定

- 每次功能迭代后更新 `CHANGELOG.md` 变更记录
- 日志文件不存放在项目中，默认存放在系统目录
- 所有核心功能接口必须登录鉴权
- 硬编码数据应迁移到数据库管理

## 许可证

本项目采用 [MIT 许可证](LICENSE) 开源。

## 致谢

- [FastAPI](https://fastapi.tiangolo.com/) - 现代 Python Web 框架
- [Vue.js](https://vuejs.org/) - 渐进式 JavaScript 框架
- [DeepSeek](https://www.deepseek.com/) - 大语言模型
- [Chroma](https://www.trychroma.com/) - 向量数据库
- [腾讯地图](https://lbs.qq.com/) - 地图 WebService API
- [高德地图](https://lbs.amap.com/) - 地图 JS API

---

**见山海** · 让每一次出发都有迹可循
