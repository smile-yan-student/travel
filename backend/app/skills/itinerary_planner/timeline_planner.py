"""
时间规划模块（P1-1 独立时间规划阶段）

整合游览时长估算、开放时间检查、交通时间计算、时间线模板为统一模块。

核心能力：
1. 游览时长估算：基于景点类型、规模、人群、推荐时长
2. 开放时间检查：使用POI的open_hours字段，避免在闭馆时间安排景点
3. 交通时间计算：景点之间的移动时间估算（基于距离和出行方式）
4. 时间线模板：早/中/晚时间段分配，用餐时间、休息时间、时间窗口

使用方式：
    from .timeline_planner import TimelinePlanner
    planner = TimelinePlanner(req)
    items = planner.plan_day(items, day_no=1)
"""

import math
from typing import List, Dict, Any, Optional

from ...data.models.models import PlanRequest, PlanItem


class TimelinePlanner:
    """
    统一时间规划器（P1-1）

    整合游览时长估算、开放时间检查、交通时间计算、时间线模板。
    """

    # 时间线模板：不同节奏的时间窗口
    PACE_CONFIG = {
        "轻松": {"start": "09:00", "end": "18:00", "max_items": 3, "break_interval": 90},
        "适中": {"start": "08:30", "end": "20:00", "max_items": 5, "break_interval": 120},
        "紧凑": {"start": "08:00", "end": "21:00", "max_items": 7, "break_interval": 150},
    }

    # 用餐时间
    LUNCH_START = 12 * 60  # 12:00
    LUNCH_END = 13 * 60    # 13:00
    DINNER_START = 18 * 60 # 18:00
    DINNER_END = 19 * 60   # 19:00

    # 景点类型默认游览时长（分钟）
    DEFAULT_DURATION = {
        "景点": 120,
        "美食": 60,
        "购物": 90,
        "夜生活": 90,
        "住宿": 0,
        "交通": 0,
    }

    # 大型景区默认游览时长
    LARGE_SCENIC_DURATION = {
        "5A": 240,
        "4A": 180,
        "3A": 120,
        "世界遗产": 300,
        "博物馆": 150,
        "公园": 120,
        "古镇": 180,
    }

    def __init__(self, req: PlanRequest):
        """
        初始化时间规划器。

        Args:
            req: 规划请求（包含节奏、出行方式、人群等参数）
        """
        self.req = req
        self.pace = req.pace or "适中"
        self.traffic_mode = req.traffic_mode or "公共交通"
        self.group_type = req.group_type or "单人"

        # 根据节奏获取时间配置
        pace_config = self.PACE_CONFIG.get(self.pace, self.PACE_CONFIG["适中"])
        self.daily_start = req.daily_start_time or pace_config["start"]
        self.daily_end = req.daily_end_time or pace_config["end"]
        self.max_items = pace_config["max_items"]
        self.break_interval = pace_config["break_interval"]

        # 解析时间窗口
        sh, sm = map(int, self.daily_start.split(":"))
        eh, em = map(int, self.daily_end.split(":"))
        self.window_start = sh * 60 + sm
        self.window_end = eh * 60 + em

    def estimate_duration(self, poi: Dict[str, Any]) -> int:
        """
        估算景点游览时长（P1-1 核心能力1）。

        基于景点类型、规模、人群、推荐时长综合估算。

        优先级：
        1. POI的recommended_duration字段（如果有）
        2. LLM优化的llm_duration字段（如果有）
        3. 大型景区等级对应的默认时长
        4. 景点类型对应的默认时长
        5. 人群调整（亲子/老人增加时长，情侣/朋友减少时长）

        Args:
            poi: 景点信息字典

        Returns:
            推荐游览时长（分钟）
        """
        # 1. 优先使用POI的推荐时长
        if poi.get("recommended_duration"):
            try:
                return int(poi["recommended_duration"])
            except (ValueError, TypeError):
                pass

        # 2. 使用LLM优化的时长
        if poi.get("llm_duration"):
            try:
                return int(poi["llm_duration"])
            except (ValueError, TypeError):
                pass

        # 3. 大型景区等级对应的默认时长
        level = poi.get("level", "") or poi.get("scenic_level", "")
        if level and level in self.LARGE_SCENIC_DURATION:
            duration = self.LARGE_SCENIC_DURATION[level]
        else:
            # 4. 景点类型对应的默认时长
            category = poi.get("category", "") or poi.get("type", "")
            duration = self.DEFAULT_DURATION.get(category, 120)

        # 5. 人群调整
        group_adjust = {
            "亲子": 1.2,   # 亲子增加20%时长
            "老人": 1.3,   # 老人增加30%时长
            "家庭": 1.1,   # 家庭增加10%时长
            "情侣": 0.9,   # 情侣减少10%时长
            "朋友": 0.95,  # 朋友减少5%时长
            "单人": 1.0,   # 单人不变
        }
        adjust = group_adjust.get(self.group_type, 1.0)
        duration = int(duration * adjust)

        # 6. 必去景点增加时长
        if poi.get("must_visit") or poi.get("is_must_visit") or poi.get("is_protected"):
            duration = int(duration * 1.2)

        # 7. 边界限制：最少30分钟，最多480分钟（8小时）
        duration = max(30, min(480, duration))

        return duration

    def check_open_hours(self, poi: Dict[str, Any], start_time_min: int) -> Dict[str, Any]:
        """
        检查景点开放时间（P1-1 核心能力2）。

        使用POI的open_hours字段，避免在闭馆时间安排景点。

        Args:
            poi: 景点信息字典
            start_time_min: 计划开始时间（分钟，从0点开始计算）

        Returns:
            检查结果字典：
            - is_open: 是否开放
            - open_time: 开放时间（字符串）
            - close_time: 关闭时间（字符串）
            - note: 备注
            - suggested_time: 建议调整后的时间（如果需要调整）
        """
        # 默认结果
        result = {
            "is_open": True,
            "open_time": "",
            "close_time": "",
            "note": "",
            "suggested_time": start_time_min,
        }

        # 获取开放时间信息
        open_hours = poi.get("open_hours", [])
        if not open_hours:
            return result

        # 解析开放时间
        try:
            if isinstance(open_hours, list) and len(open_hours) > 0:
                first = open_hours[0]
                if isinstance(first, dict):
                    result["open_time"] = first.get("open", "")
                    result["close_time"] = first.get("close", "")
                    result["note"] = first.get("note", "")

                    # 解析开放和关闭时间
                    if result["open_time"] and ":" in result["open_time"]:
                        oh, om = map(int, result["open_time"].split(":")[:2])
                        open_min = oh * 60 + om
                        if start_time_min < open_min:
                            result["suggested_time"] = open_min
                            result["note"] = f"景点{result['open_time']}开放，建议调整到开放后"

                    if result["close_time"] and ":" in result["close_time"]:
                        ch, cm = map(int, result["close_time"].split(":")[:2])
                        close_min = ch * 60 + cm
                        duration = self.estimate_duration(poi)
                        if start_time_min + duration > close_min:
                            result["is_open"] = False
                            result["note"] = f"景点{result['close_time']}闭馆，当前时间安排可能无法完成游览"
        except Exception:
            pass

        return result

    def estimate_transit_time(self, from_poi: Dict[str, Any], to_poi: Dict[str, Any]) -> int:
        """
        估算景点之间的交通时间（P1-1 核心能力3）。

        基于距离和出行方式估算交通时间。

        Args:
            from_poi: 起点景点
            to_poi: 终点景点

        Returns:
            估算交通时间（分钟）
        """
        # 获取坐标
        from_lat = from_poi.get("lat") or from_poi.get("latitude")
        from_lng = from_poi.get("lng") or from_poi.get("longitude")
        to_lat = to_poi.get("lat") or to_poi.get("latitude")
        to_lng = to_poi.get("lng") or to_poi.get("longitude")

        # 如果没有坐标，返回默认时间
        if not all([from_lat, from_lng, to_lat, to_lng]):
            return 30

        # 计算距离（公里）
        try:
            distance = self._haversine(float(from_lat), float(from_lng), float(to_lat), float(to_lng))
        except (ValueError, TypeError):
            return 30

        # 根据出行方式估算速度（公里/小时）
        speed_config = {
            "自驾": 40,      # 城市内自驾平均速度
            "公共交通": 25,   # 公交地铁平均速度（含等待）
            "骑行": 15,      # 骑行平均速度
            "步行": 5,       # 步行平均速度
            "混合": 30,      # 混合出行平均速度
        }
        speed = speed_config.get(self.traffic_mode, 25)

        # 计算时间（分钟）= 距离 / 速度 * 60
        transit_min = int(distance / speed * 60)

        # 加上固定的等待/换乘时间
        wait_time = {
            "自驾": 5,
            "公共交通": 15,
            "骑行": 3,
            "步行": 0,
            "混合": 10,
        }
        transit_min += wait_time.get(self.traffic_mode, 10)

        # 边界限制：最少5分钟，最多180分钟（3小时）
        transit_min = max(5, min(180, transit_min))

        return transit_min

    def _haversine(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """
        计算两点之间的球面距离（Haversine公式）。

        Args:
            lat1: 起点纬度
            lng1: 起点经度
            lat2: 终点纬度
            lng2: 终点经度

        Returns:
            距离（公里）
        """
        R = 6371  # 地球半径（公里）
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def plan_day(self, items: List[PlanItem], day_no: int = 1) -> List[PlanItem]:
        """
        规划一天的时间线（P1-1 核心能力4）。

        整合游览时长、开放时间、交通时间、时间线模板，生成合理的一天行程。

        时间线规则：
        1. 时间窗口：根据节奏配置（轻松/适中/紧凑）
        2. 用餐时间：午餐12:00-13:00，晚餐18:00-19:00
        3. 休息时间：每N小时休息15分钟（根据节奏配置）
        4. 开放时间：避免在闭馆时间安排景点
        5. 交通时间：景点之间的移动时间
        6. 时间超时：必去景点压缩时长，非必去景点跳过

        Args:
            items: 行程项列表
            day_no: 天数（用于开放时间检查）

        Returns:
            规划后的行程项列表（包含开始时间、时段、交通时间）
        """
        if not items:
            return items

        cur = self.window_start
        out: List[PlanItem] = []
        last_break_time = self.window_start

        for i, it in enumerate(items):
            # 1. 估算游览时长
            if it.poi:
                poi_dict = it.poi.model_dump() if hasattr(it.poi, 'model_dump') else dict(it.poi)
                estimated_duration = self.estimate_duration(poi_dict)
                if not it.duration_min or it.duration_min <= 0:
                    it.duration_min = estimated_duration

            # 2. 加上交通时间
            if i > 0 and it.poi and out and out[-1].poi:
                from_dict = out[-1].poi.model_dump() if hasattr(out[-1].poi, 'model_dump') else dict(out[-1].poi)
                to_dict = it.poi.model_dump() if hasattr(it.poi, 'model_dump') else dict(it.poi)
                transit_min = self.estimate_transit_time(from_dict, to_dict)
                it.transit_min = transit_min
                cur += transit_min

            # 3. 检查用餐时间
            is_meal_time = (self.LUNCH_START <= cur < self.LUNCH_END) or (self.DINNER_START <= cur < self.DINNER_END)
            is_food_item = it.poi and it.poi.category == "美食" if it.poi else False
            if is_meal_time and not is_food_item and out:
                if cur < self.LUNCH_END and cur >= self.LUNCH_START:
                    cur = self.LUNCH_END
                elif cur < self.DINNER_END and cur >= self.DINNER_START:
                    cur = self.DINNER_END

            # 4. 检查休息时间
            if cur - last_break_time >= self.break_interval and out:
                cur += 15
                last_break_time = cur

            # 5. 检查开放时间
            if it.poi:
                poi_dict = it.poi.model_dump() if hasattr(it.poi, 'model_dump') else dict(it.poi)
                open_check = self.check_open_hours(poi_dict, cur)
                if open_check["suggested_time"] > cur:
                    cur = open_check["suggested_time"]
                if not open_check["is_open"] and not (it.poi.must_visit or it.poi.hot):
                    # 非必去景点在闭馆时间，跳过
                    continue

            if cur < self.window_start:
                cur = self.window_start

            # 6. 检查时间是否超时
            if cur + it.duration_min > self.window_end:
                if not out:
                    cur = self.window_start
                else:
                    # 时间超时，检查是否是必去景点，如果是则尝试压缩时长
                    if it.poi and (it.poi.must_visit or it.poi.hot or it.poi.is_protected if hasattr(it.poi, 'is_protected') else False):
                        available_time = self.window_end - cur
                        if available_time >= 30:
                            it.duration_min = max(30, available_time)
                        else:
                            break
                    else:
                        break

            # 7. 设置开始时间和时段
            it.start_time = f"{cur // 60:02d}:{cur % 60:02d}"
            h = cur // 60
            it.slot = "上午" if h < 11 else ("中午" if h < 14 else ("下午" if h < 18 else "晚上"))

            # 8. 晚上不安排非必去景点
            if h >= 18 and it.poi and it.poi.category == "景点" and not (it.poi.must_visit or it.poi.hot):
                continue

            cur += it.duration_min
            out.append(it)

            # 9. 检查是否超过最大景点数量
            if len(out) >= self.max_items:
                break

        return out


# 便捷函数：创建时间规划器并规划一天
def plan_day_timeline(req: PlanRequest, items: List[PlanItem], day_no: int = 1) -> List[PlanItem]:
    """
    便捷函数：创建时间规划器并规划一天的时间线。

    Args:
        req: 规划请求
        items: 行程项列表
        day_no: 天数

    Returns:
        规划后的行程项列表
    """
    planner = TimelinePlanner(req)
    return planner.plan_day(items, day_no)
