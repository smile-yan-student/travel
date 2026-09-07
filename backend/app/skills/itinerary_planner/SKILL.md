# 行程规划 Skill（Itinerary Planner Skill）

## 概述

行程规划 Skill 是一个独立的、可复用的旅游行程规划能力模块，提供从用户需求到完整行程规划的全流程能力。

## 核心能力

### 1. 行程规划引擎（build_plan）
根据用户的出行需求（目的地、天数、人数、预算、出行方式等），生成完整的行程规划，包括：
- 每日行程安排（景点、美食、购物、夜生活）
- 时间分配（上午、中午、下午、晚上）
- 交通建议（景点间通行方式）
- 住宿区域推荐
- 预算估算
- 行程灵感和避坑提示

### 2. 地理枚举（enumerate_scoped_attractions）
按行政分级（区县/市/省）枚举范围内的景点，支持：
- 区县级别：枚举当前区县的景点
- 市级别：枚举当前市的景点，补充周边区县
- 省级别：枚举省内主要城市的景点
- 跨城污染过滤：避免不同城市的景点混入

### 3. 地理聚类（cluster_attractions）
按地理位置将景点聚类分组，支持：
- 就近优先聚类
- 距离阈值控制（默认12公里）
- 稀疏聚类合并
- 区域标签生成
- 按天分配聚类区域

### 4. 逐日构建（build_geo_day）
将聚类后的景点按天分配，支持：
- 必去景点优先安排
- 地理位置重排（最近邻 + 综合评分）
- 时间轴分配（开放时间、游玩时长）
- 辅助点位插入（美食、购物、夜生活）
- 住宿区域推荐
- 跨天去重（同地标词不重复）

### 5. 必去景点注入（inject_must_visit_attrs）
确保城市必去景点（地标、5A景区、世界遗产等）进入规划，支持：
- 从数据库读取必去景点配置
- 按城市匹配必去景点
- 优先级提升（必去景点优先安排）
- 数量控制（避免必去景点过多）

### 6. 时空规划器（spatial_temporal_plan）
时空联合规划，支持：
- 先空间后时间的两阶段规划
- 空间路线构建（出发点 → 目的城市 → 返程点）
- 时间拆分（按天数拆分空间路线）
- 通行时间估算
- 游玩时间估算

### 7. 行程质量评估（PlanQualityEvaluator）
评估行程规划的质量，包括：
- 景点覆盖度（必去景点是否都安排）
- 时间合理性（是否过于紧凑或松散）
- 地理合理性（是否来回折返）
- 多样性（景点类型是否丰富）
- 预算合理性
- 综合评分和改进建议

### 8. 大型景区识别与处理
- `is_large_scenic_area`：判断是否是大型景区（如西湖、故宫、大明湖等）
- `is_inside_large_scenic_area`：判断是否在大型景区内部
- `dedup_scenic_inner_pois`：去重景区内部POI，避免主景区和子景点同时出现
- `get_scenic_area_weight_factor`：获取景区权重因子，调整子景点优先级

## 目录结构

```
itinerary_planner/
├── __init__.py              # Skill入口，导出主要接口
├── SKILL.md                 # Skill文档（本文件）
├── planner.py               # 规划引擎主入口（build_plan）
├── constants.py             # 规划常量（聚类距离、枚举关键词、地标词等）
├── utils.py                 # 工具函数（评分、去重、灵感生成等）
├── geo_enum.py              # 地理枚举（行政分级枚举景点）
├── cluster.py               # 地理聚类（按位置聚类分组）
├── daily_build.py           # 逐日构建（按天分配景点和时间）
├── must_visit.py            # 必去景点注入
├── spatial_temporal.py      # 时空规划器
├── param_validator.py       # 参数验证
├── quality/
│   ├── __init__.py
│   └── evaluator.py         # 行程质量评估器
└── tests/
    └── test_itinerary_planner.py
```

## 使用方式

### 基本使用

```python
from app.skills.itinerary_planner import build_plan
from app.data.models.models import PlanRequest

# 创建规划请求
req = PlanRequest(
    destination="杭州",
    days=3,
    people=2,
    budget="适中",
    travel_style="人文",
    traffic_mode="公共交通",
)

# 构建行程规划
plan = await build_plan(req)
print(f"规划完成：{plan.days}天，{len(plan.day_plans)}个行程")
```

### 质量评估

```python
from app.skills.itinerary_planner import PlanQualityEvaluator

# 评估行程质量
evaluator = PlanQualityEvaluator()
report = evaluator.evaluate(plan)
print(f"综合评分：{report.overall_score}")
print(f"改进建议：{report.suggestions}")
```

### 地理枚举

```python
from app.skills.itinerary_planner import enumerate_scoped_attractions

# 枚举杭州市的景点
attractions = await enumerate_scoped_attractions(
    adcode="330100",
    scope="市",
    limit=50,
)
print(f"找到 {len(attractions)} 个景点")
```

### 地理聚类

```python
from app.skills.itinerary_planner import cluster_attractions

# 聚类景点
clusters = cluster_attractions(
    pois=attractions,
    max_dist=12000,  # 12公里
)
print(f"聚类为 {len(clusters)} 个区域")
```

## 规划流程

1. **参数解析**：解析用户的出行需求（目的地、天数、人数等）
2. **地理编码**：将目的地转换为坐标和行政区域
3. **地理枚举**：按行政分级枚举范围内的景点
4. **必去景点注入**：确保城市必去景点进入候选池
5. **大型景区处理**：识别大型景区，去重内部POI
6. **地理聚类**：按地理位置聚类分组
7. **按天分配**：将聚类区域按天分配
8. **逐日构建**：为每天分配景点和时间
9. **辅助点位**：插入美食、购物、夜生活等辅助点位
10. **质量评估**：评估规划质量，必要时调整
11. **结果返回**：返回完整的行程规划

## 配置项

### 常量配置（constants.py）

- `SCOPE_KEYWORDS`：行政分级枚举关键词
- `CLUSTER_MAX_DIST`：聚类距离上限（默认12公里）
- `SCOPE_MAX_RANGE`：省内景点距离市中心上限（默认150公里）
- `CLOSED_MARKERS`：闭馆/停业标记
- `AUX_FOOD_BAD_NAMES`：美食辅助点名称护栏
- `LANDMARK_WORDS`：全国知名地标特征词

### 可配置参数

- 天数（1-30天）
- 人数（1-10人）
- 预算（经济/适中/舒适/豪华）
- 出行风格（人文/自然/美食/亲子/情侣/摄影等）
- 出行方式（自驾/公共交通/骑行/步行/混合）
- 节奏（紧凑/适中/休闲）

## 依赖

- `app.services.map`：地图服务（地理编码、POI搜索、路径规划、天气）
- `app.services.major_attractions`：主要景点服务
- `app.data.models.models`：数据模型（PlanRequest、PlanResponse、POI等）
- `app.data.repositories`：数据仓库（必去景点、POI层级、开放时间等）
- `app.skills.rule_engine`：规则引擎（参数验证、规划规则）
- `app.ai`：AI服务（行程优化、对话生成）
- `app.infrastructure.logger`：日志服务

## 版本历史

- v1.0.0（2026-08-31）：初始版本，从 core/planner.py 和 services/planner/ 迁移而来
