"""
多策略规划配置（Multi-Strategy Planning Configuration）。

定义8种规划策略，每种策略有不同的景点筛选规则、时间分配、节奏控制、
点位类型比例、必去景点优先级等。

策略列表：
1. classic（经典打卡）- 必去景点全覆盖，知名地标优先
2. deep（深度体验）- 小众景点+当地生活，深度文化体验
3. leisure（休闲度假）- 慢节奏+舒适住宿，轻松游玩
4. family（亲子友好）- 儿童景点+安全考虑，互动体验
5. couple（情侣浪漫）- 浪漫景点+私密体验，氛围优先
6. photography（摄影之旅）- 最佳机位+黄金时间，出片优先
7. food（美食之旅）- 特色餐厅+当地小吃，美食为主
8. culture（历史文化）- 博物馆+古迹+讲解，文化深度

使用方式：
    from app.skills.itinerary_planner.strategy import get_strategy_config
    
    # 根据style获取策略配置
    config = get_strategy_config("classic")
    
    # 获取点位类型比例
    ratio = config["poi_ratio"]
    
    # 获取每天景点数量
    items_per_day = config["items_per_day"]
"""
from typing import Any, Dict, List, Optional


# 策略配置定义
STRATEGY_CONFIGS: Dict[str, Dict[str, Any]] = {
    # 1. 经典打卡
    "classic": {
        "name": "经典打卡",
        "description": "必去景点全覆盖，知名地标优先，适合首次到访",
        "poi_ratio": {
            "attraction": 0.75,  # 景点占比
            "food": 0.15,        # 美食占比
            "shopping": 0.05,    # 购物占比
            "nightlife": 0.05,   # 夜生活占比
        },
        "items_per_day": {
            "relaxed": 3,
            "moderate": 4,
            "compact": 5,
        },
        "must_visit_priority": 1.0,      # 必去景点优先级（0-1，越高越优先）
        "major_attraction_weight": 1.0,   # 主要景点权重
        "high_rating_threshold": 4.5,     # 高评分阈值
        "prefer_famous": True,             # 偏好知名景点
        "prefer_5a": True,                 # 偏好5A景区
        "prefer_world_heritage": True,     # 偏好世界遗产
        "duration_per_attraction": 120,    # 每个景点建议时长（分钟）
        "rest_between_attractions": 30,    # 景点间休息时间（分钟）
        "meal_duration": 90,                # 用餐时长（分钟）
        "start_time": "08:30",             # 每日开始时间
        "end_time": "20:00",               # 每日结束时间
        "include_night_view": True,         # 包含夜景
        "include_local_food": True,         # 包含当地特色美食
        "tags_preference": ["地标", "必去", "知名", "5A", "世界遗产"],
        "tags_avoid": [],
    },

    # 2. 深度体验
    "deep": {
        "name": "深度体验",
        "description": "小众景点+当地生活，深度文化体验，适合重复到访",
        "poi_ratio": {
            "attraction": 0.60,
            "food": 0.20,
            "shopping": 0.10,
            "nightlife": 0.10,
        },
        "items_per_day": {
            "relaxed": 2,
            "moderate": 3,
            "compact": 4,
        },
        "must_visit_priority": 0.5,
        "major_attraction_weight": 0.6,
        "high_rating_threshold": 4.3,
        "prefer_famous": False,
        "prefer_5a": False,
        "prefer_world_heritage": False,
        "duration_per_attraction": 180,
        "rest_between_attractions": 45,
        "meal_duration": 120,
        "start_time": "09:00",
        "end_time": "21:00",
        "include_night_view": True,
        "include_local_food": True,
        "tags_preference": ["小众", "文艺", "当地", "特色", "深度", "文化"],
        "tags_avoid": ["游客多", "商业化"],
    },

    # 3. 休闲度假
    "leisure": {
        "name": "休闲度假",
        "description": "慢节奏+舒适住宿，轻松游玩，适合放松身心",
        "poi_ratio": {
            "attraction": 0.50,
            "food": 0.25,
            "shopping": 0.15,
            "nightlife": 0.10,
        },
        "items_per_day": {
            "relaxed": 2,
            "moderate": 3,
            "compact": 3,
        },
        "must_visit_priority": 0.6,
        "major_attraction_weight": 0.7,
        "high_rating_threshold": 4.2,
        "prefer_famous": True,
        "prefer_5a": False,
        "prefer_world_heritage": False,
        "duration_per_attraction": 150,
        "rest_between_attractions": 60,
        "meal_duration": 120,
        "start_time": "09:30",
        "end_time": "19:30",
        "include_night_view": False,
        "include_local_food": True,
        "tags_preference": ["休闲", "放松", "舒适", "美景", "温泉", "度假"],
        "tags_avoid": ["爬山", "徒步", "体力消耗大"],
    },

    # 4. 亲子友好
    "family": {
        "name": "亲子友好",
        "description": "儿童景点+安全考虑，互动体验，适合带孩子出行",
        "poi_ratio": {
            "attraction": 0.65,
            "food": 0.20,
            "shopping": 0.10,
            "nightlife": 0.05,
        },
        "items_per_day": {
            "relaxed": 2,
            "moderate": 3,
            "compact": 4,
        },
        "must_visit_priority": 0.7,
        "major_attraction_weight": 0.8,
        "high_rating_threshold": 4.4,
        "prefer_famous": True,
        "prefer_5a": True,
        "prefer_world_heritage": False,
        "duration_per_attraction": 120,
        "rest_between_attractions": 45,
        "meal_duration": 90,
        "start_time": "09:00",
        "end_time": "19:00",
        "include_night_view": False,
        "include_local_food": True,
        "tags_preference": ["亲子", "儿童", "互动", "科普", "乐园", "动物园", "海洋馆"],
        "tags_avoid": ["危险", "高空", "刺激", "不适合儿童"],
    },

    # 5. 情侣浪漫
    "couple": {
        "name": "情侣浪漫",
        "description": "浪漫景点+私密体验，氛围优先，适合情侣出行",
        "poi_ratio": {
            "attraction": 0.55,
            "food": 0.25,
            "shopping": 0.10,
            "nightlife": 0.10,
        },
        "items_per_day": {
            "relaxed": 2,
            "moderate": 3,
            "compact": 4,
        },
        "must_visit_priority": 0.6,
        "major_attraction_weight": 0.7,
        "high_rating_threshold": 4.5,
        "prefer_famous": True,
        "prefer_5a": False,
        "prefer_world_heritage": False,
        "duration_per_attraction": 150,
        "rest_between_attractions": 45,
        "meal_duration": 120,
        "start_time": "09:30",
        "end_time": "21:30",
        "include_night_view": True,
        "include_local_food": True,
        "tags_preference": ["浪漫", "情侣", "夜景", "私密", "美景", "日落", "星空"],
        "tags_avoid": ["亲子", "儿童", "人多嘈杂"],
    },

    # 6. 摄影之旅
    "photography": {
        "name": "摄影之旅",
        "description": "最佳机位+黄金时间，出片优先，适合摄影爱好者",
        "poi_ratio": {
            "attraction": 0.80,
            "food": 0.10,
            "shopping": 0.05,
            "nightlife": 0.05,
        },
        "items_per_day": {
            "relaxed": 3,
            "moderate": 4,
            "compact": 5,
        },
        "must_visit_priority": 0.8,
        "major_attraction_weight": 0.9,
        "high_rating_threshold": 4.6,
        "prefer_famous": True,
        "prefer_5a": True,
        "prefer_world_heritage": True,
        "duration_per_attraction": 90,
        "rest_between_attractions": 30,
        "meal_duration": 60,
        "start_time": "06:00",  # 早起拍日出
        "end_time": "21:00",    # 晚归拍日落/夜景
        "include_night_view": True,
        "include_local_food": False,
        "tags_preference": ["摄影", "机位", "日出", "日落", "夜景", "全景", "光影"],
        "tags_avoid": ["室内", "禁止拍照"],
    },

    # 7. 美食之旅
    "food": {
        "name": "美食之旅",
        "description": "特色餐厅+当地小吃，美食为主，适合美食爱好者",
        "poi_ratio": {
            "attraction": 0.35,
            "food": 0.50,
            "shopping": 0.10,
            "nightlife": 0.05,
        },
        "items_per_day": {
            "relaxed": 4,
            "moderate": 5,
            "compact": 6,
        },
        "must_visit_priority": 0.4,
        "major_attraction_weight": 0.5,
        "high_rating_threshold": 4.3,
        "prefer_famous": False,
        "prefer_5a": False,
        "prefer_world_heritage": False,
        "duration_per_attraction": 60,
        "rest_between_attractions": 30,
        "meal_duration": 90,
        "start_time": "09:00",
        "end_time": "22:00",
        "include_night_view": True,
        "include_local_food": True,
        "tags_preference": ["美食", "小吃", "特色", "老字号", "网红", "本地"],
        "tags_avoid": ["连锁", "快餐"],
    },

    # 8. 历史文化
    "culture": {
        "name": "历史文化",
        "description": "博物馆+古迹+讲解，文化深度，适合文化爱好者",
        "poi_ratio": {
            "attraction": 0.80,
            "food": 0.15,
            "shopping": 0.03,
            "nightlife": 0.02,
        },
        "items_per_day": {
            "relaxed": 2,
            "moderate": 3,
            "compact": 4,
        },
        "must_visit_priority": 0.9,
        "major_attraction_weight": 0.95,
        "high_rating_threshold": 4.5,
        "prefer_famous": True,
        "prefer_5a": True,
        "prefer_world_heritage": True,
        "duration_per_attraction": 180,
        "rest_between_attractions": 30,
        "meal_duration": 75,
        "start_time": "08:30",
        "end_time": "19:00",
        "include_night_view": False,
        "include_local_food": True,
        "tags_preference": ["历史", "文化", "博物馆", "古迹", "遗址", "古建筑", "讲解"],
        "tags_avoid": ["娱乐", "购物", "现代"],
    },
}

# style参数到策略的映射
STYLE_TO_STRATEGY = {
    "人文": "culture",
    "历史": "culture",
    "文化": "culture",
    "自然": "classic",
    "风景": "classic",
    "亲子": "family",
    "家庭": "family",
    "儿童": "family",
    "情侣": "couple",
    "浪漫": "couple",
    "约会": "couple",
    "美食": "food",
    "吃货": "food",
    "吃": "food",
    "摄影": "photography",
    "拍照": "photography",
    "出片": "photography",
    "休闲": "leisure",
    "度假": "leisure",
    "放松": "leisure",
    "深度": "deep",
    "小众": "deep",
    "文艺": "deep",
    "打卡": "classic",
    "经典": "classic",
    "必去": "classic",
    "综合": "classic",
}


def get_strategy_config(strategy: str) -> Dict[str, Any]:
    """
    根据策略名称获取策略配置。

    Args:
        strategy: 策略名称（classic/deep/leisure/family/couple/photography/food/culture）

    Returns:
        Dict[str, Any]: 策略配置，找不到时返回经典打卡策略
    """
    return STRATEGY_CONFIGS.get(strategy, STRATEGY_CONFIGS["classic"])


def get_strategy_by_style(style: str) -> str:
    """
    根据style参数获取对应的策略名称。

    Args:
        style: 风格参数（人文/自然/亲子/情侣/美食/摄影/休闲/深度/打卡/综合等）

    Returns:
        str: 策略名称
    """
    return STYLE_TO_STRATEGY.get(style, "classic")


def get_all_strategies() -> List[Dict[str, Any]]:
    """
    获取所有策略列表。

    Returns:
        List[Dict[str, Any]]: 策略列表（包含名称、描述等）
    """
    return [
        {
            "key": key,
            "name": config["name"],
            "description": config["description"],
        }
        for key, config in STRATEGY_CONFIGS.items()
    ]


def apply_strategy_to_params(params: Dict[str, Any], strategy: str) -> Dict[str, Any]:
    """
    将策略配置应用到规划参数中。

    Args:
        params: 规划参数字典
        strategy: 策略名称

    Returns:
        Dict[str, Any]: 应用策略后的参数
    """
    config = get_strategy_config(strategy)
    result = params.copy()

    # 应用点位类型比例
    result["poi_ratio"] = config["poi_ratio"]

    # 应用每天景点数量（根据pace）
    pace = params.get("pace", "moderate")
    result["items_per_day"] = config["items_per_day"].get(pace, 4)

    # 应用必去景点优先级
    result["must_visit_priority"] = config["must_visit_priority"]

    # 应用主要景点权重
    result["major_attraction_weight"] = config["major_attraction_weight"]

    # 应用高评分阈值
    result["high_rating_threshold"] = config["high_rating_threshold"]

    # 应用时间设置
    result["start_time"] = config["start_time"]
    result["end_time"] = config["end_time"]

    # 应用时长设置
    result["duration_per_attraction"] = config["duration_per_attraction"]
    result["rest_between_attractions"] = config["rest_between_attractions"]
    result["meal_duration"] = config["meal_duration"]

    # 应用标签偏好
    result["tags_preference"] = config["tags_preference"]
    result["tags_avoid"] = config["tags_avoid"]

    # 应用偏好设置
    result["prefer_famous"] = config["prefer_famous"]
    result["prefer_5a"] = config["prefer_5a"]
    result["prefer_world_heritage"] = config["prefer_world_heritage"]
    result["include_night_view"] = config["include_night_view"]
    result["include_local_food"] = config["include_local_food"]

    return result
