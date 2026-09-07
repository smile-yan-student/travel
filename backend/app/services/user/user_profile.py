"""
用户长期画像模块（User Profile）。

- 行为偏好自动学习：从用户的修改记录和行程历史中沉淀隐性偏好
- 跨行程记忆带入：下次规划时自动带入用户偏好，无需重复输入
- 用户画像持久化：存储在数据库中，按用户ID关联

功能特性：
- 用户偏好数据类（行程偏好、行为偏好、内容偏好、统计）
- 用户完整画像数据类（用户ID、用户名、偏好、创建时间、更新时间）
- 用户画像服务（获取、保存、学习、合并、摘要）
- 从规划参数中学习用户偏好
- 从用户修改行为中学习偏好
- 获取带用户偏好的规划参数（跨行程记忆带入）
- 获取用户画像摘要（用于前端展示）
- 计算画像完整度（0-100）
- 全局单例

使用方式：
    from app.services.user.user_profile import get_user_profile_service

    # 获取全局用户画像服务单例
    profile_service = get_user_profile_service()

    # 获取用户画像
    profile = profile_service.get_profile(user_id=1)

    # 保存用户画像
    success = profile_service.save_profile(profile)

    # 从规划参数中学习用户偏好
    profile = profile_service.learn_from_plan(
        user_id=1,
        plan_params={"destination": "杭州", "days": 3, "pace": "适中"}
    )

    # 从用户修改行为中学习偏好
    profile = profile_service.learn_from_modification(
        user_id=1,
        mod_type="pace_adjust",
        mod_params={"pace": "轻松"}
    )

    # 获取带用户偏好的规划参数
    merged_params = profile_service.get_plan_params_with_preferences(
        user_id=1,
        base_params={"destination": "北京"}
    )

    # 获取用户画像摘要
    summary = profile_service.get_profile_summary(user_id=1)
"""
import json
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class UserPreferences:
    """
    用户偏好（从行为中学习）。

    Attributes:
        pace_preference: 行程节奏（轻松/适中/暴走）
        budget_preference: 预算偏好（经济/适中/舒适/奢华）
        group_type: 出行人群（单人/情侣/亲子/家庭/朋友/老人）
        style_preferences: 旅行风格（人文/自然/美食/网红/小众等）
        traffic_preference: 出行方式（自驾/公共交通/骑行/步行/混合）
        early_rise: 是否爱早起
        food_lover: 是否喜欢美食
        paid_attitude: 收费景点态度（去掉收费/正常/必去收费）
        crowd_preference: 人流偏好（避开人流/正常/热门优先）
        physical_level: 体力水平（体力偏弱/正常/体力好）
        humanities_interest: 是否对人文历史感兴趣
        photography_interest: 是否喜欢拍照
        shopping_interest: 是否喜欢购物
        nightlife_interest: 是否喜欢夜生活
        total_plans: 总规划次数
        total_modifications: 总修改次数
        favorite_destinations: 常去目的地
        last_plan_time: 最后规划时间
        custom_notes: 自定义备注
    """

    # 行程偏好
    pace_preference: Optional[str] = None  # 轻松/适中/暴走
    budget_preference: Optional[str] = None  # 经济/适中/舒适/奢华
    group_type: Optional[str] = None  # 单人/情侣/亲子/家庭/朋友/老人
    style_preferences: List[str] = field(
        default_factory=list
    )  # 人文/自然/美食/网红/小众等
    traffic_preference: Optional[str] = None  # 自驾/公共交通/骑行/步行/混合

    # 行为偏好
    early_rise: Optional[bool] = None  # 是否爱早起
    food_lover: Optional[bool] = None  # 是否喜欢美食
    paid_attitude: Optional[str] = None  # 去掉收费/正常/必去收费
    crowd_preference: Optional[str] = None  # 避开人流/正常/热门优先
    physical_level: Optional[str] = None  # 体力偏弱/正常/体力好

    # 内容偏好
    humanities_interest: Optional[bool] = None  # 是否对人文历史感兴趣
    photography_interest: Optional[bool] = None  # 是否喜欢拍照
    shopping_interest: Optional[bool] = None  # 是否喜欢购物
    nightlife_interest: Optional[bool] = None  # 是否喜欢夜生活

    # 统计
    total_plans: int = 0  # 总规划次数
    total_modifications: int = 0  # 总修改次数
    favorite_destinations: List[str] = field(default_factory=list)  # 常去目的地
    last_plan_time: float = 0  # 最后规划时间

    # 自定义备注
    custom_notes: List[str] = field(default_factory=list)


@dataclass
class UserProfile:
    """
    用户完整画像。

    Attributes:
        user_id: 用户ID
        username: 用户名
        preferences: 用户偏好
        created_at: 创建时间
        updated_at: 更新时间
    """

    user_id: int
    username: str = ""
    preferences: UserPreferences = field(default_factory=UserPreferences)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典。

        Returns:
            Dict[str, Any]: 字典表示
        """
        return {
            "user_id": self.user_id,
            "username": self.username,
            "preferences": asdict(self.preferences),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserProfile":
        """
        从字典创建用户画像。

        Args:
            data: 字典数据

        Returns:
            UserProfile: 用户画像
        """
        prefs_data = data.get("preferences", {})
        return cls(
            user_id=data.get("user_id", 0),
            username=data.get("username", ""),
            preferences=UserPreferences(**prefs_data),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
        )


class UserProfileService:
    """
    用户画像服务。

    - 从用户行为中学习偏好
    - 跨行程记忆带入
    - 画像持久化
    """

    def __init__(self, storage_dir: str = "") -> None:
        """
        初始化用户画像服务。

        Args:
            storage_dir: 存储目录（默认为 data/user_profiles）
        """
        self.storage_dir = storage_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "data",
            "user_profiles",
        )
        os.makedirs(self.storage_dir, exist_ok=True)
        self._cache: Dict[int, UserProfile] = {}

    def _profile_path(self, user_id: int) -> str:
        """
        获取用户画像文件路径。

        Args:
            user_id: 用户ID

        Returns:
            str: 文件路径
        """
        return os.path.join(self.storage_dir, f"user_{user_id}.json")

    def get_profile(self, user_id: int) -> UserProfile:
        """
        获取用户画像（不存在则创建）。

        Args:
            user_id: 用户ID

        Returns:
            UserProfile: 用户画像
        """
        if user_id in self._cache:
            return self._cache[user_id]

        file_path = self._profile_path(user_id)
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                profile = UserProfile.from_dict(data)
            except Exception:
                profile = UserProfile(user_id=user_id)
        else:
            profile = UserProfile(user_id=user_id)

        self._cache[user_id] = profile
        return profile

    def save_profile(self, profile: UserProfile) -> bool:
        """
        保存用户画像。

        Args:
            profile: 用户画像

        Returns:
            bool: 是否成功
        """
        profile.updated_at = time.time()
        self._cache[profile.user_id] = profile
        try:
            file_path = self._profile_path(profile.user_id)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(profile.to_dict(), f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"[UserProfileService] 保存画像失败: {e}")
            return False

    def learn_from_plan(
        self, user_id: int, plan_params: Dict[str, Any]
    ) -> UserProfile:
        """
        从规划参数中学习用户偏好。

        Args:
            user_id: 用户ID
            plan_params: 规划参数（PlanRequest的dict）

        Returns:
            UserProfile: 更新后的用户画像
        """
        profile = self.get_profile(user_id)
        prefs = profile.preferences

        # 学习行程偏好
        if plan_params.get("pace"):
            prefs.pace_preference = plan_params["pace"]
        if plan_params.get("budget_level"):
            prefs.budget_preference = plan_params["budget_level"]
        if plan_params.get("group_type"):
            prefs.group_type = plan_params["group_type"]
        if plan_params.get("traffic_mode"):
            prefs.traffic_preference = plan_params["traffic_mode"]
        if plan_params.get("style"):
            styles = [
                s.strip() for s in plan_params["style"].split("+") if s.strip()
            ]
            for style in styles:
                if style not in prefs.style_preferences:
                    prefs.style_preferences.append(style)
            # 只保留最近的5个风格偏好
            prefs.style_preferences = prefs.style_preferences[-5:]

        # 学习目的地偏好
        destination = plan_params.get("destination", "")
        if destination and destination not in prefs.favorite_destinations:
            prefs.favorite_destinations.append(destination)
            # 只保留最近的10个目的地
            prefs.favorite_destinations = prefs.favorite_destinations[-10:]

        # 更新统计
        prefs.total_plans += 1
        prefs.last_plan_time = time.time()

        self.save_profile(profile)
        return profile

    def learn_from_modification(
        self, user_id: int, mod_type: str, mod_params: Dict[str, Any]
    ) -> UserProfile:
        """
        从用户修改行为中学习偏好。

        Args:
            user_id: 用户ID
            mod_type: 修改类型
            mod_params: 修改参数

        Returns:
            UserProfile: 更新后的用户画像
        """
        profile = self.get_profile(user_id)
        prefs = profile.preferences

        # 从修改类型学习偏好
        if mod_type == "pace_adjust":
            pace = mod_params.get("pace")
            if pace:
                prefs.pace_preference = pace
                if pace == "轻松":
                    prefs.physical_level = "体力偏弱"
                elif pace == "暴走":
                    prefs.physical_level = "体力好"
        elif mod_type == "add_food":
            prefs.food_lover = True
        elif mod_type == "remove_paid":
            prefs.paid_attitude = "去掉收费"
        elif mod_type == "theme_adjust":
            theme = mod_params.get("theme", "")
            if theme and theme not in prefs.style_preferences:
                prefs.style_preferences.append(theme)
                prefs.style_preferences = prefs.style_preferences[-5:]

        # 更新统计
        prefs.total_modifications += 1

        self.save_profile(profile)
        return profile

    def get_plan_params_with_preferences(
        self, user_id: int, base_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        获取带用户偏好的规划参数（跨行程记忆带入）。

        Args:
            user_id: 用户ID
            base_params: 基础规划参数

        Returns:
            Dict[str, Any]: 合并用户偏好后的规划参数
        """
        profile = self.get_profile(user_id)
        prefs = profile.preferences
        merged = dict(base_params)

        # 只在用户未明确指定时带入偏好
        if not merged.get("pace") and prefs.pace_preference:
            merged["pace"] = prefs.pace_preference
        if not merged.get("budget_level") and prefs.budget_preference:
            merged["budget_level"] = prefs.budget_preference
        if not merged.get("group_type") and prefs.group_type:
            merged["group_type"] = prefs.group_type
        if not merged.get("traffic_mode") and prefs.traffic_preference:
            merged["traffic_mode"] = prefs.traffic_preference

        # 风格偏好合并
        if not merged.get("style") and prefs.style_preferences:
            merged["style"] = "+".join(prefs.style_preferences[-2:])

        return merged

    def get_profile_summary(self, user_id: int) -> Dict[str, Any]:
        """
        获取用户画像摘要（用于前端展示）。

        Args:
            user_id: 用户ID

        Returns:
            Dict[str, Any]: 用户画像摘要
        """
        profile = self.get_profile(user_id)
        prefs = profile.preferences
        return {
            "user_id": profile.user_id,
            "username": profile.username,
            "preferences": {
                "pace": prefs.pace_preference,
                "budget": prefs.budget_preference,
                "group_type": prefs.group_type,
                "styles": prefs.style_preferences,
                "traffic": prefs.traffic_preference,
                "food_lover": prefs.food_lover,
                "humanities_interest": prefs.humanities_interest,
                "photography_interest": prefs.photography_interest,
            },
            "stats": {
                "total_plans": prefs.total_plans,
                "total_modifications": prefs.total_modifications,
                "favorite_destinations": prefs.favorite_destinations[-5:],
                "last_plan_time": prefs.last_plan_time,
            },
            "profile_completeness": self._calculate_completeness(prefs),
        }

    def _calculate_completeness(self, prefs: UserPreferences) -> int:
        """
        计算画像完整度（0-100）。

        Args:
            prefs: 用户偏好

        Returns:
            int: 完整度（0-100）
        """
        score = 0
        total = 10
        if prefs.pace_preference:
            score += 1
        if prefs.budget_preference:
            score += 1
        if prefs.group_type:
            score += 1
        if prefs.traffic_preference:
            score += 1
        if prefs.style_preferences:
            score += 1
        if prefs.food_lover is not None:
            score += 1
        if prefs.physical_level:
            score += 1
        if prefs.favorite_destinations:
            score += 1
        if prefs.total_plans > 0:
            score += 1
        return int(score / total * 100)


# 全局单例
_profile_service: Optional[UserProfileService] = None


def get_user_profile_service() -> UserProfileService:
    """
    获取全局用户画像服务单例。

    Returns:
        UserProfileService: 全局用户画像服务单例
    """
    global _profile_service
    if _profile_service is None:
        _profile_service = UserProfileService()
    return _profile_service
