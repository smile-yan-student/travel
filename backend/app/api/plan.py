"""
行程规划路由模块。

提供行程规划相关的接口：
- /api/plan - 一键规划行程
- /api/chat/plan - 对话式规划行程
- /api/route - 路线计算

包含 LLM 意图分析 + 工具调用路由（_llm_chat_plan），
以及天气类咨询降级（_try_weather_reply）。

功能特性：
- 一键规划行程（AI生成 + 规则引擎兜底）
- 对话式规划行程（LLM意图分析 + 工具调用路由）
- 路线计算（两点间交通方案）
- 天气类咨询降级（当用户询问天气时，直接返回天气信息）
- 意图识别Skill集成（Intent Recognition Skill）
- 登录鉴权（所有规划接口需要登录）

使用方式：
    from app.api.plan import router

    # 在FastAPI应用中注册路由
    app.include_router(router)

    # POST /api/plan 一键规划行程
    # POST /api/chat/plan 对话式规划行程
    # POST /api/route 路线计算
"""
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException

from app.skills.intent_recognition import DEFAULT_PARAMS, clean_place, extract_city
from app.skills.intent_recognition.legacy_parser import parse_intent

from ..ai import ai as ai_mod
from ..skills.itinerary_planner import build_plan
from ..data.models.models import (
    ChatPlanRequest,
    ChatPlanResponse,
    PlanRequest,
    PlanResponse,
    RouteRequest,
)
from ..data.repositories import admin_repository
from ..infrastructure import logger as log_mod
from ..services import map as amap
from ..services.usage_limit import get_usage_limit_service
from .deps import bearer_user

router = APIRouter(prefix="/api", tags=["plan"])
_logger = log_mod.get_logger("plan_api")


def _require_user(authorization: Optional[str]) -> dict:
    user = bearer_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="未登录或登录已失效")
    return user


@router.post("/plan", response_model=PlanResponse)
async def plan(req: PlanRequest, authorization: Optional[str] = Header(None)):
    """核心接口：AI 一键生成旅行行程（需登录）"""
    user = _require_user(authorization)
    user_id = str(user.get("id", "unknown"))
    
    # 检查每日规划次数限制
    usage_service = get_usage_limit_service()
    can_plan, plan_remaining = usage_service.check_plan_limit(user_id)
    if not can_plan:
        raise HTTPException(
            status_code=429,
            detail=usage_service.get_plan_limit_message(user_id)
        )
    
    result = await build_plan(req)
    
    # 记录规划调用
    usage_service.increment_plan_count(user_id)
    
    return result


# ---------------- LLM 意图分析 + 工具调用 ----------------

async def _llm_chat_plan(user_msgs: List[str]) -> Optional[ChatPlanResponse]:
    """LLM 意图分析 + 工具调用路由（主路径）。成功返回响应，失败返回 None（降级规则）。

    使用意图识别Skill（Intent Recognition Skill）进行意图识别。
    Skill内部优先使用LLM识别，失败时自动降级到规则兜底。
    """
    # 使用意图识别Skill进行意图识别
    try:
        from app.skills.intent_recognition import get_intent_recognizer
        intent_recognizer = get_intent_recognizer()
        intent_result = await intent_recognizer.recognize(user_msgs)

        # 将IntentResult转换为字典格式，保持与原有代码的兼容性
        analysis = intent_result.to_dict()
        _logger.info(f"意图识别Skill结果: intent={analysis.get('intent')}, confidence={analysis.get('confidence')}, source={intent_result.source}")
    except Exception as e:
        _logger.error(f"意图识别Skill调用失败: {e}")
        return None

    if not analysis:
        return None
    intent = analysis.get("intent", "chat")
    args = analysis.get("args", {}) or {}
    ai_reply = (analysis.get("reply") or "").strip()

    # intent 容错：不在预期列表中的一律按chat处理（安全默认）
    if intent not in ("weather", "plan", "poi", "chat"):
        intent = "chat"

    # ---- chat：普通对话 / 寒暄 ----
    if intent == "chat":
        # 【优化】简单寒暄直接用意图识别的reply，跳过chat_reply的LLM调用，减少token消耗
        SIMPLE_GREETINGS = {"你好", "您好", "哈喽", "hello", "hi", "嗨", "在吗", "在不在",
                           "谢谢", "感谢", "多谢", "辛苦了", "再见", "拜拜", "好的", "嗯", "哦",
                           "ok", "知道了", "明白了", "好", "行", "可以"}
        latest_msg = user_msgs[-1].strip().lower() if user_msgs else ""
        is_simple_greeting = latest_msg in SIMPLE_GREETINGS or len(latest_msg) <= 4

        if is_simple_greeting and ai_reply:
            # 简单寒暄且意图识别已返回reply，直接使用，不调用LLM
            reply = ai_reply
        else:
            # 复杂对话调用chat_reply，确保历史名人检测、RAG检索等功能生效
            reply = await ai_mod.chat_reply(user_msgs)
            if not reply:
                reply = ai_reply or "我在呢～无论是景点、美食还是天气，都乐意陪你聊。要是想把某个地方变成一场真正的行程，直接告诉我「去X玩几天」就行。"
        return ChatPlanResponse(ready=False, reply=reply, params=DEFAULT_PARAMS)

    # ---- weather：实时天气查询 ----
    if intent == "weather":
        city = (args.get("city") or "").strip()
        if not city:
            return ChatPlanResponse(ready=False,
                reply="想帮你查实时天气，先告诉我城市名吧，比如「济南的天气怎么样」🌤",
                params=DEFAULT_PARAMS)
        data = await amap.weather(city)
        if data and data.get("weather"):
            reply = await ai_mod.reply_with_tool_result(user_msgs, "weather", data)
            if not reply:
                reply = (f"📍 {data.get('city', city)} 实时天气\n"
                         f"· 天气：{data['weather']}\n· 气温：{data['temperature']}\n"
                         f"· 风力：{data['wind']}\n· 温馨提示：{data['tips']}")
        else:
            reply = f"{city} 的实时天气暂时没查到，出发前记得关注当地天气预报哦～"
        return ChatPlanResponse(ready=False, reply=reply, params=DEFAULT_PARAMS)

    # ---- poi：景点/美食/购物/夜生活搜索 ----
    if intent == "poi":
        city = (args.get("city") or "").strip()
        category = args.get("category") or "景点"
        keyword = (args.get("keyword") or "").strip()
        if not city:
            return ChatPlanResponse(ready=False,
                reply="想帮你搜好去处，先告诉我城市名吧～比如「杭州有什么好玩的」",
                params=DEFAULT_PARAMS)
        center = await amap.geocode(city)
        pois = await amap.search_pois(city, center, [category])
        if pois:
            poi_summary = [{"name": p.get("name"), "category": p.get("category"),
                            "address": p.get("address", ""), "rating": p.get("rating", 0)} for p in pois[:10]]
            result = {"city": city, "category": category, "keyword": keyword,
                      "count": len(pois), "pois": poi_summary}
            reply = await ai_mod.reply_with_tool_result(user_msgs, "poi", result)
            if not reply:
                names = "、".join(p["name"] for p in poi_summary[:6])
                reply = f"为你找到{city}{category}推荐：{names}等{len(pois)}个好去处，要不要我帮你把它们排进行程？"
        else:
            reply = f"{city}的{category}暂时没搜到合适的，换个关键词试试？"
        return ChatPlanResponse(ready=False, reply=reply, params=DEFAULT_PARAMS)

    # ---- plan：生成/调整行程 ----
    if intent == "plan":
        # 【关键修复】先不合并DEFAULT_PARAMS，让dialogue_manager检测天数是否缺失
        # 只有LLM明确识别出的参数才传入，天数缺失时触发多轮追问
        raw_params = dict(args)
        # 记录LLM识别的参数，便于排查
        _logger.info(f"plan_LLM原始参数: 天数={raw_params.get('days')}, 人数={raw_params.get('travelers')}, 目的地={raw_params.get('destination')}")

        # 【多轮对话管理】检查参数是否完整，不完整则主动追问
        # 【关键修复】在参数校验之前先进行多轮对话管理，确保天数等关键参数被补全
        try:
            from ..services.session.dialogue_manager import get_dialogue_manager
            dialogue_manager = get_dialogue_manager()

            # 生成稳定的会话ID（基于用户消息的前20个字符的哈希，确保同一对话的会话ID稳定）
            # 使用第一条用户消息作为会话标识，避免每次消息都生成新的会话ID
            first_msg = user_msgs[0] if user_msgs else ""
            session_id = f"plan_{hash(first_msg[:50]) % 100000}"

            # 处理用户消息，维护对话状态
            # 只传入LLM明确识别出的参数，让dialogue_manager检测缺失的关键参数（如天数）
            dialogue_result = dialogue_manager.process_message(
                session_id=session_id,
                user_message=user_msgs[-1] if user_msgs else "",
                extracted_params={
                    "destination": raw_params.get("destination", ""),
                    "days": raw_params.get("days"),
                    "travelers": raw_params.get("travelers"),
                    "budget_level": raw_params.get("budget_level"),
                    "style": raw_params.get("style"),
                    "pace": raw_params.get("pace"),
                    "traffic_mode": raw_params.get("traffic_mode"),
                },
                intent="plan",
            )

            # 如果需要追问，返回追问消息
            if dialogue_result.need_clarification:
                _logger.info(f"多轮对话追问: 参数={dialogue_result.clarification_param}, 已收集={dialogue_result.state.collected_params if dialogue_result.state else []}")
                # 返回追问消息时，合并DEFAULT_PARAMS以确保前端能正常显示
                clarification_params = {**DEFAULT_PARAMS, **dialogue_result.params}
                return ChatPlanResponse(
                    ready=False,
                    reply=dialogue_result.clarification_message,
                    params=clarification_params,
                )

            # 多轮对话完成，使用对话管理器收集的参数（可能包含多轮补充的参数）
            # 【关键修复】现在才合并DEFAULT_PARAMS，确保天数等关键参数已经被补全
            params = {**DEFAULT_PARAMS, **raw_params}
            if dialogue_result.params:
                for key, value in dialogue_result.params.items():
                    if value and key in params:
                        params[key] = value

        except Exception as e:
            _logger.warning(f"多轮对话管理失败，降级到原逻辑: {e}")
            # 降级时合并DEFAULT_PARAMS
            params = {**DEFAULT_PARAMS, **raw_params}

        # 【参数校验与纠错】全面校验和纠正参数（在多轮对话补全之后）
        try:
            from app.skills.rule_engine import validate_and_correct_params
            validation_result = validate_and_correct_params(params)
            if validation_result.has_corrections:
                _logger.info(f"参数校验纠错: {validation_result.corrections}")
            if validation_result.warnings:
                _logger.warning(f"参数校验警告: {validation_result.warnings}")
            if validation_result.has_errors:
                _logger.error(f"参数校验错误: {validation_result.errors}")
                # 如果有错误，返回错误信息
                return ChatPlanResponse(
                    ready=False,
                    reply=f"参数校验失败：{'; '.join(validation_result.errors)}。请重新输入你的出行需求。",
                    params=params,
                )
            # 使用校验和纠正后的参数
            params = validation_result.params
        except Exception as e:
            _logger.warning(f"参数校验失败，降级到原逻辑: {e}")

        _logger.info(f"plan最终参数: 天数={params.get('days')}, 人数={params.get('travelers')}, 目的地={params.get('destination')}")
        destination = (params.get("destination") or "").strip()
        if not destination:
            return ChatPlanResponse(ready=False,
                reply="你心里已经有想去的远方了吗？告诉我一个名字，我替你把它变成出发的理由——比如「去成都玩4天，节奏慢一点」。",
                params=params)

        # RAG辅助：验证目的地、同名消歧、标准化名称
        try:
            from ..services.rag import get_retriever
            retriever = get_retriever()
            if retriever.available:
                # 尝试标准化景点名称（如果目的地是已知景点）
                normalized = retriever.normalize_poi_name(destination)
                if normalized != destination:
                    _logger.info(f"RAG目的地标准化: {destination} -> {normalized}")
                    destination = normalized
                    params["destination"] = destination

                # RAG检索目的地知识，验证目的地有效性
                query = f"{destination} 旅游 景点"
                rag_results = retriever.search_by_query(query, n_results=3)
                if rag_results:
                    _logger.info(f"RAG目的地验证成功: {destination}, 检索到{len(rag_results)}条知识")
                else:
                    _logger.info(f"RAG目的地验证无结果: {destination}（可能是小众地点或城市级目的地）")
        except Exception as e:
            _logger.warning(f"RAG目的地验证失败: {e}")

        params["destination"] = clean_place(destination)
        try:
            params["days"] = max(1, min(15, int(params.get("days") or 3)))
        except (TypeError, ValueError):
            params["days"] = 3
        try:
            params["travelers"] = max(1, min(99, int(params.get("travelers") or 1)))
        except (TypeError, ValueError):
            params["travelers"] = 1
        plan_req = PlanRequest(
            destination=params["destination"], days=params["days"],
            span_unit=params.get("span_unit", "day"),
            span_value=params.get("span_value", params["days"]),
            origin=params.get("origin", ""), travelers=params.get("travelers", 1),
            return_point=params.get("return_point", ""),
            group_type=params.get("group_type", "单人"),
            budget_level=params.get("budget_level", "适中"),
            style=params.get("style", "综合"), pace=params.get("pace", "适中"),
            traffic_mode=params.get("traffic_mode", "公共交通"),
            interests=params.get("interests", []),
            must_include_poi=params.get("must_include_poi", []),
            exclude_poi=params.get("exclude_poi", []),
        )
        plan = await build_plan(plan_req)
        
        # 检查规划是否被拒绝（未知目的地/中国境外等）
        if plan.source == "rejected":
            _logger.info(f"plan_rejected, destination={plan.destination}, message={plan.departure_message}")
            return ChatPlanResponse(
                ready=False,
                reply=plan.departure_message or f"抱歉，无法为「{plan.destination}」生成行程规划。",
                params=params,
                plan=plan,
            )
        
        try:
            admin_repository.add_gen_log(kind="plan",
                model=ai_mod.resolve_model() if ai_mod.ai_available() else "rule",
                status="ok" if plan.source == "ai" else "rule", ms=0,
                detail=f"{plan.destination} {plan.days}天")
        except Exception:
            pass
        src = "本地AI大模型" if plan.source == "ai" else "内置规则引擎"
        must_txt = "、".join(params.get("must_include_poi") or [])
        must_suffix = f"，已安排必去：{must_txt}" if must_txt else ""

        # 尝试用LLM生成有人文介绍的回复，失败则使用固定模板
        plan_dict = {
            "destination": plan.destination,
            "days": plan.days,
            "all_pois": plan.all_pois,
            "total_budget": plan.total_budget,
            "group_type": plan.group_type,
            "budget_level": plan.budget_level,
            "style": plan.style,
            "pace": plan.pace,
            "source": plan.source,
        }
        ai_reply_text = None
        try:
            ai_reply_text = await ai_mod.generate_plan_reply(plan_dict, user_msgs)
        except Exception as e:
            _logger.warning(f"generate_plan_reply exception: {e}")
        if ai_reply_text:
            reply = ai_reply_text
            # 在AI回复末尾加上查看行程的提示
            if "查看" not in reply and "行程" not in reply:
                reply += "\n\n点击下方按钮查看完整行程和地图～想调整随时告诉我。"
        else:
            _logger.info(f"generate_plan_reply returned None, using fallback template for {plan.destination}")
            reply = (f"世界在等你，{plan.destination}见！✨ 已为你备好 {plan.days} 天行程"
                     f"（{plan.group_type} · {plan.budget_level}预算 · {plan.style} · {plan.pace}节奏）{must_suffix}。"
                     f"共 {len(plan.day_plans)} 天、{len(plan.all_pois)} 个点位，预算约 ¥{round(plan.total_budget)}，"
                     f"由{src}生成——剩下的，交给你的脚步。"
                     f"点击下方按钮查看完整行程和地图～想调整随时告诉我，比如「预算经济一点」或「改成4天」。")
        return ChatPlanResponse(ready=True, reply=reply, params=params, plan=plan)

    return None


# ---------------- 天气降级（正则匹配） ----------------

_WEATHER_KW = re.compile(r"天气|气温|温度|冷不冷|热不热|下雨|下雪|降温|几度|会不会冷|穿衣|防晒|台风|雾霾")


async def _try_weather_reply(messages) -> Optional[str]:
    """天气类咨询：调高德实时天气返回真实数据文案；非天气咨询返回 None。"""
    latest = next((m.strip() for m in reversed(messages) if m and m.strip()), "")
    if not latest or not _WEATHER_KW.search(latest):
        return None
    city = extract_city(latest)
    if not city:
        return "想帮你查实时天气，先告诉我城市名吧，比如「济南的天气怎么样」🌤"
    data = await amap.weather(city)
    if not data or not data.get("weather"):
        return f"{city} 的实时天气暂时没查到，出发前记得关注当地天气预报哦～"
    return (
        f"📍 {data.get('city', city)} 实时天气\n"
        f"· 天气：{data['weather']}\n"
        f"· 气温：{data['temperature']}\n"
        f"· 风力：{data['wind']}\n"
        f"· 温馨提示：{data['tips']}\n\n"
        f"出门前再看一眼实时预报心里更有底～要不要我根据天气帮你把行程调得更舒服？"
    )


@router.post("/chat/plan", response_model=ChatPlanResponse)
async def chat_plan(req: ChatPlanRequest, authorization: Optional[str] = Header(None)):
    """对话式规划：先区分用户意图（需登录）。"""
    user = _require_user(authorization)
    user_id = str(user.get("id", "unknown"))
    
    # 检查每日对话次数限制
    usage_service = get_usage_limit_service()
    can_chat, chat_remaining = usage_service.check_chat_limit(user_id)
    if not can_chat:
        return ChatPlanResponse(
            ready=False,
            reply=usage_service.get_chat_limit_message(user_id),
            params=DEFAULT_PARAMS,
            usage_info=usage_service.get_usage_info(user_id),
        )
    
    user_msgs = [m.content for m in req.messages if m.role == "user" and m.content.strip()]
    if not user_msgs:
        # 记录对话调用
        usage_service.increment_chat_count(user_id)
        return ChatPlanResponse(
            ready=False,
            reply="你好呀，我是你的旅行伙伴！世界很大，而我们正从一次出发开始。想去哪儿？哪怕只是心里一个模糊的方向，也可以说给我听——比如「带爸妈去杭州玩3天，预算适中」。",
            params=DEFAULT_PARAMS,
            usage_info=usage_service.get_usage_info(user_id),
        )

    # LLM 意图分析 + 工具调用（主路径）；LLM 不可用或解析失败则降级规则
    llm_resp = await _llm_chat_plan(user_msgs)
    if llm_resp:
        # 记录对话调用
        usage_service.increment_chat_count(user_id)
        # 如果是规划响应，还需要记录规划调用
        if getattr(llm_resp, 'ready', False):
            can_plan, plan_remaining = usage_service.check_plan_limit(user_id)
            if not can_plan:
                return ChatPlanResponse(
                    ready=False,
                    reply=usage_service.get_plan_limit_message(user_id),
                    params=DEFAULT_PARAMS,
                    usage_info=usage_service.get_usage_info(user_id),
                )
            usage_service.increment_plan_count(user_id)
        # 添加使用信息到响应
        if hasattr(llm_resp, 'usage_info'):
            llm_resp.usage_info = usage_service.get_usage_info(user_id)
        return llm_resp

    params = parse_intent(user_msgs)
    intent = params.pop("intent", "plan")

    # 非规划意图：普通咨询 / 闲聊 → AI 直接回答，不生成行程
    if intent == "chat":
        # 记录对话调用
        usage_service.increment_chat_count(user_id)
        weather_reply = await _try_weather_reply(user_msgs)
        if weather_reply:
            return ChatPlanResponse(ready=False, reply=weather_reply, params=params, usage_info=usage_service.get_usage_info(user_id))
        reply = await ai_mod.chat_reply(user_msgs)
        if not reply:
            reply = "我在呢～无论是景点、美食还是天气，都乐意陪你聊。要是想把某个地方变成一场真正的行程，直接告诉我「去X玩几天」就行。"
        return ChatPlanResponse(ready=False, reply=reply, params=params, usage_info=usage_service.get_usage_info(user_id))

    if not params.get("destination"):
        # 记录对话调用
        usage_service.increment_chat_count(user_id)
        return ChatPlanResponse(
            ready=False,
            reply="你心里已经有想去的远方了吗？告诉我一个名字，我替你把它变成出发的理由——比如「去成都玩4天，节奏慢一点」。",
            params=params,
            usage_info=usage_service.get_usage_info(user_id),
        )

    # 出行人群类型需要确认时，先询问用户，不直接生成行程
    if params.get("group_type_needs_confirmation", False):
        # 记录对话调用
        usage_service.increment_chat_count(user_id)
        confirm_msg = params.get("group_type_confirm_message", "你们是几个人出行？是情侣/家庭/朋友？")
        return ChatPlanResponse(
            ready=False,
            reply=confirm_msg,
            params=params,
            usage_info=usage_service.get_usage_info(user_id),
        )
    
    # 检查每日规划次数限制
    can_plan, plan_remaining = usage_service.check_plan_limit(user_id)
    if not can_plan:
        return ChatPlanResponse(
            ready=False,
            reply=usage_service.get_plan_limit_message(user_id),
            params=params,
            usage_info=usage_service.get_usage_info(user_id),
        )

    plan_req = PlanRequest(
        destination=params["destination"],
        days=params["days"],
        origin=params.get("origin", ""),
        travelers=params.get("travelers", 1),
        return_point=params.get("return_point", ""),
        group_type=params["group_type"],
        budget_level=params["budget_level"],
        style=params["style"],
        pace=params["pace"],
        traffic_mode=params["traffic_mode"],
        interests=params["interests"],
        must_include_poi=params["must_include_poi"],
        exclude_poi=params["exclude_poi"],
    )
    plan = await build_plan(plan_req)
    
    # 记录对话和规划调用
    usage_service.increment_chat_count(user_id)
    usage_service.increment_plan_count(user_id)

    # 记录行程生成日志
    try:
        admin_repository.add_gen_log(
            kind="plan",
            model=ai_mod.resolve_model() if ai_mod.ai_available() else "rule",
            status="ok" if plan.source == "ai" else "rule",
            ms=0,
            detail=f"{plan.destination} {plan.days}天",
        )
    except Exception:
        pass

    src = "本地AI大模型" if plan.source == "ai" else "内置规则引擎"
    must_txt = "、".join(params["must_include_poi"]) if params["must_include_poi"] else ""
    must_suffix = f"，已安排必去：{must_txt}" if must_txt else ""

    # 尝试用LLM生成有人文介绍的回复，失败则使用固定模板
    plan_dict = {
        "destination": plan.destination,
        "days": plan.days,
        "all_pois": plan.all_pois,
        "total_budget": plan.total_budget,
        "group_type": plan.group_type,
        "budget_level": plan.budget_level,
        "style": plan.style,
        "pace": plan.pace,
        "source": plan.source,
    }
    ai_reply_text = None
    try:
        ai_reply_text = await ai_mod.generate_plan_reply(plan_dict, user_msgs)
    except Exception as e:
        _logger.warning(f"generate_plan_reply exception: {e}")
    if ai_reply_text:
        reply = ai_reply_text
        if "查看" not in reply and "行程" not in reply:
            reply += "\n\n点击下方按钮查看完整行程和地图～想调整随时告诉我。"
    else:
        _logger.info(f"generate_plan_reply returned None, using fallback template for {plan.destination}")
        reply = (
            f"世界在等你，{plan.destination}见！✨ 已为你备好 {plan.days} 天行程"
            f"（{plan.group_type} · {plan.budget_level}预算 · {plan.style} · {plan.pace}节奏）{must_suffix}。"
            f"共 {len(plan.day_plans)} 天、{len(plan.all_pois)} 个点位，预算约 ¥{round(plan.total_budget)}，"
            f"由{src}生成——剩下的，交给你的脚步。"
            f"点击下方按钮查看完整行程和地图～想调整随时告诉我，比如「预算经济一点」或「改成4天」。"
        )
    return ChatPlanResponse(ready=True, reply=reply, params=params, plan=plan)


@router.post("/route")
async def route(req: RouteRequest, authorization: Optional[str] = Header(None)):
    """两点间交通方案（供前端拖拽重排时重算路线，需登录）"""
    _require_user(authorization)
    return await amap.route(req.origin, req.destination, req.traffic_mode)
