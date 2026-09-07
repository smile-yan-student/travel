# 代码目录结构梳理

> 本文档按「模块 → 目录 → 职责」梳理当前项目代码，便于快速定位与新人上手。
> 更新日期：2026-08-28

## 0. 项目总览

```
travel/                          # 项目根目录
├── backend/                     # 后端：FastAPI (Python)
│   ├── app/                     #   业务代码包
│   ├── scripts/                 #   运维脚本
│   ├── .env                     #   环境配置（高德 Key / DB / JWT）
│   ├── requirements.txt         #   依赖清单
│   └── run.py                   #   启动入口（uvicorn reload, :8000）
├── frontend/                    # 前端：Vue3 + Vite + 高德 JS API
│   └── src/                     #   源码
├── docs/                        # 项目文档
├── screenshots/                 # 界面截图归档
├── AGENTS.md                    # 项目协作约定（变更记录强制）
├── README.md                    # 项目说明 + 变更日志
├── docs_app_preview.png         # 应用预览图
└── start.sh                     # 一键启动脚本
```

---

## 1. 后端模块（backend/）

### 1.1 入口与路由
| 文件 | 职责 |
|---|---|
| `run.py` | 后端启动入口，uvicorn reload 模式，端口 8000 |
| `app/main.py` | FastAPI 应用装配：lifespan（高德探测 + 建表 + 恢复后台 Key）、CORS、全部 `/api/*` 接口（对话规划 / 探索 / 认证 / 足迹 / 会话 / 站点配置）、挂载 admin 路由 |

### 1.2 配置层
| 文件 | 职责 |
|---|---|
| `app/config.py` | 全局配置：环境变量读取、高德 Key 可用性探测状态、**后台可运行时覆盖的高德 Key**（`set_amap_key` / `amap_key_source`）、JWT 密钥、Ollama 模型、MySQL 连接 |

### 1.3 存储层
| 文件 | 职责 |
|---|---|
| `app/userstore.py` | C 端存储：users / trips / conversations 建表与 CRUD、JWT 签发与校验、bcrypt 密码、注册规则校验、登录鉴权（含 enabled 校验） |
| `app/admin_store.py` | 后台存储：admins / must_visit / site_config / generation_log 数据访问、管理员登录与鉴权、用户治理、行程/对话统计、配置读写（含敏感键隔离） |

### 1.4 业务核心（行程规划引擎）
| 文件 | 职责 |
|---|---|
| `app/planner.py` | **行程规划引擎**（`build_plan` 主入口）：`_geo_plan` 行政分级枚举景点 → must_visit 必去地标注入（表优先）→ 聚类 → 圈层分配 → 逐日构建；同地标去重、跨天区域不重复 |
| `app/intent.py` | 对话意图解析：`parse_intent` 区分 plan/chat、`_rule_extract` 最新消息优先提取目的地/天数/预算/风格等参数、城市提取 |
| `app/ai.py` | 本地 AI 模型（Ollama）：模型可用性探测、模型解析、对话回复生成 |
| `app/amap.py` | **高德 Web 服务客户端**：地理编码 / POI 检索 / 行政枚举 / 路径规划 / 天气；真实 Key 不可用时诚实降级 mock；全部接口接 TTL 缓存 |

### 1.5 后台管理（M1-M9）
| 文件 | 职责 |
|---|---|
| `app/admin_router.py` | 管理后台路由 `/api/admin/*`：登录鉴权（super/ops 两级）、仪表盘、用户管理、行程足迹、对话运营、内容管理（must_visit/城市库）、AI 管理、高德与缓存管理（含 **API Key 保存/探测/清缓存**）、系统配置 |

### 1.6 基础设施
| 文件 | 职责 |
|---|---|
| `app/cache.py` | 线程安全 TTL 缓存（进程内）：geo/poi/route/weather 分 TTL，支持后台动态覆盖（`set_ttl`/`get_ttl`） |
| `app/models.py` | Pydantic 请求/响应模型（PlanRequest、ChatPlanRequest、ExploreRequest、POI 等） |

### 1.7 数据资产（app/data/）
| 文件 | 职责 |
|---|---|
| `data/must_visit.py` | 城市「必打卡」地标知识库（后台建表时的种子源，已迁移至 MySQL 后为兜底） |
| `data/place_geo.json` | 内置地名坐标表：全国地级市/区县归属与坐标（真实 Key 不可用时的定位兜底） |
| `data/app.db` | 本地 SQLite 缓存库（演进遗留，正式数据在 MySQL） |

### 1.8 部署与配置
| 文件 | 职责 |
|---|---|
| `.env` / `.env.example` | 环境变量：`AMAP_KEY`（Web 服务 Key）、`DB_*`（MySQL）、`JWT_SECRET`、`OLLAMA_*`（本地模型） |
| `requirements.txt` | Python 依赖清单 |
| `scripts/` | 运维辅助脚本 |

---

## 2. 前端模块（frontend/）

### 2.1 应用骨架
| 文件 | 职责 |
|---|---|
| `src/main.js` | Vue 应用入口 |
| `src/App.vue` | 根组件：底部三板块导航（对话/探索/我的），admin 路由自动隐藏 |
| `src/router/index.js` | 路由表：`/`（对话）、`/plan`（行程全屏）、`/explore`（探索）、`/me`（我的）、`/admin`（后台登录）、`/admin/app`（后台应用） |
| `src/styles/main.css` | 全局样式与 CSS 变量 |

### 2.2 C 端视图（三板块）
| 文件 | 职责 |
|---|---|
| `views/Home.vue` | **对话板块（默认）**：品牌 Hero（文案接口化）、对话规划入口 ChatPlanner |
| `views/Explore.vue` | **探索板块**：地图选点 → 放射状展示周边可游览景点 |
| `views/Me.vue` | **我的板块**：登录/注册、足迹、历史会话管理 |
| `views/Plan.vue` | 行程详情全屏页（由对话生成的行程进入） |

### 2.3 核心组件
| 文件 | 职责 |
|---|---|
| `components/ChatPlanner.vue` | **对话规划组件**：多轮对话、历史会话时间线、上拉加载、意图驱动生成行程 |
| `components/MapView.vue` | 地图渲染：marker 锚点居中、Polyline 平滑采样线、按天分色、卡片联动聚焦 |
| `components/DayCard.vue` | 单日行程卡片 |

### 2.4 工具与接口层
| 文件 | 职责 |
|---|---|
| `api/index.js` | API 封装：C 端接口 + admin 接口（`adminRequest`）+ 站点配置 |
| `utils/amap.js` | 高德 JS API 工具（地图初始化/标记） |
| `utils/convo.js` | 会话本地缓存/合并逻辑（未登录会话保留） |
| `utils/user.js` | 用户态工具（登录态判断、token 存取） |
| `constants.js` | 常量定义（预算档位、旅行风格等） |

### 2.5 管理后台（views/admin/）
| 文件 | 职责 |
|---|---|
| `AdminLogin.vue` | 后台登录页 |
| `AdminApp.vue` | 后台布局：侧边栏 9 模块导航 + 面板切换 |
| `panels/DashboardPanel.vue` | M2 仪表盘 |
| `panels/UsersPanel.vue` | M3 用户管理 |
| `panels/TripsPanel.vue` | M4 行程与足迹 |
| `panels/ConversationsPanel.vue` | M5 对话运营 |
| `panels/ContentPanel.vue` | M6 内容与景点（必去地标库/城市库） |
| `panels/AiPanel.vue` | M7 AI 模型 |
| `panels/AmapPanel.vue` | M8 高德与缓存（含 **API Key 管理**） |
| `panels/ConfigPanel.vue` | M9 系统配置 |
| `panels/AdminsPanel.vue` | M1 管理员账号 |

---

## 3. 模块调用关系速览

```
用户 → Vue 视图(Home/Explore/Me) → api/index.js → FastAPI(main.py)
                                                  ├─ intent.py 解析意图 → planner.py 规划 → amap.py 数据
                                                  ├─ userstore.py / admin_store.py（MySQL）
                                                  └─ admin_router.py（后台 /api/admin/*，受 JWT 守卫）
对话规划链路：ChatPlanner → /api/chat/plan → intent(plan/chat) → planner.build_plan → amap(真实/mock) → 行程卡片+地图
后台管理链路：/admin → admin 登录(JWT) → 9 面板 → /api/admin/* → admin_store → MySQL
```

## 4. 常用命令

```bash
# 后端（端口 8000）
cd backend && ./.venv/bin/python run.py
# 前端（端口 5173）
cd frontend && npm run dev
# 接口文档
http://127.0.0.1:8000/docs
# 管理后台
http://127.0.0.1:5173/#/admin
```
