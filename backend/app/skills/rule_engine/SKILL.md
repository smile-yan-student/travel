---
name: rule_engine
description: 规则引擎Skill。提供旅行规划的规则引擎，包含参数标准化、人群影响、交通灵活性、景点过滤、天数分配、规划审查等功能。用于规划生成过程中的参数校验、景点筛选、行程分配和质量审查。
version: 1.0.0
author: 去见山海团队
---

# 规则引擎 Skill（Rule Engine Skill）

## 概述

规则引擎Skill是旅行规划应用的核心模块，负责规划生成过程中的规则执行和质量控制。它包含多个专业引擎，协同完成参数标准化、人群影响分析、交通灵活性评估、景点过滤、天数分配和规划审查等任务。

## 架构设计

```
PlanningRuleEngine（主类，对外接口）
    ├── ParameterNormalizer（参数规范化器）
    │   ├── 天数标准化（兜底和收束）
    │   ├── 人数标准化
    │   ├── 预算档位标准化
    │   ├── 人群类型标准化
    │   ├── 节奏标准化
    │   └── 出行方式标准化
    ├── GroupInfluenceEngine（人群影响引擎）
    │   ├── 人群配置获取
    │   ├── 主POI/辅助POI比例
    │   ├── 默认节奏
    │   ├── 辅助类别
    │   ├── 景点过滤（亲子/老人友好）
    │   └── 节奏调整
    ├── TrafficFlexibilityEngine（交通灵活性引擎）
    │   ├── 目的地类型判断
    │   ├── POI分布判断
    │   ├── 影响强度计算
    │   ├── 规划程度计算
    │   └── 通行方式建议
    ├── AttractionFilterEngine（景点过滤引擎）
    │   ├── 预算过滤
    │   ├── 硬约束过滤（必去/排除）
    │   ├── 中国区域过滤
    │   └── 同名地点处理
    ├── DayAllocationEngine（天数分配引擎）
    │   ├── 聚类分配到天
    │   ├── 体验曲线
    │   └── 推荐强度
    └── PlanReviewEngine（规划审查引擎）
        ├── 行程审查
        ├── 问题识别
        └── 行程补充
```

## 目录结构

```
app/skills/rule_engine/
├── SKILL.md              # Skill说明文档（本文件）
├── __init__.py           # 模块初始化，导出主要类和函数
├── rule_engine.py        # 规则引擎主文件（包含所有引擎）
└── tests/
    └── test_rule_engine.py  # 测试用例
```

## 快速开始

### 基本使用

```python
from app.skills.rule_engine import get_rule_engine

# 获取规则引擎单例
rule_engine = get_rule_engine()

# 1. 参数标准化
params = {
    "days": 100,  # 超出范围，会被收束
    "travelers": 0,  # 小于最小值，会被兜底
    "budget_level": "超级豪华",  # 不合法，会被标准化
    "group_type": "亲子",
    "pace": "非常慢",
    "traffic_mode": "坐飞机",
}
normalized_params = rule_engine.normalize_params(params)
print(normalized_params)
# {'days': 30, 'travelers': 1, 'budget_level': '豪华', 'group_type': '亲子', 'pace': '适中', 'traffic_mode': '公共交通'}

# 2. 人群影响配置
group_config = rule_engine.group_engine.get_group_config("亲子")
print(group_config)
# {'main_poi_ratio': 0.6, 'aux_poi_ratio': 0.4, 'default_pace': '轻松', 'aux_categories': ['亲子', '公园', '博物馆']}

# 3. 景点过滤
pois = [
    {"name": "故宫", "category": "景点", "price": 60},
    {"name": "迪士尼乐园", "category": "亲子", "price": 400},
    {"name": "酒吧", "category": "夜生活", "price": 200},
]
filtered, excluded = rule_engine.filter_attractions(pois, {"group_type": "亲子", "budget_level": "经济"})
print(f"保留: {[p['name'] for p in filtered]}")
print(f"排除: {[p['name'] for p in excluded]}")

# 4. 规划审查
day_plans = [
    {"day": 1, "pois": [{"name": "故宫"}, {"name": "天安门"}]},
    {"day": 2, "pois": []},  # 空天，会被识别为问题
]
is_valid, issues = rule_engine.review_plan(day_plans, {"days": 2})
print(f"是否有效: {is_valid}")
print(f"问题: {issues}")
```

### 自定义配置

```python
from app.skills.rule_engine import PlanningRuleEngine

# 创建自定义配置的规则引擎
rule_engine = PlanningRuleEngine()

# 可以单独使用各个引擎
normalizer = rule_engine.normalizer
group_engine = rule_engine.group_engine
traffic_engine = rule_engine.traffic_engine
filter_engine = rule_engine.filter_engine
allocation_engine = rule_engine.allocation_engine
review_engine = rule_engine.review_engine
```

## API 文档

### PlanningRuleEngine（规划规则引擎主类）

#### `__init__(self)`

初始化规则引擎，创建各个子引擎的实例。

#### `normalize_params(self, params: dict) -> dict`

规范化参数。

**参数：**
- `params` (dict): 原始参数字典

**返回：**
- `dict`: 规范化后的参数字典

**示例：**
```python
normalized = rule_engine.normalize_params({"days": 100, "travelers": 0})
# {'days': 30, 'travelers': 1, ...}
```

#### `filter_attractions(self, pois: List[dict], params: dict) -> Tuple[List[dict], List[dict]]`

筛选景点。

**参数：**
- `pois` (List[dict]): 景点列表
- `params` (dict): 规划参数

**返回：**
- `Tuple[List[dict], List[dict]]`: (保留的景点, 被排除的景点)

#### `allocate_to_days(self, clusters: List[dict], total_days: int, center: dict = None) -> List[dict]`

分配聚类到每天。

**参数：**
- `clusters` (List[dict]): 景点聚类列表
- `total_days` (int): 总天数
- `center` (dict, optional): 中心点坐标

**返回：**
- `List[dict]`: 每天的行程分配

#### `review_plan(self, day_plans: List[dict], params: dict) -> Tuple[bool, List[dict]]`

检视行程。

**参数：**
- `day_plans` (List[dict]): 每天的行程计划
- `params` (dict): 规划参数

**返回：**
- `Tuple[bool, List[dict]]`: (是否有效, 问题列表)

#### `supplement_plan(self, day_plans: List[dict], issues: List[dict], candidate_pool: List[dict], used_poi_ids: set) -> List[dict]`

补充行程。

**参数：**
- `day_plans` (List[dict]): 每天的行程计划
- `issues` (List[dict]): 问题列表
- `candidate_pool` (List[dict]): 候选景点池
- `used_poi_ids` (set): 已使用的POI ID集合

**返回：**
- `List[dict]`: 补充后的行程计划

#### `calculate_traffic_impact(self, params: dict, center: dict, pois: List[dict]) -> dict`

计算出行方式影响强度和规划程度。

**参数：**
- `params` (dict): 规划参数
- `center` (dict): 中心点坐标
- `pois` (List[dict]): 景点列表

**返回：**
- `dict`: 包含影响强度、规划程度、目的地类型、POI分布等信息

#### `get_traffic_suggestion(self, distance_m: float, group_type: str = "单人", budget_level: str = "适中") -> dict`

获取通行方式建议。

**参数：**
- `distance_m` (float): 距离（米）
- `group_type` (str): 人群类型
- `budget_level` (str): 预算档位

**返回：**
- `dict`: 通行方式建议

### get_rule_engine()

获取规则引擎单例。

**返回：**
- `PlanningRuleEngine`: 规则引擎单例

## 核心引擎详解

### 1. ParameterNormalizer（参数规范化器）

负责无上限参数的兜底和收束规则。

**核心方法：**
- `normalize_days(days)`: 天数标准化（1-30天）
- `normalize_travelers(travelers)`: 人数标准化（1-99人）
- `normalize_budget(budget_level)`: 预算档位标准化
- `normalize_group_type(group_type)`: 人群类型标准化
- `normalize_pace(pace)`: 节奏标准化
- `normalize_traffic_mode(traffic_mode)`: 出行方式标准化
- `normalize_all(params)`: 全部参数标准化
- `get_days_interval(days)`: 获取天数区间描述
- `get_travelers_interval(travelers)`: 获取人数区间描述

**规则说明：**
- 天数：最小值1天，最大值30天，超出范围自动收束
- 人数：最小值1人，最大值99人，超出范围自动收束
- 预算档位：经济/适中/舒适/豪华，不合法时模糊匹配或使用默认值
- 人群类型：单人/情侣/朋友/家庭/亲子/商务/其他，不合法时模糊匹配或使用默认值
- 节奏：轻松/适中/紧凑，不合法时模糊匹配或使用默认值
- 出行方式：公共交通/自驾/骑行/步行/混合，不合法时模糊匹配或使用默认值

### 2. GroupInfluenceEngine（人群影响引擎）

负责人群类型对规划的影响分析。

**核心方法：**
- `get_group_config(group_type)`: 获取人群配置
- `get_main_poi_ratio(group_type)`: 获取主POI比例
- `get_aux_poi_ratio(group_type)`: 获取辅助POI比例
- `get_default_pace(group_type)`: 获取默认节奏
- `get_aux_categories(group_type)`: 获取辅助类别
- `filter_pois_by_group(pois, group_type)`: 按人群过滤景点
- `is_family_friendly(poi)`: 判断是否亲子友好
- `is_elderly_friendly(poi)`: 判断是否老人友好
- `adjust_pace_by_group(group_type, pace)`: 按人群调整节奏

**人群配置说明：**
- 单人：主POI比例0.8，辅助POI比例0.2，默认节奏适中
- 情侣：主POI比例0.7，辅助POI比例0.3，默认节奏适中，辅助类别包含浪漫、摄影
- 家庭：主POI比例0.6，辅助POI比例0.4，默认节奏轻松，辅助类别包含亲子、公园、博物馆
- 亲子：主POI比例0.5，辅助POI比例0.5，默认节奏轻松，辅助类别包含亲子、公园、动物园、博物馆
- 朋友：主POI比例0.7，辅助POI比例0.3，默认节奏适中，辅助类别包含美食、购物、夜生活

### 3. TrafficFlexibilityEngine（交通灵活性引擎）

负责出行方式对规划的影响评估和通行建议。

**核心方法：**
- `calculate_impact_score(group_type, destination_type, poi_distribution, days, budget_level)`: 计算影响强度
- `get_impact_level(score)`: 获取影响等级
- `calculate_plan_score(group_type, traffic_mode, destination_type, days)`: 计算规划程度
- `get_plan_level(score)`: 获取规划等级
- `get_traffic_suggestion(distance_m, group_type, budget_level)`: 获取通行方式建议
- `determine_destination_type(center, pois)`: 判断目的地类型
- `determine_poi_distribution(pois)`: 判断POI分布

**目的地类型：**
- 城市型：景点集中在城市内
- 景区型：景点集中在某个景区
- 跨城型：景点分布在多个城市
- 混合型：多种类型混合

**POI分布：**
- 集中型：景点距离较近
- 分散型：景点距离较远
- 混合型：集中和分散混合

### 4. AttractionFilterEngine（景点过滤引擎）

负责景点的筛选和过滤。

**核心方法：**
- `filter_by_budget(pois, budget_level)`: 按预算过滤
- `filter_hard_constraints(pois, must_include, exclude)`: 硬约束过滤
- `is_in_china(poi)`: 判断是否在中国
- `resolve_same_name_destination(destination, geo)`: 同名地点处理

**过滤规则：**
- 预算过滤：根据预算档位过滤价格过高的景点
- 必去景点：必须包含用户指定的必去景点
- 排除景点：排除用户指定的排除景点
- 中国区域：只规划中国区域内的地点
- 同名地点：优先以目的地的地点为先，或通过用户对话确认

### 5. DayAllocationEngine（天数分配引擎）

负责将景点聚类分配到每天。

**核心方法：**
- `allocate_clusters_to_days(clusters, total_days, center)`: 分配聚类到天
- `get_experience_curve(day_no, total_days)`: 获取体验曲线
- `get_recommended_intensity(day_no, total_days)`: 获取推荐强度

**分配规则：**
- 就近优先：距离近的景点优先分配在同一天
- 体验曲线：第一天和最后一天强度较低，中间天数强度较高
- 跨天不重复：跨天出行，出行内容不能重复

### 6. PlanReviewEngine（规划审查引擎）

负责行程的质量审查和补充。

**核心方法：**
- `review_plan(day_plans, params)`: 审查行程
- `supplement_plan(day_plans, issues, candidate_pool, used_poi_ids)`: 补充行程

**审查规则：**
- 空天检查：每天都应该有景点
- 景点数量检查：每天景点数量应该合理
- 重复检查：不应该有重复的景点
- 距离检查：同一天的景点距离应该合理
- 人群适配检查：景点应该适合出行人群

## 使用场景

### 场景1：规划生成流程

```python
from app.skills.rule_engine import get_rule_engine

rule_engine = get_rule_engine()

# 1. 参数标准化
normalized_params = rule_engine.normalize_params(user_params)

# 2. 景点过滤
filtered_pois, excluded_pois = rule_engine.filter_attractions(pois, normalized_params)

# 3. 聚类和分配（需要外部聚类算法）
clusters = cluster_pois(filtered_pois)
day_plans = rule_engine.allocate_to_days(clusters, normalized_params["days"], center)

# 4. 规划审查
is_valid, issues = rule_engine.review_plan(day_plans, normalized_params)

# 5. 规划补充（如果有问题）
if not is_valid:
    day_plans = rule_engine.supplement_plan(day_plans, issues, candidate_pool, used_poi_ids)

# 6. 计算交通影响
traffic_impact = rule_engine.calculate_traffic_impact(normalized_params, center, filtered_pois)
```

### 场景2：人群影响分析

```python
from app.skills.rule_engine import get_rule_engine

rule_engine = get_rule_engine()

# 获取亲子出行的配置
group_config = rule_engine.group_engine.get_group_config("亲子")
print(f"主POI比例: {group_config['main_poi_ratio']}")
print(f"辅助POI比例: {group_config['aux_poi_ratio']}")
print(f"默认节奏: {group_config['default_pace']}")
print(f"辅助类别: {group_config['aux_categories']}")

# 过滤亲子友好的景点
family_friendly, not_family_friendly = rule_engine.group_engine.filter_pois_by_group(pois, "亲子")
```

### 场景3：通行方式建议

```python
from app.skills.rule_engine import get_rule_engine

rule_engine = get_rule_engine()

# 获取两个景点之间的通行建议
distance_m = 5000  # 5公里
suggestion = rule_engine.get_traffic_suggestion(distance_m, group_type="单人", budget_level="适中")
print(f"建议出行方式: {suggestion['mode']}")
print(f"预计时间: {suggestion['duration']}")
print(f"预计费用: {suggestion['cost']}")
```

## 最佳实践

### 1. 使用单例模式

```python
# 推荐：使用单例模式，避免重复初始化
from app.skills.rule_engine import get_rule_engine
rule_engine = get_rule_engine()

# 不推荐：每次都创建新实例
rule_engine = PlanningRuleEngine()
```

### 2. 先标准化再使用

```python
# 推荐：先标准化参数，再使用
normalized_params = rule_engine.normalize_params(user_params)
filtered_pois, _ = rule_engine.filter_attractions(pois, normalized_params)

# 不推荐：直接使用原始参数
filtered_pois, _ = rule_engine.filter_attractions(pois, user_params)
```

### 3. 审查后补充

```python
# 推荐：审查后如果有问题，进行补充
is_valid, issues = rule_engine.review_plan(day_plans, params)
if not is_valid:
    day_plans = rule_engine.supplement_plan(day_plans, issues, candidate_pool, used_poi_ids)

# 不推荐：只审查不补充
is_valid, issues = rule_engine.review_plan(day_plans, params)
```

### 4. 结合人群和交通

```python
# 推荐：结合人群影响和交通灵活性进行规划
group_config = rule_engine.group_engine.get_group_config(params["group_type"])
traffic_impact = rule_engine.calculate_traffic_impact(params, center, pois)

# 根据人群配置和交通影响调整规划
if traffic_impact["impact_level"] == "high":
    # 高影响，需要详细规划通行方式
    pass
```

## 常见问题

### Q1: 规则引擎和规划引擎有什么区别？

A: 规则引擎负责规划生成过程中的规则执行和质量控制，包括参数标准化、景点过滤、天数分配、规划审查等。规划引擎（planner.py）负责整体的规划流程，包括POI检索、聚类、逐日构建等，它会调用规则引擎来执行具体的规则。

### Q2: 如何添加新的人群类型？

A: 需要修改 `GroupInfluenceEngine` 类，添加新的人群配置。具体来说，需要修改 `get_group_config`、`get_main_poi_ratio`、`get_aux_poi_ratio` 等方法，添加新人群类型的配置。

### Q3: 如何调整参数的范围？

A: 需要修改 `ParameterNormalizer` 类中的常量和方法。例如，要调整天数范围，需要修改 `normalize_days` 方法中的最小值和最大值。

### Q4: 规则引擎的性能如何？

A: 规则引擎是纯计算的，不涉及IO操作，性能很好。参数标准化、景点过滤、规划审查等操作都是毫秒级的。

### Q5: 可以单独使用某个引擎吗？

A: 可以。`PlanningRuleEngine` 类包含了各个子引擎的实例，可以直接访问使用。例如，`rule_engine.group_engine` 可以单独使用人群影响引擎。

### Q6: 如何调试规则引擎的执行过程？

A: 可以在调用各个方法前后添加日志，记录输入和输出。也可以单独测试各个引擎的方法，验证其行为是否符合预期。

## 版本历史

### v1.0.0 (2026-08-30)
- 初始版本
- 包含6个核心引擎：参数规范化、人群影响、交通灵活性、景点过滤、天数分配、规划审查
- 提供统一的主类 `PlanningRuleEngine` 和单例函数 `get_rule_engine`
- 完整的文档和测试用例

## 许可证

本Skill遵循项目的许可证。

## 联系方式

如有问题或建议，请联系去见山海团队。
