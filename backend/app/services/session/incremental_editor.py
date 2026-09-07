"""
增量修改器（Incremental Editor）。

核心能力：所有修改都是「增量局部修改」，不全局重刷。
用户说"节奏慢一点""多加美食""去掉收费景点"，只改动对应区块，保留用户之前的调整。

功能特性：
- 支持多种局部修改操作（节奏调整、增加POI、删除POI、替换POI、增加美食、去掉收费景点、调整主题、调整天数、重排顺序）
- 修改快照（只记录相关部分，便于回滚和对比）
- 修改记录（保存修改历史，支持用户偏好学习）
- 用户偏好更新（隐性偏好学习，从修改行为中学习用户偏好）
- 全局单例

支持的修改操作：
- pace_adjust: 调整节奏（轻松/适中/暴走）
- add_poi: 增加POI到指定天
- remove_poi: 删除指定POI
- replace_poi: 替换POI
- add_food: 增加美食点位（就近插入到中午或晚上）
- remove_paid: 去掉收费景点
- theme_adjust: 调整旅行主题/风格
- day_adjust: 调整天数（增加或减少）
- reorder_day: 重排某天的行程顺序

使用方式：
    from app.services.session.incremental_editor import get_incremental_editor

    # 获取全局增量修改器单例
    editor = get_incremental_editor()

    # 应用增量修改
    success, message, workspace = editor.apply_modification(
        workspace=workspace,
        mod_type="pace_adjust",
        params={"pace": "轻松"},
        user_instruction="节奏慢一点"
    )

    if success:
        print(f"修改成功: {message}")
    else:
        print(f"修改失败: {message}")
"""
import copy
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from .itinerary_workspace import ItineraryWorkspace, ModificationRecord


class IncrementalEditor:
    """
    增量修改器。

    支持多种局部修改操作，每种操作只修改行程的对应部分，不全局重生成。
    """

    def __init__(self) -> None:
        """初始化增量修改器，注册支持的修改操作。"""
        self.supported_operations: Dict[str, Callable] = {
            "pace_adjust": self._adjust_pace,
            "add_poi": self._add_poi,
            "remove_poi": self._remove_poi,
            "replace_poi": self._replace_poi,
            "add_food": self._add_food,
            "remove_paid": self._remove_paid_attractions,
            "theme_adjust": self._adjust_theme,
            "day_adjust": self._adjust_days,
            "reorder_day": self._reorder_day_items,
        }

    def apply_modification(
        self,
        workspace: ItineraryWorkspace,
        mod_type: str,
        params: Dict[str, Any],
        user_instruction: str = "",
    ) -> Tuple[bool, str, ItineraryWorkspace]:
        """
        应用增量修改。

        Args:
            workspace: 行程工作记忆
            mod_type: 修改类型
            params: 修改参数
            user_instruction: 用户原始指令

        Returns:
            Tuple[bool, str, ItineraryWorkspace]: (是否成功, 描述信息, 修改后的工作记忆)
        """
        if mod_type not in self.supported_operations:
            return False, f"不支持的修改类型: {mod_type}", workspace

        # 保存修改前快照
        before_snapshot = self._take_snapshot(workspace, mod_type, params)

        # 执行修改
        success, message = self.supported_operations[mod_type](workspace, params)

        if success:
            # 保存修改后快照
            after_snapshot = self._take_snapshot(workspace, mod_type, params)
            # 记录修改
            record = ModificationRecord(
                mod_type=mod_type,
                description=message,
                target_day=params.get("day"),
                target_poi=params.get("poi_name"),
                before_snapshot=before_snapshot,
                after_snapshot=after_snapshot,
                user_instruction=user_instruction,
            )
            workspace.add_modification(record)
            # 更新用户偏好
            self._update_preferences(workspace, mod_type, params)

        return success, message, workspace

    def _take_snapshot(
        self,
        workspace: ItineraryWorkspace,
        mod_type: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        拍摄修改快照（只记录相关部分）。

        Args:
            workspace: 行程工作记忆
            mod_type: 修改类型
            params: 修改参数

        Returns:
            Dict[str, Any]: 快照数据
        """
        snapshot: Dict[str, Any] = {}
        day = params.get("day")
        if day:
            day_plan = workspace.get_day_plan(day)
            if day_plan:
                snapshot["day_plan"] = copy.deepcopy(day_plan)
        else:
            # 全局修改，记录所有天的POI列表
            snapshot["all_pois"] = [
                {
                    "day": dp.get("day"),
                    "pois": [
                        item.get("poi", {}).get("name")
                        for item in dp.get("items", [])
                    ],
                }
                for dp in workspace.current_plan.get("day_plans", [])
            ]
        return snapshot

    def _update_preferences(
        self,
        workspace: ItineraryWorkspace,
        mod_type: str,
        params: Dict[str, Any],
    ) -> None:
        """
        根据修改更新用户偏好（隐性偏好学习）。

        Args:
            workspace: 行程工作记忆
            mod_type: 修改类型
            params: 修改参数
        """
        prefs = workspace.preferences
        if mod_type == "pace_adjust":
            pace = params.get("pace")
            if pace:
                prefs.pace_preference = pace
        elif mod_type == "add_food":
            prefs.food_preference = "多加美食"
        elif mod_type == "remove_paid":
            prefs.paid_attitude = "去掉收费"
        elif mod_type == "theme_adjust":
            theme = params.get("theme")
            if theme and theme not in prefs.theme_preferences:
                prefs.theme_preferences.append(theme)

    # ========== 具体修改操作 ==========

    def _adjust_pace(
        self, workspace: ItineraryWorkspace, params: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        调整节奏。

        Args:
            workspace: 行程工作记忆
            params: 修改参数 {pace: "轻松"/"适中"/"暴走", day: Optional[int]}

        Returns:
            Tuple[bool, str]: (是否成功, 描述信息)
        """
        pace = params.get("pace", "适中")
        target_day = params.get("day")
        day_plans = workspace.current_plan.get("day_plans", [])

        adjusted_days = []
        for dp in day_plans:
            if target_day and dp.get("day") != target_day:
                continue
            items = dp.get("items", [])
            if pace == "轻松":
                # 轻松：减少景点数量，增加每个景点停留时间
                if len(items) > 3:
                    dp["items"] = items[:3]
                for item in dp["items"]:
                    item["duration_min"] = max(item.get("duration_min", 120), 150)
                dp["tip"] = "轻松节奏，留足休息和拍照时间"
            elif pace == "暴走":
                # 暴走：增加景点数量，减少停留时间
                for item in dp["items"]:
                    item["duration_min"] = max(item.get("duration_min", 120) - 30, 60)
                dp["tip"] = "紧凑节奏，高效打卡更多景点"
            else:
                dp["tip"] = "适中节奏，平衡游览和休息"
            adjusted_days.append(dp.get("day"))

        workspace.current_plan["pace"] = pace
        message = f"节奏已调整为「{pace}」"
        if target_day:
            message += f"（第{target_day}天）"
        return True, message

    def _add_poi(
        self, workspace: ItineraryWorkspace, params: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        增加POI到指定天。

        Args:
            workspace: 行程工作记忆
            params: 修改参数 {poi: POI dict, day: int, slot: Optional[str]}

        Returns:
            Tuple[bool, str]: (是否成功, 描述信息)
        """
        poi = params.get("poi")
        day = params.get("day")
        slot = params.get("slot", "下午")
        if not poi or not day:
            return False, "缺少POI或天数参数"

        day_plan = workspace.get_day_plan(day)
        if not day_plan:
            return False, f"第{day}天不存在"

        # 检查是否已存在
        existing_names = [
            item.get("poi", {}).get("name") for item in day_plan.get("items", [])
        ]
        if poi.get("name") in existing_names:
            return False, f"「{poi.get('name')}」已在第{day}天行程中"

        # 创建新的PlanItem
        new_item = {
            "slot": slot,
            "start_time": "",
            "poi": poi,
            "duration_min": 120,
            "transport": "",
            "transit_min": 0,
            "distance_m": 0,
            "note": "用户添加",
        }
        day_plan["items"].append(new_item)
        # 重新按slot排序
        slot_order = {"上午": 0, "中午": 1, "下午": 2, "晚上": 3}
        day_plan["items"].sort(
            key=lambda x: slot_order.get(x.get("slot", "下午"), 2)
        )

        return True, f"已将「{poi.get('name')}」添加到第{day}天{slot}"

    def _remove_poi(
        self, workspace: ItineraryWorkspace, params: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        删除指定POI。

        Args:
            workspace: 行程工作记忆
            params: 修改参数 {poi_name: str, day: Optional[int]}

        Returns:
            Tuple[bool, str]: (是否成功, 描述信息)
        """
        poi_name = params.get("poi_name")
        target_day = params.get("day")
        if not poi_name:
            return False, "缺少POI名称参数"

        removed_from = []
        for dp in workspace.current_plan.get("day_plans", []):
            if target_day and dp.get("day") != target_day:
                continue
            before_count = len(dp.get("items", []))
            dp["items"] = [
                item
                for item in dp.get("items", [])
                if item.get("poi", {}).get("name") != poi_name
            ]
            if len(dp["items"]) < before_count:
                removed_from.append(dp.get("day"))

        if not removed_from:
            return False, f"未找到「{poi_name}」"
        return True, f"已从第{', '.join(map(str, removed_from))}天删除「{poi_name}」"

    def _replace_poi(
        self, workspace: ItineraryWorkspace, params: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        替换POI。

        Args:
            workspace: 行程工作记忆
            params: 修改参数 {old_poi_name: str, new_poi: POI dict, day: Optional[int]}

        Returns:
            Tuple[bool, str]: (是否成功, 描述信息)
        """
        old_name = params.get("old_poi_name")
        new_poi = params.get("new_poi")
        target_day = params.get("day")
        if not old_name or not new_poi:
            return False, "缺少旧POI名称或新POI参数"

        replaced = False
        for dp in workspace.current_plan.get("day_plans", []):
            if target_day and dp.get("day") != target_day:
                continue
            for item in dp.get("items", []):
                if item.get("poi", {}).get("name") == old_name:
                    item["poi"] = new_poi
                    item["note"] = f"由「{old_name}」替换"
                    replaced = True

        if not replaced:
            return False, f"未找到「{old_name}」"
        return True, f"已将「{old_name}」替换为「{new_poi.get('name')}」"

    def _add_food(
        self, workspace: ItineraryWorkspace, params: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        增加美食点位（就近插入到中午或晚上）。

        Args:
            workspace: 行程工作记忆
            params: 修改参数 {food_pois: List[POI], day: Optional[int]}

        Returns:
            Tuple[bool, str]: (是否成功, 描述信息)
        """
        food_pois = params.get("food_pois", [])
        target_day = params.get("day")
        if not food_pois:
            return False, "缺少美食POI参数"

        added_count = 0
        for dp in workspace.current_plan.get("day_plans", []):
            if target_day and dp.get("day") != target_day:
                continue
            # 找到中午和晚上的位置插入美食
            for food in food_pois[:2]:  # 每天最多加2个美食
                food_item = {
                    "slot": "中午" if added_count % 2 == 0 else "晚上",
                    "start_time": "",
                    "poi": food,
                    "duration_min": 90,
                    "transport": "",
                    "transit_min": 0,
                    "distance_m": 0,
                    "note": "美食推荐",
                }
                dp["items"].append(food_item)
                added_count += 1
            # 重新排序
            slot_order = {"上午": 0, "中午": 1, "下午": 2, "晚上": 3}
            dp["items"].sort(
                key=lambda x: slot_order.get(x.get("slot", "下午"), 2)
            )

        return True, f"已添加{added_count}个美食推荐"

    def _remove_paid_attractions(
        self, workspace: ItineraryWorkspace, params: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        去掉收费景点。

        Args:
            workspace: 行程工作记忆
            params: 修改参数 {day: Optional[int]}

        Returns:
            Tuple[bool, str]: (是否成功, 描述信息)
        """
        target_day = params.get("day")
        removed = []
        for dp in workspace.current_plan.get("day_plans", []):
            if target_day and dp.get("day") != target_day:
                continue
            before_items = dp.get("items", [])
            # 去掉收费景点：category为"景点"且price>0的item
            dp["items"] = [
                item
                for item in before_items
                if not (
                    item.get("poi", {}).get("category", "") == "景点"
                    and item.get("poi", {}).get("price", 0) > 0
                )
            ]
            removed.extend(
                [
                    item.get("poi", {}).get("name")
                    for item in before_items
                    if item not in dp["items"]
                ]
            )

        if not removed:
            return True, "行程中没有收费景点，无需调整"
        return True, f"已去掉收费景点：{', '.join(removed[:5])}"

    def _adjust_theme(
        self, workspace: ItineraryWorkspace, params: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        调整旅行主题/风格。

        Args:
            workspace: 行程工作记忆
            params: 修改参数 {theme: str, day: Optional[int]}

        Returns:
            Tuple[bool, str]: (是否成功, 描述信息)
        """
        theme = params.get("theme")
        if not theme:
            return False, "缺少主题参数"
        workspace.current_plan["style"] = theme
        return True, f"旅行风格已调整为「{theme}」"

    def _adjust_days(
        self, workspace: ItineraryWorkspace, params: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        调整天数（增加或减少）。

        Args:
            workspace: 行程工作记忆
            params: 修改参数 {days: int}

        Returns:
            Tuple[bool, str]: (是否成功, 描述信息)
        """
        days = params.get("days")
        if not days or days < 1:
            return False, "无效的天数参数"

        current_days = len(workspace.current_plan.get("day_plans", []))
        if days == current_days:
            return True, "天数无需调整"

        if days < current_days:
            # 减少天数：保留前N天
            workspace.current_plan["day_plans"] = workspace.current_plan[
                "day_plans"
            ][:days]
            message = f"已将行程从{current_days}天缩减为{days}天"
        else:
            # 增加天数：复制最后一天的结构（需要后续填充内容）
            last_day = (
                workspace.current_plan["day_plans"][-1]
                if workspace.current_plan.get("day_plans")
                else None
            )
            for i in range(current_days, days):
                new_day = {
                    "day": i + 1,
                    "theme": f"第{i+1}天",
                    "date_label": "",
                    "items": [],
                    "budget": 0,
                    "tip": "待规划",
                    "inspiration": "",
                    "hotel": None,
                }
                workspace.current_plan["day_plans"].append(new_day)
            message = f"已将行程从{current_days}天扩展为{days}天（新增天数待填充内容）"

        workspace.current_plan["days"] = days
        return True, message

    def _reorder_day_items(
        self, workspace: ItineraryWorkspace, params: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        重排某天的行程顺序。

        Args:
            workspace: 行程工作记忆
            params: 修改参数 {day: int, item_order: List[int]}  # item_order是原索引的新顺序

        Returns:
            Tuple[bool, str]: (是否成功, 描述信息)
        """
        day = params.get("day")
        item_order = params.get("item_order")
        if not day or not item_order:
            return False, "缺少天数或顺序参数"

        day_plan = workspace.get_day_plan(day)
        if not day_plan:
            return False, f"第{day}天不存在"

        items = day_plan.get("items", [])
        if max(item_order) >= len(items):
            return False, "顺序索引超出范围"

        day_plan["items"] = [items[i] for i in item_order]
        return True, f"第{day}天行程顺序已调整"


# 全局单例
_editor: Optional[IncrementalEditor] = None


def get_incremental_editor() -> IncrementalEditor:
    """
    获取全局增量修改器单例。

    Returns:
        IncrementalEditor: 全局增量修改器单例
    """
    global _editor
    if _editor is None:
        _editor = IncrementalEditor()
    return _editor
