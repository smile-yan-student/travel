"""
行程工作记忆（Itinerary Workspace）。

每个会话固定保存：当前完整行程JSON + 用户原始参数 + 用户历次修改偏好。
核心能力：所有修改都是「增量局部修改」，不全局重刷。

功能特性：
- 行程工作记忆（每个会话一个实例，保存完整行程状态和修改历史）
- 修改记录（单次修改记录，包含修改前后快照）
- 用户偏好（用户历次修改沉淀的偏好，隐性偏好学习的基础）
- 增量修改（所有修改都是「增量局部修改」，不全局重刷）
- 修改历史（按时间倒序，最新在前，只保留最近50条）
- 最近指令（最近N轮用户指令，用于增量修改的指代理解）

使用方式：
    from app.services.session.itinerary_workspace import (
        ItineraryWorkspace, ModificationRecord, UserPreferences
    )

    # 创建行程工作记忆
    workspace = ItineraryWorkspace(session_id="abc123")

    # 更新行程（全量替换，用于首次生成或全局重生成）
    workspace.update_plan(plan_dict)

    # 添加修改记录
    mod = ModificationRecord(
        mod_type="add_poi",
        description="添加西湖景点",
        target_day=1,
        target_poi="西湖",
        user_instruction="把西湖加进去"
    )
    workspace.add_modification(mod)

    # 获取指定天数的行程
    day_plan = workspace.get_day_plan(1)

    # 获取行程中所有POI
    pois = workspace.get_all_pois()

    # 获取行程中所有POI名称
    poi_names = workspace.get_poi_names()

    # 序列化为dict（用于存储和传输）
    data = workspace.to_dict()

    # 从dict反序列化
    workspace = ItineraryWorkspace.from_dict(data)

    # 获取工作记忆摘要（用于日志和调试）
    summary = workspace.summary()
"""
import time
import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ModificationRecord(BaseModel):
    """
    单次修改记录。

    记录每次修改的详细信息，包括修改类型、描述、目标、修改前后快照等。
    """

    mod_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: float = Field(default_factory=time.time)
    mod_type: str = ""  # pace_adjust / add_poi / remove_poi / replace_poi / add_food / remove_paid / theme_adjust / day_adjust / custom
    description: str = ""  # 用户可读的修改描述
    target_day: Optional[int] = None  # 修改目标天数（None表示全局）
    target_poi: Optional[str] = None  # 修改目标POI名称
    before_snapshot: Dict[str, Any] = Field(default_factory=dict)  # 修改前快照（关键部分）
    after_snapshot: Dict[str, Any] = Field(default_factory=dict)  # 修改后快照（关键部分）
    user_instruction: str = ""  # 用户原始指令


class UserPreferences(BaseModel):
    """
    用户历次修改沉淀的偏好（隐性偏好学习的基础）。

    记录用户在多次修改中表现出的偏好，用于后续行程生成和优化。
    """

    pace_preference: Optional[str] = None  # 轻松/适中/暴走
    food_preference: Optional[str] = None  # 多加美食/正常/少美食
    paid_attitude: Optional[str] = None  # 去掉收费/正常/必去收费
    early_rise_preference: Optional[bool] = None  # 是否爱早起
    theme_preferences: List[str] = Field(default_factory=list)  # 人文/自然/美食/网红/小众等
    crowd_preference: Optional[str] = None  # 避开人流/正常/热门优先
    transport_preference: Optional[str] = None  # 自驾/公共交通/步行/混合
    custom_notes: List[str] = Field(default_factory=list)  # 用户自定义偏好备注


class ItineraryWorkspace(BaseModel):
    """
    行程工作记忆（核心）。

    每个会话一个实例，保存完整行程状态和修改历史。
    所有修改都是「增量局部修改」，不全局重刷。
    """

    session_id: str = ""
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)

    # 用户原始参数（首次生成时的参数）
    original_params: Dict[str, Any] = Field(default_factory=dict)

    # 当前完整行程（PlanResponse的dict形式）
    current_plan: Dict[str, Any] = Field(default_factory=dict)

    # 用户历次修改沉淀的偏好
    preferences: UserPreferences = Field(default_factory=UserPreferences)

    # 修改历史记录（按时间倒序，最新在前）
    modification_history: List[ModificationRecord] = Field(default_factory=list)

    # 行程状态：draft / generated / modified / finalized
    status: str = "draft"

    # 生成来源：ai / rule / hybrid
    source: str = ""

    # 对话上下文（最近N轮用户指令，用于增量修改的指代理解）
    recent_instructions: List[str] = Field(default_factory=list)

    def add_modification(self, mod: ModificationRecord) -> None:
        """
        添加修改记录。

        Args:
            mod: 修改记录
        """
        self.modification_history.insert(0, mod)
        self.updated_at = time.time()
        self.status = "modified"
        # 只保留最近50条修改记录
        if len(self.modification_history) > 50:
            self.modification_history = self.modification_history[:50]

    def add_instruction(self, instruction: str) -> None:
        """
        添加用户指令到最近上下文。

        Args:
            instruction: 用户指令
        """
        self.recent_instructions.append(instruction)
        if len(self.recent_instructions) > 20:
            self.recent_instructions = self.recent_instructions[-20:]

    def update_plan(self, plan_dict: Dict[str, Any]) -> None:
        """
        更新当前行程（全量替换，用于首次生成或全局重生成）。

        Args:
            plan_dict: 行程字典
        """
        self.current_plan = plan_dict
        self.updated_at = time.time()
        if self.status == "draft":
            self.status = "generated"

    def get_day_plan(self, day: int) -> Optional[Dict[str, Any]]:
        """
        获取指定天数的行程。

        Args:
            day: 天数

        Returns:
            Optional[Dict[str, Any]]: 当天行程，不存在返回 None
        """
        for dp in self.current_plan.get("day_plans", []):
            if dp.get("day") == day:
                return dp
        return None

    def get_all_pois(self) -> List[Dict[str, Any]]:
        """
        获取行程中所有POI。

        Returns:
            List[Dict[str, Any]]: POI列表
        """
        pois = []
        for dp in self.current_plan.get("day_plans", []):
            for item in dp.get("items", []):
                if item.get("poi"):
                    pois.append(item["poi"])
        return pois

    def get_poi_names(self) -> List[str]:
        """
        获取行程中所有POI名称（用于去重和指代理解）。

        Returns:
            List[str]: POI名称列表
        """
        return [p.get("name", "") for p in self.get_all_pois()]

    def to_dict(self) -> Dict[str, Any]:
        """
        序列化为dict（用于存储和传输）。

        Returns:
            Dict[str, Any]: 序列化后的字典
        """
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ItineraryWorkspace":
        """
        从dict反序列化。

        Args:
            data: 字典数据

        Returns:
            ItineraryWorkspace: 行程工作记忆实例
        """
        return cls(**data)

    def summary(self) -> Dict[str, Any]:
        """
        工作记忆摘要（用于日志和调试）。

        Returns:
            Dict[str, Any]: 摘要信息
        """
        return {
            "session_id": self.session_id,
            "status": self.status,
            "destination": self.current_plan.get("destination", ""),
            "days": self.current_plan.get("days", 0),
            "total_pois": len(self.get_all_pois()),
            "modification_count": len(self.modification_history),
            "last_modified": self.updated_at,
        }
