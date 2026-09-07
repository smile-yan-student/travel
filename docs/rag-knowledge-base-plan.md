# 景点人文RAG知识库建设与落地计划

> 基于《AI旅行规划产品｜全能力升级可落地执行计划（最终版）》补充完善
> 定位：解决LLM幻觉，提供权威、准确、结构化的景点人文知识

---

## 一、RAG在产品架构中的定位

### 1.1 三大系统协同

```
用户输入 / 多轮对话
    ↓
LLM意图解析（7B模型）
    ↓
硬规则规划引擎 → 生成合法点位池 + 硬约束
    ↓
RAG知识库检索 → 注入景点人文知识（权威、无幻觉）
    ↓
LLM在约束内编排行程 + 人文内容生成
    ↓
规划引擎二次校验修复
    ↓
前端可视化行程、点位详情、人文讲解
```

### 1.2 RAG的核心价值

| 问题 | RAG解决方案 |
|---|---|
| LLM生成景点历史时幻觉严重 | 基于权威知识库检索，事实可追溯 |
| 热门景点信息不准确 | 5A/4A景区人工审核+权威数据源 |
| 人文内容千篇一律 | 结构化知识库支持多维度讲解（历史/建筑/文化/典故） |
| 小众景点无资料 | 知识库覆盖不到时，诚实降级为LLM通用生成并标注 |

### 1.3 RAG不做什么

- 不做地理判断、距离计算（归规划引擎）
- 不做行程编排（归LLM+规划引擎）
- 不做实时信息（开闭园、门票价格走API或定期更新）

---

## 二、知识库建设方案

### 2.1 数据来源（优先级从高到低）

| 优先级 | 数据源 | 覆盖范围 | 数据质量 | 获取方式 |
|---|---|---|---|---|
| P0 | 维基百科（中文） | 全国热门景点 | 高 | 定期爬取/API |
| P0 | 百度百科 | 全国景点 | 中高 | 定期爬取 |
| P1 | 国家文旅部景区名录 | 5A/4A景区 | 权威 | 官方公开数据 |
| P1 | 各省市文旅局官网 | 省市级景点 | 权威 | 定期爬取 |
| P2 | 景区官方网站 | 单个景区 | 权威 | 定向爬取 |
| P2 | 权威历史资料（二十四史、地方志） | 历史文化景点 | 极高 | 结构化录入 |
| P3 | 优质游记/攻略（马蜂窝、携程） | 游玩体验 | 中 | NLP提取+人工审核 |

### 2.2 数据覆盖范围（分阶段）

| 阶段 | 覆盖范围 | 数量预估 | 数据量 |
|---|---|---|---|
| MVP | Top50热门景点（北京/西安/杭州/成都/南京等） | 50个 | ~50MB |
| 阶段一 | 全国5A级景区 | ~350个 | ~300MB |
| 阶段二 | 全国4A级景区 | ~4000个 | ~3GB |
| 阶段三 | 热门小众景点+历史文化名城 | ~10000个 | ~8GB |

### 2.3 知识数据结构（每个景点）

```json
{
  "poi_id": "string，景点唯一ID",
  "name": "string，景点标准名称",
  "alias": ["string，别名/曾用名"],
  "location": {
    "province": "string，省",
    "city": "string，市",
    "district": "string，区县",
    "address": "string，详细地址"
  },
  "level": "string，景区级别（5A/4A/3A/无）",
  "category": "string，景点类型（自然风光/历史古迹/博物馆/宗教场所/主题公园等）",
  "tags": ["string，标签（世界遗产/全国重点文保/爱国主义教育基地等）"],

  "summary": "string，一句话简介（50字以内）",
  "description": "string，详细介绍（300-500字）",

  "history": {
    "founded_year": "string，始建年代（如'明洪武十七年'）",
    "historical_periods": ["string，重要历史时期"],
    "major_events": [
      {"time": "string，时间", "event": "string，事件", "significance": "string，意义"}
    ],
    "historical_figures": ["string，相关历史人物"],
    "cultural_relics": ["string，珍贵文物"]
  },

  "architecture": {
    "style": "string，建筑风格（如'明清官式建筑'）",
    "layout": "string，建筑布局/格局",
    "key_buildings": [
      {"name": "string，建筑名称", "description": "string，介绍", "highlight": "string，看点"}
    ],
    "architectural_features": ["string，建筑特色"]
  },

  "culture": {
    "cultural_significance": "string，文化意义",
    "literary_references": [
      {"work": "string，作品名称", "author": "string，作者", "quote": "string，名句", "context": "string，背景"}
    ],
    "folk_customs": ["string，民俗活动"],
    "related_legends": ["string，相关传说"]
  },

  "visit_guide": {
    "best_time": "string，最佳游玩时间（季节/时段）",
    "recommended_duration": "string，建议游玩时长",
    "internal_route": ["string，推荐内部游览动线（按顺序）"],
    "must_see": ["string，必看景点"],
    "photo_spots": ["string，拍照机位"],
    "avoid_tips": ["string，避坑提示"],
    "nearby_attractions": ["string，周边联动景点"],
    "nearby_food_streets": ["string，周边美食街/市井街区"]
  },

  "practical_info": {
    "opening_hours": "string，开放时间",
    "ticket_price": "string，门票价格",
    "booking_url": "string，预约链接",
    "transport": "string，交通方式",
    "facilities": ["string，园内设施（轮椅/母婴室/讲解器等）"]
  },

  "source": {
    "primary_source": "string，主要数据来源",
    "last_updated": "string，最后更新时间（ISO格式）",
    "version": "string，数据版本",
    "review_status": "string，审核状态（待审核/已审核/需更新）"
  }
}
```

### 2.4 数据分块策略（向量化用）

**不按简单长度分块，按主题分块：**

| 分块类型 | 内容 | 用途 |
|---|---|---|
| `summary` | 一句话简介+详细介绍 | 点位卡片简介、行程人文短句 |
| `history` | 历史沿革+重大事件+历史人物 | AI讲解-历史部分、知识问答 |
| `architecture` | 建筑风格+格局+主要建筑 | AI讲解-建筑部分 |
| `culture` | 文化意义+文学引用+民俗传说 | AI讲解-文化部分、人文短句 |
| `visit_guide` | 最佳时间+内部路线+必看+避坑 | 点位卡片游玩建议、行程规划辅助 |
| `practical_info` | 开放时间+门票+交通 | 点位卡片实用信息 |

**每个分块携带元数据：**
```json
{
  "poi_id": "景点ID",
  "poi_name": "景点名称",
  "chunk_type": "history/architecture/culture/...",
  "content": "分块文本内容",
  "keywords": ["关键词1", "关键词2"],
  "importance": "high/medium/low"
}
```

---

## 三、技术选型（本地轻量化方案）

### 3.1 整体技术栈

| 组件 | 选型 | 理由 |
|---|---|---|
| 向量数据库 | **Chroma** | 本地文件存储、无需额外服务、Python原生支持、轻量 |
| 备选向量库 | FAISS | 性能更高，但需要额外维护索引文件 |
| Embedding模型 | **bge-small-zh-v1.5** | 中文优化、384维、轻量（~100MB）、本地可跑 |
| 备选Embedding | m3e-small | 中文通用、效果稳定 |
| 检索策略 | **向量检索 + BM25关键词检索 混合** | 兼顾语义匹配和精确匹配 |
| 重排模型 | bge-reranker-base（可选） | 提升Top-K准确率，本地可跑 |
| LLM生成 | 现有7B模型 | 基于检索结果生成讲解/回答 |

### 3.2 检索流程

```
用户查询 / 景点ID
    ↓
查询理解（LLM提取关键词/实体）
    ↓
┌─────────────────┬──────────────────┐
│  向量检索        │  BM25关键词检索   │
│  (语义相似)      │  (精确匹配)       │
└────────┬────────┴────────┬─────────┘
         ↓                 ↓
    结果融合（RRF算法）
         ↓
    重排（可选，bge-reranker）
         ↓
    Top-K结果（默认5条）
         ↓
    注入LLM Prompt作为上下文
         ↓
    LLM生成最终回答/讲解
```

### 3.3 与现有LLM的协同策略

| 场景 | 策略 |
|---|---|
| 景点在知识库中 | RAG检索 → 注入上下文 → LLM基于检索结果生成，要求引用来源 |
| 景点不在知识库中 | 诚实告知"该景点暂无详细知识库"，LLM生成通用介绍并标注"AI生成，仅供参考" |
| 知识问答 | 优先RAG检索，检索不到再走LLM通用知识 |
| 行程人文短句 | 从知识库`summary`和`culture`字段提取，不经过LLM（确定性） |

---

## 四、四大应用场景

### 4.1 场景一：AI景点完整讲解

**触发方式：** 点位卡片上的【AI完整讲解】按钮

**输出结构：**
```
【景点名称】
一句话定位

📜 历史沿革
（基于history分块生成，200-300字）

🏛️ 建筑格局
（基于architecture分块生成，150-200字）

✨ 文化意义
（基于culture分块生成，150-200字）

📖 名人典故
（3-5个典故，每个1-2句话）

🎯 游玩重点
（基于visit_guide分块，必看+内部路线+拍照机位）

⚠️ 避坑提示
（3-5条实用建议）

📚 信息来源：维基百科/文旅局官网（最后更新：2026-08）
```

**技术实现：**
1. 根据poi_id检索知识库所有分块
2. 按分块类型组织上下文
3. LLM基于结构化上下文生成讲解
4. 要求LLM不得编造检索结果中没有的信息

### 4.2 场景二：点位卡片人文信息自动填充

**触发方式：** 规划引擎选中景点后，自动从知识库提取

**填充字段：**
| 卡片字段 | 知识库来源 |
|---|---|
| 景点简介 | `summary`（一句话） |
| 历史渊源 | `history.founded_year` + `history.major_events[0]` |
| 知名典故 | `culture.related_legends[0]` 或 `culture.literary_references[0]` |
| 最佳游玩时间 | `visit_guide.best_time` |
| 建议游玩时长 | `visit_guide.recommended_duration` |
| 内部游玩路线 | `visit_guide.internal_route` |
| 周边联动街区 | `visit_guide.nearby_food_streets` |
| 避坑提示 | `visit_guide.avoid_tips[0:2]` |

**技术实现：**
- 不经过LLM，直接从知识库结构化字段提取（确定性、无幻觉）
- 规划引擎在`build_plan`中调用`knowledge_service.get_poi_card_info(poi_id)`
- 知识库没有的字段留空，前端不展示

### 4.3 场景三：行程人文短句

**触发方式：** 每段行程自动生成1-2句人文背景

**示例：**
> 上午：故宫博物院（3小时）
> 「故宫，明清两代皇家宫殿，世界现存规模最大、保存最完整的木质结构古建筑群。」

**技术实现：**
- 从知识库`summary` + `culture.cultural_significance`提取
- 不经过LLM，直接拼接（确定性）
- 控制在50字以内，不冗长、不抢行程主体

### 4.4 场景四：多轮对话知识问答

**触发方式：** 用户在对话中提问（如"这个景点有什么历史？"、"为什么叫这个名字？"）

**意图分类：**
| 用户输入 | 意图 | 处理方式 |
|---|---|---|
| "故宫有什么历史？" | 知识问答-历史 | RAG检索history分块 → LLM生成回答 |
| "这个建筑是什么风格？" | 知识问答-建筑 | RAG检索architecture分块 → LLM生成回答 |
| "有什么典故吗？" | 知识问答-文化 | RAG检索culture分块 → LLM生成回答 |
| "帮我改一下第二天" | 行程修改 | 走行程工作记忆，不涉及RAG |
| "北京天气怎么样" | 实用查询 | 走天气API，不涉及RAG |

**技术实现：**
1. LLM意图分类（知识问答 vs 行程修改 vs 实用查询）
2. 知识问答 → 识别景点实体（当前行程中的景点 / 用户明确提到的景点）
3. RAG检索对应分块
4. LLM基于检索结果回答，标注信息来源
5. 检索不到 → 诚实告知，LLM通用回答并标注

---

## 五、分阶段落地计划

### 阶段零：MVP（2周，与架构重构同步）

**目标：** 验证RAG技术可行性，跑通AI讲解功能

**开发内容：**
1. 搭建RAG基础框架
   - Chroma向量库集成
   - bge-small-zh Embedding模型接入
   - 基础向量检索功能
2. 录入Top50热门景点数据
   - 北京：故宫、天安门、长城、颐和园、天坛、圆明园、鸟巢、水立方、南锣鼓巷、什刹海
   - 西安：兵马俑、大雁塔、华清池、西安城墙、陕西历史博物馆、回民街、大唐不夜城
   - 杭州：西湖、灵隐寺、千岛湖、宋城、西溪湿地、河坊街
   - 成都：宽窄巷子、锦里、武侯祠、杜甫草堂、大熊猫基地、春熙路
   - 南京：中山陵、夫子庙、明孝陵、总统府、南京博物院、玄武湖
   - 其他：黄山、张家界、九寨沟、鼓浪屿、丽江古城、大理洱海
3. 实现AI景点讲解功能
   - 后端API：`GET /api/poi/{poi_id}/explain`
   - 前端点位卡片增加【AI完整讲解】按钮
   - 讲解结果弹窗/展开展示
4. 实现点位卡片简介自动填充
   - 规划引擎调用知识库提取`summary`
   - 前端点位卡片展示简介

**验收标准：**
- Top50景点AI讲解可正常生成，内容基于知识库无明显幻觉
- 点位卡片自动显示景点简介
- 检索响应时间 < 2秒（本地）

---

### 阶段一：知识库扩展（3周，精细点位体系阶段）

**目标：** 覆盖全国5A景区，优化检索质量

**开发内容：**
1. 知识库扩展到全国5A景区（~350个）
   - 自动化数据采集脚本（维基百科+百度百科）
   - 数据清洗与结构化流水线
   - 人工审核关键景点（Top100）
2. 优化检索策略
   - 实现BM25关键词检索
   - 向量+关键词混合检索（RRF融合）
   - 可选：接入bge-reranker重排
3. 实现行程人文短句
   - 规划引擎自动为每个景点生成人文短句
   - 前端行程展示中嵌入
4. 实现多轮对话知识问答
   - LLM意图分类（知识问答 vs 行程修改）
   - 景点实体识别（当前行程上下文）
   - RAG检索+LLM生成回答
5. 知识库管理后台
   - 管理员可查看/编辑/审核景点知识
   - 数据版本管理

**验收标准：**
- 全国5A景区覆盖率 > 90%
- 知识问答准确率 > 85%（人工评估）
- 检索Top-5命中率 > 90%

---

### 阶段二：深度完善（4周，人文内容体系阶段）

**目标：** 覆盖4A景区，完善数据质量，建立更新机制

**开发内容：**
1. 知识库扩展到4A景区（~4000个）
   - 批量数据采集与清洗
   - 自动化质量评估（完整度/准确性）
2. 建立数据更新机制
   - 每月自动爬取数据源更新
   - 变更检测与差异对比
   - 人工审核流程（关键信息变更）
3. 事实校验机制
   - RAG检索结果与LLM生成交叉验证
   - 多数据源一致性校验
   - 可疑信息标记人工审核
4. 用户反馈闭环
   - 用户可对讲解内容点赞/纠错
   - 纠错提交人工审核
   - 审核通过后更新知识库
5. 点位卡片全套信息升级
   - 历史渊源、知名典故、最佳时间、内部路线、周边联动、避坑提示全部展示
   - 前端卡片UI优化

**验收标准：**
- 4A景区覆盖率 > 80%
- 数据完整度 > 75%（所有字段填充率）
- 用户纠错响应时间 < 48小时

---

### 阶段三：智能进化（持续，用户长期画像阶段）

**目标：** 知识图谱化、个性化讲解、智能推荐

**开发内容：**
1. 知识图谱构建
   - 景点之间的关联（地理位置/历史事件/文化脉络）
   - 历史人物与景点的关联
   - 文学作品与景点的关联
2. 个性化讲解
   - 基于用户偏好调整讲解侧重点（历史爱好者→多讲历史，摄影爱好者→多讲拍照机位）
   - 讲解风格调整（严谨/通俗/文艺）
3. 智能知识推荐
   - 行程中自动推荐相关景点的关联知识
   - "你知道吗"式的趣味知识推送
4. 小众景点覆盖
   - 扩展到热门小众景点（~10000个）
   - UGC内容审核入库

**验收标准：**
- 知识图谱节点 > 50000个
- 个性化讲解用户满意度 > 80%
- 小众景点覆盖率 > 60%

---

## 六、数据更新与维护策略

### 6.1 更新频率

| 数据类型 | 更新频率 | 方式 |
|---|---|---|
| 热门景点（Top500） | 每月 | 自动爬取+人工审核 |
| 5A景区 | 每季度 | 自动爬取+变更检测 |
| 4A景区 | 每半年 | 批量爬取+抽样审核 |
| 实用信息（开闭园/门票） | 每周 | API/官网自动检测 |
| 历史文化内容 | 每年 | 人工复核+权威资料更新 |

### 6.2 版本管理

- 每个景点知识数据带`version`和`last_updated`字段
- 重要变更保留历史版本，可回滚
- 数据变更日志记录：变更时间、变更字段、变更原因、审核人

### 6.3 质量保障

| 环节 | 措施 |
|---|---|
| 数据采集 | 多数据源交叉验证，不一致标记 |
| 数据清洗 | 自动化规则校验（字段完整度/格式/长度） |
| 人工审核 | Top500景点100%人工审核，其他抽样审核 |
| 上线前 | 自动化测试（检索准确率/生成质量） |
| 上线后 | 用户反馈监控，低评分内容自动标记复审 |

---

## 七、与现有系统的集成方案

### 7.1 后端模块结构

```
backend/app/
├── services/
│   └── rag/                          # 新增：RAG服务模块
│       ├── __init__.py
│       ├── knowledge_base.py         # 知识库管理（增删改查）
│       ├── vector_store.py           # 向量存储（Chroma封装）
│       ├── retriever.py              # 检索器（混合检索+重排）
│       ├── generator.py              # 基于检索的内容生成
│       ├── data_pipeline.py          # 数据采集与清洗流水线
│       └── models.py                 # 数据模型（POIKnowledge等）
├── data/
│   ├── knowledge_base/               # 新增：知识库数据目录
│   │   ├── chroma/                   # Chroma向量库文件
│   │   ├── raw/                      # 原始采集数据
│   │   └── processed/                # 清洗后结构化数据
│   └── ...
└── ...
```

### 7.2 数据库表设计

**表1：`poi_knowledge`（景点知识主表）**

| 字段 | 类型 | 说明 |
|---|---|---|
| id | BIGINT PK | 自增ID |
| poi_id | VARCHAR(64) UNIQUE | 景点唯一ID（与POI系统对齐） |
| name | VARCHAR(128) | 景点标准名称 |
| alias | JSON | 别名列表 |
| province | VARCHAR(32) | 省 |
| city | VARCHAR(32) | 市 |
| district | VARCHAR(32) | 区县 |
| level | VARCHAR(16) | 景区级别（5A/4A/3A/无） |
| category | VARCHAR(32) | 景点类型 |
| tags | JSON | 标签列表 |
| summary | VARCHAR(256) | 一句话简介 |
| description | TEXT | 详细介绍 |
| history | JSON | 历史信息（结构化） |
| architecture | JSON | 建筑信息（结构化） |
| culture | JSON | 文化信息（结构化） |
| visit_guide | JSON | 游玩指南（结构化） |
| practical_info | JSON | 实用信息（结构化） |
| data_source | VARCHAR(64) | 主要数据来源 |
| data_version | VARCHAR(32) | 数据版本 |
| review_status | VARCHAR(16) | 审核状态（pending/approved/needs_update） |
| completeness_score | FLOAT | 数据完整度评分（0-1） |
| last_updated | DATETIME | 最后更新时间 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

**索引：**
- `idx_poi_id` (poi_id)
- `idx_name` (name)
- `idx_location` (province, city, district)
- `idx_level` (level)
- `idx_review_status` (review_status)
- `idx_last_updated` (last_updated)

**表2：`poi_knowledge_chunks`（知识分块表，用于向量化）**

| 字段 | 类型 | 说明 |
|---|---|---|
| id | BIGINT PK | 自增ID |
| poi_id | VARCHAR(64) | 关联景点ID |
| chunk_type | VARCHAR(32) | 分块类型（summary/history/architecture/culture/visit_guide/practical） |
| content | TEXT | 分块文本内容 |
| keywords | JSON | 关键词列表 |
| importance | VARCHAR(16) | 重要性（high/medium/low） |
| vector_id | VARCHAR(64) | 向量库中的ID |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

**索引：**
- `idx_poi_id` (poi_id)
- `idx_chunk_type` (chunk_type)
- `idx_vector_id` (vector_id)

**表3：`poi_knowledge_feedback`（用户反馈表）**

| 字段 | 类型 | 说明 |
|---|---|---|
| id | BIGINT PK | 自增ID |
| user_id | BIGINT | 用户ID |
| poi_id | VARCHAR(64) | 景点ID |
| feedback_type | VARCHAR(16) | 反馈类型（like/correction/report） |
| content | TEXT | 反馈内容（纠错详情/举报原因） |
| status | VARCHAR(16) | 处理状态（pending/processing/resolved/rejected） |
| handler_id | BIGINT | 处理人ID |
| handled_at | DATETIME | 处理时间 |
| created_at | DATETIME | 创建时间 |

### 7.3 API接口设计

#### 7.3.1 景点知识查询

```
GET /api/poi/{poi_id}/knowledge
```

**响应：**
```json
{
  "code": 0,
  "data": {
    "poi_id": "poi_001",
    "name": "故宫博物院",
    "summary": "明清两代皇家宫殿，世界现存规模最大的木质结构古建筑群",
    "description": "...",
    "history": {...},
    "architecture": {...},
    "culture": {...},
    "visit_guide": {...},
    "practical_info": {...},
    "data_source": "维基百科+文旅部官网",
    "last_updated": "2026-08-15"
  }
}
```

#### 7.3.2 AI景点讲解

```
GET /api/poi/{poi_id}/explain?style=default
```

**参数：**
- `style`: 讲解风格（default/history_focus/photography_focus/family_friendly）

**响应：**
```json
{
  "code": 0,
  "data": {
    "poi_id": "poi_001",
    "name": "故宫博物院",
    "introduction": "一句话定位",
    "history": "历史沿革（200-300字）",
    "architecture": "建筑格局（150-200字）",
    "culture": "文化意义（150-200字）",
    "legends": ["典故1", "典故2", "典故3"],
    "visit_highlights": ["必看1", "必看2"],
    "internal_route": ["午门", "太和殿", "中和殿", "..."],
    "photo_spots": ["拍照机位1", "拍照机位2"],
    "avoid_tips": ["避坑1", "避坑2"],
    "sources": ["维基百科", "故宫博物院官网"],
    "last_updated": "2026-08-15",
    "rag_retrieved": true
  }
}
```

#### 7.3.3 知识问答

```
POST /api/poi/qa
```

**请求：**
```json
{
  "poi_id": "poi_001",
  "question": "故宫为什么叫紫禁城？",
  "conversation_id": "conv_001"
}
```

**响应：**
```json
{
  "code": 0,
  "data": {
    "answer": "故宫之所以叫紫禁城，是因为...",
    "sources": ["维基百科-故宫"],
    "rag_retrieved": true,
    "related_chunks": [
      {"chunk_type": "culture", "content": "..."}
    ]
  }
}
```

#### 7.3.4 点位卡片信息（规划引擎内部调用）

```
GET /api/internal/poi/{poi_id}/card-info
```

**响应：**
```json
{
  "summary": "一句话简介",
  "historical_origin": "始建于明洪武十七年...",
  "famous_legend": "相关典故...",
  "best_time": "春秋最佳，建议上午",
  "recommended_duration": "3-4小时",
  "internal_route": ["午门", "太和殿", "..."],
  "nearby_food_streets": ["南锣鼓巷", "什刹海"],
  "avoid_tips": ["周一闭馆", "需提前预约"]
}
```

#### 7.3.5 知识库管理（管理员）

```
GET    /api/admin/knowledge/pois              # 景点知识列表
GET    /api/admin/knowledge/pois/{poi_id}     # 景点知识详情
PUT    /api/admin/knowledge/pois/{poi_id}     # 更新景点知识
POST   /api/admin/knowledge/pois/import        # 批量导入
POST   /api/admin/knowledge/pois/rebuild-index # 重建向量索引
GET    /api/admin/knowledge/stats              # 知识库统计
```

### 7.4 与规划引擎的集成点

| 规划引擎阶段 | RAG集成 |
|---|---|
| `build_plan` 生成行程后 | 为每个选中景点调用`get_poi_card_info`，填充人文信息 |
| 逐日构建行程时 | 为每个景点生成人文短句（从`summary`提取） |
| LLM优化行程时 | 将景点知识库摘要作为上下文注入LLM，辅助编排 |
| 前端展示时 | 点位卡片展示知识库字段，【AI讲解】按钮调用RAG生成 |

---

## 八、质量评估与指标

### 8.1 知识库质量指标

| 指标 | 目标 | 测量方式 |
|---|---|---|
| 5A景区覆盖率 | > 95% | 数据库记录数 / 官方5A总数 |
| 4A景区覆盖率 | > 80% | 数据库记录数 / 官方4A总数 |
| 数据完整度 | > 75% | 已填充字段数 / 总字段数 |
| 人工审核率（Top500） | 100% | 已审核数 / Top500总数 |
| 事实准确率 | > 90% | 人工抽样评估 |

### 8.2 检索质量指标

| 指标 | 目标 | 测量方式 |
|---|---|---|
| Top-1命中率 | > 75% | 标准测试集 |
| Top-5命中率 | > 90% | 标准测试集 |
| 检索响应时间 | < 2秒 | P95延迟 |
| MRR（平均倒数排名） | > 0.8 | 标准测试集 |

### 8.3 生成质量指标

| 指标 | 目标 | 测量方式 |
|---|---|---|
| 幻觉率 | < 5% | 人工评估生成内容中未在检索结果出现的事实 |
| 引用准确率 | > 95% | 生成内容引用的来源是否真实存在 |
| 用户满意度 | > 80% | 用户点赞/评分 |
| 讲解完整度 | > 85% | 是否覆盖所有要求的模块 |

---

## 九、风险与应对

| 风险 | 影响 | 应对措施 |
|---|---|---|
| 数据采集被封 | 知识库更新受阻 | 多数据源备份、控制爬取频率、使用官方API |
| 数据质量参差不齐 | 生成内容不准确 | 多源交叉验证、人工审核关键景点、用户反馈闭环 |
| 向量库性能瓶颈 | 检索慢 | 分库分表、量化压缩、定期优化索引 |
| Embedding模型效果不佳 | 检索准确率低 | 对比多个模型、领域微调、混合检索补偿 |
| LLM仍产生幻觉 | 用户信任度下降 | 强制引用来源、事实校验机制、未检索到时诚实降级 |
| 知识库维护成本高 | 可持续性差 | 自动化流水线、社区贡献、UGC审核 |

---

## 十、里程碑与交付物

| 阶段 | 时间 | 交付物 |
|---|---|---|
| MVP | 2周 | RAG基础框架 + Top50景点数据 + AI讲解功能 + 点位卡片简介 |
| 阶段一 | 3周 | 5A景区全覆盖 + 混合检索 + 人文短句 + 知识问答 + 管理后台 |
| 阶段二 | 4周 | 4A景区覆盖 + 数据更新机制 + 事实校验 + 用户反馈闭环 + 卡片全套信息 |
| 阶段三 | 持续 | 知识图谱 + 个性化讲解 + 智能推荐 + 小众景点覆盖 |

---

## 附录：Top50热门景点清单（MVP数据录入范围）

### 北京（10个）
故宫博物院、天安门广场、八达岭长城、颐和园、天坛公园、圆明园遗址公园、鸟巢（国家体育场）、水立方（国家游泳中心）、南锣鼓巷、什刹海

### 西安（7个）
秦始皇兵马俑博物馆、大雁塔（大慈恩寺）、华清宫、西安城墙、陕西历史博物馆、回民街、大唐不夜城

### 杭州（6个）
西湖风景名胜区、灵隐寺、千岛湖、宋城、西溪国家湿地公园、河坊街

### 成都（6个）
宽窄巷子、锦里古街、武侯祠、杜甫草堂、成都大熊猫繁育研究基地、春熙路

### 南京（6个）
中山陵园风景区、夫子庙秦淮风光带、明孝陵、总统府、南京博物院、玄武湖公园

### 其他热门（15个）
黄山风景区、张家界国家森林公园、九寨沟风景名胜区、鼓浪屿、丽江古城、大理洱海、泰山、华山、峨眉山、乐山大佛、敦煌莫高窟、布达拉宫、三亚亚龙湾、桂林漓江、苏州园林

---

*文档版本：v1.0*
*创建时间：2026-08-29*
*基于：《AI旅行规划产品｜全能力升级可落地执行计划（最终版）》补充完善*
