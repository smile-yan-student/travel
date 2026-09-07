# RAG 知识库增强 - 技术实现方案文档

## 文档信息



| 项目       | 内容              |
| -------- | --------------- |
| **文档名称** | RAG 知识库增强技术实现方案 |
| **版本**   | v1.0            |
| **日期**   | 2026-09-03      |
| **状态**   | 待评审             |
| **作者**   | 技术团队            |



***

## 一、技术架构设计

### 1.1 整体架构



```
┌─────────────────────────────────────────────────────────────────┐

│                        客户端层（Client Layer）                    │

├─────────────────────────────────────────────────────────────────┤

│  Web端（Vue3）  │  移动端（H5/小程序）  │  管理后台（Vue3）      │

└─────────────────────────────────────────────────────────────────┘

&#x20;                             │

&#x20;                             ▼

┌─────────────────────────────────────────────────────────────────┐

│                      网关层（Gateway Layer）                       │

├─────────────────────────────────────────────────────────────────┤

│  Nginx反向代理  │  负载均衡  │  SSL终止  │  静态资源服务          │

└─────────────────────────────────────────────────────────────────┘

&#x20;                             │

&#x20;                             ▼

┌─────────────────────────────────────────────────────────────────┐

│                      应用层（Application Layer）                   │

├─────────────────────────────────────────────────────────────────┤

│                                                                   │

│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │

│  │  对话服务    │  │  规划服务    │  │  探索服务    │            │

│  │  (Chat)     │  │  (Planner)  │  │  (Explore)  │            │

│  └─────────────┘  └─────────────┘  └─────────────┘            │

│                                                                   │

│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │

│  │  RAG服务     │  │  知识库服务  │  │  用户服务    │            │

│  │  (RAG)      │  │  (Knowledge) │  │  (User)     │            │

│  └─────────────┘  └─────────────┘  └─────────────┘            │

│                                                                   │

│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │

│  │  管理服务    │  │  审核服务    │  │  分析服务    │            │

│  │  (Admin)    │  │  (Review)   │  │  (Analytics) │            │

│  └─────────────┘  └─────────────┘  └─────────────┘            │

│                                                                   │

└─────────────────────────────────────────────────────────────────┘

&#x20;                             │

&#x20;                             ▼

┌─────────────────────────────────────────────────────────────────┐

│                      基础服务层（Infrastructure Layer）            │

├─────────────────────────────────────────────────────────────────┤

│                                                                   │

│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │

│  │  LLM服务     │  │  嵌入服务    │  │  地图服务    │            │

│  │  (DeepSeek) │  │  (text2vec) │  │  (腾讯/高德) │            │

│  └─────────────┘  └─────────────┘  └─────────────┘            │

│                                                                   │

└─────────────────────────────────────────────────────────────────┘

&#x20;                             │

&#x20;                             ▼

┌─────────────────────────────────────────────────────────────────┐

│                      数据层（Data Layer）                          │

├─────────────────────────────────────────────────────────────────┤

│                                                                   │

│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │

│  │  MySQL       │  │  Redis       │  │  向量数据库  │            │

│  │  (业务数据)  │  │  (缓存/会话) │  │  (Chroma)   │            │

│  └─────────────┘  └─────────────┘  └─────────────┘            │

│                                                                   │

│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │

│  │  对象存储    │  │  消息队列    │  │  日志系统    │            │

│  │  (S3/MinIO) │  │  (RabbitMQ) │  │  (ELK)      │            │

│  └─────────────┘  └─────────────┘  └─────────────┘            │

│                                                                   │

└─────────────────────────────────────────────────────────────────┘
```

### 1.2 架构特点



1. **分层架构**：客户端层 → 网关层 → 应用层 → 基础服务层 → 数据层，职责清晰

2. **微服务化**：按业务领域拆分服务，独立开发、部署、扩展

3. **RAG 核心**：RAG 服务作为核心服务，负责知识检索和增强生成

4. **知识库独立**：知识库服务独立管理，支持多类型知识存储和检索

5. **可扩展性**：各层均可独立扩展，支持水平扩容

6. **高可用性**：无状态服务 + 负载均衡，数据层主从复制

### 1.3 技术栈总览



| 层级        | 技术选型                                          | 说明            |
| --------- | --------------------------------------------- | ------------- |
| **前端**    | Vue3 + TypeScript + Vite + Pinia + Vue Router | 用户端和管理后台      |
| **移动端**   | H5 + 小程序（Taro/uni-app）                        | 多端覆盖          |
| **后端**    | Python + FastAPI + Uvicorn                    | 高性能异步框架       |
| **LLM**   | DeepSeek Chat（线上）+ Qwen2.5-7B（本地备选）           | 大语言模型         |
| **嵌入模型**  | text2vec-base-chinese                         | 中文语义嵌入        |
| **向量数据库** | Chroma（中小规模）→ Milvus（大规模）                     | 向量存储和检索       |
| **关系数据库** | MySQL 8.0                                     | 业务数据存储        |
| **缓存**    | Redis 7.0                                     | 缓存、会话、限流      |
| **消息队列**  | RabbitMQ / Redis Stream                       | 异步任务、事件驱动     |
| **对象存储**  | MinIO / 阿里云 OSS                               | 文件、图片、附件存储    |
| **网关**    | Nginx                                         | 反向代理、负载均衡、SSL |
| **容器化**   | Docker + Docker Compose                       | 开发和部署         |
| **监控**    | Prometheus + Grafana + ELK                    | 监控、日志、告警      |
| **CI/CD** | GitHub Actions / GitLab CI                    | 持续集成和部署       |



***

## 二、系统模块划分

### 2.1 后端模块划分



```
backend/

├── app/

│   ├── main.py                 # 应用入口

│   ├── config.py               # 配置管理

│   ├── app\_context.py          # 服务调度器（依赖注入）

│   │

│   ├── api/                    # 接口层（路由、请求模型、鉴权）

│   │   ├── chat.py             # 对话接口

│   │   ├── plan.py             # 行程规划接口

│   │   ├── explore.py          # 探索接口

│   │   ├── rag.py              # RAG检索接口

│   │   ├── knowledge.py        # 知识库管理接口

│   │   ├── user.py             # 用户接口

│   │   ├── admin.py            # 管理后台接口

│   │   ├── review.py           # 审核接口

│   │   └── deps.py             # 共享依赖（鉴权、分页等）

│   │

│   ├── core/                   # 核心业务层

│   │   ├── chat\_engine.py      # 对话引擎（意图识别、多轮对话）

│   │   ├── planner\_engine.py   # 规划引擎（行程生成、调整）

│   │   ├── rag\_engine.py       # RAG引擎（检索、增强、生成）

│   │   ├── knowledge\_engine.py # 知识库引擎（入库、更新、审核）

│   │   └── user\_engine.py      # 用户引擎（注册、登录、权限）

│   │

│   ├── services/               # 业务服务层

│   │   ├── llm/                # LLM服务

│   │   │   ├── client.py       # LLM客户端（DeepSeek/Ollama）

│   │   │   ├── prompt.py       # 提示词模板管理

│   │   │   └── tokenizer.py    # Token计算和管理

│   │   │

│   │   ├── embedding/          # 嵌入服务

│   │   │   ├── client.py       # 嵌入模型客户端

│   │   │   └── cache.py        # 嵌入结果缓存

│   │   │

│   │   ├── vector/             # 向量检索服务

│   │   │   ├── client.py       # 向量数据库客户端

│   │   │   ├── retriever.py    # 检索器（向量/关键词/混合）

│   │   │   └── reranker.py     # 重排序器

│   │   │

│   │   ├── knowledge/          # 知识库服务

│   │   │   ├── loader.py       # 数据加载器

│   │   │   ├── splitter.py     # 文本分段器

│   │   │   ├── cleaner.py      # 数据清洗器

│   │   │   └── classifier.py   # 数据分类器

│   │   │

│   │   ├── map/                # 地图服务

│   │   │   ├── geocode.py      # 地理编码

│   │   │   ├── poi.py          # POI搜索

│   │   │   ├── route.py        # 路径规划

│   │   │   └── weather.py      # 天气查询

│   │   │

│   │   └── notification/       # 通知服务

│   │       ├── email.py        # 邮件通知

│   │       └── push.py         # 推送通知

│   │

│   ├── data/                   # 数据访问层

│   │   ├── database.py         # 数据库连接管理

│   │   ├── models/             # 数据模型（Pydantic/SQLAlchemy）

│   │   │   ├── user.py         # 用户模型

│   │   │   ├── plan.py         # 行程模型

│   │   │   ├── knowledge.py    # 知识库模型

│   │   │   └── review.py       # 审核模型

│   │   └── repositories/       # 数据仓库（CRUD操作）

│   │       ├── user\_repo.py

│   │       ├── plan\_repo.py

│   │       ├── knowledge\_repo.py

│   │       └── review\_repo.py

│   │

│   ├── infrastructure/         # 基础设施层

│   │   ├── cache.py            # 缓存管理（Redis）

│   │   ├── logger.py           # 日志系统

│   │   ├── metrics.py          # 监控指标

│   │   ├── exceptions.py       # 异常处理

│   │   ├── middleware.py       # 中间件（鉴权、限流、CORS）

│   │   └── queue.py            # 消息队列

│   │

│   ├── security/               # 安全层

│   │   ├── auth.py             # 认证授权（JWT）

│   │   ├── password.py         # 密码加密（bcrypt）

│   │   ├── rate\_limiter.py     # 限流

│   │   └── validator.py        # 输入校验

│   │

│   └── utils/                  # 工具层

│       ├── responses.py        # 统一响应格式

│       ├── datetime.py         # 时间处理

│       └── text.py             # 文本处理

│

├── tests/                      # 测试

│   ├── unit/                   # 单元测试

│   ├── integration/            # 集成测试

│   └── e2e/                    # 端到端测试

│

├── scripts/                    # 脚本

│   ├── init\_db.py              # 数据库初始化

│   ├── init\_knowledge.py       # 知识库初始化

│   ├── migrate.py              # 数据迁移

│   └── backup.py               # 数据备份

│

├── docker/                     # Docker配置

│   ├── Dockerfile

│   ├── docker-compose.yml

│   └── nginx.conf

│

├── docs/                       # 文档

├── .env.example                # 环境变量示例

├── requirements.txt            # Python依赖

└── run.py                      # 启动脚本
```

### 2.2 前端模块划分



```
frontend/                          # 用户端

├── src/

│   ├── main.ts                    # 入口

│   ├── App.vue                    # 根组件

│   ├── router/                    # 路由

│   ├── store/                     # 状态管理（Pinia）

│   │   ├── user.ts                # 用户状态

│   │   ├── chat.ts                # 对话状态

│   │   └── plan.ts                # 行程状态

│   ├── api/                       # API接口

│   │   ├── chat.ts                # 对话接口

│   │   ├── plan.ts                # 规划接口

│   │   ├── explore.ts             # 探索接口

│   │   └── user.ts                # 用户接口

│   ├── views/                     # 页面

│   │   ├── Chat.vue               # 对话页（首页）

│   │   ├── Plan.vue               # 行程详情页

│   │   ├── Explore.vue            # 探索页

│   │   └── Me.vue                 # 我的页

│   ├── components/                # 组件

│   │   ├── ChatMessage.vue        # 对话消息

│   │   ├── PlanTimeline.vue       # 行程时间轴

│   │   ├── MapView.vue            # 地图视图

│   │   ├── AttractionCard.vue     # 景点卡片

│   │   ├── ReservationAlert.vue   # 预约提醒

│   │   └── TravelTips.vue         # 避坑提示

│   ├── utils/                     # 工具函数

│   └── styles/                    # 样式

│

frontend-admin/                    # 管理后台

├── src/

│   ├── main.ts

│   ├── App.vue

│   ├── router/

│   ├── store/

│   ├── api/

│   ├── views/

│   │   ├── admin/

│   │   │   ├── Dashboard.vue      # 数据看板

│   │   │   ├── Knowledge.vue      # 知识库管理

│   │   │   ├── Review.vue         # 审核管理

│   │   │   ├── User.vue           # 用户管理

│   │   │   └── Settings.vue       # 系统设置

│   │   └── panels/

│   │       ├── AttractionPanel.vue # 景点库管理

│   │       ├── ItineraryPanel.vue  # 行程库管理

│   │       ├── FoodPanel.vue       # 美食库管理

│   │       ├── AccommodationPanel.vue # 住宿库管理

│   │       ├── TipsPanel.vue       # 避坑库管理

│   │       └── CulturePanel.vue    # 人文库管理

│   └── components/
```



***

## 三、核心技术选型

### 3.1 LLM 模型选型



| 模型                        | 用途                | 部署方式      | 优势             | 劣势          |
| ------------------------- | ----------------- | --------- | -------------- | ----------- |
| **DeepSeek Chat**         | 主模型（对话、规划、RAG 生成） | 线上 API    | 中文能力强、成本低、长上下文 | 依赖网络、有调用限制  |
| **Qwen2.5-7B**            | 备选模型（本地部署）        | 本地 Ollama | 可离线、无调用限制、数据安全 | 能力稍弱、需要 GPU |
| **text2vec-base-chinese** | 嵌入模型              | 本地部署      | 中文语义好、体积适中、速度快 | 需要本地资源      |

**选型理由**：



1. **DeepSeek 作为主模型**：中文理解能力强，成本低（约 \$0.002/1K tokens），支持 64K 长上下文，适合 RAG 场景

2. **Qwen2.5-7B 作为备选**：可本地部署，数据安全，无调用限制，适合对数据安全要求高的场景

3. **text2vec-base-chinese 作为嵌入模型**：专门针对中文优化，语义相似度计算准确，模型体积适中（\~400MB），CPU 可运行

### 3.2 向量数据库选型



| 数据库          | 适用规模           | 部署方式          | 优势                   | 劣势         |
| ------------ | -------------- | ------------- | -------------------- | ---------- |
| **Chroma**   | 中小规模（<100 万向量） | 本地 / 嵌入式      | 轻量易用、Python 原生、支持持久化 | 分布式支持弱     |
| **FAISS**    | 中小规模           | 本地库           | 性能极高、内存友好            | 无服务端、需自行管理 |
| **Milvus**   | 大规模（>100 万向量）  | 分布式集群         | 高性能、可扩展、企业级          | 部署复杂、资源消耗大 |
| **pgvector** | 已有 PostgreSQL  | PostgreSQL 扩展 | 与业务数据统一、事务支持         | 性能不如专用向量库  |

**选型策略**：



1. **MVP 阶段**：使用 Chroma，轻量易用，快速验证

2. **成长阶段**：数据量 < 100 万时继续使用 Chroma，优化索引

3. **规模阶段**：数据量 > 100 万时迁移到 Milvus，分布式部署

### 3.3 后端框架选型



| 框架          | 语言      | 性能    | 生态    | 选型理由                           |
| ----------- | ------- | ----- | ----- | ------------------------------ |
| **FastAPI** | Python  | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 异步高性能、自动文档、类型提示、Python AI 生态丰富 |
| Django      | Python  | ⭐⭐⭐   | ⭐⭐⭐⭐⭐ | 功能全但较重，不适合 API 服务              |
| Flask       | Python  | ⭐⭐⭐⭐  | ⭐⭐⭐   | 轻量但需要自行组装，异步支持弱                |
| Express     | Node.js | ⭐⭐⭐⭐  | ⭐⭐⭐⭐⭐ | JS 生态好，但 AI 库不如 Python 丰富      |
| Gin         | Go      | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐  | 性能极高，但 AI 库不如 Python 丰富        |

**选型理由**：



1. **Python 生态**：AI/ML 相关库最丰富（LangChain、sentence-transformers、numpy 等）

2. **异步高性能**：FastAPI 基于 Starlette，异步支持好，性能接近 Node.js

3. **开发效率**：自动生成 API 文档（Swagger/ReDoc），类型提示，开发效率高

4. **团队熟悉**：团队已有 Python 项目经验，学习成本低

### 3.4 前端框架选型



| 框架       | 性能    | 生态    | 学习曲线 | 选型理由                       |
| -------- | ----- | ----- | ---- | -------------------------- |
| **Vue3** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐  | 组合式 API、性能好、生态丰富、团队熟悉      |
| React    | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 生态最丰富，但学习曲线稍陡              |
| Svelte   | ⭐⭐⭐⭐⭐ | ⭐⭐⭐   | ⭐⭐⭐  | 编译时优化，性能极好，但生态不如 Vue/React |

**选型理由**：



1. **团队熟悉**：已有 Vue3 项目经验，可复用组件和工具

2. **性能优秀**：Vue3 组合式 API，响应式系统优化，性能优秀

3. **生态丰富**：Vue Router、Pinia、Element Plus/Ant Design Vue 等生态完善

4. **开发效率**：单文件组件、TypeScript 支持、Vite 构建，开发效率高



***

## 四、数据库设计

### 4.1 数据库概览



| 数据库        | 用途       | 表数量   | 数据量预估（V2.0）                    |
| ---------- | -------- | ----- | ------------------------------ |
| **MySQL**  | 业务数据存储   | 15+   | 用户 10 万 +、行程 100 万 +、知识库 1 万 + |
| **Redis**  | 缓存、会话、限流 | -     | 热点数据缓存，内存占用 < 10GB             |
| **Chroma** | 向量数据存储   | 6 个集合 | 知识库文本分段，10 万 + 向量              |

### 4.2 MySQL 核心表设计

#### 用户相关表

**users（用户表）**



| 字段              | 类型              | 说明                    | 索引      |
| --------------- | --------------- | --------------------- | ------- |
| id              | BIGINT UNSIGNED | 主键                    | PRIMARY |
| username        | VARCHAR(50)     | 用户名                   | UNIQUE  |
| email           | VARCHAR(100)    | 邮箱                    | UNIQUE  |
| password\_hash  | VARCHAR(255)    | 密码哈希（bcrypt）          | -       |
| nickname        | VARCHAR(50)     | 昵称                    | -       |
| avatar          | VARCHAR(500)    | 头像 URL                | -       |
| phone           | VARCHAR(20)     | 手机号                   | INDEX   |
| status          | TINYINT         | 状态（0 禁用 / 1 正常）       | INDEX   |
| role            | VARCHAR(20)     | 角色（user/admin/editor） | INDEX   |
| last\_login\_at | DATETIME        | 最后登录时间                | -       |
| created\_at     | DATETIME        | 创建时间                  | -       |
| updated\_at     | DATETIME        | 更新时间                  | -       |

**user\_profiles（用户资料表）**



| 字段                | 类型              | 说明                      |
| ----------------- | --------------- | ----------------------- |
| id                | BIGINT UNSIGNED | 主键                      |
| user\_id          | BIGINT UNSIGNED | 用户 ID（外键）               |
| gender            | TINYINT         | 性别（0 未知 / 1 男 / 2 女）    |
| birthday          | DATE            | 生日                      |
| city              | VARCHAR(50)     | 所在城市                    |
| travel\_style     | VARCHAR(50)     | 旅行风格（休闲 / 深度 / 摄影 / 美食） |
| budget\_level     | VARCHAR(20)     | 预算等级（经济 / 适中 / 豪华）      |
| travel\_frequency | VARCHAR(20)     | 旅行频率（偶尔 / 经常 / 频繁）      |
| preferences       | JSON            | 偏好设置（JSON 格式）           |
| created\_at       | DATETIME        | 创建时间                    |
| updated\_at       | DATETIME        | 更新时间                    |

#### 行程相关表

**plans（行程表）**



| 字段                 | 类型              | 说明                                | 索引      |
| ------------------ | --------------- | --------------------------------- | ------- |
| id                 | BIGINT UNSIGNED | 主键                                | PRIMARY |
| user\_id           | BIGINT UNSIGNED | 用户 ID（外键）                         | INDEX   |
| title              | VARCHAR(100)    | 行程标题                              | -       |
| destination        | VARCHAR(100)    | 目的地                               | INDEX   |
| start\_date        | DATE            | 开始日期                              | -       |
| end\_date          | DATE            | 结束日期                              | -       |
| days               | INT             | 天数                                | -       |
| people\_count      | INT             | 人数                                | -       |
| crowd\_type        | VARCHAR(20)     | 人群类型（单人 / 情侣 / 亲子 / 家庭 / 朋友 / 老人） | INDEX   |
| budget             | DECIMAL(10,2)   | 预算                                | -       |
| travel\_mode       | VARCHAR(20)     | 出行方式（自驾 / 公共交通 / 混合）              | -       |
| status             | VARCHAR(20)     | 状态（draft/published/archived）      | INDEX   |
| source             | VARCHAR(20)     | 来源（ai/manual/import）              | -       |
| summary            | TEXT            | 行程摘要                              | -       |
| total\_attractions | INT             | 景点总数                              | -       |
| estimated\_budget  | DECIMAL(10,2)   | 预估预算                              | -       |
| created\_at        | DATETIME        | 创建时间                              | -       |
| updated\_at        | DATETIME        | 更新时间                              | -       |

**plan\_days（行程日表）**



| 字段                  | 类型              | 说明        |
| ------------------- | --------------- | --------- |
| id                  | BIGINT UNSIGNED | 主键        |
| plan\_id            | BIGINT UNSIGNED | 行程 ID（外键） |
| day\_number         | INT             | 第几天       |
| title               | VARCHAR(100)    | 当天标题      |
| theme               | VARCHAR(50)     | 当天主题      |
| notes               | TEXT            | 备注        |
| accommodation\_area | VARCHAR(100)    | 住宿区域      |
| created\_at         | DATETIME        | 创建时间      |

**plan\_items（行程项表）**



| 字段                  | 类型              | 说明                                 |
| ------------------- | --------------- | ---------------------------------- |
| id                  | BIGINT UNSIGNED | 主键                                 |
| plan\_day\_id       | BIGINT UNSIGNED | 行程日 ID（外键）                         |
| attraction\_id      | BIGINT UNSIGNED | 景点 ID（外键，可空）                       |
| type                | VARCHAR(20)     | 类型（attraction/food/rest/transport） |
| name                | VARCHAR(100)    | 名称                                 |
| start\_time         | TIME            | 开始时间                               |
| end\_time           | TIME            | 结束时间                               |
| duration            | INT             | 时长（分钟）                             |
| description         | TEXT            | 描述                                 |
| location            | JSON            | 位置信息（经纬度、地址）                       |
| transport\_mode     | VARCHAR(20)     | 交通方式                               |
| transport\_duration | INT             | 交通时长（分钟）                           |
| cost                | DECIMAL(10,2)   | 费用                                 |
| sort\_order         | INT             | 排序                                 |
| created\_at         | DATETIME        | 创建时间                               |

#### 知识库相关表

**knowledge\_base（知识库表）**



| 字段              | 类型              | 说明                                                       | 索引      |
| --------------- | --------------- | -------------------------------------------------------- | ------- |
| id              | BIGINT UNSIGNED | 主键                                                       | PRIMARY |
| category        | VARCHAR(20)     | 分类（attraction/itinerary/food/accommodation/tips/culture） | INDEX   |
| title           | VARCHAR(200)    | 标题                                                       | INDEX   |
| content         | LONGTEXT        | 内容                                                       | -       |
| summary         | TEXT            | 摘要                                                       | -       |
| tags            | JSON            | 标签                                                       | -       |
| destination     | VARCHAR(100)    | 目的地                                                      | INDEX   |
| source          | VARCHAR(50)     | 来源（official/manual/import/ai\_generated/user）            | INDEX   |
| source\_url     | VARCHAR(500)    | 来源 URL                                                   | -       |
| quality\_score  | DECIMAL(3,2)    | 质量评分（0-1）                                                | INDEX   |
| review\_status  | VARCHAR(20)     | 审核状态（pending/approved/rejected）                          | INDEX   |
| reviewed\_by    | BIGINT UNSIGNED | 审核人 ID                                                   | -       |
| reviewed\_at    | DATETIME        | 审核时间                                                     | -       |
| review\_comment | VARCHAR(500)    | 审核备注                                                     | -       |
| version         | INT             | 版本号                                                      | -       |
| is\_active      | TINYINT         | 是否启用                                                     | INDEX   |
| expire\_at      | DATETIME        | 过期时间（可空）                                                 | -       |
| view\_count     | INT             | 查看次数                                                     | -       |
| use\_count      | INT             | 使用次数                                                     | -       |
| created\_by     | BIGINT UNSIGNED | 创建人 ID                                                   | -       |
| created\_at     | DATETIME        | 创建时间                                                     | -       |
| updated\_at     | DATETIME        | 更新时间                                                     | -       |

**knowledge\_chunks（知识分段表）**



| 字段            | 类型              | 说明         |
| ------------- | --------------- | ---------- |
| id            | BIGINT UNSIGNED | 主键         |
| knowledge\_id | BIGINT UNSIGNED | 知识库 ID（外键） |
| chunk\_index  | INT             | 分段序号       |
| content       | TEXT            | 分段内容       |
| vector\_id    | VARCHAR(100)    | 向量数据库中的 ID |
| token\_count  | INT             | Token 数量   |
| created\_at   | DATETIME        | 创建时间       |

**attractions（景点表）**



| 字段                    | 类型              | 说明                                   |
| --------------------- | --------------- | ------------------------------------ |
| id                    | BIGINT UNSIGNED | 主键                                   |
| name                  | VARCHAR(100)    | 景点名称                                 |
| destination           | VARCHAR(100)    | 所属城市                                 |
| province              | VARCHAR(50)     | 省份                                   |
| city                  | VARCHAR(50)     | 城市                                   |
| district              | VARCHAR(50)     | 区县                                   |
| address               | VARCHAR(500)    | 详细地址                                 |
| longitude             | DECIMAL(10,6)   | 经度                                   |
| latitude              | DECIMAL(10,6)   | 纬度                                   |
| category              | VARCHAR(50)     | 分类（自然风光 / 历史古迹 / 主题乐园 / 博物馆 / 美食购物等） |
| level                 | VARCHAR(20)     | 等级（5A/4A/3A / 无）                     |
| description           | TEXT            | 描述                                   |
| opening\_hours        | VARCHAR(500)    | 开放时间                                 |
| closing\_days         | VARCHAR(200)    | 闭馆日                                  |
| ticket\_price         | VARCHAR(500)    | 票价信息                                 |
| reservation\_required | TINYINT         | 是否需要预约                               |
| reservation\_channel  | VARCHAR(200)    | 预约渠道                                 |
| reservation\_url      | VARCHAR(500)    | 预约链接                                 |
| ticket\_release\_time | VARCHAR(200)    | 放票时间                                 |
| daily\_limit          | VARCHAR(200)    | 每日限流                                 |
| visitor\_route        | VARCHAR(500)    | 游览路线                                 |
| recommended\_duration | INT             | 推荐游览时长（分钟）                           |
| best\_season          | VARCHAR(100)    | 最佳季节                                 |
| tips                  | TEXT            | 提示                                   |
| parent\_id            | BIGINT UNSIGNED | 父景点 ID（主 POI）                        |
| is\_parent            | TINYINT         | 是否为主 POI                             |
| source                | VARCHAR(20)     | 来源                                   |
| quality\_score        | DECIMAL(3,2)    | 质量评分                                 |
| review\_status        | VARCHAR(20)     | 审核状态                                 |
| is\_active            | TINYINT         | 是否启用                                 |
| created\_at           | DATETIME        | 创建时间                                 |
| updated\_at           | DATETIME        | 更新时间                                 |

#### 审核相关表

**review\_tasks（审核任务表）**



| 字段              | 类型              | 说明                                   |
| --------------- | --------------- | ------------------------------------ |
| id              | BIGINT UNSIGNED | 主键                                   |
| target\_type    | VARCHAR(20)     | 审核对象类型（knowledge/attraction/comment） |
| target\_id      | BIGINT UNSIGNED | 审核对象 ID                              |
| status          | VARCHAR(20)     | 状态（pending/approved/rejected）        |
| assigned\_to    | BIGINT UNSIGNED | 分配给（审核人 ID）                          |
| reviewed\_by    | BIGINT UNSIGNED | 审核人 ID                               |
| reviewed\_at    | DATETIME        | 审核时间                                 |
| review\_comment | VARCHAR(500)    | 审核备注                                 |
| created\_at     | DATETIME        | 创建时间                                 |

#### 对话相关表

**conversations（会话表）**



| 字段          | 类型              | 说明                          |
| ----------- | --------------- | --------------------------- |
| id          | BIGINT UNSIGNED | 主键                          |
| user\_id    | BIGINT UNSIGNED | 用户 ID（外键）                   |
| title       | VARCHAR(100)    | 会话标题                        |
| status      | VARCHAR(20)     | 状态（active/archived/deleted） |
| plan\_id    | BIGINT UNSIGNED | 关联的行程 ID（可空）                |
| created\_at | DATETIME        | 创建时间                        |
| updated\_at | DATETIME        | 更新时间                        |

**messages（消息表）**



| 字段               | 类型              | 说明                         |
| ---------------- | --------------- | -------------------------- |
| id               | BIGINT UNSIGNED | 主键                         |
| conversation\_id | BIGINT UNSIGNED | 会话 ID（外键）                  |
| role             | VARCHAR(20)     | 角色（user/assistant/system）  |
| content          | TEXT            | 消息内容                       |
| message\_type    | VARCHAR(20)     | 消息类型（text/plan/image/card） |
| metadata         | JSON            | 元数据（意图、参数、引用等）             |
| token\_count     | INT             | Token 数量                   |
| created\_at      | DATETIME        | 创建时间                       |

### 4.3 Redis 数据设计



| Key 模式                       | 类型     | 用途         | 过期时间              |
| ---------------------------- | ------ | ---------- | ----------------- |
| `user:{id}`                  | Hash   | 用户信息缓存     | 1 小时              |
| `session:{token}`            | String | 会话 Token   | 7 天               |
| `plan:{id}`                  | Hash   | 行程缓存       | 1 天               |
| `chat:history:{user_id}`     | List   | 对话历史缓存     | 1 天               |
| `rag:cache:{query_hash}`     | String | RAG 检索结果缓存 | 7 天               |
| `embedding:{text_hash}`      | String | 嵌入结果缓存     | 永久                |
| `rate_limit:{user_id}:{api}` | String | 用户 API 限流  | 1 分钟 / 1 小时 / 1 天 |
| `rate_limit:{ip}:{api}`      | String | IP 限流      | 1 分钟 / 1 小时       |
| `knowledge:hot:{category}`   | ZSet   | 热门知识排行     | 1 天               |
| `lock:{resource}`            | String | 分布式锁       | 30 秒              |

### 4.4 向量数据库设计

**Chroma 集合设计**



| 集合名              | 用途    | 向量维度 | 数据量预估 |
| ---------------- | ----- | ---- | ----- |
| `attractions`    | 景点知识库 | 768  | 5000+ |
| `itineraries`    | 行程知识库 | 768  | 1000+ |
| `foods`          | 美食知识库 | 768  | 2000+ |
| `accommodations` | 住宿知识库 | 768  | 500+  |
| `tips`           | 避坑知识库 | 768  | 1000+ |
| `cultures`       | 人文知识库 | 768  | 1000+ |

**向量元数据设计**

每个向量都附带以下元数据，用于过滤和检索：



```
{

&#x20; "knowledge\_id": 123,

&#x20; "category": "attraction",

&#x20; "destination": "北京",

&#x20; "province": "北京",

&#x20; "city": "北京",

&#x20; "tags": \["故宫", "历史", "文化"],

&#x20; "quality\_score": 0.95,

&#x20; "review\_status": "approved",

&#x20; "is\_active": 1,

&#x20; "chunk\_index": 0,

&#x20; "token\_count": 256

}
```



***

## 五、API 接口设计

### 5.1 API 设计原则



1. **RESTful 风格**：遵循 RESTful 设计规范，资源导向

2. **版本控制**：URL 中包含版本号（/api/v1/），便于平滑升级

3. **统一响应格式**：统一的成功 / 失败响应格式

4. **鉴权方式**：JWT Bearer Token，所有需要登录的接口必须携带

5. **分页规范**：统一的分页参数（page、page\_size）和响应格式

6. **错误码规范**：统一的错误码和错误信息

7. **限流控制**：按用户和 IP 进行 API 限流

8. **文档自动生成**：FastAPI 自动生成 Swagger 文档

### 5.2 统一响应格式

**成功响应**



```
{

&#x20; "code": 0,

&#x20; "message": "success",

&#x20; "data": {

&#x20;   // 业务数据

&#x20; },

&#x20; "request\_id": "uuid"

}
```

**失败响应**



```
{

&#x20; "code": 10001,

&#x20; "message": "参数错误",

&#x20; "data": null,

&#x20; "request\_id": "uuid",

&#x20; "errors": \[

&#x20;   {

&#x20;     "field": "destination",

&#x20;     "message": "目的地不能为空"

&#x20;   }

&#x20; ]

}
```

**分页响应**



```
{

&#x20; "code": 0,

&#x20; "message": "success",

&#x20; "data": {

&#x20;   "items": \[],

&#x20;   "total": 100,

&#x20;   "page": 1,

&#x20;   "page\_size": 20,

&#x20;   "total\_pages": 5

&#x20; },

&#x20; "request\_id": "uuid"

}
```

### 5.3 核心 API 列表

#### 认证接口（/api/v1/auth）



| 方法   | 路径                    | 说明       | 鉴权 |
| ---- | --------------------- | -------- | -- |
| POST | /auth/register        | 用户注册     | 否  |
| POST | /auth/login           | 用户登录     | 否  |
| POST | /auth/logout          | 用户登出     | 是  |
| POST | /auth/refresh         | 刷新 Token | 是  |
| GET  | /auth/me              | 获取当前用户信息 | 是  |
| PUT  | /auth/me              | 更新当前用户信息 | 是  |
| POST | /auth/email-code      | 发送邮箱验证码  | 否  |
| POST | /auth/forgot-password | 忘记密码     | 否  |
| POST | /auth/reset-password  | 重置密码     | 否  |

#### 对话接口（/api/v1/chat）



| 方法     | 路径                                | 说明        | 鉴权 |
| ------ | --------------------------------- | --------- | -- |
| GET    | /chat/conversations               | 获取会话列表    | 是  |
| POST   | /chat/conversations               | 创建会话      | 是  |
| GET    | /chat/conversations/{id}          | 获取会话详情    | 是  |
| DELETE | /chat/conversations/{id}          | 删除会话      | 是  |
| GET    | /chat/conversations/{id}/messages | 获取消息列表    | 是  |
| POST   | /chat/conversations/{id}/messages | 发送消息      | 是  |
| POST   | /chat/stream                      | 流式对话（SSE） | 是  |
| POST   | /chat/intent                      | 意图识别      | 是  |

#### 行程规划接口（/api/v1/plan）



| 方法     | 路径                   | 说明       | 鉴权 |
| ------ | -------------------- | -------- | -- |
| POST   | /plan/generate       | 生成行程     | 是  |
| POST   | /plan/adjust         | 调整行程     | 是  |
| GET    | /plan/{id}           | 获取行程详情   | 是  |
| GET    | /plan/list           | 获取行程列表   | 是  |
| PUT    | /plan/{id}           | 更新行程     | 是  |
| DELETE | /plan/{id}           | 删除行程     | 是  |
| POST   | /plan/{id}/duplicate | 复制行程     | 是  |
| POST   | /plan/{id}/export    | 导出行程     | 是  |
| GET    | /plan/{id}/map       | 获取行程地图数据 | 是  |

#### 探索接口（/api/v1/explore）



| 方法  | 路径                             | 说明     | 鉴权 |
| --- | ------------------------------ | ------ | -- |
| GET | /explore/nearby                | 获取附近景点 | 是  |
| GET | /explore/search                | 搜索景点   | 是  |
| GET | /explore/hot                   | 热门景点   | 是  |
| GET | /explore/attraction/{id}       | 景点详情   | 是  |
| GET | /explore/attraction/{id}/intro | 景点人文介绍 | 是  |

#### RAG 检索接口（/api/v1/rag）



| 方法   | 路径            | 说明     | 鉴权 |
| ---- | ------------- | ------ | -- |
| POST | /rag/retrieve | 知识检索   | 是  |
| POST | /rag/generate | 增强生成   | 是  |
| POST | /rag/chat     | RAG 对话 | 是  |
| GET  | /rag/sources  | 获取引用来源 | 是  |

#### 知识库管理接口（/api/v1/knowledge）



| 方法     | 路径                      | 说明     | 鉴权     |
| ------ | ----------------------- | ------ | ------ |
| GET    | /knowledge/list         | 获取知识列表 | 是（管理员） |
| GET    | /knowledge/{id}         | 获取知识详情 | 是（管理员） |
| POST   | /knowledge              | 创建知识   | 是（管理员） |
| PUT    | /knowledge/{id}         | 更新知识   | 是（管理员） |
| DELETE | /knowledge/{id}         | 删除知识   | 是（管理员） |
| POST   | /knowledge/import       | 批量导入   | 是（管理员） |
| POST   | /knowledge/export       | 批量导出   | 是（管理员） |
| POST   | /knowledge/{id}/reindex | 重建索引   | 是（管理员） |
| GET    | /knowledge/stats        | 知识库统计  | 是（管理员） |

#### 审核接口（/api/v1/review）



| 方法   | 路径                         | 说明       | 鉴权     |
| ---- | -------------------------- | -------- | ------ |
| GET  | /review/tasks              | 获取审核任务列表 | 是（审核员） |
| GET  | /review/tasks/{id}         | 获取审核任务详情 | 是（审核员） |
| POST | /review/tasks/{id}/approve | 审核通过     | 是（审核员） |
| POST | /review/tasks/{id}/reject  | 审核拒绝     | 是（审核员） |
| GET  | /review/stats              | 审核统计     | 是（管理员） |

#### 管理后台接口（/api/v1/admin）



| 方法     | 路径                      | 说明     | 鉴权     |
| ------ | ----------------------- | ------ | ------ |
| GET    | /admin/dashboard        | 数据看板   | 是（管理员） |
| GET    | /admin/users            | 用户列表   | 是（管理员） |
| GET    | /admin/users/{id}       | 用户详情   | 是（管理员） |
| PUT    | /admin/users/{id}       | 更新用户   | 是（管理员） |
| POST   | /admin/users/{id}/ban   | 封禁用户   | 是（管理员） |
| POST   | /admin/users/{id}/unban | 解封用户   | 是（管理员） |
| GET    | /admin/plans            | 行程列表   | 是（管理员） |
| DELETE | /admin/plans/{id}       | 删除行程   | 是（管理员） |
| GET    | /admin/analytics        | 数据分析   | 是（管理员） |
| GET    | /admin/settings         | 系统设置   | 是（管理员） |
| PUT    | /admin/settings         | 更新系统设置 | 是（管理员） |

### 5.4 错误码设计



| 错误码   | 说明       | HTTP 状态码 |
| ----- | -------- | -------- |
| 0     | 成功       | 200      |
| 10000 | 通用错误     | 400      |
| 10001 | 参数错误     | 400      |
| 10002 | 资源不存在    | 404      |
| 10003 | 资源已存在    | 409      |
| 10004 | 操作失败     | 500      |
| 20001 | 未登录      | 401      |
| 20002 | Token 无效 | 401      |
| 20003 | Token 过期 | 401      |
| 20004 | 权限不足     | 403      |
| 20005 | 账号被封禁    | 403      |
| 30001 | 用户名已存在   | 409      |
| 30002 | 邮箱已存在    | 409      |
| 30003 | 用户名或密码错误 | 401      |
| 30004 | 验证码错误    | 400      |
| 30005 | 验证码过期    | 400      |
| 40001 | 目的地不能为空  | 400      |
| 40002 | 行程生成失败   | 500      |
| 40003 | 行程调整失败   | 500      |
| 50001 | RAG 检索失败 | 500      |
| 50002 | LLM 调用失败 | 500      |
| 50003 | 向量数据库错误  | 500      |
| 60001 | 请求过于频繁   | 429      |
| 60002 | 调用次数超限   | 429      |
| 70001 | 地图服务错误   | 500      |
| 70002 | 地理编码失败   | 500      |



***

## 六、RAG 实现方案

### 6.1 RAG 整体流程



```
用户输入（自然语言）

&#x20;   │

&#x20;   ▼

┌─────────────────┐

│  1. 查询理解     │  意图识别、实体提取、查询扩展

│  Query Understanding │

└─────────────────┘

&#x20;   │

&#x20;   ▼

┌─────────────────┐

│  2. 知识检索     │  向量检索 + 关键词检索 + 元数据过滤

│  Retrieval      │

└─────────────────┘

&#x20;   │

&#x20;   ▼

┌─────────────────┐

│  3. 结果重排序   │  Cross-Encoder重排序、去重、过滤

│  Reranking      │

└─────────────────┘

&#x20;   │

&#x20;   ▼

┌─────────────────┐

│  4. 上下文组装   │  拼接检索结果、控制长度、构建提示词

│  Context Building│

└─────────────────┘

&#x20;   │

&#x20;   ▼

┌─────────────────┐

│  5. 增强生成     │  LLM基于上下文生成回答

│  Generation     │

└─────────────────┘

&#x20;   │

&#x20;   ▼

┌─────────────────┐

│  6. 输出处理     │  结构化解析、引用标注、后处理

│  Output Processing│

└─────────────────┘

&#x20;   │

&#x20;   ▼

最终输出（结构化行程/对话回答）
```

### 6.2 查询理解（Query Understanding）

**功能**：



1. **意图识别**：判断用户是要规划行程、咨询信息、还是调整行程

2. **实体提取**：提取目的地、天数、人数、人群、预算、出行方式等实体

3. **查询扩展**：

* 同义词扩展（"西安" → "西安、长安、陕西省会"）

* 相关实体扩展（"故宫" → "故宫、天安门、景山、北海"）

* 上下位扩展（"北京景点" → "故宫、长城、颐和园、天坛..."）

**实现方式**：



* 使用 LLM 进行意图识别和实体提取（Few-shot 提示词）

* 使用行政区域数据进行查询扩展（本地数据库）

* 使用景点层级关系进行相关实体扩展（主 POI / 子 POI）

**提示词示例**：



```
你是一个旅行规划助手。请从用户输入中提取以下信息，并以JSON格式返回：

1\. intent: 意图类型（plan/query/adjust/other）

2\. destination: 目的地（省/市/区/景点）

3\. days: 出行天数（数字）

4\. people\_count: 人数（数字）

5\. crowd\_type: 人群类型（solo/couple/family/friends/elderly/other）

6\. budget: 预算（数字，可空）

7\. travel\_mode: 出行方式（self\_driving/public\_transit/mixed/other）

8\. keywords: 关键词列表

9\. query\_expansions: 查询扩展词列表

用户输入：{user\_input}

只返回JSON，不要其他内容。
```

### 6.3 知识检索（Retrieval）

**检索策略**：混合检索（Hybrid Search）



1. **向量检索**（语义相似度）

* 使用 text2vec-base-chinese 将查询向量化

* 在 Chroma 中进行余弦相似度检索

* 返回 Top-K（默认 K=20）最相似的知识片段

* 支持元数据过滤（按目的地、分类、审核状态等过滤）

1. **关键词检索**（BM25）

* 使用 BM25 算法进行关键词匹配

* 对标题、标签、内容进行加权匹配

* 返回 Top-K（默认 K=20）最相关的知识片段

1. **结果融合**

* 使用 Reciprocal Rank Fusion（RRF）算法融合向量检索和关键词检索结果

* RRF 公式：`score = sum(1 / (k + rank_i))`，k 默认取 60

* 去重（相同 knowledge\_id 只保留一个）

* 返回融合后的 Top-N（默认 N=10）

**检索参数**：



| 参数                    | 默认值 | 说明                |
| --------------------- | --- | ----------------- |
| vector\_top\_k        | 20  | 向量检索返回数量          |
| keyword\_top\_k       | 20  | 关键词检索返回数量         |
| final\_top\_n         | 10  | 最终返回数量            |
| similarity\_threshold | 0.5 | 相似度阈值（低于此值的结果被过滤） |
| rrf\_k                | 60  | RRF 融合参数          |

**元数据过滤示例**：



```
\# 只检索北京的景点类知识，且已审核通过

where\_clause = {

&#x20;   "\$and": \[

&#x20;       {"category": {"\$eq": "attraction"}},

&#x20;       {"destination": {"\$eq": "北京"}},

&#x20;       {"review\_status": {"\$eq": "approved"}},

&#x20;       {"is\_active": {"\$eq": 1}}

&#x20;   ]

}
```

### 6.4 结果重排序（Reranking）

**功能**：



1. **相关性重排序**：使用 Cross-Encoder 模型对检索结果进行重排序，提升相关性

2. **去重**：基于语义相似度去除重复内容

3. **多样性保证**：MMR（Maximal Marginal Relevance）算法保证结果多样性

4. **质量过滤**：过滤低质量、过期、未审核的内容

**重排序模型**：



* 使用 BGE-reranker-base 中文重排序模型

* 输入：查询 + 知识片段

* 输出：相关性分数（0-1）

* 按分数降序排列

**重排序流程**：



```
检索结果（N=10）

&#x20;   │

&#x20;   ▼

1\. 质量过滤（去除未审核、低质量、过期）

&#x20;   │

&#x20;   ▼

2\. 语义去重（相似度>0.9的只保留一个）

&#x20;   │

&#x20;   ▼

3\. Cross-Encoder重排序（计算查询与每个片段的相关性）

&#x20;   │

&#x20;   ▼

4\. MMR多样性保证（避免结果过于相似）

&#x20;   │

&#x20;   ▼

5\. 取Top-K（默认K=5）

&#x20;   │

&#x20;   ▼

最终检索结果
```

### 6.5 上下文组装（Context Building）

**功能**：



1. **内容拼接**：将检索到的知识片段按相关性排序后拼接

2. **长度控制**：控制总 Token 数不超过 LLM 上下文窗口的 70%（预留 30% 给生成）

3. **引用标注**：为每个知识片段标注来源（knowledge\_id、标题、URL）

4. **提示词构建**：构建完整的 RAG 提示词，包含系统提示、上下文、用户查询

**上下文格式**：



```
【参考资料1】

标题：故宫博物院游览攻略

来源：知识库ID:123，分类:景点，目的地:北京

内容：

故宫博物院开放时间为08:30-17:00，16:00停止入场。

每周一闭馆（法定节假日除外）。

旺季门票60元，淡季40元，学生半价。

需要提前7天在官方公众号预约，每日限流8万人。

推荐游览路线：午门进 → 太和殿 → 中和殿 → 保和殿 → 乾清宫 → 御花园 → 神武门出。

推荐游览时长：3-4小时。

【参考资料2】

...

【参考资料3】

...

请基于以上参考资料回答用户的问题。如果参考资料中没有相关信息，请如实告知，不要编造。

回答时请标注引用来源，如【1】【2】。

用户问题：{user\_query}
```

**Token 控制策略**：



* 总 Token 上限：LLM 上下文窗口的 70%（如 64K 窗口 → 44.8K）

* 每个知识片段 Token 上限：2000 tokens

* 优先保留相关性高的片段

* 超出限制时截断低相关性片段

### 6.6 增强生成（Generation）

**功能**：



1. **LLM 调用**：调用 DeepSeek Chat 模型，基于上下文生成回答

2. **结构化输出**：对于行程规划，输出结构化 JSON（包含每天的景点、时间、交通等）

3. **引用保留**：保留引用标注，便于后续展示来源

4. **事实校验**：关键信息（开放时间、票价等）与检索结果交叉验证

**生成参数**：



| 参数                 | 值             | 说明           |
| ------------------ | ------------- | ------------ |
| model              | deepseek-chat | 模型名称         |
| temperature        | 0.3           | 温度（低温度保证稳定性） |
| max\_tokens        | 4096          | 最大生成 Token 数 |
| top\_p             | 0.9           | 核采样参数        |
| frequency\_penalty | 0.5           | 频率惩罚（减少重复）   |
| presence\_penalty  | 0.3           | 存在惩罚（增加多样性）  |

**行程规划输出格式**：



```
{

&#x20; "title": "北京3天经典行程",

&#x20; "summary": "覆盖北京核心景点，适合首次来京游客...",

&#x20; "days": \[

&#x20;   {

&#x20;     "day": 1,

&#x20;     "theme": "老城中心",

&#x20;     "items": \[

&#x20;       {

&#x20;         "type": "attraction",

&#x20;         "name": "天安门广场",

&#x20;         "start\_time": "08:00",

&#x20;         "end\_time": "09:00",

&#x20;         "duration": 60,

&#x20;         "description": "观看升旗仪式，参观天安门城楼...",

&#x20;         "location": {"longitude": 116.3974, "latitude": 39.9087},

&#x20;         "cost": 0,

&#x20;         "tips": "需要提前预约，带好身份证...",

&#x20;         "source": 123

&#x20;       },

&#x20;       {

&#x20;         "type": "transport",

&#x20;         "name": "步行",

&#x20;         "start\_time": "09:00",

&#x20;         "end\_time": "09:15",

&#x20;         "duration": 15,

&#x20;         "description": "从天安门广场步行到故宫午门",

&#x20;         "cost": 0

&#x20;       }

&#x20;     ],

&#x20;     "accommodation\_area": "王府井/前门",

&#x20;     "notes": "今天行程较满，注意休息..."

&#x20;   }

&#x20; ],

&#x20; "budget": {

&#x20;   "total": 1240,

&#x20;   "breakdown": {

&#x20;     "tickets": 300,

&#x20;     "transport": 200,

&#x20;     "food": 400,

&#x20;     "accommodation": 300,

&#x20;     "other": 40

&#x20;   }

&#x20; },

&#x20; "reservation\_alerts": \[

&#x20;   {

&#x20;     "attraction": "故宫博物院",

&#x20;     "alert": "需提前7天预约，每日限流8万人",

&#x20;     "channel": "故宫博物院官方公众号",

&#x20;     "url": "https://www.dpm.org.cn/"

&#x20;   }

&#x20; ],

&#x20; "travel\_tips": \[

&#x20;   {

&#x20;     "tip": "不要参加路边的长城一日游，多为黑导游",

&#x20;     "category": "anti\_fraud",

&#x20;     "severity": "danger"

&#x20;   }

&#x20; ],

&#x20; "sources": \[123, 124, 125]

}
```

### 6.7 输出处理（Output Processing）

**功能**：



1. **JSON 解析**：解析 LLM 输出的 JSON，处理格式错误

2. **数据校验**：校验必填字段、数据类型、数值范围

3. **引用解析**：解析引用标注，关联到具体的知识库条目

4. **数据富化**：补充景点经纬度、图片、详细介绍等信息

5. **错误处理**：LLM 输出异常时的降级处理（重试 / 规则引擎兜底）

**降级策略**：



1. **第一次失败**：重试一次（调整 temperature）

2. **第二次失败**：使用规则引擎生成基础行程

3. **第三次失败**：返回错误提示，引导用户调整需求

### 6.8 RAG 缓存策略



| 缓存类型   | 缓存 Key                                       | 过期时间 | 说明               |
| ------ | -------------------------------------------- | ---- | ---------------- |
| 查询理解缓存 | `rag:query_understanding:{text_hash}`        | 7 天  | 相同查询的意图识别和实体提取结果 |
| 嵌入缓存   | `rag:embedding:{text_hash}`                  | 永久   | 相同文本的嵌入向量        |
| 检索结果缓存 | `rag:retrieval:{query_hash}:{filters_hash}`  | 7 天  | 相同查询和过滤条件的检索结果   |
| 生成结果缓存 | `rag:generation:{query_hash}:{context_hash}` | 1 天  | 相同查询和上下文的生成结果    |
| 行程缓存   | `rag:plan:{params_hash}`                     | 1 天  | 相同参数的行程生成结果      |

**缓存命中率目标**：



* 查询理解缓存：>80%（相同查询重复出现）

* 嵌入缓存：>90%（相同文本重复嵌入）

* 检索结果缓存：>50%（热门目的地查询重复）

* 生成结果缓存：>30%（相同参数重复生成）



***

## 七、知识库构建方案

### 7.1 知识库分类



| 分类      | 内容                          | 数据来源            | 目标数量（V2.0） |
| ------- | --------------------------- | --------------- | ---------- |
| **景点库** | 景点介绍、开放时间、票价、预约方式、游览路线、最佳季节 | 官方网站、公开数据集、人工录入 | 5000+      |
| **行程库** | 经典行程、主题路线、一日游 / 多日游、游览顺序    | 旅游平台、人工整理、AI 生成 | 1000+      |
| **美食库** | 特色美食、老字号、网红餐厅、人均消费、推荐菜品     | 大众点评、美食平台、人工录入  | 2000+      |
| **住宿库** | 住宿区域推荐、酒店类型、价格区间、交通便利度      | 旅游平台、人工整理       | 500+       |
| **避坑库** | 防骗指南、预约提醒、交通提示、天气注意、安全提醒    | 旅游攻略、用户反馈、人工整理  | 1000+      |
| **人文库** | 历史背景、名人故事、革命先辈、文化传统、红色景点    | 百科、历史资料、人工录入    | 1000+      |

### 7.2 数据采集方案

#### 数据来源优先级



| 优先级 | 来源              | 质量    | 成本 | 说明                      |
| --- | --------------- | ----- | -- | ----------------------- |
| P0  | 官方渠道（景区官网、文旅局）  | ⭐⭐⭐⭐⭐ | 中  | 最权威，需人工整理               |
| P0  | 已有预置数据          | ⭐⭐⭐⭐⭐ | 低  | 已有的 21 条预约规则 + 38 条避坑提示 |
| P1  | 公开数据集           | ⭐⭐⭐⭐  | 低  | 开源旅游数据，需清洗              |
| P1  | 百科知识（维基 / 百度百科） | ⭐⭐⭐⭐  | 低  | 景点介绍、历史文化               |
| P2  | 旅游平台（马蜂窝 / 携程）  | ⭐⭐⭐   | 中  | 攻略、游记，需去广告              |
| P2  | 美食平台（大众点评）      | ⭐⭐⭐   | 中  | 美食推荐，需去重                |
| P3  | 用户贡献（UGC）       | ⭐⭐    | 低  | 用户上传，需严格审核              |
| P3  | AI 生成           | ⭐⭐⭐   | 低  | 基于已有知识扩展，需审核            |

#### 数据采集流程



```
数据来源

&#x20;   │

&#x20;   ▼

┌─────────────┐

│  1. 数据获取  │  爬虫/API/人工录入/批量导入

│  Acquisition │

└─────────────┘

&#x20;   │

&#x20;   ▼

┌─────────────┐

│  2. 数据清洗  │  去广告、去重、格式标准化、内容校验

│  Cleaning    │

└─────────────┘

&#x20;   │

&#x20;   ▼

┌─────────────┐

│  3. 数据分类  │  自动分类（6大类）、标签提取、实体识别

│  Classification│

└─────────────┘

&#x20;   │

&#x20;   ▼

┌─────────────┐

│  4. 质量评估  │  自动评分（来源、完整性、准确性、时效性）

│  Quality     │

└─────────────┘

&#x20;   │

&#x20;   ▼

┌─────────────┐

│  5. 人工审核  │  审核通过/拒绝，审核备注

│  Review      │

└─────────────┘

&#x20;   │

&#x20;   ▼

┌─────────────┐

│  6. 文本分段  │  语义分段、重叠分段、Token控制

│  Splitting   │

└─────────────┘

&#x20;   │

&#x20;   ▼

┌─────────────┐

│  7. 向量化    │  嵌入模型向量化、存入向量数据库

│  Embedding   │

└─────────────┘

&#x20;   │

&#x20;   ▼

┌─────────────┐

│  8. 入库生效  │  写入MySQL、更新索引、设置有效期

│  Indexing    │

└─────────────┘
```

### 7.3 数据清洗方案

**清洗规则**：



1. **去广告**：

* 去除包含 "广告"、"推广"、"赞助" 等关键词的内容

* 去除明显的营销话术（"限时优惠"、"立即抢购" 等）

* 去除联系方式（电话、微信、QQ 等）

1. **去重**：

* 精确去重：完全相同的内容只保留一个

* 语义去重：相似度 > 0.9 的内容只保留质量最高的一个

* 标题去重：相同标题的内容合并

1. **格式标准化**：

* 统一日期格式（YYYY-MM-DD）

* 统一时间格式（HH:MM）

* 统一价格格式（数字 + 单位）

* 去除 HTML 标签、特殊字符

* 统一标点符号（中文标点）

1. **内容校验**：

* 长度校验：过短（<50 字）或过长（>10000 字）的内容标记

* 完整性校验：缺少关键字段的内容标记

* 准确性校验：明显错误的信息（如开放时间 > 24 小时）标记

* 时效性校验：过期信息（如去年的活动）标记

### 7.4 文本分段方案

**分段策略**：语义分段 + 重叠分段



1. **语义分段**：

* 按段落分割（空行分隔）

* 按标题分割（#、##、### 等）

* 按语义单元分割（使用 LLM 判断语义边界）

1. **分段参数**：



| 参数               | 值   | 说明                       |
| ---------------- | --- | ------------------------ |
| chunk\_size      | 500 | 每个分段的最大 Token 数          |
| chunk\_overlap   | 50  | 相邻分段的重叠 Token 数          |
| min\_chunk\_size | 100 | 最小分段 Token 数（小于此值合并到前一段） |



1. **分段元数据**：

* knowledge\_id：所属知识库 ID

* chunk\_index：分段序号

* token\_count：Token 数量

* title：分段标题（从上下文提取）

* keywords：关键词（从内容提取）

### 7.5 向量化方案

**嵌入模型**：text2vec-base-chinese

**模型参数**：



* 维度：768

* 最大输入长度：512 tokens

* 语言：中文

* 模型大小：\~400MB

**向量化流程**：



1. 文本预处理（去除特殊字符、统一编码）

2. 调用嵌入模型生成向量

3. 向量归一化（L2 归一化，便于余弦相似度计算）

4. 存入 Chroma 向量数据库

5. 缓存嵌入结果（相同文本不重复计算）

**性能优化**：



* 批量处理：一次处理 32 个文本，提升吞吐量

* GPU 加速：使用 GPU 进行嵌入计算（如可用）

* 缓存机制：相同文本的嵌入结果永久缓存

* 异步处理：大批量数据异步处理，不阻塞主流程

### 7.6 数据更新策略

**更新频率**：



| 数据类型        | 更新频率 | 说明            |
| ----------- | ---- | ------------- |
| 景点开放时间 / 票价 | 每月   | 景区政策可能变化      |
| 预约规则        | 每月   | 预约渠道、放票时间可能变化 |
| 避坑提示        | 每季度  | 坑点可能变化        |
| 美食推荐        | 每季度  | 餐厅可能开业 / 倒闭   |
| 行程攻略        | 每半年  | 经典行程相对稳定      |
| 人文历史        | 每年   | 历史文化相对稳定      |

**更新方式**：



1. **自动检测**：定期爬取官方网站，检测信息变化

2. **用户反馈**：用户报告错误信息，触发更新

3. **人工审核**：运营人员定期检查和更新

4. **版本管理**：每次更新记录版本，支持回滚

**过期处理**：



* 设置数据有效期（如预约规则有效期 6 个月）

* 过期数据自动标记，提醒更新

* 过期数据在检索时降低权重

* 长期未更新的数据自动下线



***

## 八、性能优化方案

### 8.1 性能目标



| 指标           | 目标值          | 说明                 |
| ------------ | ------------ | ------------------ |
| **API 响应时间** | <500ms（P95）  | 普通 API 接口          |
| **行程生成时间**   | <4s（P95）     | 包含 RAG 检索 + LLM 生成 |
| **对话响应时间**   | <2s（首 Token） | 流式输出，首 Token 延迟    |
| **检索时间**     | <200ms       | 向量检索 + 重排序         |
| **嵌入时间**     | <50ms / 条    | 单条文本嵌入             |
| **并发用户数**    | 100+         | 同时在线用户             |
| **系统可用性**    | >99.5%       | 月度可用性              |
| **数据库查询**    | <100ms（P95）  | MySQL 查询           |
| **缓存命中率**    | >70%         | Redis 缓存命中率        |

### 8.2 后端性能优化

#### 1. 异步处理



* **全异步 API**：FastAPI 原生异步，所有 IO 操作异步化

* **异步数据库**：使用 asyncmy（MySQL 异步驱动）

* **异步 LLM 调用**：使用 aiohttp 调用 LLM API

* **异步任务**：耗时操作（如批量向量化）异步处理，不阻塞主流程

#### 2. 缓存优化



| 缓存层级        | 缓存内容            | 缓存工具            | 过期时间       |
| ----------- | --------------- | --------------- | ---------- |
| L1 内存缓存     | 热点数据、配置、嵌入模型    | Python 字典 / LRU | 永久 / 手动刷新  |
| L2 Redis 缓存 | 用户信息、会话、行程、检索结果 | Redis           | 1 分钟 - 7 天 |
| L3 数据库缓存    | 查询结果、索引         | MySQL 查询缓存      | -          |
| L4 CDN 缓存   | 静态资源、图片         | Nginx/CDN       | 7 天 - 30 天 |

**缓存策略**：



* Cache-Aside：先查缓存，命中则返回，未命中则查数据库并写入缓存

* Write-Through：写入数据库时同时更新缓存

* 缓存预热：系统启动时预热热点数据（热门目的地、景点）

* 缓存穿透防护：空值缓存、布隆过滤器

* 缓存击穿防护：互斥锁、永不过期 + 异步更新

* 缓存雪崩防护：随机过期时间、多级缓存

#### 3. 数据库优化



* **索引优化**：为常用查询字段建立索引，定期分析索引使用情况

* **查询优化**：避免 SELECT \*，只查询需要的字段；使用 EXPLAIN 分析慢查询

* **连接池**：使用数据库连接池，避免频繁创建连接

* **读写分离**：主库写，从库读（大规模时）

* **分库分表**：数据量过大时按用户 ID 或时间分表

* **慢查询监控**：记录慢查询日志，定期优化

#### 4. LLM 调用优化



* **提示词优化**：精简提示词，减少 Token 消耗

* **流式输出**：使用 SSE 流式输出，降低首 Token 延迟

* **批量调用**：支持批量请求，减少网络开销

* **模型降级**：主模型不可用时自动切换到备选模型

* **结果缓存**：相同查询的结果缓存，避免重复调用

* **Token 控制**：控制输入和输出 Token 数，避免超长请求

### 8.3 前端性能优化

#### 1. 构建优化



* **Vite 构建**：使用 Vite 作为构建工具，快速冷启动和热更新

* **代码分割**：按路由分割代码，按需加载

* **Tree Shaking**：移除未使用的代码

* **资源压缩**：JS/CSS/ 图片压缩

* **CDN 加速**：静态资源使用 CDN

#### 2. 运行时优化



* **虚拟列表**：长列表使用虚拟滚动，只渲染可见区域

* **懒加载**：图片、组件按需加载

* **防抖节流**：搜索、滚动等高频操作防抖节流

* **Web Worker**：耗时计算（如地图渲染）放到 Web Worker

* **缓存策略**：API 结果缓存，避免重复请求

#### 3. 用户体验优化



* **骨架屏**：加载时显示骨架屏，减少白屏时间

* **加载动画**：长时间操作显示加载动画和进度

* **乐观更新**：用户操作后先更新 UI，后台同步数据

* **错误降级**：API 失败时显示友好提示和重试按钮

* **预加载**：预加载下一页可能需要的数据

### 8.4 RAG 性能优化

#### 1. 检索优化



* **索引优化**：使用 HNSW 索引，平衡检索速度和精度

* **批量检索**：支持批量查询，减少网络开销

* **预过滤**：先按元数据过滤，再进行向量检索，减少计算量

* **缓存检索结果**：相同查询的检索结果缓存 7 天

* **异步预检索**：用户输入时异步预检索，提交时直接使用结果

#### 2. 嵌入优化



* **嵌入缓存**：相同文本的嵌入结果永久缓存

* **批量嵌入**：一次处理 32 条文本，提升吞吐量

* **GPU 加速**：使用 GPU 进行嵌入计算

* **模型量化**：使用量化模型，减少内存和计算开销

#### 3. 生成优化



* **流式输出**：SSE 流式输出，首 Token 延迟 < 2s

* **提示词精简**：减少上下文长度，降低 Token 消耗

* **结果缓存**：相同查询的生成结果缓存 1 天

* **模型选择**：简单查询使用小模型，复杂查询使用大模型



***

## 九、安全方案

### 9.1 认证授权

#### 认证方式：JWT（JSON Web Token）



* **Access Token**：短期有效（2 小时），用于 API 访问

* **Refresh Token**：长期有效（7 天），用于刷新 Access Token

* **Token 存储**：客户端存储在 HttpOnly Cookie 中，防止 XSS

* **Token 刷新**：Access Token 过期前自动刷新，用户无感知

#### 授权方式：RBAC（基于角色的访问控制）



| 角色       | 权限                     |
| -------- | ---------------------- |
| **普通用户** | 对话、规划、探索、个人行程管理        |
| **内容编辑** | 普通用户权限 + 知识库录入、提交审核    |
| **审核员**  | 内容编辑权限 + 知识审核、数据质量监控   |
| **管理员**  | 审核员权限 + 用户管理、系统设置、数据分析 |

#### 权限控制



* **API 级**：接口装饰器校验角色权限

* **数据级**：用户只能访问自己的数据（行程、会话等）

* **前端级**：根据角色显示 / 隐藏菜单和按钮

* **操作日志**：敏感操作记录日志（删除、修改权限等）

### 9.2 数据安全

#### 数据加密



* **传输加密**：全站 HTTPS，TLS 1.2+

* **存储加密**：敏感字段（密码、手机号）加密存储

* **密码加密**：bcrypt 算法，cost factor=12

* **数据库加密**：MySQL 数据文件加密（可选）

#### 数据脱敏



* **日志脱敏**：日志中不记录密码、Token、手机号等敏感信息

* **接口脱敏**：返回用户信息时脱敏（手机号中间 4 位用 \* 代替）

* **展示脱敏**：前端展示敏感信息时脱敏

#### 数据备份



* **定时备份**：MySQL 每日全量备份，每小时增量备份

* **异地备份**：备份文件存储到异地对象存储

* **备份验证**：定期验证备份文件可恢复

* **恢复演练**：每季度进行一次恢复演练

### 9.3 接口安全

#### 限流控制



| 限流维度   | 限制          | 说明            |
| ------ | ----------- | ------------- |
| IP 限流  | 100 次 / 分钟  | 防止恶意刷接口       |
| 用户限流   | 60 次 / 分钟   | 防止单个用户过度使用    |
| API 限流 | 1000 次 / 分钟 | 保护单个 API 不被打垮 |
| 对话限流   | 20 次 / 小时   | 防止 LLM 调用过度消耗 |
| 规划限流   | 10 次 / 天    | 防止行程生成过度消耗    |

**限流实现**：



* 使用 Redis 计数器实现滑动窗口限流

* 超出限制返回 429 状态码和重试时间

* 关键 API（登录、注册）使用更严格的限流

#### 输入校验



* **参数校验**：使用 Pydantic 模型校验所有输入参数

* **SQL 注入防护**：使用参数化查询，禁止拼接 SQL

* **XSS 防护**：输出时转义 HTML 特殊字符

* **CSRF 防护**：使用 SameSite Cookie 和 CSRF Token

* **文件上传校验**：校验文件类型、大小、内容，禁止上传可执行文件

#### 错误处理



* **统一错误格式**：所有错误返回统一格式，不暴露堆栈信息

* **错误码规范**：使用业务错误码，不直接返回数据库错误

* **敏感信息保护**：错误信息中不包含敏感信息（SQL、文件路径等）

* **降级处理**：依赖服务不可用时优雅降级，返回友好提示

### 9.4 运维安全

#### 服务器安全



* **最小权限**：服务进程使用非 root 用户运行

* **防火墙**：只开放必要端口（80、443），其他端口禁止访问

* **SSH 安全**：禁用密码登录，使用密钥登录；修改默认端口

* **安全更新**：定期更新系统和软件包，修复安全漏洞

* **入侵检测**：安装入侵检测系统，监控异常行为

#### 容器安全



* **镜像安全**：使用官方基础镜像，定期扫描镜像漏洞

* **最小镜像**：多阶段构建，只包含运行时必要文件

* **资源限制**：限制容器 CPU、内存使用，防止资源耗尽

* **只读文件系统**：容器根文件系统只读，必要目录挂载可写卷

#### 监控告警



* **安全监控**：监控异常登录、异常 API 调用、数据异常访问

* **日志审计**：所有敏感操作记录审计日志，不可篡改

* **实时告警**：发现安全事件实时告警（邮件、短信、钉钉）

* **应急响应**：制定安全事件应急响应预案，定期演练



***

## 十、部署方案

### 10.1 部署架构



```
&#x20;                   ┌─────────────┐

&#x20;                   │   CDN/DNS   │

&#x20;                   └──────┬──────┘

&#x20;                          │

&#x20;                   ┌──────▼──────┐

&#x20;                   │  Nginx网关   │  反向代理、负载均衡、SSL、静态资源

&#x20;                   └──────┬──────┘

&#x20;                          │

&#x20;             ┌────────────┼────────────┐

&#x20;             │            │            │

&#x20;       ┌─────▼─────┐ ┌───▼─────┐ ┌───▼─────┐

&#x20;       │  Web前端   │ │  API服务 │ │ 管理后台 │

&#x20;       │  (静态文件)│ │ (FastAPI)│ │ (静态文件)│

&#x20;       └───────────┘ └─────┬────┘ └─────────┘

&#x20;                             │

&#x20;             ┌───────────────┼───────────────┐

&#x20;             │               │               │

&#x20;       ┌─────▼─────┐  ┌─────▼─────┐  ┌─────▼─────┐

&#x20;       │   MySQL    │  │   Redis   │  │  Chroma   │

&#x20;       │  (主从复制) │  │ (主从复制) │  │ (持久化)  │

&#x20;       └───────────┘  └───────────┘  └───────────┘

&#x20;                             │

&#x20;                   ┌─────────▼─────────┐

&#x20;                   │   异步任务队列     │  RabbitMQ / Redis Stream

&#x20;                   │  (批量向量化等)    │

&#x20;                   └───────────────────┘
```

### 10.2 开发环境部署

**使用 Docker Compose 一键启动**



```
\# docker-compose.yml

version: '3.8'

services:

&#x20; # MySQL数据库

&#x20; mysql:

&#x20;   image: mysql:8.0

&#x20;   environment:

&#x20;     MYSQL\_ROOT\_PASSWORD: \${MYSQL\_ROOT\_PASSWORD}

&#x20;     MYSQL\_DATABASE: \${MYSQL\_DATABASE}

&#x20;     MYSQL\_USER: \${MYSQL\_USER}

&#x20;     MYSQL\_PASSWORD: \${MYSQL\_PASSWORD}

&#x20;   ports:

&#x20;     - "3306:3306"

&#x20;   volumes:

&#x20;     - mysql\_data:/var/lib/mysql

&#x20;   healthcheck:

&#x20;     test: \["CMD", "mysqladmin", "ping", "-h", "localhost"]

&#x20;     interval: 10s

&#x20;     timeout: 5s

&#x20;     retries: 5

&#x20; # Redis缓存

&#x20; redis:

&#x20;   image: redis:7.0-alpine

&#x20;   ports:

&#x20;     - "6379:6379"

&#x20;   volumes:

&#x20;     - redis\_data:/data

&#x20;   healthcheck:

&#x20;     test: \["CMD", "redis-cli", "ping"]

&#x20;     interval: 10s

&#x20;     timeout: 5s

&#x20;     retries: 5

&#x20; # 后端API服务

&#x20; backend:

&#x20;   build:

&#x20;     context: ./backend

&#x20;     dockerfile: Dockerfile

&#x20;   ports:

&#x20;     - "8000:8000"

&#x20;   environment:

&#x20;     - DATABASE\_URL=mysql+asyncmy://\${MYSQL\_USER}:\${MYSQL\_PASSWORD}@mysql:3306/\${MYSQL\_DATABASE}

&#x20;     - REDIS\_URL=redis://redis:6379/0

&#x20;     - CHROMA\_PERSIST\_DIR=/data/chroma

&#x20;   volumes:

&#x20;     - chroma\_data:/data/chroma

&#x20;     - ./backend:/app

&#x20;   depends\_on:

&#x20;     mysql:

&#x20;       condition: service\_healthy

&#x20;     redis:

&#x20;       condition: service\_healthy

&#x20;   command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

&#x20; # 用户端前端

&#x20; frontend:

&#x20;   build:

&#x20;     context: ./frontend

&#x20;     dockerfile: Dockerfile

&#x20;   ports:

&#x20;     - "5173:80"

&#x20;   depends\_on:

&#x20;     - backend

&#x20; # 管理后台

&#x20; frontend-admin:

&#x20;   build:

&#x20;     context: ./frontend-admin

&#x20;     dockerfile: Dockerfile

&#x20;   ports:

&#x20;     - "5174:80"

&#x20;   depends\_on:

&#x20;     - backend

volumes:

&#x20; mysql\_data:

&#x20; redis\_data:

&#x20; chroma\_data:
```

**启动命令**：



```
\# 复制环境变量配置

cp .env.example .env

\# 修改.env中的配置

\# 启动所有服务

docker-compose up -d

\# 查看服务状态

docker-compose ps

\# 查看日志

docker-compose logs -f backend

\# 停止服务

docker-compose down
```

### 10.3 生产环境部署

#### 部署策略：蓝绿部署



1. **蓝环境**：当前生产环境，运行稳定版本

2. **绿环境**：新版本环境，部署后进行测试

3. **切换**：测试通过后，Nginx 切换流量到绿环境

4. **回滚**：出现问题时，快速切回蓝环境

#### 服务器配置建议



| 配置项        | 最低配置     | 推荐配置          | 说明                 |
| ---------- | -------- | ------------- | ------------------ |
| **应用服务器**  | 2 核 4G   | 4 核 8G        | 运行 FastAPI 和 Nginx |
| **数据库服务器** | 2 核 4G   | 4 核 8G        | 运行 MySQL 和 Redis   |
| **向量服务器**  | 4 核 8G   | 8 核 16G + GPU | 运行 Chroma 和嵌入模型    |
| **带宽**     | 5Mbps    | 20Mbps        | 根据用户量调整            |
| **存储**     | 100G SSD | 500G SSD      | 数据库、备份、日志          |

#### CI/CD 流程



```
代码提交（Git Push）

&#x20;   │

&#x20;   ▼

┌─────────────┐

│  1. 代码检查  │  Lint、类型检查、单元测试

│  CI Pipeline │

└─────────────┘

&#x20;   │

&#x20;   ▼

┌─────────────┐

│  2. 构建镜像  │  构建Docker镜像，推送到镜像仓库

│  Build Image │

└─────────────┘

&#x20;   │

&#x20;   ▼

┌─────────────┐

│  3. 部署测试  │  部署到测试环境，运行集成测试

│  Deploy Test │

└─────────────┘

&#x20;   │

&#x20;   ▼

┌─────────────┐

│  4. 人工审核  │  审核通过后触发生产部署

│  Manual Review│

└─────────────┘

&#x20;   │

&#x20;   ▼

┌─────────────┐

│  5. 生产部署  │  蓝绿部署到生产环境

│  Deploy Prod │

└─────────────┘

&#x20;   │

&#x20;   ▼

┌─────────────┐

│  6. 监控验证  │  监控系统状态，验证部署成功

│  Monitor     │

└─────────────┘
```

### 10.4 监控方案

#### 监控指标



| 类别        | 指标          | 告警阈值         |
| --------- | ----------- | ------------ |
| **系统指标**  | CPU 使用率     | >80% 持续 5 分钟 |
|           | 内存使用率       | >85% 持续 5 分钟 |
|           | 磁盘使用率       | >90%         |
|           | 网络带宽        | >80% 持续 5 分钟 |
| **应用指标**  | API 响应时间    | P95 > 1s     |
|           | API 错误率     | >5% 持续 1 分钟  |
|           | 并发用户数       | >1000        |
|           | LLM 调用成功率   | <95%         |
|           | RAG 检索时间    | >500ms       |
| **业务指标**  | 日活用户        | 环比下降 > 20%   |
|           | 行程生成成功率     | <90%         |
|           | 用户满意度       | <80%         |
| **数据库指标** | 慢查询数        | >10 / 分钟     |
|           | 连接数使用率      | >80%         |
|           | 主从延迟        | >10s         |
| **缓存指标**  | 缓存命中率       | <60%         |
|           | Redis 内存使用率 | >85%         |

#### 监控工具



* **Prometheus**：指标采集和存储

* **Grafana**：可视化仪表盘

* **ELK Stack**：日志收集、分析、可视化

* **AlertManager**：告警管理和通知

* **Sentry**：错误追踪和性能监控

#### 告警通知



* **P0（紧急）**：电话 + 短信 + 钉钉 + 邮件，15 分钟内响应

* **P1（高）**：短信 + 钉钉 + 邮件，1 小时内响应

* **P2（中）**：钉钉 + 邮件，4 小时内响应

* **P3（低）**：邮件，24 小时内响应



***

## 十一、开发计划和里程碑

### 11.1 开发阶段划分



| 阶段       | 时间        | 目标     | 主要工作                        |
| -------- | --------- | ------ | --------------------------- |
| **第一阶段** | 第 1-2 周   | 基础框架搭建 | 项目初始化、数据库设计、基础 API、RAG 基础框架 |
| **第二阶段** | 第 3-4 周   | 核心功能开发 | 对话引擎、规划引擎、RAG 检索、知识库管理      |
| **第三阶段** | 第 5-6 周   | 前端开发   | 用户端前端、管理后台前端、地图集成           |
| **第四阶段** | 第 7-8 周   | 知识库建设  | 数据采集、清洗、审核、向量化、入库           |
| **第五阶段** | 第 9-10 周  | 测试优化   | 单元测试、集成测试、性能优化、安全加固         |
| **第六阶段** | 第 11-12 周 | 上线部署   | 部署上线、监控告警、用户反馈、持续优化         |

### 11.2 详细里程碑

#### M1：基础框架完成（第 2 周末）

**目标**：项目基础框架搭建完成，可运行

**交付物**：



* [ ] 项目初始化（后端 FastAPI + 前端 Vue3）

* [ ] 数据库设计和初始化（15 + 核心表）

* [ ] 用户认证系统（注册、登录、JWT）

* [ ] 基础 API 框架（统一响应、错误处理、中间件）

* [ ] RAG 基础框架（向量数据库、嵌入模型、基础检索）

* [ ] Docker Compose 开发环境

* [ ] CI/CD 基础流程

**验收标准**：



* 后端服务可启动，API 文档可访问

* 用户可注册、登录、获取 Token

* 向量数据库可存储和检索向量

* Docker Compose 一键启动所有服务

#### M2：核心功能完成（第 4 周末）

**目标**：核心业务功能开发完成

**交付物**：



* [ ] 对话引擎（意图识别、多轮对话、流式输出）

* [ ] 规划引擎（行程生成、调整、预算估算）

* [ ] RAG 引擎（查询理解、混合检索、重排序、增强生成）

* [ ] 知识库管理（CRUD、批量导入导出、审核流程）

* [ ] 地图服务（地理编码、POI 搜索、路径规划）

* [ ] 探索功能（附近景点、热门景点、景点详情）

**验收标准**：



* 用户可通过对话生成行程

* 行程包含景点、时间、交通、预算

* RAG 检索可返回相关知识

* 知识库可管理和审核数据

#### M3：前端开发完成（第 6 周末）

**目标**：用户端和管理后台前端开发完成

**交付物**：



* [ ] 用户端：对话页（首页）

* [ ] 用户端：行程详情页（时间轴、地图、预算、预约提醒、避坑提示）

* [ ] 用户端：探索页（地图探索、景点搜索）

* [ ] 用户端：我的页（个人信息、历史行程、设置）

* [ ] 管理后台：数据看板

* [ ] 管理后台：知识库管理（6 大分类）

* [ ] 管理后台：审核管理

* [ ] 管理后台：用户管理、系统设置

**验收标准**：



* 用户端所有页面可正常访问和使用

* 管理后台所有功能可正常操作

* 地图可正常显示和交互

* 响应式布局，移动端适配

#### M4：知识库建设完成（第 8 周末）

**目标**：知识库数据建设完成，覆盖主要热门目的地

**交付物**：



* [ ] 景点库：5000 + 景点（覆盖 100 + 城市）

* [ ] 行程库：1000 + 经典行程

* [ ] 美食库：2000 + 美食推荐

* [ ] 住宿库：500 + 住宿区域

* [ ] 避坑库：1000 + 避坑提示

* [ ] 人文库：1000 + 人文介绍

* [ ] 所有数据经过清洗、审核、向量化

* [ ] 数据质量评分体系建立

**验收标准**：



* 知识库覆盖 100 + 热门城市

* 检索准确率 > 85%

* 数据审核通过率 > 90%

* 热门目的地查询可返回丰富结果

#### M5：测试优化完成（第 10 周末）

**目标**：系统测试完成，性能和安全达标

**交付物**：



* [ ] 单元测试覆盖率 > 70%

* [ ] 集成测试覆盖核心流程

* [ ] 端到端测试覆盖主要用户路径

* [ ] 性能测试达标（API 响应 < 500ms，行程生成 < 4s）

* [ ] 安全测试通过（无高危漏洞）

* [ ] 压力测试通过（支持 100 并发用户）

* [ ] 性能优化（缓存、异步、数据库优化）

* [ ] 安全加固（限流、加密、权限控制）

**验收标准**：



* 所有测试用例通过

* 性能指标达标

* 无高危安全漏洞

* 系统稳定运行 24 小时无异常

#### M6：上线部署完成（第 12 周末）

**目标**：系统上线，可对外提供服务

**交付物**：



* [ ] 生产环境部署（蓝绿部署）

* [ ] 监控告警系统搭建

* [ ] 日志系统搭建

* [ ] 备份恢复机制建立

* [ ] 用户文档和操作手册

* [ ] 运维文档和应急预案

* [ ] 小范围灰度发布

* [ ] 用户反馈收集和处理机制

**验收标准**：



* 系统稳定运行，可用性 > 99.5%

* 监控告警正常工作

* 备份可正常恢复

* 用户可正常注册、使用

* 无重大 Bug 和安全问题

### 11.3 团队配置建议



| 角色        | 人数  | 职责                      |
| --------- | --- | ----------------------- |
| **产品经理**  | 1   | 产品规划、需求管理、用户调研          |
| **后端开发**  | 2   | API 开发、RAG 引擎、知识库、性能优化  |
| **前端开发**  | 2   | 用户端、管理后台、地图集成           |
| **算法工程师** | 1   | LLM 优化、RAG 检索、嵌入模型、数据处理 |
| **测试工程师** | 1   | 测试用例、自动化测试、性能测试、安全测试    |
| **运维工程师** | 0.5 | 部署、监控、运维（可兼职或使用云服务）     |
| **运营人员**  | 1   | 知识库建设、数据审核、用户运营         |

**总计**：8.5 人



***

## 十二、风险和应对

### 12.1 技术风险



| 风险              | 影响 | 概率 | 应对措施                                |
| --------------- | -- | -- | ----------------------------------- |
| **LLM API 不稳定** | 高  | 中  | 多模型备份（DeepSeek + Qwen 本地），降级策略，结果缓存 |
| **向量数据库性能瓶颈**   | 中  | 低  | 选择成熟的 Chroma，优化索引，大规模时迁移到 Milvus    |
| **检索准确率低**      | 高  | 中  | 混合检索 + 重排序，持续优化提示词，人工审核知识库，用户反馈驱动优化 |
| **LLM 生成幻觉**    | 高  | 中  | 严格控制上下文，增加事实校验，关键数据人工审核，知识库优先       |
| **系统并发瓶颈**      | 中  | 中  | 微服务架构，水平扩展，缓存优化，异步处理，限流保护           |
| **数据安全漏洞**      | 高  | 低  | 安全审计，渗透测试，代码审查，安全加固，定期漏洞扫描          |

### 12.2 数据风险



| 风险          | 影响 | 概率 | 应对措施                            |
| ----------- | -- | -- | ------------------------------- |
| **知识库覆盖不足** | 高  | 中  | 优先覆盖热门目的地，逐步扩充，UGC 众包贡献，与文旅局合作  |
| **数据质量差**   | 高  | 中  | 严格审核流程，质量评分体系，多源交叉验证，用户反馈驱动更新   |
| **数据过时**    | 中  | 高  | 建立数据更新机制，设置有效期，定期审核更新，用户反馈触发更新  |
| **数据版权问题**  | 高  | 中  | 使用公开数据集，尊重版权，标注来源，避免直接复制，原创内容为主 |
| **数据丢失**    | 高  | 低  | 定时备份，异地备份，备份验证，恢复演练，多副本存储       |

### 12.3 业务风险



| 风险            | 影响 | 概率 | 应对措施                             |
| ------------- | -- | -- | -------------------------------- |
| **用户接受度低**    | 高  | 中  | A/B 测试，用户调研，持续优化用户体验，降低使用门槛，口碑传播 |
| **竞品模仿**      | 中  | 高  | 快速迭代，建立壁垒（数据资产、用户社区、品牌），持续创新     |
| **商业模式不清晰**   | 高  | 低  | 多元化收入，快速验证，及时调整，现金流管理            |
| **用户增长不及预期**  | 高  | 中  | 多渠道获客，KOL 合作，产品力提升，用户推荐激励，精细化运营  |
| **LLM 成本超预算** | 中  | 中  | 严格控制调用频率，增加缓存，优化提示词，设置费用告警，成本监控  |

### 12.4 运营风险



| 风险           | 影响 | 概率 | 应对措施                               |
| ------------ | -- | -- | ---------------------------------- |
| **内容审核成本高**  | 中  | 高  | 自动化审核 + 人工抽检，建立审核标准和流程，审核工具提效，众包审核 |
| **知识库维护成本高** | 中  | 高  | 自动化更新，用户众包，建立数据质量评分体系，优先级管理        |
| **团队人员流失**   | 高  | 中  | 知识沉淀，文档完善，代码规范，交叉培训，合理激励           |
| **第三方依赖风险**  | 中  | 中  | 多供应商备份，抽象接口，可替换设计，降级策略             |



***

## 十三、总结

### 13.1 技术方案总结

本技术实现方案围绕**RAG 知识库增强**这一核心，设计了完整的技术架构、模块划分、数据库设计、API 接口、RAG 实现、知识库构建、性能优化、安全方案、部署方案和开发计划。

**核心技术特点**：



1. **分层架构**：客户端层 → 网关层 → 应用层 → 基础服务层 → 数据层，职责清晰

2. **RAG 核心**：查询理解 → 混合检索 → 重排序 → 上下文组装 → 增强生成 → 输出处理

3. **知识库独立**：6 大分类知识库，完整的数据采集、清洗、审核、向量化、入库流程

4. **高性能**：异步处理、多级缓存、数据库优化、LLM 调用优化，行程生成 < 4 秒

5. **高安全**：JWT 认证、RBAC 授权、数据加密、限流控制、输入校验、运维安全

6. **易部署**：Docker 容器化、Docker Compose 开发环境、蓝绿部署、CI/CD 自动化

7. **可扩展**：微服务架构、水平扩展、向量数据库可迁移（Chroma→Milvus）

### 13.2 关键成功因素



1. **知识库质量**：高质量的知识库是 RAG 成功的基础，需要严格的审核流程和持续的更新机制

2. **检索准确率**：准确的检索是生成高质量结果的前提，需要混合检索 + 重排序 + 持续优化

3. **提示词工程**：精心设计的提示词能充分发挥 LLM 能力，需要持续迭代和优化

4. **性能优化**：良好的用户体验需要快速的响应时间，需要全链路的性能优化

5. **成本控制**：可持续的运营需要合理的成本控制，需要缓存、限流、模型选择等策略

6. **数据安全**：用户信任需要可靠的数据安全，需要加密、备份、权限控制等措施

### 13.3 下一步行动



1. **技术评审**：组织技术团队评审本方案，确认技术可行性和资源需求

2. **原型验证**：快速搭建 RAG 原型，验证检索和生成效果

3. **详细设计**：对核心模块进行详细设计，包括类图、时序图、接口定义

4. **任务拆解**：将开发计划拆解为具体的任务和用户故事

5. **启动开发**：按照第一阶段计划，启动基础框架搭建



***

**本文档为 RAG 知识库增强产品的技术实现方案，将根据产品进展和技术发展持续更新。**