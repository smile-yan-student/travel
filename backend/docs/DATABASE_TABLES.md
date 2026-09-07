# 数据库表说明文档

> 本文档记录了 travel_app 数据库中所有表的作用、字段说明和使用场景。
>
> 所有新表必须在本文档中记录，表结构变更时应同步更新本文档。

## 目录

1. [用户和认证相关](#1-用户和认证相关)
2. [行程规划相关](#2-行程规划相关)
3. [地理和POI相关](#3-地理和poi相关)
4. [知识库相关](#4-知识库相关)
5. [配置和字典相关](#5-配置和字典相关)

---

## 1. 用户和认证相关

### 1.1 users（用户表）

**作用**：存储系统用户的基本信息，包括用户名、密码哈希、邮箱等。

**字段说明**：
| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | int | 用户ID（主键，自增） |
| username | varchar | 用户名（唯一） |
| password_hash | varchar | 密码哈希（bcrypt） |
| email | varchar | 邮箱 |
| nickname | varchar | 昵称 |
| avatar | varchar | 头像URL |
| status | tinyint | 状态（0=禁用，1=正常） |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

**使用场景**：
- 用户注册、登录、信息修改
- JWT 认证时查询用户信息
- 行程规划时关联用户

**代码引用**：
- `app/data/repositories/user_repository.py`
- `app/security/auth.py`

---

### 1.2 admins（管理员表）

**作用**：存储系统管理员的基本信息，用于后台管理系统的认证和授权。

**字段说明**：
| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | int | 管理员ID（主键，自增） |
| username | varchar | 用户名（唯一） |
| password_hash | varchar | 密码哈希（bcrypt） |
| role | varchar | 角色（admin=超级管理员，editor=编辑） |
| status | tinyint | 状态（0=禁用，1=正常） |
| last_login_at | datetime | 最后登录时间 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

**使用场景**：
- 后台管理系统登录
- 管理员权限验证
- 后台操作日志记录

**代码引用**：
- `app/data/repositories/admin_repository.py`
- `app/api/admin.py`

---

### 1.3 login_log（登录日志表）

**作用**：记录用户和管理员的登录日志，包括登录时间、IP地址、登录状态等。

**字段说明**：
| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | int | 日志ID（主键，自增） |
| user_type | varchar | 用户类型（user=普通用户，admin=管理员） |
| user_id | int | 用户ID |
| username | varchar | 用户名 |
| ip_address | varchar | 登录IP地址 |
| user_agent | varchar | 用户代理（浏览器信息） |
| status | tinyint | 登录状态（0=失败，1=成功） |
| created_at | datetime | 登录时间 |

**使用场景**：
- 登录安全审计
- 异常登录检测
- 用户行为分析

**代码引用**：
- `app/security/login_security.py`

---

## 2. 行程规划相关

### 2.1 trips（行程表）

**作用**：存储用户生成的行程规划，包括行程基本信息、规划参数、行程详情等。

**字段说明**：
| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | int | 行程ID（主键，自增） |
| trip_id | varchar | 行程唯一标识（UUID） |
| user_id | int | 用户ID（关联 users 表） |
| title | varchar | 行程标题 |
| destination | varchar | 目的地 |
| days | int | 行程天数 |
| travelers | int | 出行人数 |
| params | json | 规划参数（LLM识别的参数） |
| itinerary | json | 行程详情（每天的安排） |
| summary | text | 行程摘要 |
| status | tinyint | 状态（0=草稿，1=已完成，2=已删除） |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

**使用场景**：
- 行程规划生成和保存
- 用户行程历史查询
- 行程详情展示
- 行程分享和导出

**代码引用**：
- `app/api/trips.py`
- `app/api/itinerary.py`
- `app/services/orchestrator/`

---

### 2.2 conversations（会话表）

**作用**：存储用户与AI的对话会话，包括会话基本信息、对话历史、关联的行程等。

**字段说明**：
| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | int | 会话ID（主键，自增） |
| conversation_id | varchar | 会话唯一标识（UUID） |
| user_id | int | 用户ID（关联 users 表，未登录时为NULL） |
| title | varchar | 会话标题 |
| messages | json | 对话历史（消息列表） |
| current_trip_id | varchar | 当前关联的行程ID |
| status | tinyint | 状态（0=进行中，1=已结束，2=已删除） |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

**使用场景**：
- 多轮对话上下文管理
- 历史会话查询和恢复
- 会话与行程关联
- 用户对话行为分析

**代码引用**：
- `app/api/conversations.py`
- `app/services/session/`

---

### 2.3 generation_log（生成日志表）

**作用**：记录行程规划的生成日志，包括生成时间、参数、耗时、状态等，用于排查问题和性能优化。

**字段说明**：
| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | int | 日志ID（主键，自增） |
| log_id | varchar | 日志唯一标识（UUID） |
| user_id | int | 用户ID |
| conversation_id | varchar | 会话ID |
| trip_id | varchar | 行程ID |
| user_input | text | 用户输入 |
| intent | varchar | 识别的意图 |
| params | json | 规划参数 |
| poi_count | int | POI数量 |
| duration_ms | int | 生成耗时（毫秒） |
| status | varchar | 状态（success=成功，failed=失败） |
| error_message | text | 错误信息（失败时） |
| created_at | datetime | 创建时间 |

**使用场景**：
- 行程规划问题排查
- 性能监控和优化
- 用户行为分析
- 规划质量评估

**代码引用**：
- `app/services/orchestrator/`
- `app/core/planner.py`

---

## 3. 地理和POI相关

### 3.1 admin_regions（行政区域表）

**作用**：存储中国行政区域数据，包括省、市、区县三级，用于地理编码、行政分级枚举、地点补全等。

**字段说明**：
| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | int | 区域ID（主键，自增） |
| code | varchar | 行政区域代码（国家标准） |
| name | varchar | 区域名称 |
| level | tinyint | 级别（1=省，2=市，3=区县） |
| parent_code | varchar | 父级区域代码 |
| province | varchar | 所属省 |
| city | varchar | 所属市 |
| district | varchar | 所属区县 |
| longitude | decimal | 中心经度 |
| latitude | decimal | 中心纬度 |

**使用场景**：
- 地点行政区域补全（LLM识别地点后查询所属省/市/区县）
- 行政分级景点枚举（按省/市/区县三级枚举景点）
- 地理编码（地名→坐标）
- 同名地点消歧

**代码引用**：
- `app/core/geo_local.py`
- `app/services/planner/`
- `app/core/intent.py`

**数据来源**：
- 国家标准行政区域数据
- 阿里云 DataV 地理数据（https://datav.aliyun.com/portal/school/atlas/area_selector）

---

### 3.2 major_attractions（主要景点表）

**作用**：存储中国主要景点数据，作为POI检索的补充，确保主要景点不会因第三方POI数据覆盖不全而缺失。

**字段说明**：
| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | int | 景点ID（主键，自增） |
| name | varchar | 景点名称 |
| province | varchar | 所属省 |
| city | varchar | 所属市 |
| district | varchar | 所属区县 |
| address | varchar | 详细地址 |
| longitude | decimal | 经度 |
| latitude | decimal | 纬度 |
| category | varchar | 类别（景点/美食/购物/夜生活） |
| level | varchar | 等级（5A/4A/3A等） |
| rating | float | 评分 |
| description | text | 景点描述 |
| tags | json | 标签（人文/自然/历史/亲子等） |
| is_must_visit | tinyint | 是否必去景点（0=否，1=是） |
| is_landmark | tinyint | 是否城市地标（0=否，1=是） |
| open_hours | json | 开放时间 |
| ticket_price | varchar | 门票价格 |
| duration | varchar | 建议游玩时长 |
| source | varchar | 数据来源 |
| status | tinyint | 状态（0=待审核，1=已审核，2=已禁用） |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

**使用场景**：
- 行程规划前预加载主要景点
- 与第三方POI数据混合做规划
- 确保主要景点（如天安门、长城、西湖等）不会缺失
- 景点详情展示

**代码引用**：
- `app/core/planner.py`
- `app/services/planner/`

**数据来源**：
- 人工录入
- 第三方POI数据导入
- 后台管理系统维护

---

### 3.3 must_visit（必去景点表）

**作用**：存储各城市的必去景点数据，用于行程规划时优先注入必去景点，确保规划质量。

**字段说明**：
| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | int | ID（主键，自增） |
| city | varchar | 城市名称 |
| province | varchar | 所属省 |
| name | varchar | 景点名称 |
| category | varchar | 类别 |
| priority | int | 优先级（数字越小优先级越高） |
| reason | text | 必去理由 |
| longitude | decimal | 经度 |
| latitude | decimal | 纬度 |
| tags | json | 标签 |
| status | tinyint | 状态（0=禁用，1=启用） |
| created_at | datetime | 创建时间 |

**使用场景**：
- 行程规划时优先注入必去景点
- 确保规划包含城市标志性景点
- 景点推荐排序

**代码引用**：
- `app/core/planner.py`
- `app/data/static/must_visit.py`（本地默认值，数据库优先）

---

### 3.4 poi_cache（POI缓存表）

**作用**：缓存从第三方地图服务（高德/腾讯）检索的POI数据，减少第三方API调用，提高规划性能。

**字段说明**：
| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | int | ID（主键，自增） |
| cache_key | varchar | 缓存键（城市+类别+关键词） |
| city | varchar | 城市 |
| province | varchar | 省份（富化字段，用于解决同名城市问题） |
| category | varchar | 类别（景点/美食/购物/夜生活） |
| keyword | varchar | 检索关键词 |
| poi_id | varchar | 第三方POI ID |
| name | varchar | POI名称 |
| address | varchar | 地址 |
| longitude | decimal | 经度 |
| latitude | decimal | 纬度 |
| category_code | varchar | 类别代码 |
| rating | float | 评分 |
| tel | varchar | 电话 |
| photos | json | 照片 |
| source | varchar | 数据来源（amap/tencent） |
| expires_at | datetime | 过期时间 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

**使用场景**：
- POI检索结果缓存
- 减少第三方API调用
- 提高行程规划性能
- 离线POI数据查询

**代码引用**：
- `app/services/map/poi.py`
- `app/infrastructure/cache.py`

---

### 3.5 poi_hierarchy（POI层级表）

**作用**：存储POI的层级关系（主POI和子POI），用于解决大景点内子景点重复规划的问题。

**字段说明**：
| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | int | ID（主键，自增） |
| main_poi_id | varchar | 主POI ID |
| main_poi_name | varchar | 主POI名称 |
| inner_poi_id | varchar | 子POI ID |
| inner_poi_name | varchar | 子POI名称 |
| relation_type | varchar | 关系类型（contains=包含，nearby=附近） |
| city | varchar | 城市 |
| province | varchar | 省份 |
| source | varchar | 数据来源 |
| status | tinyint | 状态（0=待审核，1=已审核） |
| created_at | datetime | 创建时间 |

**使用场景**：
- 主POI和子POI识别
- 避免大景点内子景点重复规划
- 大景点内子景点只作为点位出现，不作为主要规划点位

**代码引用**：
- `app/core/planner.py`
- `app/services/planner/`
- `app/data/static/poi_hierarchy.py`（本地默认值，数据库优先）

---

### 3.6 poi_inner（POI内部景点表）

**作用**：存储大景点内部的子景点数据，用于大景点内的详细规划。

**字段说明**：
| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | int | ID（主键，自增） |
| main_poi_name | varchar | 主景点名称 |
| inner_poi_name | varchar | 内部景点名称 |
| city | varchar | 城市 |
| province | varchar | 省份 |
| description | text | 景点描述 |
| suggested_order | int | 建议游览顺序 |
| duration | varchar | 建议游玩时长 |
| status | tinyint | 状态（0=禁用，1=启用） |
| created_at | datetime | 创建时间 |

**使用场景**：
- 大景点内的详细规划
- 子景点推荐和排序
- 景点详情展示

**代码引用**：
- `app/core/planner.py`

---

### 3.7 poi_main（POI主表）

**作用**：存储主要POI的基本信息，作为POI数据的主表。

**字段说明**：
| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | int | ID（主键，自增） |
| poi_id | varchar | POI唯一标识 |
| name | varchar | POI名称 |
| category | varchar | 类别 |
| city | varchar | 城市 |
| province | varchar | 省份 |
| address | varchar | 地址 |
| longitude | decimal | 经度 |
| latitude | decimal | 纬度 |
| rating | float | 评分 |
| description | text | 描述 |
| tags | json | 标签 |
| source | varchar | 数据来源 |
| status | tinyint | 状态 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

**使用场景**：
- POI数据主表
- POI详情查询
- POI数据管理

**代码引用**：
- `app/services/map/poi.py`

---

### 3.8 poi_nearby（POI周边表）

**作用**：存储POI周边的关联POI数据，用于周边推荐和路径规划。

**字段说明**：
| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | int | ID（主键，自增） |
| center_poi_id | varchar | 中心POI ID |
| center_poi_name | varchar | 中心POI名称 |
| nearby_poi_id | varchar | 周边POI ID |
| nearby_poi_name | varchar | 周边POI名称 |
| distance | float | 距离（米） |
| city | varchar | 城市 |
| province | varchar | 省份 |
| status | tinyint | 状态 |
| created_at | datetime | 创建时间 |

**使用场景**：
- POI周边推荐
- 路径规划
- 探索功能（中心点周围的景点）

**代码引用**：
- `app/services/map/poi.py`
- `app/api/explore.py`

---

### 3.9 poi_open_hours（POI开放时间表）

**作用**：存储POI的开放时间数据，用于行程规划时考虑景点开放时间。

**字段说明**：
| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | int | ID（主键，自增） |
| poi_id | varchar | POI ID |
| poi_name | varchar | POI名称 |
| weekday | tinyint | 星期（1=周一，7=周日） |
| open_time | time | 开放时间 |
| close_time | time | 关闭时间 |
| is_closed | tinyint | 是否闭馆（0=开放，1=闭馆） |
| special_date | date | 特殊日期（节假日等） |
| status | tinyint | 状态 |
| created_at | datetime | 创建时间 |

**使用场景**：
- 行程规划时考虑景点开放时间
- 避免规划闭馆的景点
- 景点时间安排优化

**代码引用**：
- `app/core/planner.py`
- `app/services/planner/`

---

## 4. 知识库相关

### 4.1 historical_figure（历史人物表）

**作用**：存储历史名人、革命先辈等人物信息，用于对话中加入人文介绍和出行推荐。

**字段说明**：
| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | int | ID（主键，自增） |
| name | varchar | 人物姓名 |
| alias | varchar | 别名/字号 |
| dynasty | varchar | 朝代/时代 |
| birth_year | varchar | 出生年份 |
| death_year | varchar | 逝世年份 |
| title | varchar | 头衔/称号 |
| description | text | 人物简介 |
| achievements | text | 主要成就 |
| category | varchar | 类别（历史名人/革命先辈/文化名人等） |
| avatar | varchar | 头像URL |
| status | tinyint | 状态（0=待审核，1=已审核） |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

**使用场景**：
- 对话中加入历史人物人文介绍
- 关联人物相关的地点和出行推荐
- 知识库问答

**代码引用**：
- `app/services/rag/`
- `app/api/rag.py`

---

### 4.2 historical_figure_place（历史人物地点关联表）

**作用**：存储历史人物与地点的关联关系，用于对话中根据人物推荐相关地点。

**字段说明**：
| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | int | ID（主键，自增） |
| figure_id | int | 人物ID（关联 historical_figure 表） |
| figure_name | varchar | 人物姓名 |
| place_name | varchar | 地点名称 |
| place_type | varchar | 地点类型（出生地/逝世地/活动地/纪念地等） |
| province | varchar | 省份 |
| city | varchar | 城市 |
| address | varchar | 详细地址 |
| longitude | decimal | 经度 |
| latitude | decimal | 纬度 |
| description | text | 关联描述 |
| status | tinyint | 状态 |
| created_at | datetime | 创建时间 |

**使用场景**：
- 根据历史人物推荐相关地点
- 对话中加入人物相关的出行介绍
- 知识库问答

**代码引用**：
- `app/services/rag/`
- `app/api/rag.py`

---

### 4.3 knowledge_category（知识分类表）

**作用**：存储知识库的分类信息，用于知识文档的组织和检索。

**字段说明**：
| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | int | ID（主键，自增） |
| category_code | varchar | 分类编码 |
| category_name | varchar | 分类名称 |
| parent_id | int | 父分类ID |
| description | text | 分类描述 |
| sort_order | int | 排序 |
| status | tinyint | 状态（0=禁用，1=启用） |
| created_at | datetime | 创建时间 |

**使用场景**：
- 知识文档分类管理
- 知识库检索过滤
- 后台知识管理

**代码引用**：
- `app/services/rag/`
- `app/api/rag.py`

---

### 4.4 knowledge_config（知识配置表）

**作用**：存储知识库的配置信息，用于控制知识库的行为。

**字段说明**：
| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | int | ID（主键，自增） |
| config_key | varchar | 配置键 |
| config_value | text | 配置值 |
| description | text | 配置描述 |
| status | tinyint | 状态 |
| created_at | datetime | 创建时间 |

**使用场景**：
- 知识库参数配置
- 检索参数调整
- 模型参数配置

**代码引用**：
- `app/services/rag/`

---

### 4.5 knowledge_doc（知识文档表）

**作用**：存储知识库的文档内容，用于RAG检索和问答。

**字段说明**：
| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | int | ID（主键，自增） |
| doc_id | varchar | 文档唯一标识 |
| title | varchar | 文档标题 |
| category_id | int | 分类ID（关联 knowledge_category 表） |
| content | longtext | 文档内容 |
| summary | text | 文档摘要 |
| tags | json | 标签 |
| source | varchar | 来源 |
| author | varchar | 作者 |
| vector_id | varchar | 向量ID（用于向量检索） |
| status | tinyint | 状态（0=草稿，1=已发布，2=已删除） |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

**使用场景**：
- RAG知识库文档存储
- 知识检索和问答
- 后台知识管理
- 知识导入导出

**代码引用**：
- `app/services/rag/`
- `app/api/rag.py`

---

## 5. 配置和字典相关

### 5.1 site_config（站点配置表）

**作用**：存储站点的动态配置信息，包括地图Key、规划参数、缓存TTL等，支持后台动态修改，无需重启服务。

**字段说明**：
| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | int | ID（主键，自增） |
| config_key | varchar | 配置键（唯一） |
| config_value | text | 配置值 |
| config_type | varchar | 配置类型（string/int/float/bool/json/list） |
| description | text | 配置描述 |
| category | varchar | 配置分类（map/planner/cache/security等） |
| is_system | tinyint | 是否系统配置（0=否，1=是，系统配置不可删除） |
| status | tinyint | 状态（0=禁用，1=启用） |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

**使用场景**：
- 地图Key动态配置（高德/腾讯Key）
- 规划参数动态调整（候选池数量、距离范围等）
- 缓存TTL配置
- 系统参数配置
- 后台配置管理

**代码引用**：
- `app/data/dict_store.py`
- `app/api/admin.py`
- `app/config.py`

**重要说明**：
- 数据库配置优先于环境变量和代码默认值
- 系统配置（is_system=1）不可删除，只能修改值
- 配置修改后立即生效，无需重启服务

---

### 5.2 dict_brand_copy（品牌字典表）

**作用**：存储品牌相关的字典数据，可能是从其他表复制的备份表。

**字段说明**：
| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | int | ID（主键，自增） |
| brand_name | varchar | 品牌名称 |
| category | varchar | 类别 |
| description | text | 描述 |
| status | tinyint | 状态 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

**使用场景**：
- 品牌数据存储
- 字典数据管理

**注意**：
- 此表可能是复制表，需要确认是否仍在使用
- 如果不再使用，建议清理

---

## 附录

### A. 表统计

| 分类 | 表数量 | 说明 |
|------|--------|------|
| 用户和认证相关 | 3 | users, admins, login_log |
| 行程规划相关 | 3 | trips, conversations, generation_log |
| 地理和POI相关 | 9 | admin_regions, major_attractions, must_visit, poi_cache, poi_hierarchy, poi_inner, poi_main, poi_nearby, poi_open_hours |
| 知识库相关 | 5 | historical_figure, historical_figure_place, knowledge_category, knowledge_config, knowledge_doc |
| 配置和字典相关 | 2 | site_config, dict_brand_copy |
| **总计** | **22** | |

### B. 数据优先级说明

1. **数据库优先**：所有存储在数据库中的数据，优先从数据库读取
2. **本地默认值**：数据库中不存在时，使用本地静态数据作为默认值
3. **第三方API**：本地数据不足时，调用第三方地图API获取数据
4. **缓存**：第三方API获取的数据，缓存到数据库（poi_cache表），下次优先从缓存读取

### C. 数据更新策略

1. **行政区域数据**：每年更新一次，或国家标准变更时更新
2. **主要景点数据**：定期更新，或后台手动维护
3. **POI缓存数据**：按TTL自动过期，过期后重新从第三方API获取
4. **知识库数据**：后台手动维护，支持批量导入导出
5. **站点配置**：后台动态修改，立即生效

### D. 变更记录

| 日期 | 版本 | 变更内容 | 负责人 |
|------|------|----------|--------|
| 2026-08-30 | 1.0.0 | 初始版本，记录22个表的作用 | AI |
