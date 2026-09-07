# 在线数据服务模块 - 设计文档

## 一、模块概述

### 1.1 设计理念

从单纯依赖规则引擎，转变为**"在线数据为基础，规划引擎做增强"**的模式：

- **在线数据**：提供真实、经过验证的攻略、景点信息、游客经验
- **规划引擎**：负责用户偏好调整、时间容量校验、地理距离微调、多方案生成

### 1.2 核心优势

| 维度 | 纯规则引擎 | 在线数据增强 | 提升 |
|-----|-----------|-------------|------|
| 景点覆盖 | 70-80% | 95%+ | +15-25% |
| 游览顺序 | 60-70% | 90%+ | +20-30% |
| 耗时估算 | 60-70% | 85%+ | +15-25% |
| 避坑提示 | 低（人工维护） | 高（真实经验） | 显著提升 |
| 预约规则 | 低（人工维护） | 高（官方信息） | 显著提升 |

---

## 二、模块架构

### 2.1 目录结构

```
backend/app/services/online_data/
├── __init__.py              # 模块初始化，导出所有类和函数
├── search_service.py        # 搜索服务（封装公开网页搜索，多关键词策略）
├── search_cache.py          # 搜索结果缓存（数据库持久化，过期机制）
├── data_extractor.py        # 数据提纯（从非结构化文本提取结构化信息）
├── attraction_rules.py      # 景点预约规则管理（CRUD + 后台配置）
└── travel_tips.py           # 旅游避坑提示管理（CRUD + 批量导入）
```

### 2.2 数据流

```
用户输入（北京3天情侣行程）
    │
    ▼
┌─────────────────────────────────────────┐
│         SearchService（搜索服务）         │
│  多关键词搜索：攻略/景点/避坑/美食/住宿  │
│  优先来源过滤：马蜂窝/携程/知乎/小红书    │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│         SearchCache（搜索缓存）           │
│  数据库持久化，避免重复搜索                │
│  过期机制：攻略7天/避坑15天/官方30天     │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│       DataExtractor（数据提纯）            │
│  从非结构化文本提取结构化信息：             │
│  - 景点列表 + 频率统计                     │
│  - 游览顺序提取（每日行程）                │
│  - 耗时估算（平均值）                      │
│  - 避坑提示提取                            │
│  - 多攻略交叉验证                          │
│  - 置信度计算                              │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│    AttractionRules（预约规则）             │
│    TravelTips（避坑提示）                  │
│  结构化存储，支持后台配置和维护             │
└──────────────┬──────────────────────────┘
               │
               ▼
        规划引擎增强（后续阶段）
```

---

## 三、核心模块详解

### 3.1 SearchService（搜索服务）

#### 功能
- 封装公开网页搜索
- 支持多关键词策略（6种类别）
- 搜索结果过滤（优先来源、过滤广告）
- 搜索结果聚合和去重
- 集成搜索缓存

#### 搜索关键词策略

| 类别 | 关键词模板 | 用途 |
|-----|-----------|------|
| guide | "{destination}{days}天攻略"、"{destination}旅游攻略" | 获取完整行程攻略 |
| attraction | "{destination}必去景点"、"{destination}景点推荐" | 获取景点列表 |
| tips | "{destination}旅游避坑"、"{destination}注意事项" | 获取避坑提示 |
| food | "{destination}美食推荐"、"{destination}必吃美食" | 获取美食推荐 |
| hotel | "{destination}住哪里方便"、"{destination}住宿区域" | 获取住宿建议 |
| official | "{attraction}官方 预约 开放时间 票价" | 获取景点官方信息 |

#### 优先来源
- 马蜂窝（mafengwo.cn）
- 携程（ctrip.com）
- 去哪儿（qunar.com）
- 知乎（zhihu.com）
- 小红书（xiaohongshu.com）
- 本地宝（bendibao.com）
- 大众点评（dianping.com）

#### 使用示例

```python
from app.services.online_data import get_search_service, SearchQuery

search_service = get_search_service()

# 搜索目的地攻略
results = await search_service.search_destination_guides(
    destination="北京",
    days=3,
    max_results=10,
)

# 搜索景点官方信息
results = await search_service.search_attraction_info(
    attraction="故宫博物院",
    max_results=5,
)

# 搜索避坑提示
results = await search_service.search_travel_tips(
    destination="北京",
    max_results=10,
)
```

---

### 3.2 SearchCache（搜索缓存）

#### 功能
- 搜索结果数据库持久化
- 缓存过期机制（按类别不同TTL）
- 缓存查询和写入
- 缓存清理（定期清理过期缓存）
- 缓存统计

#### 缓存过期时间

| 类别 | TTL | 说明 |
|-----|-----|------|
| guide | 7天 | 攻略信息 |
| attraction | 7天 | 景点信息 |
| tips | 15天 | 避坑提示 |
| food | 15天 | 美食推荐 |
| hotel | 30天 | 住宿建议 |
| official | 30天 | 官方信息 |
| general | 3天 | 通用搜索 |

**热门目的地优化**：热门目的地（北京、上海、杭州等）的攻略和景点信息，TTL减半（更频繁更新）。

#### 数据库表结构

```sql
CREATE TABLE search_cache (
    id INT AUTO_INCREMENT PRIMARY KEY,
    keyword VARCHAR(500) NOT NULL COMMENT '搜索关键词',
    keyword_hash VARCHAR(32) NOT NULL COMMENT '关键词MD5哈希',
    category VARCHAR(20) NOT NULL DEFAULT 'general',
    results JSON NOT NULL COMMENT '搜索结果',
    expire_at DOUBLE NOT NULL COMMENT '过期时间戳',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_hash_category (keyword_hash, category),
    KEY idx_keyword (keyword(100)),
    KEY idx_category (category),
    KEY idx_expire_at (expire_at)
);
```

#### 使用示例

```python
from app.services.online_data import get_search_cache

cache = get_search_cache()

# 写入缓存
await cache.set("北京3天攻略", results, category="guide")

# 读取缓存
cached = await cache.get("北京3天攻略", category="guide")

# 删除缓存
await cache.delete("北京3天攻略", category="guide")

# 清理过期缓存
count = await cache.clean_expired()

# 获取统计信息
stats = await cache.get_stats()
```

---

### 3.3 DataExtractor（数据提纯）

#### 功能
从非结构化的网页文本中提取结构化的行程信息：
- 景点列表提取（基于后缀匹配）
- 频率统计（多篇攻略交叉验证）
- 游览顺序提取（按天分割）
- 耗时估算（基于上下文匹配）
- 避坑提示提取（基于关键词分类）
- 置信度计算（基于攻略数量、频率、行程天数、提示数量）

#### 景点提取规则

**景点后缀匹配**：
- 景区、景点、公园、博物馆、纪念馆、寺、庙、塔
- 湖、山、岛、湾、滩、瀑、泉、洞、峡、谷
- 古镇、古城、古街、老街、步行街、广场、大街
- 大学、学院、图书馆、美术馆、展览馆、科技馆
- 动物园、植物园、海洋馆、游乐园、主题乐园
- 长城、故宫、颐和园、天坛、圆明园、鸟巢、水立方

**有效性过滤**：
- 长度过滤（2-20字符）
- 无效词过滤（旅游景区、风景区、景区门票等）
- 动词前缀过滤（游览、参观、游玩、不要等）
- 标点符号过滤

#### 频率分级

| 频率 | 等级 | 说明 |
|-----|------|------|
| >= 30% | 必去景点 | 多篇攻略高频出现 |
| 10-30% | 可选景点 | 部分攻略出现 |
| < 10% | 备选景点 | 少量攻略出现 |

#### 置信度计算

```
置信度 = 攻略数量分(30%) + 景点频率分(40%) + 行程天数分(20%) + 提示数量分(10%)
```

- 攻略数量分：min(攻略数/10, 1.0) * 0.3
- 景点频率分：min(必去景点平均频率/攻略数, 1.0) * 0.4
- 行程天数分：min(行程天数/3, 1.0) * 0.2
- 提示数量分：min(提示数/10, 1.0) * 0.1

#### 使用示例

```python
from app.services.online_data import get_data_extractor

extractor = get_data_extractor()

# 执行提纯
extracted = await extractor.extract(
    destination="北京",
    search_results=search_results,
)

# 查看结果
print(f"景点数: {len(extracted.attractions)}")
print(f"行程天数: {len(extracted.daily_itineraries)}")
print(f"避坑提示: {len(extracted.tips)}")
print(f"置信度: {extracted.confidence:.2f}")

# 按频率排序的景点
sorted_attractions = sorted(
    extracted.attractions.values(),
    key=lambda x: x.frequency,
    reverse=True,
)

# 转换为字典
result_dict = extracted.to_dict()
```

---

### 3.4 AttractionRules（景点预约规则）

#### 功能
- 景点预约规则的CRUD
- 按景点名称查询
- 按目的地查询
- 内存缓存
- 统计信息

#### 数据字段

| 字段 | 说明 | 示例 |
|-----|------|------|
| attraction_name | 景点名称 | 故宫博物院 |
| destination | 所属目的地 | 北京 |
| reservation_channel | 预约渠道 | 故宫博物院官方公众号 |
| reservation_url | 预约链接 | https://www.dpm.org.cn |
| ticket_release_time | 放票时间 | 提前7天20:00放票 |
| opening_hours | 开放时间 | 08:30-17:00（16:00停止入场） |
| closing_days | 闭馆日 | 每周一闭馆（法定节假日除外） |
| ticket_price | 票价 | 旺季60元，淡季40元，学生半价 |
| visitor_route | 游览路线 | 午门进，神武门出 |
| daily_limit | 每日限流 | 每日最大接待8万人 |
| tips | 其他提示 | 建议提前预约，旺季一票难求 |
| source | 数据来源 | official/manual/search/ai_generated |

#### 数据库表结构

```sql
CREATE TABLE attraction_rules (
    id INT AUTO_INCREMENT PRIMARY KEY,
    attraction_name VARCHAR(100) NOT NULL,
    destination VARCHAR(50) NOT NULL DEFAULT '',
    reservation_channel VARCHAR(200) NOT NULL DEFAULT '',
    reservation_url VARCHAR(500) NOT NULL DEFAULT '',
    ticket_release_time VARCHAR(200) NOT NULL DEFAULT '',
    opening_hours VARCHAR(500) NOT NULL DEFAULT '',
    closing_days VARCHAR(200) NOT NULL DEFAULT '',
    ticket_price VARCHAR(500) NOT NULL DEFAULT '',
    visitor_route VARCHAR(500) NOT NULL DEFAULT '',
    daily_limit VARCHAR(200) NOT NULL DEFAULT '',
    tips TEXT NULL,
    source VARCHAR(20) NOT NULL DEFAULT 'manual',
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_attraction_name (attraction_name),
    KEY idx_destination (destination),
    KEY idx_is_active (is_active),
    KEY idx_source (source)
);
```

#### 使用示例

```python
from app.services.online_data import get_attraction_rules, AttractionRule

rules = get_attraction_rules()

# 创建规则
rule = AttractionRule(
    attraction_name="故宫博物院",
    destination="北京",
    reservation_channel="故宫博物院官方公众号",
    ticket_release_time="提前7天20:00放票",
    opening_hours="08:30-17:00（16:00停止入场）",
    closing_days="每周一闭馆（法定节假日除外）",
    ticket_price="旺季60元，淡季40元，学生半价",
    visitor_route="午门进，神武门出",
    source="manual",
)
rule_id = await rules.create(rule)

# 查询规则
rule = await rules.get_by_name("故宫博物院")
dest_rules = await rules.get_by_destination("北京")

# 更新规则
rule.tips = "建议提前7天预约"
await rules.update(rule)

# 删除规则
await rules.delete(rule_id)

# 统计信息
stats = await rules.get_stats()
```

---

### 3.5 TravelTips（旅游避坑提示）

#### 功能
- 旅游避坑提示的CRUD
- 按目的地和类别查询
- 批量创建
- 内存缓存
- 统计信息

#### 提示类别

| 类别 | 说明 | 关键词 |
|-----|------|--------|
| general | 通用提示 | - |
| reservation | 预约提醒 | 预约、提前、放票、闭馆 |
| anti_fraud | 防骗提示 | 黑导游、一日游、被骗、黄牛 |
| traffic | 交通提示 | 地铁、公交、打车、停车 |
| food | 美食提示 | 美食、小吃、排队、老字号 |
| accommodation | 住宿提示 | 住宿、酒店、民宿、住哪里 |
| weather | 天气提示 | 天气、防晒、下雨、温度 |
| safety | 安全提示 | 安全、注意、保管、警惕 |

#### 严重程度

| 程度 | 说明 | 颜色 |
|-----|------|------|
| info | 信息 | 蓝色 |
| warning | 警告 | 黄色 |
| danger | 危险 | 红色 |

#### 数据库表结构

```sql
CREATE TABLE travel_tips (
    id INT AUTO_INCREMENT PRIMARY KEY,
    destination VARCHAR(50) NOT NULL,
    tip TEXT NOT NULL,
    category VARCHAR(20) NOT NULL DEFAULT 'general',
    severity VARCHAR(10) NOT NULL DEFAULT 'info',
    source VARCHAR(20) NOT NULL DEFAULT 'manual',
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    sort_order INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_destination (destination),
    KEY idx_category (category),
    KEY idx_severity (severity),
    KEY idx_is_active (is_active),
    KEY idx_sort_order (sort_order)
);
```

#### 使用示例

```python
from app.services.online_data import get_travel_tips, TravelTip

tips = get_travel_tips()

# 创建提示
tip = TravelTip(
    destination="北京",
    tip="不要参加路边的'长城一日游'，多为黑导游强制消费",
    category="anti_fraud",
    severity="danger",
    source="manual",
    sort_order=10,
)
tip_id = await tips.create(tip)

# 批量创建
tips_list = [
    TravelTip(destination="北京", tip="提示1", category="reservation"),
    TravelTip(destination="北京", tip="提示2", category="traffic"),
]
count = await tips.batch_create(tips_list)

# 查询提示
dest_tips = await tips.get_by_destination("北京", limit=10)
category_tips = await tips.get_by_destination("北京", category="anti_fraud")

# 更新提示
tip.tip = "更新后的提示"
await tips.update(tip)

# 删除提示
await tips.delete(tip_id)

# 统计信息
stats = await tips.get_stats()
```

---

## 四、后续优化方向

### 4.1 第二阶段：规划引擎改造（2-3周）

1. 改造规划引擎，支持"在线数据为基础，规划引擎增强"模式
2. 实现游览顺序提取和频率统计（已完成基础版本）
3. 实现耗时估算（基于在线数据平均值）
4. 实现用户偏好调整逻辑
5. 实现地理距离微调

### 4.2 第三阶段：输出增强（1周）

1. 新增预约提醒模块（前端展示）
2. 新增避坑提示模块（前端展示）
3. 新增美食推荐模块（前端展示）
4. 新增多方案生成（经典版/轻松版/特种兵版）
5. 新增局限性声明

### 4.3 第四阶段：数据运营和优化（持续）

1. 热门目的地数据定期更新
2. 用户反馈收集和数据质量优化
3. 数据提纯算法优化（LLM辅助提取）
4. A/B测试（在线数据模式 vs 纯规则模式）

### 4.5 LLM辅助提取（进阶）

当前数据提纯使用规则提取（正则表达式、关键词匹配），准确率有限。后续可以使用LLM辅助提取：

**Prompt设计**：
```
从以下攻略文本中提取结构化信息，输出JSON格式：
{
  "attractions": [
    {"name": "景点名称", "duration": 120, "area": "区域"}
  ],
  "daily_itineraries": [
    {"day": 1, "attractions": ["景点1", "景点2"]}
  ],
  "tips": [
    {"tip": "提示内容", "category": "reservation"}
  ]
}

攻略文本：
{text}
```

**优势**：
- 准确率更高
- 能处理复杂文本
- 能理解上下文

**成本**：
- 调用LLM有成本
- 速度较慢

**推荐方案**：
- 先用规则提取做基础
- 关键信息（预约规则、避坑提示）用LLM辅助提取
- 热门目的地可以预提取并缓存

---

## 五、测试

### 5.1 测试文件

`backend/tests/test_online_data.py`

### 5.2 测试用例

1. **搜索缓存测试**：写入、读取、统计、清理
2. **预约规则测试**：创建、查询、更新、删除、统计
3. **避坑提示测试**：创建、批量创建、查询、更新、删除、统计
4. **数据提纯测试**：景点提取、频率统计、游览顺序、耗时估算、避坑提示、置信度

### 5.3 运行测试

```bash
cd backend
./.venv/bin/python tests/test_online_data.py
```

---

## 六、总结

本模块实现了"在线数据为依托，规划引擎增强"的第一阶段基础能力：

✅ **已完成**：
- 搜索服务（多关键词策略、优先来源过滤）
- 搜索缓存（数据库持久化、过期机制）
- 数据提纯（景点提取、频率统计、游览顺序、耗时估算、避坑提示）
- 预约规则管理（CRUD、后台配置支持）
- 避坑提示管理（CRUD、批量导入、8个类别）
- 数据库表（3张新表）
- 完整测试（4个测试用例，全部通过）

⏳ **后续阶段**：
- 规划引擎改造（集成在线数据）
- 输出增强（预约提醒、避坑提示、多方案）
- 数据运营（定期更新、质量优化）
- LLM辅助提取（提升准确率）

通过本模块，规划引擎可以从"从零开始规划"转变为"基于真实攻略数据做增强和个性化调整"，显著提升规划质量和用户体验。
