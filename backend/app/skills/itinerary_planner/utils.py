"""
行程规划引擎 - 工具函数与常量。

从 planner.py 抽出的独立工具函数，不依赖其他规划模块。

功能特性：
- 时段排序（上午/中午/下午/晚上）
- 预算档位（经济/适中/舒适/奢华）
- 节奏控制（轻松/适中/暴走）
- 人群节奏修正（亲子/老人/单人/情侣/家庭/朋友）
- 旅程叙事（出发宣言 & 每日寄语，激发行走天下的勇气）
- POI 工具函数（是否停业/关闭、是否为顶级地标、综合评分、平均评分）
- 子景点去除（同一大景区内的小景点，保留主景区）

使用方式：
    from app.services.planner.utils import (
        SLOT_ORDER, SLOT_TIME, BUDGET_TABLE, PACE_ITEMS, GROUP_PACE,
        departure_message, daily_inspiration,
        is_closed, is_landmark, rank, avg_rank, drop_sub_venues
    )

    # 获取出发宣言
    message = departure_message("杭州", 3)
    print(message)  # 世界很大，从杭州出发——这一步，就是行走天下的开始。

    # 获取每日寄语
    inspiration = daily_inspiration("西湖", 1)
    print(inspiration)  # 出发，是解决一切犹豫的办法。

    # 检查POI是否停业
    is_closed_poi = is_closed(poi)

    # 检查是否为顶级地标
    is_landmark_poi = is_landmark(poi)

    # 获取POI综合评分
    poi_rank = rank(poi)

    # 获取POI列表平均评分
    avg = avg_rank(pois)

    # 去除子景点
    main_pois = drop_sub_venues(pois)
"""
from typing import Any, Dict, List

from .constants import CLOSED_MARKERS, LANDMARK_WORDS

# 时段排序
SLOT_ORDER = {"上午": 0, "中午": 1, "下午": 2, "晚上": 3}
SLOT_TIME = {"上午": "09:00", "中午": "12:00", "下午": "14:00", "晚上": "19:00"}

# 预算档位：每天人均参考（元）[餐饮/顿, 住宿/晚, 交通/天]
BUDGET_TABLE = {
    "经济": {"food": 30, "hotel": 150, "transport": 30},
    "适中": {"food": 80, "hotel": 400, "transport": 60},
    "舒适": {"food": 150, "hotel": 800, "transport": 120},
    "奢华": {"food": 300, "hotel": 1500, "transport": 200},
}

# 节奏 → 每天点位数量
PACE_ITEMS = {"轻松": 3, "适中": 4, "暴走": 5}
# 人群 → 节奏修正
GROUP_PACE = {
    "亲子": "轻松",
    "老人": "轻松",
    "单人": "适中",
    "情侣": "适中",
    "家庭": "适中",
    "朋友": "暴走",
}

# ---- 旅程叙事：出发宣言 & 每日寄语（激发行走天下的勇气） ----
DEPARTURE_MESSAGES = [
    "世界很大，从{dest}出发——这一步，就是行走天下的开始。",
    "你要去的{dest}，正等着你的脚步。出发吧，勇气都在路上。",
    "旅行最好的开始，就是你决定出发的这一刻。{dest}见。",
    "别怕远方太远，{dest}会告诉你：世界值得去看看。",
    "带上好奇，去见{dest}——每一次出发，都在把世界变成自己的地图。",
]
DAILY_INSPIRATIONS = [
    "出发，是解决一切犹豫的办法。",
    "你走过的路，会成为你看世界的底气。",
    "今天的每一步，都在把远方拉近。",
    "去发现，去感受，去成为那个勇敢出发的人。",
    "世界不只在你听说的故事里，也在你脚下。",
    "别等有空，出发本身就是答案。",
    "远方不远，勇气就在今天。",
    "去走一走陌生的路，世界会还你新的自己。",
]


def pick(items: List[str], seed: str) -> str:
    """
    按种子稳定选取一条文案（同目的地/同主题始终同一句）。

    Args:
        items: 文案列表
        seed: 种子（用于稳定选取）

    Returns:
        str: 选取的文案
    """
    return items[abs(hash(seed)) % len(items)]


def departure_message(destination: str, days: int) -> str:
    """
    获取出发宣言。

    Args:
        destination: 目的地
        days: 天数

    Returns:
        str: 出发宣言
    """
    return pick(DEPARTURE_MESSAGES, destination).format(dest=destination)


def daily_inspiration(theme: str, day_no: int) -> str:
    """
    获取每日寄语。

    Args:
        theme: 主题
        day_no: 天数

    Returns:
        str: 每日寄语
    """
    return pick(DAILY_INSPIRATIONS, f"{theme}:{day_no}")


def is_closed(p: Dict[str, Any]) -> bool:
    """
    POI 是否停业/关闭。

    Args:
        p: POI信息

    Returns:
        bool: 是否停业/关闭
    """
    name = p.get("name") or ""
    return any(m in name for m in CLOSED_MARKERS)


def is_landmark(p: Dict[str, Any]) -> bool:
    """
    是否为顶级地标（城市名片级地标：type 标「世界遗产」或名称命中全国知名地标特征词）。

    Args:
        p: POI信息

    Returns:
        bool: 是否为顶级地标
    """
    t = p.get("type") or ""
    if "世界遗产" in t:
        return True
    name = p.get("name") or ""
    return any(w in name for w in LANDMARK_WORDS)


def rank(p: Dict[str, Any]) -> float:
    """
    POI 综合评分（rating + 权重）。

    Args:
        p: POI信息

    Returns:
        float: 综合评分
    """
    r = float(p.get("rating", 0) or 0)
    # 顶级地标加分
    if is_landmark(p):
        r = max(r, 4.5)
    return r


def _rank(p: Dict[str, Any]) -> float:
    """
    排序用评分：真实 rating + 地标加成（must_visit +0.3 / hot 热门 +0.1）。

    Args:
        p: POI信息

    Returns:
        float: 排序用评分
    """
    bonus = 0.3 if p.get("must_visit") else (0.1 if p.get("hot") else 0.0)
    return (p.get("rating") or 0) + bonus


def avg_rank(pois: List[Dict[str, Any]]) -> float:
    """
    POI 列表平均评分。

    Args:
        pois: POI列表

    Returns:
        float: 平均评分
    """
    if not pois:
        return 0
    return sum(rank(p) for p in pois) / len(pois)


def _avg_rank(pois: List[Dict[str, Any]]) -> float:
    """
    POI 列表平均评分（avg_rank的别名，保持向后兼容）。

    Args:
        pois: POI列表

    Returns:
        float: 平均评分
    """
    return avg_rank(pois)


def drop_sub_venues(pois: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    去除子景点（同一大景区内的小景点，保留主景区）。

    Args:
        pois: POI列表

    Returns:
        List[Dict[str, Any]]: 去除子景点后的POI列表
    """
    if len(pois) <= 1:
        return pois
    # 按名称去重：短名称包含长名称时，保留短名称（主景区）
    sorted_pois = sorted(pois, key=lambda p: len(p.get("name", "")))
    result = []
    used_names = set()
    for p in sorted_pois:
        name = p.get("name", "")
        # 检查是否是已保留景点的子景点
        is_sub = any(
            name != kept and (name.startswith(kept) or kept in name)
            for kept in used_names
        )
        if not is_sub:
            result.append(p)
            used_names.add(name)
    return result
