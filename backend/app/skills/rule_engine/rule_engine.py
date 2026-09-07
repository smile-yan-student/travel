"""
行程规划规则引擎 - 核心规则模块

整合了完整的9阶段规划规则体系：
- 无上限参数兜底收束（时间、人数、预算）
- 人群影响比例（6种人群类型的影响点和比例）
- 出行方式灵活机制（影响强度、规划程度分级）
- 阶段2：景点检索与筛选规则
- 阶段3：景点聚类与分组规则
- 阶段4：按天分配与切分规则
- 阶段5：每日排序与时间线规则
- 阶段6：辅助点位与检视补充规则
"""

from typing import List, Dict, Optional, Tuple
import math

from app.constants import (
    MIN_DAYS, MAX_DAYS,
    GROUP_TYPES, GROUP_TYPE_KEYWORDS,
    BUDGET_KEYWORDS, STYLE_KEYWORDS, PACE_KEYWORDS, TRAFFIC_KEYWORDS,
)


# ============================================================
# 第一部分：无上限参数的兜底和收束规则
# ============================================================

class ParameterNormalizer:
    """参数规范化器 - 无上限参数的兜底和收束"""

    # 时间参数（从constants.py导入，保持一致性）
    MIN_DAYS = MIN_DAYS
    MAX_DAYS = MAX_DAYS

    # 人数参数
    MIN_TRAVELERS = 1
    MAX_TRAVELERS = 99

    # 预算档位
    BUDGET_LEVELS = ["经济", "适中", "舒适", "奢华"]
    DEFAULT_BUDGET = "适中"

    # 人群类型（从constants.py导入）
    GROUP_TYPES = GROUP_TYPES
    DEFAULT_GROUP_TYPE = "单人"

    # 节奏
    PACE_LEVELS = ["轻松", "适中", "暴走"]
    DEFAULT_PACE = "适中"

    # 出行方式
    TRAFFIC_MODES = ["自驾", "公共交通", "骑行", "步行", "混合"]
    DEFAULT_TRAFFIC_MODE = "公共交通"

    @classmethod
    def normalize_days(cls, days: int) -> int:
        """规范化天数 - 兜底和收束"""
        if days is None or days < cls.MIN_DAYS:
            return cls.MIN_DAYS
        if days > cls.MAX_DAYS:
            return cls.MAX_DAYS
        return days

    @classmethod
    def normalize_travelers(cls, travelers: int) -> int:
        """规范化人数 - 兜底和收束"""
        if travelers is None or travelers < cls.MIN_TRAVELERS:
            return cls.MIN_TRAVELERS
        if travelers > cls.MAX_TRAVELERS:
            return cls.MAX_TRAVELERS
        return travelers

    @classmethod
    def normalize_budget(cls, budget_level: str) -> str:
        """规范化预算档位 - 兜底和收束"""
        if not budget_level or budget_level not in cls.BUDGET_LEVELS:
            return cls.DEFAULT_BUDGET
        return budget_level

    @classmethod
    def normalize_group_type(cls, group_type: str) -> str:
        """规范化人群类型"""
        if not group_type or group_type not in cls.GROUP_TYPES:
            return cls.DEFAULT_GROUP_TYPE
        return group_type

    @classmethod
    def normalize_pace(cls, pace: str) -> str:
        """规范化节奏"""
        if not pace or pace not in cls.PACE_LEVELS:
            return cls.DEFAULT_PACE
        return pace

    @classmethod
    def normalize_traffic_mode(cls, traffic_mode: str) -> str:
        """规范化出行方式"""
        if not traffic_mode or traffic_mode not in cls.TRAFFIC_MODES:
            return cls.DEFAULT_TRAFFIC_MODE
        return traffic_mode

    @classmethod
    def normalize_all(cls, params: dict) -> dict:
        """规范化所有参数"""
        normalized = params.copy()
        normalized['days'] = cls.normalize_days(params.get('days', 3))
        normalized['travelers'] = cls.normalize_travelers(params.get('travelers', 1))
        normalized['budget_level'] = cls.normalize_budget(params.get('budget_level', '适中'))
        normalized['group_type'] = cls.normalize_group_type(params.get('group_type', '单人'))
        normalized['pace'] = cls.normalize_pace(params.get('pace', '适中'))
        normalized['traffic_mode'] = cls.normalize_traffic_mode(params.get('traffic_mode', '公共交通'))
        return normalized

    @classmethod
    def get_days_interval(cls, days: int) -> str:
        """获取天数区间描述"""
        if days == 1:
            return "单日游"
        elif days <= 3:
            return "短途游"
        elif days <= 7:
            return "中途游"
        else:
            return "长途游"

    @classmethod
    def get_travelers_interval(cls, travelers: int) -> str:
        """获取人数区间描述"""
        if travelers == 1:
            return "单人游"
        elif travelers == 2:
            return "双人游"
        elif travelers <= 4:
            return "小团体"
        elif travelers <= 10:
            return "中团体"
        else:
            return "大团体"


# ============================================================
# 第二部分：人群参数对出行规划的影响点
# ============================================================

class GroupInfluenceEngine:
    """人群影响引擎 - 6种人群类型的影响点和比例"""

    # 人群影响配置：主要景点比例、辅助景点比例、节奏、餐饮偏好、住宿偏好
    GROUP_CONFIG = {
        "单人": {
            "main_poi_ratio": 0.90,      # 主要景点比例
            "aux_poi_ratio": 0.10,       # 辅助景点比例
            "default_pace": "适中",       # 默认节奏
            "food_preference": "单人友好", # 餐饮偏好
            "hotel_preference": "经济型",  # 住宿偏好
            "traffic_preference": "公共交通", # 交通偏好
            "aux_categories": ["小众", "个性化", "独立书店", "咖啡馆", "艺术展览"],
        },
        "情侣": {
            "main_poi_ratio": 0.80,
            "aux_poi_ratio": 0.20,
            "default_pace": "适中",
            "food_preference": "浪漫餐厅",
            "hotel_preference": "精品/情侣酒店",
            "traffic_preference": "地铁/打车/特色交通",
            "aux_categories": ["浪漫", "网红", "夜景", "摩天轮", "湖边散步", "浪漫咖啡馆"],
        },
        "亲子": {
            "main_poi_ratio": 0.60,
            "aux_poi_ratio": 0.40,
            "default_pace": "轻松",
            "food_preference": "亲子餐厅",
            "hotel_preference": "亲子酒店/家庭房",
            "traffic_preference": "自驾/打车",
            "aux_categories": ["亲子", "游乐园", "动物园", "海洋馆", "科技馆", "儿童博物馆"],
        },
        "家庭": {
            "main_poi_ratio": 0.85,
            "aux_poi_ratio": 0.15,
            "default_pace": "适中",
            "food_preference": "全家友好",
            "hotel_preference": "家庭房/套房",
            "traffic_preference": "自驾/打车",
            "aux_categories": ["全家友好", "公园", "文化景点", "经典景点"],
        },
        "朋友": {
            "main_poi_ratio": 0.70,
            "aux_poi_ratio": 0.30,
            "default_pace": "暴走",
            "food_preference": "网红/特色",
            "hotel_preference": "经济型/青旅/民宿",
            "traffic_preference": "公共交通",
            "aux_categories": ["网红", "夜生活", "美食", "购物", "打卡"],
        },
        "老人": {
            "main_poi_ratio": 0.90,
            "aux_poi_ratio": 0.10,
            "default_pace": "轻松",
            "food_preference": "清淡/易消化",
            "hotel_preference": "舒适型/低楼层/有电梯",
            "traffic_preference": "自驾/打车",
            "aux_categories": ["平缓", "文化", "公园", "寺庙", "历史文化街区"],
        },
    }

    # 亲子友好的名胜古迹筛选标准
    FAMILY_FRIENDLY_CRITERIA = {
        "has_child_guide": "有儿童讲解或互动设施",
        "has_transport": "有缆车/游船等代步工具",
        "is_spacious": "场地开阔，不会过于拥挤",
        "has_rest_area": "有休息区和卫生间",
        "not_strenuous": "不会过于陡峭或需要大量体力",
    }

    # 老人友好的名胜古迹筛选标准
    ELDERLY_FRIENDLY_CRITERIA = {
        "has_wheelchair": "有轮椅通道或无障碍设施",
        "has_transport": "有缆车/游船等代步工具",
        "is_spacious": "场地开阔，不会过于拥挤",
        "has_rest_area": "有休息区和卫生间",
        "not_strenuous": "不会过于陡峭或需要大量体力",
        "has_shade": "有遮阳避雨的地方",
    }

    @classmethod
    def get_group_config(cls, group_type: str) -> dict:
        """获取人群配置"""
        return cls.GROUP_CONFIG.get(group_type, cls.GROUP_CONFIG["单人"])

    @classmethod
    def get_main_poi_ratio(cls, group_type: str) -> float:
        """获取主要景点比例"""
        config = cls.get_group_config(group_type)
        return config["main_poi_ratio"]

    @classmethod
    def get_aux_poi_ratio(cls, group_type: str) -> float:
        """获取辅助景点比例"""
        config = cls.get_group_config(group_type)
        return config["aux_poi_ratio"]

    @classmethod
    def get_default_pace(cls, group_type: str) -> str:
        """获取默认节奏"""
        config = cls.get_group_config(group_type)
        return config["default_pace"]

    @classmethod
    def get_aux_categories(cls, group_type: str) -> List[str]:
        """获取辅助景点类别"""
        config = cls.get_group_config(group_type)
        return config["aux_categories"]

    @classmethod
    def filter_pois_by_group(cls, pois: List[dict], group_type: str) -> Tuple[List[dict], List[dict]]:
        """
        按人群筛选景点，返回(主要景点, 辅助景点)
        
        根据人群类型，将景点分为主要景点和辅助景点：
        - 主要景点：名胜古迹、标志性景点（占70-90%）
        - 辅助景点：人群相关的景点（占10-40%）
        """
        main_pois = []
        aux_pois = []
        
        aux_categories = cls.get_aux_categories(group_type)
        
        for poi in pois:
            poi_type = poi.get("type", "")
            poi_name = poi.get("name", "")
            poi_tags = poi.get("tags", [])
            
            # 判断是否为辅助景点
            is_aux = False
            for cat in aux_categories:
                if cat in poi_type or cat in poi_name or cat in " ".join(poi_tags):
                    is_aux = True
                    break
            
            if is_aux:
                aux_pois.append(poi)
            else:
                main_pois.append(poi)
        
        return main_pois, aux_pois

    @classmethod
    def is_family_friendly(cls, poi: dict) -> bool:
        """判断是否为亲子友好景点"""
        # 简单判断：有儿童设施、有代步工具、场地开阔
        poi_name = poi.get("name", "")
        poi_type = poi.get("type", "")
        
        # 排除过于陡峭的景点
        not_strenuous = not any(kw in poi_name for kw in ["华山", "泰山", "黄山", "张家界", "爬山", "徒步"])
        
        # 有儿童设施或互动
        has_child = any(kw in poi_name + poi_type for kw in ["儿童", "亲子", "科技馆", "动物园", "海洋馆", "博物馆"])
        
        # 有代步工具
        has_transport = any(kw in poi_name + poi_type for kw in ["缆车", "游船", "观光车", "小火车"])
        
        return not_strenuous and (has_child or has_transport)

    @classmethod
    def is_elderly_friendly(cls, poi: dict) -> bool:
        """判断是否为老人友好景点"""
        poi_name = poi.get("name", "")
        poi_type = poi.get("type", "")
        
        # 排除过于陡峭的景点
        not_strenuous = not any(kw in poi_name for kw in ["华山", "泰山", "黄山", "张家界", "爬山", "徒步"])
        
        # 有无障碍设施
        has_accessibility = any(kw in poi_name + poi_type for kw in ["无障碍", "轮椅", "电梯"])
        
        # 有代步工具
        has_transport = any(kw in poi_name + poi_type for kw in ["缆车", "游船", "观光车", "小火车"])
        
        # 场地开阔
        is_spacious = any(kw in poi_name + poi_type for kw in ["公园", "广场", "湖", "园林", "古迹"])
        
        return not_strenuous and (has_accessibility or has_transport or is_spacious)

    @classmethod
    def adjust_pace_by_group(cls, group_type: str, pace: str = None) -> str:
        """根据人群调整节奏"""
        if pace and pace in ["轻松", "适中", "暴走"]:
            return pace
        return cls.get_default_pace(group_type)


# ============================================================
# 第三部分：出行方式影响的灵活机制
# ============================================================

class TrafficFlexibilityEngine:
    """出行方式灵活引擎 - 影响强度和规划程度分级"""

    # 影响强度分级
    IMPACT_STRONG = "强影响"
    IMPACT_MEDIUM = "中影响"
    IMPACT_WEAK = "弱影响"

    # 规划程度分级
    PLAN_DETAILED = "详细规划"
    PLAN_BRIEF = "简要规划"
    PLAN_NONE = "不规划"

    @classmethod
    def calculate_impact_score(cls, group_type: str, destination_type: str,
                                poi_distribution: str, days: int, budget_level: str) -> int:
        """
        计算影响强度得分（0-100分）
        
        维度权重：
        - 人群类型：30%
        - 目的地类型：25%
        - 景点分布：20%
        - 出行天数：15%
        - 预算档位：10%
        """
        # 人群类型得分
        group_scores = {"亲子": 100, "老人": 100, "家庭": 60, "朋友": 60, "单人": 20, "情侣": 20}
        group_score = group_scores.get(group_type, 20) * 0.30

        # 目的地类型得分
        dest_scores = {"郊区": 100, "山区": 100, "跨城": 100, "混合": 60, "市中心": 20}
        dest_score = dest_scores.get(destination_type, 20) * 0.25

        # 景点分布得分
        dist_scores = {"分散": 100, "中等分散": 60, "密集": 20}
        dist_score = dist_scores.get(poi_distribution, 20) * 0.20

        # 出行天数得分
        if days > 5:
            days_score = 100 * 0.15
        elif days >= 3:
            days_score = 60 * 0.15
        else:
            days_score = 20 * 0.15

        # 预算档位得分
        budget_scores = {"舒适": 100, "奢华": 100, "适中": 60, "经济": 20}
        budget_score = budget_scores.get(budget_level, 20) * 0.10

        total_score = int(group_score + dest_score + dist_score + days_score + budget_score)
        return min(100, max(0, total_score))

    @classmethod
    def get_impact_level(cls, score: int) -> str:
        """根据得分获取影响强度等级"""
        if score >= 70:
            return cls.IMPACT_STRONG
        elif score >= 40:
            return cls.IMPACT_MEDIUM
        else:
            return cls.IMPACT_WEAK

    @classmethod
    def calculate_plan_score(cls, group_type: str, traffic_mode: str,
                              destination_type: str, days: int) -> int:
        """
        计算规划程度得分（0-100分）
        
        维度权重：
        - 人群类型：30%
        - 出行方式：30%
        - 目的地类型：25%
        - 出行天数：15%
        """
        # 人群类型得分
        group_scores = {"亲子": 100, "老人": 100, "家庭": 60, "朋友": 60, "单人": 20, "情侣": 20}
        group_score = group_scores.get(group_type, 20) * 0.30

        # 出行方式得分
        traffic_scores = {"公共交通": 100, "混合": 60, "自驾": 20, "骑行": 60, "步行": 20}
        traffic_score = traffic_scores.get(traffic_mode, 60) * 0.30

        # 目的地类型得分
        dest_scores = {"郊区": 100, "山区": 100, "跨城": 100, "混合": 60, "市中心": 20}
        dest_score = dest_scores.get(destination_type, 20) * 0.25

        # 出行天数得分
        if days > 5:
            days_score = 100 * 0.15
        elif days >= 3:
            days_score = 60 * 0.15
        else:
            days_score = 20 * 0.15

        total_score = int(group_score + traffic_score + dest_score + days_score)
        return min(100, max(0, total_score))

    @classmethod
    def get_plan_level(cls, score: int) -> str:
        """根据得分获取规划程度等级"""
        if score >= 70:
            return cls.PLAN_DETAILED
        elif score >= 40:
            return cls.PLAN_BRIEF
        else:
            return cls.PLAN_NONE

    @classmethod
    def get_traffic_suggestion(cls, distance_m: float, group_type: str = "单人",
                                 budget_level: str = "适中") -> dict:
        """
        根据距离获取通行方式建议
        
        返回：{mode, duration_min, cost_yuan, description}
        """
        if distance_m < 500:
            return {
                "mode": "步行",
                "duration_min": max(1, int(distance_m / 80)),
                "cost_yuan": 0,
                "description": f"步行约{max(1, int(distance_m / 80))}分钟"
            }
        elif distance_m < 2000:
            return {
                "mode": "共享单车",
                "duration_min": max(3, int(distance_m / 200)),
                "cost_yuan": 2,
                "description": f"骑行约{max(3, int(distance_m / 200))}分钟，约2元"
            }
        elif distance_m < 5000:
            if budget_level in ["经济", "适中"]:
                return {
                    "mode": "地铁/公交",
                    "duration_min": max(10, int(distance_m / 400)),
                    "cost_yuan": 3,
                    "description": f"地铁/公交约{max(10, int(distance_m / 400))}分钟，约3元"
                }
            else:
                return {
                    "mode": "打车",
                    "duration_min": max(8, int(distance_m / 500)),
                    "cost_yuan": max(10, int(distance_m / 200)),
                    "description": f"打车约{max(8, int(distance_m / 500))}分钟，约{max(10, int(distance_m / 200))}元"
                }
        elif distance_m < 15000:
            return {
                "mode": "地铁/打车",
                "duration_min": max(20, int(distance_m / 600)),
                "cost_yuan": max(5, int(distance_m / 1000)),
                "description": f"地铁/打车约{max(20, int(distance_m / 600))}分钟"
            }
        elif distance_m < 30000:
            return {
                "mode": "地铁/打车/自驾",
                "duration_min": max(30, int(distance_m / 800)),
                "cost_yuan": max(10, int(distance_m / 1500)),
                "description": f"地铁/打车/自驾约{max(30, int(distance_m / 800))}分钟"
            }
        else:
            return {
                "mode": "自驾/高铁",
                "duration_min": max(45, int(distance_m / 1000)),
                "cost_yuan": max(30, int(distance_m / 2000)),
                "description": f"自驾/高铁约{max(45, int(distance_m / 1000))}分钟"
            }

    @classmethod
    def determine_destination_type(cls, center: dict, pois: List[dict]) -> str:
        """判断目的地类型（市中心/混合/郊区/山区/跨城）"""
        if not pois:
            return "市中心"
        
        # 计算景点与中心的平均距离
        distances = []
        for poi in pois:
            if 'lng' in poi and 'lat' in poi and 'lng' in center and 'lat' in center:
                dist = cls._haversine(center['lng'], center['lat'], poi['lng'], poi['lat'])
                distances.append(dist)
        
        if not distances:
            return "市中心"
        
        avg_dist = sum(distances) / len(distances)
        max_dist = max(distances)
        
        if max_dist > 50000:  # 50公里以上
            return "跨城"
        elif max_dist > 20000:  # 20公里以上
            return "郊区"
        elif avg_dist > 5000:  # 平均5公里以上
            return "混合"
        else:
            return "市中心"

    @classmethod
    def determine_poi_distribution(cls, pois: List[dict]) -> str:
        """判断景点分布（密集/中等分散/分散）"""
        if len(pois) < 2:
            return "密集"
        
        # 计算景点之间的平均距离
        distances = []
        for i in range(len(pois)):
            for j in range(i + 1, len(pois)):
                if 'lng' in pois[i] and 'lat' in pois[i] and 'lng' in pois[j] and 'lat' in pois[j]:
                    dist = cls._haversine(pois[i]['lng'], pois[i]['lat'], pois[j]['lng'], pois[j]['lat'])
                    distances.append(dist)
        
        if not distances:
            return "密集"
        
        avg_dist = sum(distances) / len(distances)
        
        if avg_dist < 2000:  # 平均2公里以内
            return "密集"
        elif avg_dist < 5000:  # 平均5公里以内
            return "中等分散"
        else:
            return "分散"

    @staticmethod
    def _haversine(lng1: float, lat1: float, lng2: float, lat2: float) -> float:
        """计算两点之间的距离（米）"""
        R = 6371000  # 地球半径（米）
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lng2 - lng1)
        
        a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c


# ============================================================
# 第四部分：阶段2 - 景点检索与筛选规则
# ============================================================

class AttractionFilterEngine:
    """景点筛选引擎 - 阶段2规则"""

    @staticmethod
    def resolve_same_name_destination(destination: str, geo: dict = None) -> dict:
        """
        同名地点处理 - 优先以目的地的地点为先
        
        返回：{resolved_name, admin_area, confidence}
        """
        # 简单实现：如果有geo信息，使用geo中的行政区域
        if geo and 'province' in geo:
            return {
                'resolved_name': destination,
                'admin_area': f"{geo.get('province', '')}{geo.get('city', '')}",
                'confidence': 'high'
            }
        return {
            'resolved_name': destination,
            'admin_area': '',
            'confidence': 'medium'
        }

    @staticmethod
    def filter_by_budget(pois: List[dict], budget_level: str) -> List[dict]:
        """按预算筛选景点"""
        if budget_level == "经济":
            # 优先免费/低价景点
            free_pois = [p for p in pois if float(p.get('price', 0) or 0) == 0]
            low_price_pois = [p for p in pois if 0 < float(p.get('price', 0) or 0) <= 50]
            return free_pois + low_price_pois[:len(free_pois) // 2]
        elif budget_level == "奢华":
            # 优先高品质景点
            high_rating = [p for p in pois if float(p.get('rating', 0) or 0) >= 4.5]
            return high_rating if high_rating else pois
        else:
            return pois

    @staticmethod
    def filter_hard_constraints(pois: List[dict], must_include: List[str] = None,
                                  exclude: List[str] = None) -> List[dict]:
        """硬性约束筛选"""
        result = pois
        
        # 排除景点
        if exclude:
            result = [p for p in result if p.get('name', '') not in exclude]
        
        # 必去景点保留（在后续步骤中优先）
        # 这里不过滤必去景点，只标记
        
        return result

    @staticmethod
    def is_in_china(poi: dict) -> bool:
        """判断是否在中国境内（统一使用geo_enum中的实现）"""
        try:
            from app.skills.itinerary_planner import is_in_china as _is_in_china_impl
            return _is_in_china_impl(poi)
        except ImportError:
            # 降级：简单判断经纬度在中国范围内
            lng = poi.get('lng', 0)
            lat = poi.get('lat', 0)
            return 73.0 <= lng <= 135.5 and 17.5 <= lat <= 54.0

    @staticmethod
    def is_closed(poi: dict) -> bool:
        """判断是否已关闭"""
        name = poi.get('name', '')
        poi_type = poi.get('type', '')
        return any(kw in (name + poi_type).lower()
                   for kw in ["已关闭", "停业", "拆", "搬迁", "不存在"])

    @classmethod
    def filter_all(cls, pois: List[dict], params: dict) -> Tuple[List[dict], List[dict]]:
        """
        综合筛选景点
        
        返回：(筛选后的景点, 被过滤的景点)
        """
        filtered = []
        removed = []
        
        budget_level = params.get('budget_level', '适中')
        must_include = params.get('must_include_poi', [])
        exclude = params.get('exclude_poi', [])
        
        for poi in pois:
            # 中国区域校验
            if not cls.is_in_china(poi):
                removed.append((poi, '不在中国境内'))
                continue
            
            # 开放状态校验
            if cls.is_closed(poi):
                removed.append((poi, '已关闭'))
                continue
            
            # 排除景点
            if exclude and poi.get('name', '') in exclude:
                removed.append((poi, '排除景点'))
                continue
            
            filtered.append(poi)
        
        # 按预算筛选
        filtered = cls.filter_by_budget(filtered, budget_level)
        
        return filtered, removed


# ============================================================
# 第五部分：阶段4 - 按天分配与切分规则（体验曲线、体力曲线）
# ============================================================

class DayAllocationEngine:
    """按天分配引擎 - 阶段4规则"""

    # 景点强度分级
    INTENSITY_HIGH = "高强度"
    INTENSITY_MEDIUM = "中强度"
    INTENSITY_LOW = "低强度"

    @classmethod
    def get_experience_curve(cls, day_no: int, total_days: int) -> str:
        """
        获取旅行体验曲线
        
        第1天：兴奋但疲劳 → 轻松入门
        第2-3天：体力充沛 → 核心景点
        第4-5天：体力下降 → 中等强度
        第6天+：疲劳累积 → 轻松收尾
        """
        if day_no == 1:
            return "轻松入门"
        elif day_no <= 3:
            return "核心景点"
        elif day_no <= 5:
            return "中等强度"
        else:
            return "轻松收尾"

    @classmethod
    def get_recommended_intensity(cls, day_no: int, total_days: int) -> str:
        """获取推荐的景点强度"""
        curve = cls.get_experience_curve(day_no, total_days)
        if curve == "轻松入门":
            return cls.INTENSITY_LOW
        elif curve == "核心景点":
            return cls.INTENSITY_HIGH
        elif curve == "中等强度":
            return cls.INTENSITY_MEDIUM
        else:  # 轻松收尾
            return cls.INTENSITY_LOW

    @classmethod
    def classify_poi_intensity(cls, poi: dict) -> str:
        """
        分类景点强度
        
        高强度：需要大量步行、爬山、耗时久
        中强度：中等步行、耗时中等
        低强度：少量步行、耗时短、可休息
        """
        name = poi.get('name', '')
        poi_type = poi.get('type', '')
        duration = poi.get('duration', 0)
        
        # 高强度关键词
        high_kw = ["长城", "泰山", "黄山", "华山", "张家界", "九寨沟", "爬山", "徒步", "大型景区", "故宫", "颐和园", "兵马俑"]
        # 低强度关键词
        low_kw = ["博物馆", "公园", "街区", "购物", "广场", "湖", "寺庙", "纪念馆", "美术馆"]
        
        if any(kw in name for kw in high_kw) or (isinstance(duration, (int, float)) and duration >= 240):
            return cls.INTENSITY_HIGH
        elif any(kw in name + poi_type for kw in low_kw) or (isinstance(duration, (int, float)) and duration <= 60):
            return cls.INTENSITY_LOW
        else:
            return cls.INTENSITY_MEDIUM

    @classmethod
    def check_intensity_alternation(cls, day_intensities: List[str]) -> bool:
        """
        检查强度交替规则
        
        - 高强度景点后必须安排低强度景点（休息恢复）
        - 最多连续2天中等强度
        - 每周最多1-2个高强度景点
        """
        if not day_intensities:
            return True
        
        # 检查连续高强度
        high_count = 0
        medium_count = 0
        for intensity in day_intensities:
            if intensity == cls.INTENSITY_HIGH:
                high_count += 1
                if high_count > 1:
                    return False  # 连续高强度
                medium_count = 0
            elif intensity == cls.INTENSITY_MEDIUM:
                medium_count += 1
                if medium_count > 2:
                    return False  # 连续3天中等强度
                high_count = 0
            else:  # 低强度
                high_count = 0
                medium_count = 0
        
        # 检查高强度数量（每周最多2个）
        total_high = day_intensities.count(cls.INTENSITY_HIGH)
        weeks = max(1, len(day_intensities) // 7)
        if total_high > 2 * weeks:
            return False
        
        return True

    @classmethod
    def allocate_clusters_to_days(cls, clusters: List[dict], total_days: int,
                                    center: dict = None) -> List[dict]:
        """
        将聚类分配到每天（基于体验曲线和体力曲线）
        
        返回：每天的聚类分配
        """
        if not clusters:
            return []
        
        # 为每个聚类计算强度
        for cluster in clusters:
            pois = cluster.get('pois', [])
            if pois:
                intensities = [cls.classify_poi_intensity(poi) for poi in pois]
                # 聚类强度取最高强度
                if cls.INTENSITY_HIGH in intensities:
                    cluster['intensity'] = cls.INTENSITY_HIGH
                elif cls.INTENSITY_MEDIUM in intensities:
                    cluster['intensity'] = cls.INTENSITY_MEDIUM
                else:
                    cluster['intensity'] = cls.INTENSITY_LOW
            else:
                cluster['intensity'] = cls.INTENSITY_LOW
        
        # 按评分排序
        sorted_clusters = sorted(clusters, key=lambda c: c.get('avg_rank', 0), reverse=True)
        
        # 分配到每天
        allocation = []
        high_clusters = [c for c in sorted_clusters if c['intensity'] == cls.INTENSITY_HIGH]
        medium_clusters = [c for c in sorted_clusters if c['intensity'] == cls.INTENSITY_MEDIUM]
        low_clusters = [c for c in sorted_clusters if c['intensity'] == cls.INTENSITY_LOW]
        
        for day_no in range(1, total_days + 1):
            recommended = cls.get_recommended_intensity(day_no, total_days)
            
            # 优先选择推荐强度的聚类
            selected = None
            if recommended == cls.INTENSITY_HIGH and high_clusters:
                selected = high_clusters.pop(0)
            elif recommended == cls.INTENSITY_MEDIUM and medium_clusters:
                selected = medium_clusters.pop(0)
            elif recommended == cls.INTENSITY_LOW and low_clusters:
                selected = low_clusters.pop(0)
            
            # 如果没有推荐强度的聚类，选择任意可用的
            if not selected:
                if high_clusters:
                    selected = high_clusters.pop(0)
                elif medium_clusters:
                    selected = medium_clusters.pop(0)
                elif low_clusters:
                    selected = low_clusters.pop(0)
            
            if selected:
                allocation.append({
                    'day_no': day_no,
                    'cluster': selected,
                    'recommended_intensity': recommended,
                    'actual_intensity': selected['intensity'],
                    'experience_curve': cls.get_experience_curve(day_no, total_days),
                })
        
        return allocation


# ============================================================
# 第六部分：阶段6 - 检视与补充规则
# ============================================================

class PlanReviewEngine:
    """行程检视引擎 - 阶段6规则"""

    @classmethod
    def review_plan(cls, day_plans: List[dict], params: dict) -> Tuple[bool, List[dict]]:
        """
        检视整体行程是否符合要求
        
        返回：(是否合格, 问题列表)
        """
        issues = []
        pace = params.get('pace', '适中')
        group_type = params.get('group_type', '单人')
        budget_level = params.get('budget_level', '适中')
        must_include = params.get('must_include_poi', [])
        
        # 每天景点数量
        expected_count = {"轻松": 3, "适中": 4, "暴走": 5}.get(pace, 4)
        for i, day_plan in enumerate(day_plans):
            pois = day_plan.get('pois', [])
            if len(pois) < expected_count - 1:
                issues.append({
                    'type': '景点数量不足',
                    'day': i + 1,
                    'current': len(pois),
                    'expected': expected_count,
                    'suggestion': f'第{i+1}天景点数量不足，建议增加{expected_count - len(pois)}个景点'
                })
            elif len(pois) > expected_count + 1:
                issues.append({
                    'type': '景点数量过多',
                    'day': i + 1,
                    'current': len(pois),
                    'expected': expected_count,
                    'suggestion': f'第{i+1}天景点数量过多，建议减少{len(pois) - expected_count}个景点'
                })
        
        # 必去景点检查
        all_poi_names = set()
        for day_plan in day_plans:
            for poi in day_plan.get('pois', []):
                all_poi_names.add(poi.get('name', ''))
        
        for must_poi in must_include:
            if must_poi not in all_poi_names:
                issues.append({
                    'type': '缺少必去景点',
                    'poi': must_poi,
                    'suggestion': f'行程中缺少必去景点：{must_poi}，建议添加'
                })
        
        # 跨天区域去重检查
        day_districts = []
        for day_plan in day_plans:
            districts = set()
            for poi in day_plan.get('pois', []):
                district = poi.get('district', '') or poi.get('adname', '')
                if district:
                    districts.add(district)
            day_districts.append(districts)
        
        for i in range(len(day_districts)):
            for j in range(i + 1, len(day_districts)):
                common = day_districts[i] & day_districts[j]
                if common and len(common) > len(day_districts[i]) * 0.5:
                    issues.append({
                        'type': '跨天区域重复',
                        'days': [i + 1, j + 1],
                        'districts': list(common),
                        'suggestion': f'第{i+1}天和第{j+1}天景点区域重复，建议调整'
                    })
        
        # 强度交替检查
        day_intensities = []
        for day_plan in day_plans:
            pois = day_plan.get('pois', [])
            if pois:
                # 简单判断：有大型景区则为高强度
                has_high = any(poi.get('is_large_scenic', False) for poi in pois)
                day_intensities.append('高强度' if has_high else '中强度')
            else:
                day_intensities.append('低强度')
        
        # 检查连续高强度
        for i in range(len(day_intensities) - 1):
            if day_intensities[i] == '高强度' and day_intensities[i + 1] == '高强度':
                issues.append({
                    'type': '连续高强度',
                    'days': [i + 1, i + 2],
                    'suggestion': f'第{i+1}天和第{i+2}天连续高强度，建议中间安排低强度景点休息'
                })
        
        is_valid = len(issues) == 0
        return is_valid, issues

    @classmethod
    def supplement_plan(cls, day_plans: List[dict], issues: List[dict],
                         candidate_pool: List[dict], used_poi_ids: set) -> List[dict]:
        """
        从候选景点池中补充景点
        
        返回：补充后的行程
        """
        if not issues or not candidate_pool:
            return day_plans
        
        # 按问题类型补充
        for issue in issues:
            issue_type = issue.get('type', '')
            
            if issue_type == '景点数量不足':
                day_no = issue.get('day', 1) - 1
                if day_no < len(day_plans):
                    needed = issue.get('expected', 4) - len(day_plans[day_no].get('pois', []))
                    supplementary = cls._pick_supplementary(candidate_pool, used_poi_ids, needed)
                    day_plans[day_no]['pois'].extend(supplementary)
                    for poi in supplementary:
                        used_poi_ids.add(poi.get('id', poi.get('name', '')))
            
            elif issue_type == '缺少必去景点':
                must_poi_name = issue.get('poi', '')
                # 找到必去景点
                must_poi = next((p for p in candidate_pool if p.get('name', '') == must_poi_name), None)
                if must_poi:
                    # 添加到评分最低的一天
                    min_day = min(range(len(day_plans)), key=lambda i: len(day_plans[i].get('pois', [])))
                    day_plans[min_day]['pois'].append(must_poi)
                    used_poi_ids.add(must_poi.get('id', must_poi.get('name', '')))
            
            elif issue_type == '连续高强度':
                # 在连续高强度之间添加低强度景点
                days = issue.get('days', [])
                if len(days) >= 2:
                    mid_day = days[0]  # 在第一天补充低强度
                    if mid_day - 1 < len(day_plans):
                        supplementary = cls._pick_supplementary(candidate_pool, used_poi_ids, 1, prefer_low=True)
                        if supplementary:
                            day_plans[mid_day - 1]['pois'].extend(supplementary)
                            for poi in supplementary:
                                used_poi_ids.add(poi.get('id', poi.get('name', '')))
        
        return day_plans

    @staticmethod
    def _pick_supplementary(candidate_pool: List[dict], used_ids: set, count: int,
                             prefer_low: bool = False) -> List[dict]:
        """从候选池中挑选补充景点"""
        available = [p for p in candidate_pool if p.get('id', p.get('name', '')) not in used_ids]
        
        if prefer_low:
            # 优先低强度景点
            low_kw = ["博物馆", "公园", "街区", "购物", "广场", "湖", "寺庙"]
            low_pois = [p for p in available if any(kw in p.get('name', '') + p.get('type', '') for kw in low_kw)]
            other_pois = [p for p in available if p not in low_pois]
            available = low_pois + other_pois
        
        # 按评分排序
        available.sort(key=lambda p: p.get('rating', 0), reverse=True)
        
        return available[:count]


# ============================================================
# 第七部分：规则引擎主入口
# ============================================================

class PlanningRuleEngine:
    """规划规则引擎 - 主入口"""

    def __init__(self):
        self.normalizer = ParameterNormalizer()
        self.validator = None  # 懒加载，避免循环导入
        self.group_engine = GroupInfluenceEngine()
        self.traffic_engine = TrafficFlexibilityEngine()
        self.filter_engine = AttractionFilterEngine()
        self.allocation_engine = DayAllocationEngine()
        self.review_engine = PlanReviewEngine()

    def _get_validator(self):
        """获取参数验证器（懒加载，避免循环导入）"""
        if self.validator is None:
            from .parameter_validator import ParameterValidator
            self.validator = ParameterValidator()
        return self.validator

    def normalize_params(self, params: dict) -> dict:
        """规范化参数（标准化/兜底/收束，不报错，直接修正）"""
        return self.normalizer.normalize_all(params)

    def validate_params(self, params: dict):
        """
        验证和纠正参数（验证/纠错，记录错误、警告和纠错记录）

        Args:
            params: 原始参数字典

        Returns:
            ValidationResult: 校验结果，包含纠正后的参数、错误、警告和纠错记录
        """
        return self._get_validator().validate_and_correct(params)

    def filter_attractions(self, pois: List[dict], params: dict) -> Tuple[List[dict], List[dict]]:
        """筛选景点"""
        return self.filter_engine.filter_all(pois, params)

    def allocate_to_days(self, clusters: List[dict], total_days: int, center: dict = None) -> List[dict]:
        """分配到每天"""
        return self.allocation_engine.allocate_clusters_to_days(clusters, total_days, center)

    def review_plan(self, day_plans: List[dict], params: dict) -> Tuple[bool, List[dict]]:
        """检视行程"""
        return self.review_engine.review_plan(day_plans, params)

    def supplement_plan(self, day_plans: List[dict], issues: List[dict],
                         candidate_pool: List[dict], used_poi_ids: set) -> List[dict]:
        """补充行程"""
        return self.review_engine.supplement_plan(day_plans, issues, candidate_pool, used_poi_ids)

    def calculate_traffic_impact(self, params: dict, center: dict, pois: List[dict]) -> dict:
        """计算出行方式影响强度和规划程度"""
        group_type = params.get('group_type', '单人')
        traffic_mode = params.get('traffic_mode', '公共交通')
        budget_level = params.get('budget_level', '适中')
        days = params.get('days', 3)

        destination_type = self.traffic_engine.determine_destination_type(center, pois)
        poi_distribution = self.traffic_engine.determine_poi_distribution(pois)

        impact_score = self.traffic_engine.calculate_impact_score(
            group_type, destination_type, poi_distribution, days, budget_level
        )
        impact_level = self.traffic_engine.get_impact_level(impact_score)

        plan_score = self.traffic_engine.calculate_plan_score(
            group_type, traffic_mode, destination_type, days
        )
        plan_level = self.traffic_engine.get_plan_level(plan_score)

        return {
            'impact_score': impact_score,
            'impact_level': impact_level,
            'plan_score': plan_score,
            'plan_level': plan_level,
            'destination_type': destination_type,
            'poi_distribution': poi_distribution,
        }

    def get_traffic_suggestion(self, distance_m: float, group_type: str = "单人",
                                budget_level: str = "适中") -> dict:
        """获取通行方式建议"""
        return self.traffic_engine.get_traffic_suggestion(distance_m, group_type, budget_level)


# 全局单例
_rule_engine = None

def get_rule_engine() -> PlanningRuleEngine:
    """获取规则引擎单例"""
    global _rule_engine
    if _rule_engine is None:
        _rule_engine = PlanningRuleEngine()
    return _rule_engine
