"""
AI能力层模块。

包含以下子模块：
- ai：LLM服务（模型管理、对话生成、行程优化）
- model_manager：模型管理（多模型注册、性能监控、降级策略、模型路由）
- prompt_manager：Prompt管理（配置文件加载、版本管理、模板渲染）

功能特性：
- 多模型支持（Ollama本地模型，qwen2:7b等）
- 模型性能监控（响应时间、调用次数、成功率）
- 模型降级策略（主模型不可用时自动切换到备用模型）
- 模型路由（不同任务使用不同模型，如意图识别用小模型，规划用大模型）
- Prompt统一管理（配置文件加载、版本管理、模板渲染）
- 对话生成（温暖、真诚、博学的语气）
- 行程优化（LLM优化阶段）

使用方式：
    from app.ai import ai_available, chat_reply, generate_plan_reply

    # 检查AI服务是否可用
    available = ai_available()

    # 生成对话回复
    reply = await chat_reply(messages, model="qwen2:7b")

    # 生成规划回复
    plan_reply = await generate_plan_reply(params, attractions)
"""
from .ai import (
    ai_available,
    chat_completion,
    chat_reply,
    generate_itinerary,
    generate_plan_reply,
    optimize_itinerary,
    reply_with_tool_result,
    resolve_model,
)

__all__ = [
    "ai_available",
    "resolve_model",
    "chat_reply",
    "chat_completion",
    "reply_with_tool_result",
    "generate_plan_reply",
    "generate_itinerary",
    "optimize_itinerary",
]
