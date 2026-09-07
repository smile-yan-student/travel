"""对话式行程规划：从自然语言对话中提取结构化规划参数。

解析策略（两级兜底）：
1. 优先调用本地轻量 AI（Ollama）从对话中抽取参数（JSON 输出）；
2. AI 不可用 / 输出异常时，用内置规则引擎（关键词 + 正则）兜底。

返回与 PlanRequest 兼容的 dict；destination 为空表示还需追问目的地。
"""
import json
import re
from typing import List, Optional

import httpx

from app.services import map as amap
from app.ai.ai import _resolve_model
from app.config import settings
from app.constants import (
    DAYS_PER_WEEK, DAYS_PER_MONTH, DAYS_PER_YEAR,
    MAX_DAYS, MIN_DAYS,
    GROUP_TYPES, GROUP_TYPE_KEYWORDS, GROUP_TYPE_DEFAULT_TRAVELERS,
    BUDGET_KEYWORDS, STYLE_KEYWORDS, PACE_KEYWORDS, TRAFFIC_KEYWORDS, INTEREST_KEYWORDS,
)
from .utils import DEFAULT_PARAMS

# 为了保持代码兼容性，创建别名（后续可以逐步替换）
_GROUP_KW = GROUP_TYPE_KEYWORDS
_BUDGET_KW = BUDGET_KEYWORDS
_STYLE_KW = STYLE_KEYWORDS
_PACE_KW = PACE_KEYWORDS
_TRAFFIC_KW = TRAFFIC_KEYWORDS
_INTEREST_KW = INTEREST_KEYWORDS

# 时间跨度归一化与收束：出行跨度可能以 天/周/月/年 表达，统一归一为「天」并收束到合理上限，
# 避免「规划点不足（天数过多）或过于庞杂（天数过少但点位爆炸）」。
# 常量已统一到 app/constants.py 中管理


def extract_city(text: str) -> str:
    """从文本提取可旅行地名（供天气等轻量咨询复用），无则返回空串。"""
    return _extract_destination(text or "")


def parse_intent(messages: List[str]) -> dict:
    """从多轮对话文本中解析出规划参数（AI 优先，规则兜底）。

    返回 dict 附带 `intent` 键：'plan'（需要生成/调整行程）或 'chat'（普通咨询，不生成行程）。
    意图只依据**最后一条用户消息**判断（避免被历史规划消息污染）。
    参数提取：规则对**最新消息**命中的强信号（目的地/天数/人群/预算等）优先于 AI，防止 AI 被历史旧地点带偏。
    """
    text = " ".join(m for m in messages if m and m.strip()).strip()
    latest = next((m.strip() for m in reversed(messages) if m and m.strip()), "")
    # 最近3条消息（用于历史参数兜底，避免被太久远的历史消息干扰）
    recent_messages = [m.strip() for m in messages if m and m.strip()][-3:]
    recent_text = " ".join(recent_messages)
    rule_params = _rule_extract(text, latest, recent_text)
    rule_intent = _rule_classify(latest)

    # 调试日志：输出规则提取结果
    import logging
    _intent_logger = logging.getLogger("intent")
    _intent_logger.info("parse_intent_rule_extract", extra={"fields": {
        "latest": latest,
        "recent_text": recent_text,
        "rule_days": rule_params.get("days"),
        "rule_travelers": rule_params.get("travelers"),
        "rule_destination": rule_params.get("destination"),
        "rule_latest_hits": rule_params.get("_latest_hits", []),
    }})

    ai_params = _ai_extract(messages)

    # 调试日志：输出AI提取结果
    if ai_params:
        _intent_logger.info("parse_intent_ai_extract", extra={"fields": {
            "ai_days": ai_params.get("days"),
            "ai_travelers": ai_params.get("travelers"),
            "ai_destination": ai_params.get("destination"),
        }})

    if ai_params:
        # 规则提取的参数优先于AI提取的参数（因为规则更准确）
        # 先合并默认参数和AI参数，然后用规则参数覆盖非默认值
        merged = {**DEFAULT_PARAMS, **ai_params}
        # 规则参数中，非默认值的参数覆盖AI参数
        for k, v in rule_params.items():
            if k == "_latest_hits":
                continue
            # 如果规则参数不是默认值，就覆盖AI参数
            default_v = DEFAULT_PARAMS.get(k)
            if v != default_v and v not in (None, "", [], {}):
                merged[k] = v
    else:
        merged = {**DEFAULT_PARAMS, **rule_params}

    # 调试日志：输出最终合并结果
    _intent_logger.info("parse_intent_merged", extra={"fields": {
        "merged_days": merged.get("days"),
        "merged_travelers": merged.get("travelers"),
        "merged_destination": merged.get("destination"),
        "merged_intent": merged.get("intent"),
    }})
    
    # 记录用户是否明确指定了人数（通过正则表达式判断用户输入文本中是否包含人数相关关键词）
    # 判断依据：用户输入文本中是否包含"X人"、"X个人"、"X位"、"X名"等表述
    travelers_pattern = r'\d+\s*(?:人|个人|位|名|个大人|个孩子|个老人)|(?:一|二|三|四|五|六|七|八|九|十)\s*(?:人|个人|位|名)'
    user_specified_travelers = bool(re.search(travelers_pattern, text))

    # 意图以规则对“最新用户消息”的判断为准（chat 强信号优先，避免 AI 被整段历史带偏）
    merged["intent"] = rule_intent

    # 规则在最新消息里命中的强信号优先于 AI（如「帮我规划济南」不能被历史里的“杭州”带偏）
    for k in rule_params.get("_latest_hits", []):
        if k in rule_params:
            merged[k] = rule_params[k]
    merged.pop("_latest_hits", None)

    # 强信号修正：明确的关系/人群表述优先于模型猜测
    strong = _strong_hints(text)
    for k, v in strong.items():
        merged[k] = v

    # 字段清洗与约束
    merged["days"] = max(MIN_DAYS, min(MAX_DAYS, int(merged.get("days") or 3)))
    merged["destination"] = _clean_place(merged.get("destination") or "")
    merged["origin"] = _clean_place(merged.get("origin") or "")
    merged["return_point"] = _clean_place(merged.get("return_point") or "")
    
    # 行政区域信息清洗（LLM补全）
    merged["province"] = _clean_place(merged.get("province") or "")
    merged["city"] = _clean_place(merged.get("city") or "")
    merged["district"] = _clean_place(merged.get("district") or "")
    
    # 如果LLM没有补全行政区域信息，但destination是行政区域级别，可以尝试从本地地理数据补全
    if merged["destination"] and not (merged["province"] or merged["city"] or merged["district"]):
        try:
            from app.core.geo_local import lookup
            admin_info = lookup(merged["destination"])
            if admin_info:
                level = admin_info.get("level", "")
                name = admin_info.get("name", "")
                parent = admin_info.get("parent", "")
                
                if level == "province":
                    # 省级：name是省名
                    if not merged["province"]:
                        merged["province"] = name
                elif level == "city":
                    # 市级：name是市名，parent是省名
                    if not merged["city"]:
                        merged["city"] = name
                    if not merged["province"] and parent:
                        merged["province"] = parent
                elif level == "district":
                    # 区县级：name是区县名，parent可能是市名
                    if not merged["district"]:
                        merged["district"] = name
                    if not merged["city"] and parent:
                        merged["city"] = parent
                        # 尝试获取市级的父级（省级）
                        try:
                            from app.core.geo_local import lookup
                            city_info = lookup(parent)
                            if city_info and city_info.get("level") == "city" and city_info.get("parent"):
                                if not merged["province"]:
                                    merged["province"] = city_info["parent"]
                        except:
                            pass
        except Exception as e:
            print(f"[intent] 行政区域补全失败: {e}")
    
    # 设置默认人数
    try:
        merged["travelers"] = max(1, min(99, int(merged.get("travelers") or 1)))
    except (TypeError, ValueError):
        merged["travelers"] = 1
        user_specified_travelers = False
    
    merged["group_type"] = _pick_enums(merged.get("group_type"), ["单人", "情侣", "亲子", "家庭", "朋友", "老人"], "单人")
    
    # 根据group_type推断默认人数（仅当用户没有明确指定人数时）
    # 逻辑：不根据人数推断关系（避免误判），但可以根据关系推断人数（因为关系已经明确了）
    if not user_specified_travelers:
        default_travelers = GROUP_TYPE_DEFAULT_TRAVELERS.get(merged["group_type"], 1)
        merged["travelers"] = default_travelers
    
    merged["budget_level"] = _pick_enums(merged.get("budget_level"), ["经济", "适中", "舒适", "奢华"], "适中")
    merged["pace"] = _pick_enums(merged.get("pace"), ["轻松", "适中", "暴走"], "适中")
    merged["traffic_mode"] = _pick_enums(merged.get("traffic_mode"), ["混合", "自驾", "公共交通", "骑行", "步行"], "公共交通")
    merged["group_type"] = _pick_enums(merged.get("group_type"), GROUP_TYPES, "单人")
    merged["style"] = _clean_style(merged.get("style"))
    for k in ("interests", "must_include_poi", "exclude_poi"):
        merged[k] = [str(x).strip() for x in (merged.get(k) or []) if str(x).strip()]
    
    # 智能推断出行人群类型：根据人数设置默认group_type（不做关系推断）
    inferred_group_type, needs_confirm, confirm_msg = _infer_group_type(
        merged["group_type"], merged["travelers"], text
    )
    merged["group_type"] = inferred_group_type
    merged["group_type_needs_confirmation"] = needs_confirm
    merged["group_type_confirm_message"] = confirm_msg
    
    return merged


# ---------------------------------------------------------------------------
# 意图分类（规则兜底，AI 输出 intent 时优先用 AI）
# ---------------------------------------------------------------------------
# 非规划（普通咨询/闲聊）强信号：命中即视为 chat，不重新生成行程
_CHAT_SIGNALS = [
    r"天气|气温|温度|下雨|降雨|下雪|降温|穿衣|防晒|几度|暖和",
    r"有什么好吃的|美食推荐|推荐.{0,4}(?:餐厅|小吃|店|美食)|吃.{0,4}(?:推荐|什么好)|(?:哪|什么).{0,4}(?:好吃|美食|特色)",
    r"门票|预约|订票|多少钱|价格|费用|贵不贵|划算|值不值|人均(?:多少|多少钱|消费|价格|几)",
    r"怎么去|怎么到|怎么走|高铁|航班|飞机|火车票|机票|几号线|坐几路",
    r"最佳|什么时候去|几月去|淡季|旺季|避坑|注意|安全",
    r"^(?:你好|哈喽|hi|hello|嗨|在吗|谢谢|感谢|辛苦了|再见|拜拜|好的|嗯|ok|可以)\b",
    r"第[一二三四五六七八九十\d]+天.{0,6}(?:去|安排|行程|玩|哪里|哪)|行程.{0,6}(?:怎么样|如何|合理|安排|看看|介绍)|路线.{0,4}(?:合理|调整|改)",
    r"有没有|能不能|是不是|可不可以|请问|帮我看看.{0,4}(?:推荐|介绍)",
]
# 规划信号：命中视为 plan（生成/调整行程）
_PLAN_SIGNALS = [
    r"(?:去|到|来|前往|飞去|想去|要去|出发去|打算去|准备去).{1,16}?(?:玩|旅游|旅行|度假|逛|耍|待|天)",
    r"(?:生成|规划|计划|安排|做|出|写|设计|搞|弄).{0,8}(?:行程|攻略|方案|计划|路线|规划)",
    r"(?:改|调|换|变|增加|加|减少|减|多|少|延长|缩短).{0,6}(?:天|预算|节奏|风格|交通|人群|景点|点位|天数)",
    r"(?:预算|人均|花费|花销).{0,10}(?:改|调|换|经济|舒适|奢华|适中|高|低|一点|够|人均)",
    r"(?:改|调|换)成?.{0,6}(?:预算|人均|天数|天|行程|方案)",
    r"改成?\s*\d+\s*天|改\s*\d+\s*天|\d+\s*天.{0,6}(?:改|加|减|少|多)",
    r"(?:加|加上|增加|安排|必去|一定要去|想去|顺便去)\s*[\u4e00-\u9fa5]{2,8}",
    r"(?:去掉|不要|不想去|别去|排除|删掉|避开|取消)\s*[\u4e00-\u9fa5]{2,8}",
    r"(?:重新|重|再).{0,4}(?:规划|生成|做一|来一次|出方案|做一次)",
    r"删掉|重做|推翻|不要了|重新来",
]


def _rule_classify(latest: str) -> str:
    """规则意图分类（只针对最新一条用户消息）：chat 强信号优先；命中规划信号 → plan；默认 chat（保守不打断规划）。"""
    if not latest:
        return "chat"
    for pat in _CHAT_SIGNALS:
        if re.search(pat, latest):
            return "chat"
    for pat in _PLAN_SIGNALS:
        if re.search(pat, latest):
            return "plan"
    return "chat"


# ---------------------------------------------------------------------------
# 规则解析（兜底）
# ---------------------------------------------------------------------------
def _cn_to_int(s: str) -> Optional[int]:
    """中文/阿拉伯数字转整数（支持 一~九、十、十一、二十、二十一、两）。"""
    if not s:
        return None
    s = s.strip().replace("两", "二")
    if s.isdigit():
        return int(s)
    nums = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    if s == "十":
        return 10
    if "十" in s:
        parts = s.split("十")
        left = nums.get(parts[0]) if parts[0] else 1
        right = nums.get(parts[1]) if len(parts) > 1 and parts[1] else 0
        if left is None:
            return None
        return left * 10 + (right or 0)
    return nums.get(s)


_NUM_RE = r"[\d一二两三四五六七八九十]+"


def _normalize_days(text: str) -> Optional[int]:
    """把「N天N夜 / N天 / N周 / N个月 / N年」等时间跨度归一化为天数，并收束到 [1, MAX_DAYS]。

    - 中文数字同样支持（一周=7、一个月=30、两年=730→收束 15）；
    - 月/年维度直接乘系数：如「玩一个月」→ 30 → 收束 15；「玩一年」→ 365 → 收束 15；
    - 未提到跨度返回 None（由上层用默认 2~3 天）。
    """
    if not text:
        return None
    m = re.search(rf"({_NUM_RE})\s*天\s*({_NUM_RE})\s*夜", text)
    if m:
        v = _cn_to_int(m.group(1))
        return max(MIN_DAYS, min(MAX_DAYS, v)) if v is not None else None
    m = re.search(rf"({_NUM_RE})\s*(?:天|日)", text)
    if m:
        v = _cn_to_int(m.group(1))
        return max(MIN_DAYS, min(MAX_DAYS, v)) if v is not None else None
    m = re.search(rf"({_NUM_RE})\s*(?:周|星期)", text)
    if m:
        v = _cn_to_int(m.group(1))
        return max(MIN_DAYS, min(MAX_DAYS, v * DAYS_PER_WEEK)) if v is not None else None
    m = re.search(rf"({_NUM_RE})\s*个?月", text)
    if m:
        v = _cn_to_int(m.group(1))
        return max(MIN_DAYS, min(MAX_DAYS, v * DAYS_PER_MONTH)) if v is not None else None
    m = re.search(rf"({_NUM_RE})\s*年", text)
    if m:
        v = _cn_to_int(m.group(1))
        return max(MIN_DAYS, min(MAX_DAYS, v * DAYS_PER_YEAR)) if v is not None else None
    return None


def _extract_span(text: str) -> Optional[tuple]:
    """提取原始时间跨度（单位+数量），不做收束。返回 (span_unit, span_value) 或 None。

    用于大时间跨度（月/年）规划时按省/月分配，而不是简单收束到15天。
    span_unit: day / week / month / year
    """
    if not text:
        return None
    # 年
    m = re.search(rf"({_NUM_RE})\s*年", text)
    if m:
        v = _cn_to_int(m.group(1))
        if v:
            return ("year", v)
    # 月
    m = re.search(rf"({_NUM_RE})\s*个?月", text)
    if m:
        v = _cn_to_int(m.group(1))
        if v:
            return ("month", v)
    # 周
    m = re.search(rf"({_NUM_RE})\s*(?:周|星期)", text)
    if m:
        v = _cn_to_int(m.group(1))
        if v:
            return ("week", v)
    # 天
    m = re.search(rf"({_NUM_RE})\s*(?:天|日)", text)
    if m:
        v = _cn_to_int(m.group(1))
        if v:
            return ("day", v)
    return None


def _extract_origin(text: str) -> str:
    """出发点：仅「从X出发/从X来」句式命中才提取，避免把目的地当出发点。"""
    if not text:
        return ""
    m = re.search(r"(?:从|由)\s*([\u4e00-\u9fa5]{2,12}?)\s*(?:出发|启程|动身|来|过去)", text)
    if m:
        return _clean_place(m.group(1))
    return ""


def _extract_return_point(text: str) -> str:
    """返回点：`回到X / 返回X / 回X`（不带“去/到”的“回X”易误判，仅匹配明确返回句式）。"""
    if not text:
        return ""
    for pat in (r"(?:回到|返回|折返|回程到)\s*([\u4e00-\u9fa5]{2,12}?)",
                r"回\s*([\u4e00-\u9fa5]{2,6}?)(?:的|去|玩|$)"):
        m = re.search(pat, text)
        if m:
            cleaned = _clean_place(m.group(1))
            if cleaned:
                return cleaned
    return ""


def _extract_travelers(text: str) -> Optional[int]:
    """人数：`N个人/N人/我们N个/N大N小/一个人/带爸妈` 等句式；未提到返回 None（默认 1 人）。"""
    if not text:
        return None
    # 一个人 / 独自 / 自己 → 1
    if re.search(r"一个人|独自|单人|自己", text):
        return 1
    # 带爸妈/父母/二老 → 2
    if re.search(r"带?(?:爸妈|父母|老爸老妈|二老)", text):
        return 2
    m = re.search(rf"({_NUM_RE})\s*(?:个人|个大人|人)", text)
    if m:
        v = _cn_to_int(m.group(1))
        return max(1, min(99, v)) if v is not None else None
    m = re.search(rf"({_NUM_RE})\s*大\s*({_NUM_RE})\s*小", text)
    if m:
        a, b = _cn_to_int(m.group(1)), _cn_to_int(m.group(2))
        if a is not None and b is not None:
            return max(1, min(99, a + b))
    m = re.search(rf"我们\s*({_NUM_RE})\s*个", text)
    if m:
        v = _cn_to_int(m.group(1))
        return max(1, min(99, v)) if v is not None else None
    return None


def _match_kw_opt(text: str, pairs) -> Optional[str]:
    """命中返回对应值；未命中返回 None（用于区分‘没提’与‘命中默认值’）。"""
    for value, kws in pairs:
        if any(k in text for k in kws):
            return value
    return None


def _rule_extract(text: str, latest: str = "", recent_text: str = "") -> dict:
    """规则解析：目的地/天数等**最新用户消息强信号优先**，历史仅兜底。

    返回 params（附带内部键 `_latest_hits`：记录哪些参数是 latest 命中的，供上层覆盖 AI）。
    """
    params = dict(DEFAULT_PARAMS)
    hits = []

    # 天数：优先最新消息，其次最近3条消息，最后整段历史
    nd = _normalize_days(latest) if latest else None
    if nd is None and recent_text:
        nd = _normalize_days(recent_text)
    if nd is None:
        nd = _normalize_days(text)
    if nd is not None:
        params["days"] = nd
        if latest:
            hits.append("days")

    # 原始时间跨度（单位+数量）：用于大跨度（月/年）按省/月规划，不做收束
    span = _extract_span(latest) if latest else None
    if span is None and recent_text:
        span = _extract_span(recent_text)
    if span is None:
        span = _extract_span(text)
    if span:
        params["span_unit"], params["span_value"] = span
        if latest:
            hits.append("span")

    # 出发点（非必须）：仅最新消息「从X出发」句式
    org = _extract_origin(latest) if latest else ""
    if org:
        params["origin"] = org
        hits.append("origin")

    # 返回点（非必须）
    rp = _extract_return_point(latest) if latest else ""
    if rp:
        params["return_point"] = rp
        hits.append("return_point")

    # 人数（非必须，默认 1 人）：优先最新消息，其次最近3条消息，最后整段历史
    tr = _extract_travelers(latest) if latest else None
    if tr is None and recent_text:
        tr = _extract_travelers(recent_text)
    if tr is None:
        tr = _extract_travelers(text)
    if tr is not None:
        params["travelers"] = tr
        if latest:
            hits.append("travelers")

    # 目的地：优先最新消息，其次最近3条消息，最后整段历史
    dest = _extract_destination(latest) if latest else ""
    if not dest and recent_text:
        dest = _extract_destination(recent_text)
    if not dest:
        dest = _extract_destination(text)
    if dest:
        hits.append("destination")
    params["destination"] = dest

    # 人群/预算/节奏/交通：最新命中优先，否则整段
    for key, pairs, fallback in [
        ("group_type", _GROUP_KW, "单人"),
        ("budget_level", _BUDGET_KW, "适中"),
        ("pace", _PACE_KW, "适中"),
        ("traffic_mode", _TRAFFIC_KW, "公共交通"),
    ]:
        lv = _match_kw_opt(latest, pairs)
        if lv is not None:
            params[key] = lv
            hits.append(key)
        else:
            params[key] = _match_kw_opt(text, pairs) or fallback

    styles = _match_kw_all(latest, _STYLE_KW) or _match_kw_all(text, _STYLE_KW)
    params["style"] = "+".join(styles) if styles else "综合"
    if _match_kw_all(latest, _STYLE_KW):
        hits.append("style")

    params["interests"] = _match_kw_all(latest, _INTEREST_KW) or _match_kw_all(text, _INTEREST_KW)
    if _match_kw_all(latest, _INTEREST_KW):
        hits.append("interests")

    params["_latest_hits"] = hits
    return params


def _extract_destination(text: str) -> str:
    cities = sorted(amap.CITY_CENTERS.keys(), key=len, reverse=True)

    # 0) 天气咨询句式："X的天气/气温/温度/冷不冷/下雨/下雪/降温/几度…"
    #    不依赖手写城市表，任何地级市/区县名都能提取（修复"德州的天气如何"识别为空）
    _WEATHER_CITY_STOP = {
        "今天", "明天", "昨天", "现在", "这里", "那里", "这儿", "那儿",
        "本地", "当地", "全国", "全球", "周末", "假期", "五一", "国庆",
        "春节", "元旦", "清明", "端午", "中秋", "这周", "下周", "上周",
        "这个月", "下个月", "上个月", "今年", "明年", "去年", "近期", "最近",
    }
    m0 = re.search(
        r"([\u4e00-\u9fa5]{2,10}?)(?:的)?"
        r"(?:天气|气温|温度|冷不冷|热不冷|热不热|下雨|下雪|降温|几度|"
        r"会不会冷|穿衣|防晒|台风|雾霾|穿什么|冷吗|热吗|多少度)",
        text,
    )
    if m0:
        cand = _clean_place(m0.group(1))
        if cand and cand not in _WEATHER_CITY_STOP and len(cand) >= 2:
            return cand

    # 1) “去/到/来/前往 X”句式（最强信号：支持长地名 + 行政区划清洗）
    m = re.search(
        r"(?:去|到|来|前往|飞往|想去|要去|出发去|打算去)\s*"
        r"([\u4e00-\u9fa5]{2,14}?)(?=的|玩|旅游|旅行|度假|耍|逛|待|天|\d|[，,。！？!?]|$)",
        text,
    )
    if m:
        cleaned = _clean_place(m.group(1))
        if cleaned:
            return cleaned

    # 2) 城市表直接命中（取最后一个，通常是目的地）
    hits = [c for c in cities if c in text]
    if hits:
        return hits[-1]

    # 3) “在 X 玩 / 想 X 玩”
    m2 = re.search(r"(?:在|想)\s*([\u4e00-\u9fa5]{2,10}?)(?:玩|旅游|度假|逛逛)", text)
    if m2:
        cleaned = _clean_place(m2.group(1))
        if cleaned:
            return cleaned
    return ""


def _clean_place(cand: str) -> str:
    """清洗地名：去掉尾随动作词与省/市行政前缀，保留最具体地名。"""
    s = (cand or "").strip()
    if not s:
        return ""
    for suffix in ("游玩", "游", "玩", "逛", "待", "去"):
        if s.endswith(suffix):
            s = s[: -len(suffix)]
            break
    s = s.strip()
    if not s:
        return ""
    # 去掉省级前缀（省 / 自治区 / 特别行政区）
    for sep in ("壮族自治区", "回族自治区", "维吾尔自治区", "特别行政区", "自治区", "省"):
        idx = s.find(sep)
        if idx != -1:
            s = s[idx + len(sep):]
            break
    s = s.strip()
    # 去掉市级前缀（市后有内容才去，保留"成都市"这类纯市名）
    idx = s.find("市")
    if idx != -1 and idx + 1 < len(s):
        s = s[idx + 1:]
    s = s.strip()
    # 去掉末尾的“市”（杭州市 -> 杭州），非单字时
    if s.endswith("市") and len(s) > 2:
        s = s[:-1]
    s = s.strip()
    # 动词短语伪地名过滤：如“出去玩”“玩几”“逛逛”不是地名
    if len(s) < 2 or s.startswith(("出", "去", "玩", "逛", "想", "要")):
        return ""
    return s


def _match_kw(text: str, pairs) -> str:
    """命中返回第一个关键词组对应的值，未命中返回默认（组内第一个）。"""
    for value, kws in pairs:
        if any(k in text for k in kws):
            return value
    return pairs[0][0]


def _match_kw_all(text: str, pairs) -> List[str]:
    out = []
    for value, kws in pairs:
        if any(k in text for k in kws):
            out.append(value)
    return out


def _strong_hints(text: str) -> dict:
    """高置信度的人群/节奏信号（优先于 AI 猜测）"""
    hints = {}
    if re.search(r"对象|女朋友|男朋友|恋人|我们俩|情侣", text):
        hints["group_type"] = "情侣"
    if re.search(r"一个人|独自|单人", text):
        hints["group_type"] = "单人"
    if re.search(r"带孩子|带娃|亲子|遛娃", text):
        hints["group_type"] = "亲子"
    if re.search(r"爸妈|父母|老人|长辈|爷爷奶奶", text):
        hints["group_type"] = "家庭"
    if re.search(r"朋友|闺蜜|兄弟|同学", text):
        hints["group_type"] = "朋友"
    return hints


def _infer_group_type(group_type: str, travelers: int, text: str) -> tuple:
    """
    根据人数设置默认出行人群类型（不做关系推断）
    
    逻辑：
    1. 如果用户已经明确指定了group_type，则直接使用
    2. 根据人数设置默认值：
       - 1人 → 单人
       - 2人以上 → 朋友（中性默认值，不做情侣/家庭等关系推断）
    3. 不根据对话上下文推断关系类型，让用户自己选择
    
    Args:
        group_type: 当前的group_type
        travelers: 出行人数
        text: 对话文本（保留参数兼容，但不使用）
    
    Returns:
        tuple: (推断后的group_type, 是否需要确认, 确认提示消息)
    """
    # 明确的人群类型列表
    explicit_types = ["情侣", "亲子", "家庭", "朋友", "老人"]
    
    # 1. 如果用户已经明确指定了group_type，则直接使用
    if group_type in explicit_types:
        return group_type, False, ""
    
    # 2. 根据人数设置默认值
    if travelers == 1:
        # 1人 → 单人
        return "单人", False, ""
    else:
        # 2人以上 → 朋友（中性默认值，不做情侣/家庭等关系推断）
        return "朋友", False, ""


# ---------------------------------------------------------------------------
# AI 解析（首选）
# ---------------------------------------------------------------------------
_AI_PROMPT = """你是旅行规划对话助手，负责判断用户意图并从对话中提取结构化行程参数。
先判断用户最新消息的意图类型：
- 若用户在规划/调整行程（想去某地玩、生成/重做行程、改天数/预算/风格/节奏/交通/人群、增删景点点位等）→ intent 为 "plan"；
- 若用户只是普通对话或咨询（闲聊寒暄、问天气/美食/门票/交通/最佳时间、询问当前行程内容等，不要求生成或改动行程）→ intent 为 "chat"。
根据对话内容输出严格 JSON（不要 markdown、不要多余文字、不要注释）：
{
  "intent": "plan 或 chat，二选一",
  "destination": "目的地，可以是省/市/区县等任何具体可旅行地名；用户明确说出“去X玩/到X游玩/想去X”时，X 就是目的地（哪怕是很小的区县，如“山东省聊城市茌平区”→“茌平区”），务必提取不要留空；整段对话完全没提到地点才给空字符串",
  "province": "省份（行政区域补全）：当目的地是行政区域级别时，补全省份名称，如'浙江省'、'安徽省'；如果是具体景点或不确定则为空字符串",
  "city": "城市（行政区域补全）：当目的地是市/区县级时，补全城市名称，如'杭州市'、'黄山市'；如果是省级或具体景点或不确定则为空字符串",
  "district": "区县（行政区域补全）：当目的地是区县级时，补全区县名称，如'西湖区'、'休宁县'；如果是省/市级或具体景点或不确定则为空字符串",
  "days": 3,
  "origin": "出发点：仅当用户明确说“从X出发/从X来”时才填，否则空字符串",
  "travelers": 1,
  "return_point": "返回点：仅当用户明确说“回到X/返回X”时才填，否则空字符串",
  "group_type": "单人/情侣/亲子/家庭/朋友/老人",
  "budget_level": "经济/适中/舒适/奢华",
  "style": "美食/人文/网红/小众/亲子/自然，可组合如：美食+人文",
  "pace": "轻松/适中/暴走",
  "traffic_mode": "自驾/公共交通/骑行/步行/混合",
  "interests": ["兴趣关键词数组，没有则 []"],
  "must_include_poi": ["明确要求必去的地点名称数组，没有则 []"],
  "exclude_poi": ["明确表示不想去的地点名称数组，没有则 []"]
}
规则：
1. 未提到的字段给默认值或空；days 未提给 3（出行跨度可用"N天/N周/N个月/N年"表达，按天归一：周×7、月×30、年×365）。重要：如果最新消息中没有明确提到天数，但历史消息中用户已经明确说了天数，应该继承历史消息中的天数，不要使用默认值3天。只有当整段对话都没有提到天数时，才使用默认值3天。
2. 最后一条用户消息是最新的、最权威的表述：目的地、天数等一律以它为准；历史消息里出现过的其他地点/参数，只要最新消息里用户换了说法（比如改去另一个城市、改了天数），一律以最新消息为准，不要把历史里的旧地点当作目的地。但如果最新消息只是继续之前的话题（如"帮我规划一下"、"好的"），没有明确改变参数，应该继承历史消息中的参数。
3. 目的地必须是用户明确想去的地点（城市/区县/景区等），从“去X/到X/在X玩/规划X的行程”等表述中提取；提取不出才留空字符串。
4. 出发点/返回点/人数只在用户明确提到时填写，不要臆测。人数同理：如果最新消息中没有明确提到人数，但历史消息中用户已经明确说了人数，应该继承历史消息中的人数。
5. 意图判断示例：问“杭州有什么好吃的”虽提到杭州但只是咨询 → chat；说“带爸妈去杭州玩3天，预算适中” → plan；“预算经济一点”“加个灵隐寺” → plan；“第一天去哪”“门票多少钱”“最近天气” → chat。

【行政区域补全规则】（非常重要，必须严格遵守）
- 当目的地是行政区域级别的（省、市、区县）时，**必须补全完整的行政区域信息**
- 补全字段：province（省）、city（市）、district（区县）
- 行政区域级别判断：
  - 省级：云南、四川、浙江、山东等 → destination补全为"云南省"，province="云南省"，city=""，district=""
  - 市级：杭州、北京、济南、成都等 → destination补全为"杭州市"，province="浙江省"，city="杭州市"，district=""
  - 区县级：休宁、西湖、海淀、武侯等 → destination补全为"休宁县"，province="安徽省"，city="黄山市"，district="休宁县"
- 常见行政区域补全示例：
  - "休宁" → destination="休宁县", province="安徽省", city="黄山市", district="休宁县"
  - "杭州" → destination="杭州市", province="浙江省", city="杭州市", district=""
  - "云南" → destination="云南省", province="云南省", city="", district=""
  - "北京" → destination="北京市", province="北京市", city="北京市", district=""
  - "济南" → destination="济南市", province="山东省", city="济南市", district=""
  - "成都" → destination="成都市", province="四川省", city="成都市", district=""
  - "西安" → destination="西安市", province="陕西省", city="西安市", district=""
  - "广州" → destination="广州市", province="广东省", city="广州市", district=""
- 如果用户输入的目的地已经包含行政后缀（如"杭州市"、"休宁县"），则不需要重复补全
- 如果用户输入的是具体景点（如"大明湖"、"西湖"），则不需要补全行政区域，但可以推断其所属的省、市
- **如果你不确定某个地名的行政区域归属，不要猜测，只填写你确定的字段，不确定的字段留空字符串**"""


def _ai_extract(messages: List[str]) -> Optional[dict]:
    """AI 提取：从对话中抽取结构化参数。

    优化：
    1. 只保留最近的5条消息，避免历史对话干扰当前意图识别
    2. 最新消息单独标注，强调其权威性
    3. 在Prompt中明确要求关注最新消息
    """
    model = _resolve_model()
    if not model:
        return None

    # 只保留最近的5条消息，避免历史对话干扰
    recent_messages = [m.strip() for m in messages if m and m.strip()][-5:]
    if not recent_messages:
        return None

    # 构建消息历史，最新消息单独标注
    history = []
    for i, m in enumerate(recent_messages):
        if i == len(recent_messages) - 1:
            # 最新消息单独标注，强调其权威性
            history.append({"role": "user", "content": f"【最新消息，请重点关注】{m}"})
        else:
            history.append({"role": "user", "content": m})

    try:
        # 使用统一的chat_completion函数，支持本地Ollama和线上OpenAI兼容API
        import asyncio
        from app.ai.ai import chat_completion

        messages = [
            {"role": "system", "content": _AI_PROMPT + "\n\n【重要】必须返回合法的JSON格式，不要输出任何其他内容。"},
            *history,
        ]
        content = asyncio.run(chat_completion(
            messages=messages,
            temperature=0.1,
            max_tokens=2048,
            model=model,
        )) or ""
    except Exception:
        return None
    if not content:
        return None
    content = content.strip()
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.MULTILINE)
    start, end = content.find("{"), content.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        data = json.loads(content[start:end + 1])
    except json.JSONDecodeError:
        return None
    return {
        "intent": str(data.get("intent") or "").strip(),
        "destination": str(data.get("destination") or "").strip(),
        "province": str(data.get("province") or "").strip(),
        "city": str(data.get("city") or "").strip(),
        "district": str(data.get("district") or "").strip(),
        "days": int(data.get("days") or 3) if str(data.get("days") or "").isdigit() else 3,
        "origin": str(data.get("origin") or "").strip(),
        "travelers": int(data.get("travelers") or 1) if str(data.get("travelers") or "").isdigit() else 1,
        "return_point": str(data.get("return_point") or "").strip(),
        "group_type": str(data.get("group_type") or ""),
        "budget_level": str(data.get("budget_level") or ""),
        "style": str(data.get("style") or ""),
        "pace": str(data.get("pace") or ""),
        "traffic_mode": str(data.get("traffic_mode") or ""),
        "interests": data.get("interests") or [],
        "must_include_poi": data.get("must_include_poi") or [],
        "exclude_poi": data.get("exclude_poi") or [],
    }


# ---------------------------------------------------------------------------
# 清洗
# ---------------------------------------------------------------------------
def _pick_enums(value, allowed, default) -> str:
    if not value:
        return default
    v = str(value).strip()
    if v in allowed:
        return v
    for a in allowed:
        if a in v:
            return a
    return default


def _clean_style(value) -> str:
    if not value:
        return "综合"
    parts = [p.strip() for p in re.split(r"[+、,，/]", str(value)) if p.strip()]
    allowed = ["美食", "人文", "网红", "小众", "亲子", "自然"]
    picked = [p for p in parts if p in allowed]
    return "+".join(picked) if picked else "综合"
