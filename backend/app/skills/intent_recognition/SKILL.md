---
name: intent_recognition
description: 意图识别Skill。用于分析用户消息的意图，支持行程规划（plan）、天气查询（weather）、POI搜索（poi）、普通对话（chat）四种意图类型。优先使用LLM识别，失败时自动降级到规则兜底。提供统一的对外接口，便于集成和维护。
version: 1.0.0
author: 去见山海团队
---

# 意图识别 Skill（Intent Recognition Skill）

## 概述

意图识别Skill是旅行规划应用的核心模块，负责分析用户消息的意图，决定调用哪个工具或执行哪个操作。

支持四种意图类型：
- **plan**：行程规划（生成或调整旅行行程）
- **weather**：天气查询（查询实时天气）
- **poi**：POI搜索（搜索景点、美食、购物、夜生活地点）
- **chat**：普通对话（闲聊、寒暄、旅行咨询）

## 架构设计

```
用户消息
    ↓
IntentRecognizer（主类，对外接口）
    ├── LLMIntentRecognizer（优先使用LLM识别）
    │   ├── 调用Ollama API
    │   ├── 解析JSON结果（支持markdown格式、JSON块提取）
    │   └── 置信度校验（<0.6自动降级为chat）
    └── RuleIntentRecognizer（LLM失败时的兜底）
        ├── 天气关键词匹配
        ├── POI关键词匹配
        ├── 规划模式匹配
        └── 参数提取（天数、人数、预算、出行方式等）
```

## 目录结构

```
app/skills/intent_recognition/
├── SKILL.md              # Skill说明文档（本文件）
├── __init__.py           # 模块初始化，导出主要类和函数
├── types.py              # 类型定义（枚举、数据类）
├── prompts.py            # 提示词管理（集中管理意图识别提示词）
├── llm_recognizer.py     # LLM意图识别器
├── rule_recognizer.py    # 规则兜底意图识别器
├── recognizer.py         # 意图识别主类（对外接口）
└── tests/                # 测试用例
    └── test_intent_recognition.py
```

## 快速开始

### 安装依赖

本Skill依赖以下包：
- `httpx`：用于调用Ollama API
- `pydantic`：用于数据验证（可选）

安装命令：
```bash
pip install httpx pydantic
```

### 基本使用

```python
from app.skills.intent_recognition import (
    get_intent_recognizer,
    IntentType,
    IntentResult,
)

# 获取意图识别器单例
recognizer = get_intent_recognizer()

# 识别用户意图
messages = ["我想去杭州玩3天"]
result = await recognizer.recognize(messages)

# 根据意图类型执行不同操作
if result.intent == IntentType.PLAN:
    # 处理行程规划
    destination = result.params.get("destination")
    days = result.params.get("days")
    print(f"规划行程：{destination}，{days}天")
elif result.intent == IntentType.WEATHER:
    # 处理天气查询
    city = result.params.get("city")
    print(f"查询天气：{city}")
elif result.intent == IntentType.POI:
    # 处理POI搜索
    city = result.params.get("city")
    category = result.params.get("category")
    print(f"搜索POI：{city}，{category}")
else:
    # 处理普通对话
    reply = result.reply
    print(f"对话回复：{reply}")
```

### 自定义配置

```python
from app.skills.intent_recognition import IntentRecognizer

# 创建自定义配置的意图识别器
recognizer = IntentRecognizer(
    llm_model="qwen2:7b",        # 指定LLM模型
    llm_temperature=0.3,          # LLM温度参数
    use_llm=True,                 # 是否使用LLM识别
    use_rule_fallback=True,       # 是否使用规则兜底
)
```

## API 文档

### IntentRecognizer（意图识别主类）

#### `__init__(self, llm_model="", llm_temperature=0.3, use_llm=True, use_rule_fallback=True)`

初始化意图识别器。

**参数：**
- `llm_model` (str): LLM模型名称，为空时使用默认模型
- `llm_temperature` (float): LLM温度参数，意图识别建议使用较低温度（0.1-0.3）
- `use_llm` (bool): 是否使用LLM识别，默认为True
- `use_rule_fallback` (bool): 是否使用规则兜底，默认为True

#### `async recognize(self, messages, context=None) -> IntentResult`

识别用户意图。

**参数：**
- `messages` (List[str]): 用户消息列表（含历史）
- `context` (Optional[RecognitionContext]): 识别上下文

**返回：**
- `IntentResult`: 意图识别结果

**示例：**
```python
result = await recognizer.recognize(["我想去杭州玩3天"])
print(result.intent)  # IntentType.PLAN
print(result.params)  # {"destination": "杭州", "days": 3, ...}
```

#### `async recognize_plan_params(self, message, context=None) -> Dict[str, Any]`

专门识别规划参数（用于参数提取场景）。

**参数：**
- `message` (str): 用户消息
- `context` (Optional[RecognitionContext]): 识别上下文

**返回：**
- `Dict[str, Any]`: 提取的参数字典，如果不是规划意图则返回空字典

### IntentResult（意图识别结果）

**属性：**
- `intent` (IntentType): 意图类型
- `params` (Dict[str, Any]): 提取的参数
- `reply` (str): 回复文本（仅chat意图有值）
- `confidence` (float): 置信度（0.0-1.0）
- `source` (str): 识别来源（llm/rule/default）
- `raw_result` (Dict[str, Any]): 原始识别结果

**方法：**
- `to_dict() -> Dict[str, Any]`: 转换为字典
- `from_dict(data: Dict[str, Any]) -> IntentResult`: 从字典创建

### IntentType（意图类型枚举）

**枚举值：**
- `IntentType.PLAN`: 行程规划
- `IntentType.WEATHER`: 天气查询
- `IntentType.POI`: POI搜索
- `IntentType.CHAT`: 普通对话

**方法：**
- `from_string(value: str) -> IntentType`: 从字符串创建意图类型，不合法时返回CHAT

## 意图识别规则

### 行程规划（plan）

**触发条件：**
- 用户明确说"去X玩N天"、"我想去X"、"帮我规划X行程"
- 用户说"改成N天"、"加个X"、"预算经济一点"等调整指令
- 用户提到具体景点，如"我想去大明湖"

**参数提取：**
- `destination`: 目的地（省、市、区县、具体景点）
- `days`: 天数（默认3天）
- `travelers`: 人数（默认1人）
- `budget_level`: 预算档位（经济/适中/舒适/豪华，默认适中）
- `style`: 旅行风格（综合/人文/自然/美食/购物/亲子/打卡，默认综合）
- `pace`: 节奏（轻松/适中/紧凑，默认适中）
- `traffic_mode`: 出行方式（公共交通/自驾/骑行/步行/混合，默认公共交通）
- `province/city/district`: 行政区域补全

### 天气查询（weather）

**触发条件：**
- 用户问"X的天气"、"X天气如何"、"X冷不丁"、"X下雨吗"

**参数提取：**
- `city`: 城市名

### POI搜索（poi）

**触发条件：**
- 用户问"X有什么好玩的"、"X美食推荐"、"X景点推荐"

**参数提取：**
- `city`: 城市名
- `category`: 类别（景点/美食/购物/夜生活）
- `keyword`: 关键词

### 普通对话（chat）

**触发条件：**
- 用户说"你好"、"谢谢"、"再见"等寒暄
- 用户问"旅行的意义是什么"、"你能做什么"等咨询
- 无法判断意图的情况

## 置信度机制

为了确保意图识别的准确性，本Skill实现了置信度机制：

1. **LLM识别置信度**：LLM返回的confidence字段
2. **置信度阈值**：只有confidence >= 0.6时，才允许返回plan/weather/poi
3. **自动降级**：confidence < 0.6时，自动降级为chat
4. **规则兜底置信度**：规则识别的置信度通常为0.8-0.85

## 日志记录

本Skill实现了完整的日志记录，便于排查问题：

- **LLM识别日志**：记录意图、置信度、目的地、天数、延迟、模型
- **规则识别日志**：记录意图、城市、类别、消息
- **错误日志**：记录识别过程中的异常
- **降级日志**：记录LLM失败降级到规则的情况

日志级别：
- `INFO`: 正常识别结果
- `WARNING`: 降级、空响应、低置信度
- `ERROR`: 异常错误

## 测试

### 运行测试

```bash
cd backend
python -m pytest app/skills/intent_recognition/tests/ -v
```

### 测试用例

测试用例覆盖以下场景：
1. 行程规划意图识别
2. 天气查询意图识别
3. POI搜索意图识别
4. 普通对话意图识别
5. 只有目的地没有天数的情况
6. 调整指令识别
7. 参数提取准确性
8. 置信度校验
9. 规则兜底功能
10. 异常处理

## 最佳实践

### 1. 使用单例模式

```python
# 推荐：使用单例模式，避免重复初始化
from app.skills.intent_recognition import get_intent_recognizer
recognizer = get_intent_recognizer()

# 不推荐：每次都创建新实例
recognizer = IntentRecognizer()
```

### 2. 传入完整的对话历史

```python
# 推荐：传入完整的对话历史，便于识别调整指令
messages = ["帮我规划杭州3天行程", "改成5天"]
result = await recognizer.recognize(messages)

# 不推荐：只传入当前消息，可能无法识别调整指令
messages = ["改成5天"]
result = await recognizer.recognize(messages)
```

### 3. 处理所有意图类型

```python
# 推荐：处理所有意图类型，避免遗漏
if result.intent == IntentType.PLAN:
    # 处理规划
elif result.intent == IntentType.WEATHER:
    # 处理天气
elif result.intent == IntentType.POI:
    # 处理POI
else:
    # 处理对话

# 不推荐：只处理规划意图，其他意图忽略
if result.intent == IntentType.PLAN:
    # 处理规划
```

### 4. 检查置信度

```python
# 推荐：检查置信度，低置信度时可以询问用户确认
if result.confidence < 0.7:
    # 询问用户确认意图
    reply = "你是想规划行程吗？"
else:
    # 直接执行
    pass
```

## 常见问题

### Q1: LLM识别失败怎么办？

A: 本Skill会自动降级到规则兜底识别。如果规则兜底也失败，会返回默认chat回复。你可以通过日志查看失败原因。

### Q2: 如何提高识别准确率？

A: 可以通过以下方式提高准确率：
1. 使用更强大的LLM模型（如qwen2:14b）
2. 优化提示词（修改prompts.py）
3. 增加规则兜底的关键词和模式
4. 传入完整的对话历史

### Q3: 如何添加新的意图类型？

A: 需要修改以下文件：
1. `types.py`: 在IntentType枚举中添加新类型
2. `prompts.py`: 在提示词中添加新类型的说明和示例
3. `rule_recognizer.py`: 添加新类型的规则匹配
4. `llm_recognizer.py`: 通常不需要修改，LLM会自动识别

### Q4: 如何自定义提示词？

A: 修改`prompts.py`中的`INTENT_SYSTEM_PROMPT`变量。建议保留原有的结构和规则，只修改具体的描述和示例。

### Q5: 意图识别的延迟是多少？

A: 
- LLM识别：通常2-5秒（取决于模型和硬件）
- 规则识别：通常<10毫秒
- 总延迟：LLM识别时2-5秒，规则兜底时<10毫秒

## 版本历史

### v1.0.0 (2026-08-30)
- 初始版本
- 支持四种意图类型：plan、weather、poi、chat
- 实现LLM识别和规则兜底
- 实现置信度机制
- 完整的日志记录
- 详细的文档和测试用例

## 许可证

本Skill遵循项目的许可证。

## 联系方式

如有问题或建议，请联系去见山海团队。
