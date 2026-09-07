"""
本地轻量 AI 模型接入（Ollama）。

默认模型：qwen2:7b（约 4GB，16GB 内存可流畅运行；更省可换 3b）。
Ollama 未启动 / 未安装时，ai_available() 返回 False，由 planner 走内置规则引擎兜底。

功能特性：
- ai_available：检测 Ollama 服务是否可用（并确认至少存在一个模型）
- resolve_model：解析实际要用的模型名（优先用配置的 OLLAMA_MODEL，未拉取时自动降级）
- chat_reply：生成对话回复（温暖、真诚、博学的语气）
- reply_with_tool_result：带工具调用结果的回复
- generate_plan_reply：生成规划回复（包含行程概览、主题、建议）
- generate_itinerary：生成行程（LLM生成行程）
- optimize_itinerary：优化行程（LLM优化阶段）
- 模型管理集成（支持降级策略、性能监控）
- Prompt管理集成（支持配置文件加载、版本管理、模板渲染）
- 历史名人/革命先辈特别回复规则
- JSON结构输出（严格遵循用户给定的JSON结构）

使用方式：
    from app.ai.ai import ai_available, chat_reply, generate_plan_reply

    # 检查AI服务是否可用
    available = ai_available()

    # 生成对话回复
    reply = await chat_reply(messages, model="qwen2:7b")

    # 生成规划回复
    plan_reply = await generate_plan_reply(params, attractions)
"""
import json
import re
import time
from typing import Any, Dict, List, Optional

import httpx

from ..config import settings
from ..infrastructure import logger as log_mod

_ai_logger = log_mod.get_logger("ai")

# 模型管理模块（懒加载，避免循环导入）
_model_manager = None

def _get_model_manager():
    """获取模型管理器实例（懒加载）。"""
    global _model_manager
    if _model_manager is None:
        from .model_manager import get_model_manager
        _model_manager = get_model_manager()
    return _model_manager

def _get_model_for_task(task_type: str = "default") -> Optional[str]:
    """获取指定任务类型的模型（支持降级策略）。"""
    try:
        manager = _get_model_manager()
        model = manager.get_model(task_type)
        if model:
            return model
    except Exception as e:
        _ai_logger.warning("model_manager_get_failed", extra={"fields": {"error": str(e), "task_type": task_type}})
    # 模型管理模块失败时，回退到原有的_resolve_model函数
    return _resolve_model()

def _record_model_call(model_name: str, success: bool, latency_ms: float, error_reason: str = "") -> None:
    """记录模型调用结果（用于性能监控）。"""
    try:
        manager = _get_model_manager()
        manager.record_call(model_name, success, latency_ms, error_reason)
    except Exception as e:
        _ai_logger.warning("model_manager_record_failed", extra={"fields": {"error": str(e)}})

SYSTEM_PROMPT = """你是「去见山海」的资深旅行规划师，也是用户最真诚的旅行伙伴。
你相信「每一次出发，都是把世界变成自己的地图」，善于用温暖而有力量的语言鼓励人们走出去、去看世界。
你的回答必须严格遵循用户给定的 JSON 结构，不输出任何多余文字、不输出 markdown。
文案要有温度与出发感：overview 是一句能点燃出发勇气的总览；theme 简洁有画面感；tip 实用贴心。"""


def _resolve_model() -> Optional[str]:
    """解析实际要用的模型名：
    优先用配置的 OLLAMA_MODEL；未拉取时自动降级到任一已存在模型。"""
    try:
        r = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=3)
        if r.status_code != 200:
            return None
        models = [m.get("name", "") for m in r.json().get("models", [])]
    except Exception:
        return None
    if not models:
        return None
    if settings.ollama_model in models:
        return settings.ollama_model
    # 优先 qwen 系列轻量模型
    for pref in ("qwen2.5", "qwen2", "qwen", "llama", "gemma"):
        for m in models:
            if m.startswith(pref):
                return m
    return models[0]


def ai_available() -> bool:
    """检测AI服务是否可用（支持本地Ollama和线上OpenAI兼容API）"""
    provider = settings.ai.ai_provider
    if provider == "openai":
        # 线上模型：只要配置了API Key就认为可用
        return bool(settings.ai.openai_api_key)
    else:
        # 本地Ollama：检测服务是否启动
        return _resolve_model() is not None


CHAT_SYSTEM_PROMPT = """你是「去见山海」的旅行伙伴，一名温暖真诚、博学多识的旅行向导。
你的使命是鼓励人们走出去、去看世界，把每一次出发变成自己的地图。
你不仅懂旅行规划，更懂各地的历史文化、风土人情，善于用有温度、有文化底蕴的语言与用户交流。

【回复原则】
1. **只回应用户的【当前消息】**，不要罗列或复述历史对话中提到的所有地点
2. 如果用户只是提到一个地名但没有明确动作，友好地询问用户想做什么（规划行程/查天气/找景点），可以顺便简单介绍一下这个地方的人文特色
3. 回答简洁实用，语气温暖有力量，可以适当给建议
4. 不要输出 JSON 结构；除非用户明确要求生成/调整行程，否则不要主动规划完整行程
5. 不要把历史对话中提到的所有地点都列出来，只关注当前消息的内容

【历史名人/革命先辈特别回复规则】（重要！）
当用户提到历史名人、革命先辈、文人墨客时（如李白、杜甫、苏轼、鲁迅、毛泽东、周恩来、诸葛亮、孔子等）：
1. 自然地介绍人物的简要生平（1-2句）
2. 关联相关的地名（出生地、主要活动地、纪念地）
3. 推荐相关的出行介绍和旅行主题
4. 激发用户的出行兴趣，鼓励用户去实地感受历史文化
5. 可以引用人物的名言或诗句，增加文化底蕴
6. 回复要有温度、有画面感，让用户感受到"读万卷书，行万里路"的意义

【人文介绍能力】（重要！让对话更有温度、更有文化底蕴）
1. 当用户提到某个地点/景点时，可以自然地融入1-2句人文介绍：
   - 历史背景：如"济南是泉城，有着2600多年的建城史"
   - 文化特色：如"杭州的西湖不仅是风景，更是文人墨客的诗意栖居地"
   - 风土人情：如"北京的胡同里藏着最地道的老北京生活"
   - 诗词典故：如"姑苏城外寒山寺，夜半钟声到客船"
2. 人文介绍要自然融入，不要生硬堆砌，点到为止即可
3. 用有画面感、有温度的语言，让用户感受到旅行的意义不仅是打卡，更是与历史文化的对话
4. 可以适当引用诗词、典故、历史小故事，但要准确，不要编造
5. 回复风格可以多样化：有时诗意、有时实用、有时温暖，不要总是固定格式

【回复示例】
用户：李白
回复：李白啊，那可是"诗仙"！他的一生就是一场浪漫的旅行——"仗剑去国，辞亲远游"。
你知道吗？他的故乡在四川江油，而他写下"朝辞白帝彩云间"的白帝城在重庆奉节，"故人西辞黄鹤楼"的黄鹤楼在武汉，《梦游天姥吟留别》的天姥山在浙江新昌。
沿着诗仙的足迹走一遍，是不是很浪漫？要不要我帮你规划一条"诗仙之旅"？

用户：毛泽东
回复：毛主席啊，他的一生就是一部伟大的革命史诗！从湖南韶山的乡村少年，到井冈山的"星星之火"，再到延安的"革命圣地"，最后到北京的"开国大典"。
你可以去韶山看看伟人的故乡，去井冈山重走红军路，去延安感受延安精神，去北京瞻仰毛主席纪念堂。
这是一条"红色之旅"，感受革命先辈的奋斗历程，珍惜今天的幸福生活。要不要我帮你规划一条红色旅行路线？

用户：济南
回复：济南啊，那可是"家家泉水，户户垂杨"的泉城！有着2600多年的建城史，李清照、辛弃疾都从这里走出。你是想规划济南的行程，还是想了解济南的景点、天气？我可以帮你～"""


async def chat_reply(messages: List[str]) -> Optional[str]:
    """普通对话回复（非规划意图走这里，不生成行程结构）。失败返回 None。

    【历史消息处理】
    - 只传最近2条消息（1条历史+1条当前），避免过长历史干扰
    - 明确标记【历史消息】和【当前消息】
    - 提示词强调只回应当前消息，不要罗列历史地点

    【RAG集成】
    - 当用户消息中提到已知景点时，先RAG检索相关知识
    - 将检索结果作为上下文传给LLM，让回复更精准、有真实知识支撑
    """
    model = _get_model_for_task("chat")
    if not model:
        return None
    all_msgs = [m.strip() for m in messages if m and m.strip()]
    if not all_msgs:
        return None

    # 记录调用开始时间
    call_start = time.time()

    # 只保留最近2条消息（1条历史+1条当前）
    recent_msgs = all_msgs[-2:]
    latest_msg = recent_msgs[-1]

    # RAG检索：检查用户消息中是否提到已知景点
    rag_context = ""
    try:
        from ..services.rag import get_retriever
        retriever = get_retriever()
        if retriever.available:
            # 从POI_ALIASES中获取所有已知景点名称
            from ..services.rag.retriever import POI_ALIASES
            known_pois = list(set(POI_ALIASES.values())) | set(POI_ALIASES.keys())

            # 检查用户消息中是否包含已知景点
            matched_poi = None
            for poi in known_pois:
                if len(poi) >= 2 and poi in latest_msg:
                    matched_poi = poi
                    break

            if matched_poi:
                # RAG检索该景点的知识
                results = retriever.search_by_poi(matched_poi, n_results=5)
                if results:
                    # 提取检索结果的文本内容
                    knowledge_texts = []
                    for doc in results[:3]:  # 只取前3条，避免上下文过长
                        text = doc.get("document", "") or doc.get("text", "")
                        if text:
                            knowledge_texts.append(text[:300])  # 每条限制300字
                    if knowledge_texts:
                        rag_context = "\n\n【RAG检索到的景点知识】\n" + "\n---\n".join(knowledge_texts)
                        _ai_logger.info("chat_reply_rag_retrieved", extra={"fields": {
                            "poi": matched_poi,
                            "results_count": len(results),
                        }})
    except Exception as e:
        _ai_logger.warning("chat_reply_rag_failed", extra={"fields": {"error": str(e)}})

    # 历史名人/革命先辈检测：当用户提到历史名人时，自动关联相关地名和出行推荐
    figure_recommendations = []
    matched_figures = []
    try:
        from ..data.repositories.historical_figure_repository import HistoricalFigureRepository
        # 从数据库获取所有历史名人，检测文本中提到的人物
        all_figures, _ = HistoricalFigureRepository.list_figures(page_size=100)
        for figure in all_figures:
            name = figure.get("name", "")
            aliases = figure.get("aliases", [])
            if name in latest_msg or any(alias in latest_msg for alias in aliases):
                # 获取完整的人物信息（含相关地点）
                full_figure = HistoricalFigureRepository.get_figure(figure["id"])
                if full_figure:
                    matched_figures.append(full_figure)
        if matched_figures:
            for figure in matched_figures[:2]:  # 最多处理2个人物
                # 生成出行推荐
                places = figure.get("related_places", [])
                if places:
                    lines = []
                    lines.append(f"📖 {figure['name']}（{figure['category']}）")
                    lines.append(f"   {figure.get('brief_intro', '')}")
                    lines.append(f"")
                    lines.append(f"🗺️ 相关旅行地推荐：")
                    for place in places[:4]:
                        lines.append(f"")
                        lines.append(f"  📍 {place.get('place_name', '')}（{place.get('relation', '')}）")
                        lines.append(f"     {place.get('travel_recommendation', '')}")
                        if place.get("attractions"):
                            attractions = "、".join(place["attractions"][:3])
                            lines.append(f"     🏛️ 必去景点：{attractions}")
                    lines.append(f"")
                    lines.append(f"🎯 旅行主题：{figure.get('travel_theme', '')}")
                    rec = "\n".join(lines)
                    if rec:
                        figure_recommendations.append(rec)
            if figure_recommendations:
                _ai_logger.info("chat_reply_historical_figure_detected", extra={"fields": {
                    "figures": [f["name"] for f in matched_figures],
                    "count": len(matched_figures),
                }})
    except Exception as e:
        _ai_logger.warning("chat_reply_figure_detection_failed", extra={"fields": {"error": str(e)}})

    # 构建历史名人上下文（传给LLM参考）
    figure_context = ""
    if figure_recommendations:
        figure_context = "\n\n【历史名人相关旅行地推荐】\n" + "\n\n".join(figure_recommendations)

    chat_messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]
    for i, msg in enumerate(recent_msgs[:-1]):
        chat_messages.append({"role": "user", "content": f"【历史消息】{msg}"})

    # 当前消息 + RAG检索结果 + 历史名人推荐
    current_content = f"【当前消息】{latest_msg}"
    if rag_context:
        current_content += rag_context + "\n\n请基于以上景点知识回答用户的问题，知识可以自然融入回复中，但不要直接照搬。"
    if figure_context:
        current_content += figure_context + "\n\n用户提到了历史名人/革命先辈，请在回复中自然融入相关的地名和出行推荐，激发用户的出行兴趣。可以推荐相关的旅行主题和路线。"
    chat_messages.append({"role": "user", "content": current_content})

    try:
        # 【回复多样性优化】随机调整temperature（0.6-0.9），让回复更有变化
        # 避免每次回复都是固定的风格和格式
        import random
        temperature = random.uniform(0.6, 0.9)

        # 使用统一的chat_completion函数，支持本地Ollama和线上OpenAI兼容API
        content = await chat_completion(
            messages=chat_messages,
            temperature=temperature,
            max_tokens=2048,
            model=model,
        ) or ""
    except Exception:
        content = ""

    result = (content or "").strip()

    # 【回复长度控制】限制回复长度在100-500字之间
    # 过短的回复可能不够丰富，过长的回复可能让用户失去耐心
    if result:
        if len(result) < 50:
            # 回复过短，补充一些品牌气质的内容
            result += "\n\n世界很大，而我们正从一次出发开始。想去哪儿？告诉我，我帮你把它变成现实。"
        elif len(result) > 800:
            # 回复过长，截断到800字
            result = result[:800] + "..."

    # 【品牌气质强化】确保回复中包含品牌气质关键词
    # 品牌气质：鼓励人们走出去、去看世界、激发行走天下的勇气
    brand_keywords = ["出发", "探索", "行走", "远方", "世界", "山海", "足迹", "旅程"]
    if result and not any(kw in result for kw in brand_keywords):
        # 随机选择一个品牌气质关键词，自然融入回复末尾
        brand_phrases = [
            "\n\n每一次出发，都是与世界的一次对话。",
            "\n\n世界在等你，而你的足迹，就是最好的答案。",
            "\n\n去见山海吧，远方的风景，值得你迈出这一步。",
            "\n\n旅行的意义，不在于到达，而在于行走的过程。",
        ]
        result += random.choice(brand_phrases)

    # 确保历史名人推荐内容一定会出现在回复中
    if figure_recommendations and result:
        # 检查LLM回复是否已经包含了推荐内容的关键地名
        has_recommendation = any(
            any(place["name"] in result for place in fig.get("related_places", []))
            for fig in matched_figures
        )
        if not has_recommendation:
            # 如果LLM回复没有包含推荐地名，在末尾加上精简版推荐
            short_recommendations = []
            for fig in matched_figures[:1]:  # 只加第一个人物的精简推荐
                places = fig.get("related_places", [])[:3]
                if places:
                    place_names = "、".join([p["name"] for p in places])
                    short_recommendations.append(
                        f"\n\n🗺️ {fig['name']}相关旅行地推荐：{place_names}等。"
                        f"要不要我帮你规划一条「{fig.get('travel_theme', '文化之旅')}」？"
                    )
            if short_recommendations:
                result += "\n".join(short_recommendations)

    # 记录模型调用结果（性能监控）
    latency_ms = (time.time() - call_start) * 1000
    _record_model_call(model, bool(result), latency_ms)

    return result or None


async def chat_completion(
    messages: List[Dict[str, str]],
    temperature: float = 0.7,
    max_tokens: int = 2048,
    model: Optional[str] = None,
) -> Optional[str]:
    """底层LLM对话补全接口（供RAG生成器等内部模块使用）。

    支持本地Ollama和线上OpenAI兼容API两种模式，通过AI_PROVIDER配置切换。

    与 chat_reply 的区别：
    - chat_reply 是高层对话接口，包含历史消息处理、RAG集成、品牌气质强化等业务逻辑
    - chat_completion 是底层接口，直接调用LLM API，不包含业务逻辑

    Args:
        messages: 消息列表，格式为 [{"role": "system"/"user"/"assistant", "content": "..."}]
        temperature: 生成温度（0-1），越低越确定，越高越随机
        max_tokens: 最大生成token数
        model: 模型名称，为空时自动选择

    Returns:
        生成的文本内容，失败时返回 None
    """
    # 选择模型提供方
    provider = settings.ai.ai_provider
    
    # 选择模型
    if not model:
        if provider == "openai":
            model = settings.ai.openai_model
        else:
            model = _get_model_for_task("default")
    if not model:
        return None

    # 记录调用开始时间
    call_start = time.time()

    try:
        if provider == "openai":
            # 线上OpenAI兼容API（DeepSeek、通义千问、智谱AI等）
            api_key = settings.ai.openai_api_key
            base_url = settings.ai.openai_base_url
            
            if not api_key:
                _ai_logger.warning("openai_api_key_not_configured", extra={"fields": {
                    "base_url": base_url,
                    "model": model,
                }})
                return None
            
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            async with httpx.AsyncClient(timeout=120) as client:
                r = await client.post(f"{base_url}/chat/completions", json=payload, headers=headers)
                r.raise_for_status()
                content = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
        else:
            # 本地Ollama
            payload = {
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            }
            async with httpx.AsyncClient(timeout=120) as client:
                r = await client.post(f"{settings.ollama_base_url}/api/chat", json=payload)
                r.raise_for_status()
                content = r.json().get("message", {}).get("content", "")
    except Exception as e:
        _ai_logger.warning("chat_completion_failed", extra={"fields": {
            "error": str(e),
            "provider": provider,
            "model": model,
            "messages_count": len(messages),
        }})
        content = ""

    result = (content or "").strip()

    # 记录模型调用结果（性能监控）
    latency_ms = (time.time() - call_start) * 1000
    _record_model_call(model, bool(result), latency_ms)

    return result or None


def resolve_model() -> str:
    """返回当前实际使用的模型名（供展示），不可用时返回空字符串"""
    provider = settings.ai.ai_provider
    if provider == "openai":
        return settings.ai.openai_model if settings.ai.openai_api_key else ""
    return _resolve_model() or ""




TOOL_REPLY_SYSTEM_PROMPT = """你是「去见山海」的旅行伙伴，一名温暖真诚、博学多识的旅行向导。
你的使命是鼓励人们走出去、去看世界，把每一次出发变成自己的地图。
你不仅懂旅行规划，更懂各地的历史文化、风土人情。

根据下方工具返回的结果，用简洁、温暖、有出发感、有文化底蕴的语言组织回复。
不要输出 JSON，不要 markdown 代码块，直接输出自然语言。
如果工具结果为空或查询失败，友好地告知用户并给出建议，不要编造数据。

【人文介绍能力】（重要！让回复更有温度、更有文化底蕴）
1. 在介绍景点/地点时，可以自然地融入1-2句人文介绍：
   - 历史背景：如"故宫是明清两代的皇家宫殿，有着600多年的历史"
   - 文化特色：如"西湖不仅是风景，更是文人墨客的诗意栖居地"
   - 诗词典故：如"姑苏城外寒山寺，夜半钟声到客船"
2. 人文介绍要自然融入，不要生硬堆砌，点到为止即可
3. 用有画面感、有温度的语言，让用户感受到旅行的意义不仅是打卡，更是与历史文化的对话
4. 可以适当引用诗词、典故、历史小故事，但要准确，不要编造
5. 回复风格多样化：有时诗意、有时实用、有时温暖，不要总是固定格式

【回复结构建议】
1. 开头：一句温暖的总结或人文介绍
2. 中间：列出关键信息（景点/天气/美食等），每个可以带一句简短的人文点评
3. 结尾：一句鼓励出发的话，或询问用户是否需要进一步规划"""


async def reply_with_tool_result(messages: List[str], tool_name: str, tool_result: dict) -> Optional[str]:
    """基于工具执行结果，让 LLM 组织成自然语言回复。失败返回 None。

    tool_name: weather / poi（plan 意图直接返回结构化行程，不走此函数）
    tool_result: 工具返回的数据 dict
    """
    model = _get_model_for_task("chat")
    if not model:
        return None
    history = [{"role": "user", "content": m.strip()} for m in messages if m and m.strip()]
    tool_block = f"【工具 {tool_name} 返回结果】\n{json.dumps(tool_result, ensure_ascii=False, indent=2)}"

    # 记录调用开始时间（用于性能监控）
    call_start = time.time()

    try:
        messages = [
            {"role": "system", "content": TOOL_REPLY_SYSTEM_PROMPT},
            *history,
            {"role": "user", "content": tool_block},
        ]
        # 使用统一的chat_completion函数，支持本地Ollama和线上OpenAI兼容API
        content = await chat_completion(
            messages=messages,
            temperature=0.5,
            max_tokens=2048,
            model=model,
        ) or ""
    except Exception:
        # 记录模型调用结果（性能监控）
        latency_ms = (time.time() - call_start) * 1000
        _record_model_call(model, False, latency_ms, "exception")
        return None

    result = (content or "").strip()

    # 记录模型调用结果（性能监控）
    latency_ms = (time.time() - call_start) * 1000
    _record_model_call(model, bool(result), latency_ms)

    return result or None


PLAN_REPLY_SYSTEM_PROMPT = """你是「去见山海」的旅行伙伴，一名温暖真诚、博学多识的旅行向导。
你的使命是鼓励人们走出去、去看世界，把每一次出发变成自己的地图。
你不仅懂旅行规划，更懂各地的历史文化、风土人情。

根据下方的行程规划结果，用简洁、温暖、有出发感、有文化底蕴的语言组织回复。
不要输出 JSON，不要 markdown 代码块，直接输出自然语言。

【人文介绍能力】（重要！让回复更有温度、更有文化底蕴）
1. 在开头加入1-2句目的地的人文介绍：
   - 历史背景：如"济南是泉城，有着2600多年的建城史"
   - 文化特色：如"杭州的西湖不仅是风景，更是文人墨客的诗意栖居地"
   - 诗词典故：如"姑苏城外寒山寺，夜半钟声到客船"
   - 小众地点：如果不知道具体人文，可以用更通用的温暖语言，如"每一个小众目的地，都藏着不为人知的惊喜"
2. 人文介绍要自然融入，不要生硬堆砌，点到为止即可
3. 用有画面感、有温度的语言，让用户感受到旅行的意义不仅是打卡，更是与历史文化的对话
4. 可以适当引用诗词、典故、历史小故事，但要准确，不要编造
5. 对于小众地点，不要强行编造人文信息，可以用温暖的出发感言代替

【回复结构】（必须包含以下信息，但表达方式可以多样化）
1. 开头：一句温暖的人文介绍或出发感言（1-2句）
2. 中间：简要说明行程的基本信息（X天行程、X个点位、预算约¥X、XX风格、XX节奏）
3. 结尾：一句鼓励出发的话，或告知用户可以查看详细行程和地图

【重要约束】
1. 回复要简洁，控制在100-150字以内，不要太长
2. 必须包含行程的基本信息（天数、点位数量、预算）
3. 语气要温暖、有力量、有文化底蕴
4. 不要总是用固定格式，每次回复可以有不同的表达方式
5. 不要罗列所有景点，只说总体情况
6. 不要输出JSON或markdown"""


async def generate_plan_reply(plan: dict, user_messages: List[str]) -> Optional[str]:
    """基于行程规划结果，让 LLM 生成有人文介绍的回复。失败返回 None。

    plan: 行程规划结果 dict
    user_messages: 用户历史消息

    【RAG集成】
    - RAG检索目的地的人文知识（历史背景、文化特色、诗词典故等）
    - 将检索结果作为上下文传给LLM，让人文介绍更准确、有真实知识支撑
    """
    model = _get_model_for_task("plan")
    if not model:
        return None
    destination = plan.get("destination", "")
    plan_summary = {
        "destination": destination,
        "days": plan.get("days", 0),
        "poi_count": len(plan.get("all_pois", [])),
        "total_budget": plan.get("total_budget", 0),
        "group_type": plan.get("group_type", ""),
        "budget_level": plan.get("budget_level", ""),
        "style": plan.get("style", ""),
        "pace": plan.get("pace", ""),
        "source": plan.get("source", ""),
    }

    # 记录调用开始时间（用于性能监控）
    call_start = time.time()

    # RAG检索：目的地的人文知识
    rag_context = ""
    try:
        from ..services.rag import get_retriever
        retriever = get_retriever()
        if retriever.available and destination:
            # 用语义检索查找目的地相关的人文知识
            query = f"{destination} 历史文化 人文介绍 旅游特色"
            results = retriever.search_by_query(query, n_results=5)
            if results:
                knowledge_texts = []
                for doc in results[:3]:  # 只取前3条
                    text = doc.get("document", "") or doc.get("text", "")
                    if text:
                        knowledge_texts.append(text[:300])
                if knowledge_texts:
                    rag_context = "\n\n【RAG检索到的目的地人文知识】\n" + "\n---\n".join(knowledge_texts)
                    _ai_logger.info("generate_plan_reply_rag_retrieved", extra={"fields": {
                        "destination": destination,
                        "results_count": len(results),
                    }})
    except Exception as e:
        _ai_logger.warning("generate_plan_reply_rag_failed", extra={"fields": {"error": str(e)}})

    plan_block = f"【行程规划结果】\n{json.dumps(plan_summary, ensure_ascii=False, indent=2)}"
    if rag_context:
        plan_block += rag_context + "\n\n请基于以上目的地人文知识生成回复，人文介绍可以自然融入，但不要直接照搬。"
    history = [{"role": "user", "content": m.strip()} for m in user_messages[-2:] if m and m.strip()]
    start_time = time.time()
    try:
        messages = [
            {"role": "system", "content": PLAN_REPLY_SYSTEM_PROMPT},
            *history,
            {"role": "user", "content": plan_block},
        ]
        # 使用统一的chat_completion函数，支持本地Ollama和线上OpenAI兼容API
        content = await chat_completion(
            messages=messages,
            temperature=0.7,
            max_tokens=2048,
            model=model,
        ) or ""
    except Exception as e:
        duration_ms = round((time.time() - start_time) * 1000, 2)
        _ai_logger.warning("generate_plan_reply_failed", extra={"fields": {
            "model": model,
            "destination": destination,
            "error": str(e),
            "duration_ms": duration_ms,
        }})

        # 记录模型调用结果（性能监控）
        latency_ms = (time.time() - call_start) * 1000
        _record_model_call(model, False, latency_ms, str(e))

        return None
    result = (content or "").strip()
    duration_ms = round((time.time() - start_time) * 1000, 2)
    if result:
        _ai_logger.info("generate_plan_reply_ok", extra={"fields": {
            "model": model,
            "destination": destination,
            "duration_ms": duration_ms,
            "reply_length": len(result),
            "rag_used": bool(rag_context),
        }})

    # 记录模型调用结果（性能监控）
    latency_ms = (time.time() - call_start) * 1000
    _record_model_call(model, bool(result), latency_ms)

    return result or None


async def generate_itinerary(req: dict, pois: List[dict]) -> Optional[dict]:
    """调用本地模型生成结构化行程 JSON。

    返回结构：
    {
      "overview": str,
      "days": [
        {"day": 1, "theme": str, "tip": str,
         "items": [{"poi_name": str, "category": str, "slot": str, "duration_min": int, "note": str}]}
      ]
    }
    失败返回 None。
    """
    model = _get_model_for_task("plan")
    if not model:
        return None
    user_prompt = _build_prompt(req, pois)

    # 记录调用开始时间（用于性能监控）
    call_start = time.time()

    try:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT + "\n\n【重要】必须返回合法的JSON格式，不要输出任何其他内容。"},
            {"role": "user", "content": user_prompt},
        ]
        # 使用统一的chat_completion函数，支持本地Ollama和线上OpenAI兼容API
        content = await chat_completion(
            messages=messages,
            temperature=0.7,
            max_tokens=4096,
            model=model,
        ) or ""
    except Exception as e:
        # 记录模型调用结果（性能监控）
        latency_ms = (time.time() - call_start) * 1000
        _record_model_call(model, False, latency_ms, str(e))
        return None

    result = _parse_json(content)

    # 记录模型调用结果（性能监控）
    latency_ms = (time.time() - call_start) * 1000
    _record_model_call(model, bool(result), latency_ms)

    return result


def _build_prompt(req: dict, pois: List[dict]) -> str:
    # 候选池截断（控制 prompt 长度，小模型更能聚焦高分知名点）
    top_pois = pois[:60]
    poi_lines = []
    for p in top_pois:
        star = " ★热门" if p.get("hot") else ""
        region = f" | 区域:{p.get('district', '')}" if p.get("district") else ""
        poi_lines.append(
            f"- id={p['id']} | {p['name']} | 类别:{p['category']} | 参考价:{p['price']}元 "
            f"| 评分:{p['rating']} | 坐标:({p['lng']},{p['lat']}){region}{star}"
        )
    interests = "、".join(req.get("interests") or []) or "不限"
    must = "、".join(req.get("must_include_poi") or []) or "无"
    exclude = "、".join(req.get("exclude_poi") or []) or "无"
    pool_block = chr(10).join(poi_lines) if poi_lines else "（无）"

    return f"""【任务】为以下用户生成一份顺路、可执行的逐日旅行行程。

目的地：{req['destination']}
出行天数：{req['days']}天
出行人群：{req['group_type']}
预算档位：{req['budget_level']}
旅行风格：{req['style']}
节奏偏好：{req['pace']}
交通方式：{req.get('traffic_mode', '混合')}（决定点位可达性与移动耗时）
每日活动时间：{req.get('daily_start_time', '09:00')} - {req.get('daily_end_time', '21:00')}
兴趣标签：{interests}
必去点位：{must}
排除点位：{exclude}（不得安排）

【参考点位】（高德检索到的候选，仅作参考，可不限于此）
{pool_block}

【输出要求】输出严格 JSON，结构如下（不要 markdown 代码块）：
{{
  "overview": "一句话行程总览",
  "days": [
    {{
      "day": 1,
      "theme": "当日主题，如『西湖经典一日』",
      "tip": "当日贴士：预约要求/穿衣/避坑",
      "items": [
        {{"poi_name": "杭州西湖风景名胜区", "category": "景点", "slot": "上午", "duration_min": 150, "note": "游玩建议"}}
      ]
    }}
  ]
}}

【规划规则】
1. 点位必须**优先从【参考点位】中选择**（尤其是带 ★热门 的知名点位），禁止自行编造参考点位之外的名称；只有当某类参考点位确实不足时，才可补充你确信真实存在且广为人知的知名点位（名称写完整）。
2. category ∈ {{景点, 美食, 购物, 夜生活}}；与 poi_name 匹配。
3. 每天安排 3-5 个点位，按地理位置顺路排序，避免来回折返。
4. slot ∈ {{上午, 中午, 下午, 晚上}}，上午 9:00 左右开始。
5. 景点放上午/下午，美食放中午/晚上，晚上优先安排夜景/夜市/购物/酒吧。
6. 每天品类必须均衡：至少安排 1 个景点，美食不超过 2 个，购物/夜生活视情况 0-1 个；不要把一天排成全是餐厅。
7. 亲子、老人节奏放慢（每天 3 个点位左右）；暴走可每天 5 个。
8. 景点 duration_min 120-180，美食 60-90，购物 90-120。
9. day 从 1 开始连续编号，共 {req['days']} 天。
10. **区域分布**：同一天安排的点位尽量集中在同一个区县/区域（顺路）；不同天不要重复使用同一区县，避免来回跨区与地域重复（如第1天用西湖区点位，第2天就别再排西湖区的点）。"""


def _parse_json(content: str) -> Optional[dict]:
    if not content:
        return None
    content = content.strip()
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.MULTILINE)
    # 提取第一个 { 到最后一个 }
    start, end = content.find("{"), content.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(content[start:end + 1])
    except json.JSONDecodeError:
        return None


# ========== 行程优化：POI 智能筛选 + 主题分组 + 智能时长 ==========

OPTIMIZE_SYSTEM_PROMPT = """你是「去见山海」的资深旅行规划专家，从候选景点中筛选最适合用户的景点，分配主题标签和建议游览时长。

【核心任务】
1. 筛选：选出 出行天数×4 个景点（每天约4个主线）
2. 主题分组：为每天景点分配有画面感的主题名（如"皇城根脉""湖光山色"），同主题景点地理接近
3. 智能时长：大型景点150-180分钟，中型90-120分钟，小型60-90分钟（最多180分钟，确保每天3-4个景点）
4. 最佳时段：上午/下午/晚上

【筛选原则】（按优先级）
1. 标志性景点必选：目的地最著名代表性景点必须入选（如北京故宫/长城、济南趵突泉/大明湖、杭州西湖）
2. ★热门标记景点优先
3. 评分4.5以上优先，低于4.0除非特殊原因不选
4. 结合用户偏好（亲子/老人/摄影/美食），但不能替代标志性景点
5. 景点类型均衡，同一天景点地理接近
6. 排除重复/高度相似景点（如"趵突泉"和"天下第一泉"只选一个；主景区和子景点只选主景区）

【输出】严格JSON：
{"selected":[{"name":"故宫","theme":"皇城根脉","duration_min":180,"best_slot":"上午","reason":"北京必去世界遗产"}]}

【字段要求】name与候选列表完全一致，duration_min整数，best_slot取上午/中午/下午/晚上，reason说明选择理由。"""


async def optimize_itinerary(req: dict, attrs: List[dict]) -> Optional[List[dict]]:
    """LLM 智能筛选景点 + 主题分组 + 建议时长。

    输入：用户参数 req + 候选景点列表 attrs
    输出：[{"name","theme","duration_min","best_slot","reason"}, ...]
    失败返回 None（planner 降级到纯规则）。

    LLM 做"决策"（筛选哪些景点、分什么主题、给多少时长），
    规则引擎做"执行"（聚类、排序、预算、辅助点位补充）。
    """
    model = _get_model_for_task("optimize")
    if not model or not attrs:
        return None
    days = int(req.get("days") or 3)
    # 候选池截断（控制prompt长度，聚焦高分知名点）
    top_attrs = attrs[:25]
    poi_lines = []
    for p in top_attrs:
        star = " ★热门" if p.get("hot") else ""
        region = f" | 区域:{p.get('district', '')}" if p.get("district") else ""
        rating = f" | 评分:{p.get('rating', 0)}" if p.get("rating") else ""
        poi_lines.append(f"- {p['name']}{star}{region}{rating}")
    poi_block = "\n".join(poi_lines) if poi_lines else "（无）"

    # 记录调用开始时间（用于性能监控）
    call_start = time.time()

    interests = "、".join(req.get("interests") or []) or "不限"
    user_block = (
        f"目的地：{req.get('destination', '')}\n"
        f"出行天数：{days}天\n"
        f"出行人群：{req.get('group_type', '情侣')}\n"
        f"预算档位：{req.get('budget_level', '适中')}\n"
        f"旅行风格：{req.get('style', '综合')}\n"
        f"节奏偏好：{req.get('pace', '适中')}\n"
        f"交通方式：{req.get('traffic_mode', '公共交通')}\n"
        f"兴趣标签：{interests}\n"
        f"建议选出约 {days * 4} 个景点（每天约4个主线）"
    )

    try:
        messages = [
            {"role": "system", "content": OPTIMIZE_SYSTEM_PROMPT + "\n\n【重要】必须返回合法的JSON格式，不要输出任何其他内容。"},
            {"role": "user", "content": f"【用户需求】\n{user_block}\n\n【候选景点】\n{poi_block}"},
        ]
        # 使用统一的chat_completion函数，支持本地Ollama和线上OpenAI兼容API
        content = await chat_completion(
            messages=messages,
            temperature=0.3,
            max_tokens=4096,
            model=model,
        ) or ""
    except Exception as e:
        _ai_logger.warning("optimize_itinerary_failed", extra={"fields": {
            "model": model, "destination": req.get("destination"), "error": str(e),
        }})

        # 记录模型调用结果（性能监控）
        latency_ms = (time.time() - call_start) * 1000
        _record_model_call(model, False, latency_ms, str(e))

        return None

    result = _parse_json(content)
    if not result or not isinstance(result.get("selected"), list):
        _ai_logger.warning("optimize_itinerary_parse_failed", extra={"fields": {
            "model": model, "raw": content[:200],
        }})

        # 记录模型调用结果（性能监控）
        latency_ms = (time.time() - call_start) * 1000
        _record_model_call(model, False, latency_ms, "parse_failed")

        return None

    selected = result["selected"]
    # 校验：name 必须在候选景点中，duration_min 必须是正整数
    valid_names = {p["name"] for p in attrs}
    cleaned = []
    for item in selected:
        name = (item.get("name") or "").strip()
        if not name or name not in valid_names:
            continue
        try:
            # 【关键修复】限制景点时长上限为180分钟（3小时），确保每天能安排3-4个景点
            # 大型景点如故宫/长城最多3小时，避免因时长过长导致每天只有1个景点
            duration = max(30, min(180, int(item.get("duration_min") or 120)))
        except (TypeError, ValueError):
            duration = 120
        slot = item.get("best_slot") or "上午"
        if slot not in ("上午", "中午", "下午", "晚上"):
            slot = "上午"
        theme = (item.get("theme") or "精彩一日").strip()
        cleaned.append({
            "name": name, "theme": theme,
            "duration_min": duration, "best_slot": slot,
            "reason": item.get("reason", ""),
        })

    if not cleaned:
        # 记录模型调用结果（性能监控）
        latency_ms = (time.time() - call_start) * 1000
        _record_model_call(model, False, latency_ms, "no_valid_selected")
        return None

    _ai_logger.info("optimize_itinerary_ok", extra={"fields": {
        "model": model, "destination": req.get("destination"),
        "days": days, "selected_count": len(cleaned),
        "themes": list({c["theme"] for c in cleaned}),
    }})

    # 记录模型调用结果（性能监控）
    latency_ms = (time.time() - call_start) * 1000
    _record_model_call(model, True, latency_ms)

    return cleaned
