"""
意图识别Skill - 工具函数

提供默认参数、地名清洗、城市提取等工具函数。
"""
import re
from typing import List, Dict, Optional

from app.services.map import CITY_CENTERS


# 默认参数
DEFAULT_PARAMS: Dict = {
    "destination": "",
    "province": "",        # 省份（LLM行政区域补全）
    "city": "",            # 城市（LLM行政区域补全）
    "district": "",        # 区县（LLM行政区域补全）
    "days": 3,
    "span_unit": "day",     # 原始时间跨度单位：day/week/month/year
    "span_value": 3,        # 原始时间跨度数量（如 span_unit=month, span_value=2 表示2个月）
    "origin": "",          # 出发点（非必须）
    "travelers": 1,        # 人数（非必须，默认 1 人）
    "return_point": "",    # 返回点（非必须）
    "group_type": "单人",
    "budget_level": "适中",
    "style": "综合",
    "pace": "适中",
    "traffic_mode": "公共交通",
    "interests": [],
    "must_include_poi": [],
    "exclude_poi": [],
}


def clean_place(cand: str) -> str:
    """
    清洗地名：去掉尾随动作词与省/市行政前缀，保留最具体地名。

    Args:
        cand: 原始地名字符串

    Returns:
        清洗后的地名字符串
    """
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
    # 去掉末尾的"市"（杭州市 -> 杭州），非单字时
    if s.endswith("市") and len(s) > 2:
        s = s[:-1]
    s = s.strip()
    # 动词短语伪地名过滤：如"出去玩""玩几""逛逛"不是地名
    if len(s) < 2 or s.startswith(("出", "去", "玩", "逛", "想", "要")):
        return ""
    return s


def extract_city(text: str) -> str:
    """
    从文本提取可旅行地名（供天气等轻量咨询复用），无则返回空串。

    Args:
        text: 输入文本

    Returns:
        提取到的地名字符串
    """
    return _extract_destination(text or "")


def _extract_destination(text: str) -> str:
    """
    从文本中提取目的地。

    Args:
        text: 输入文本

    Returns:
        提取到的目的地
    """
    cities = sorted(CITY_CENTERS.keys(), key=len, reverse=True)

    # 0) 天气咨询句式："X的天气/气温/温度/冷不冷/下雨/下雪/降温/几度…"
    #    不依赖手写城市表，任何地级市/区县名都能提取
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
        cand = clean_place(m0.group(1))
        if cand and cand not in _WEATHER_CITY_STOP and len(cand) >= 2:
            return cand

    # 1) "去/到/来/前往 X"句式（最强信号：支持长地名 + 行政区划清洗）
    m = re.search(
        r"(?:去|到|来|前往|飞往|想去|要去|出发去|打算去)\s*"
        r"([\u4e00-\u9fa5]{2,14}?)(?=的|玩|旅游|旅行|度假|耍|逛|待|天|\d|[，,。！？!?]|$)",
        text,
    )
    if m:
        cleaned = clean_place(m.group(1))
        if cleaned:
            return cleaned

    # 2) 城市表直接命中（取最后一个，通常是目的地）
    hits = [c for c in cities if c in text]
    if hits:
        return hits[-1]

    # 3) "在 X 玩 / 想 X 玩"
    m2 = re.search(r"(?:在|想)\s*([\u4e00-\u9fa5]{2,10}?)(?:玩|旅游|度假|逛逛)", text)
    if m2:
        cleaned = clean_place(m2.group(1))
        if cleaned:
            return cleaned
    return ""
