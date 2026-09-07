"""
核心能力层模块。

包含以下子模块：
- planner：行程规划引擎（build_plan 主入口）
- intent：意图识别（LLM解析用户输入、参数提取）
- geo_local：本地地理数据（行政区域、城市坐标、缓存）
- health：健康检查（服务状态、依赖检查）
- pipeline_stages：规划流水线阶段定义
"""
