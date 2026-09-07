"""
调用次数限制服务

功能特性：
- 按用户统计每日对话和规划调用次数
- 超过限制时拒绝调用
- 支持内存缓存（自动按天重置）
- 提供剩余次数查询接口

使用方式：
    from app.services.usage_limit import get_usage_limit_service
    
    service = get_usage_limit_service()
    
    # 检查是否可以调用
    can_call, remaining = service.check_chat_limit(user_id)
    if not can_call:
        raise HTTPException(status_code=429, detail="今日对话次数已用完")
    
    # 记录调用
    service.increment_chat_count(user_id)
"""
import time
from datetime import datetime
from typing import Dict, Optional, Tuple

from ..config import settings
from ..infrastructure import logger as log_mod

_usage_logger = log_mod.get_logger("usage_limit")


class UsageLimitService:
    """调用次数限制服务（支持用户级限制和全局限制）"""
    
    def __init__(self):
        # 用户级内存缓存：{user_id: {"date": "2026-08-31", "chat_count": 10, "plan_count": 5}}
        self._cache: Dict[str, Dict] = {}
        # 全局内存缓存：{"date": "2026-08-31", "chat_count": 100, "plan_count": 20}
        self._global_cache: Dict = {}
    
    @property
    def daily_chat_limit(self) -> int:
        """用户级每日对话次数上限（动态读取配置）"""
        return settings.ai.daily_chat_limit
    
    @property
    def daily_plan_limit(self) -> int:
        """用户级每日规划次数上限（动态读取配置）"""
        return settings.ai.daily_plan_limit
    
    @property
    def global_daily_chat_limit(self) -> int:
        """全局每日对话次数上限（动态读取配置）"""
        return settings.ai.global_daily_chat_limit
    
    @property
    def global_daily_plan_limit(self) -> int:
        """全局每日规划次数上限（动态读取配置）"""
        return settings.ai.global_daily_plan_limit
    
    def _get_today_str(self) -> str:
        """获取今天的日期字符串"""
        return datetime.now().strftime("%Y-%m-%d")
    
    def _get_user_data(self, user_id: str) -> Dict:
        """获取用户的调用数据（自动重置过期数据）"""
        today = self._get_today_str()
        user_data = self._cache.get(user_id)
        
        if user_data is None or user_data.get("date") != today:
            # 新用户或新的一天，重置计数
            user_data = {
                "date": today,
                "chat_count": 0,
                "plan_count": 0,
            }
            self._cache[user_id] = user_data
        
        return user_data
    
    def _get_global_data(self) -> Dict:
        """获取全局的调用数据（自动重置过期数据）"""
        today = self._get_today_str()
        global_data = self._global_cache
        
        if not global_data or global_data.get("date") != today:
            # 新的一天，重置全局计数
            global_data = {
                "date": today,
                "chat_count": 0,
                "plan_count": 0,
            }
            self._global_cache = global_data
        
        return global_data
    
    def check_chat_limit(self, user_id: str) -> Tuple[bool, int]:
        """
        检查对话调用次数是否超限（同时检查用户级和全局限制）
        
        Returns:
            (can_call, remaining): 是否可以调用，剩余次数（取用户级和全局限制的最小值）
        """
        # 检查用户级限制
        user_can_call = True
        user_remaining = -1
        if self.daily_chat_limit > 0:
            user_data = self._get_user_data(user_id)
            user_count = user_data.get("chat_count", 0)
            user_remaining = self.daily_chat_limit - user_count
            user_can_call = user_remaining > 0
        
        # 检查全局限制
        global_can_call = True
        global_remaining = -1
        if self.global_daily_chat_limit > 0:
            global_data = self._get_global_data()
            global_count = global_data.get("chat_count", 0)
            global_remaining = self.global_daily_chat_limit - global_count
            global_can_call = global_remaining > 0
        
        # 取两者的最小值作为剩余次数
        if user_remaining < 0:
            remaining = global_remaining
        elif global_remaining < 0:
            remaining = user_remaining
        else:
            remaining = min(user_remaining, global_remaining)
        
        can_call = user_can_call and global_can_call
        return can_call, max(0, remaining) if remaining >= 0 else -1
    
    def check_plan_limit(self, user_id: str) -> Tuple[bool, int]:
        """
        检查规划调用次数是否超限（同时检查用户级和全局限制）
        
        Returns:
            (can_call, remaining): 是否可以调用，剩余次数（取用户级和全局限制的最小值）
        """
        # 检查用户级限制
        user_can_call = True
        user_remaining = -1
        if self.daily_plan_limit > 0:
            user_data = self._get_user_data(user_id)
            user_count = user_data.get("plan_count", 0)
            user_remaining = self.daily_plan_limit - user_count
            user_can_call = user_remaining > 0
        
        # 检查全局限制
        global_can_call = True
        global_remaining = -1
        if self.global_daily_plan_limit > 0:
            global_data = self._get_global_data()
            global_count = global_data.get("plan_count", 0)
            global_remaining = self.global_daily_plan_limit - global_count
            global_can_call = global_remaining > 0
        
        # 取两者的最小值作为剩余次数
        if user_remaining < 0:
            remaining = global_remaining
        elif global_remaining < 0:
            remaining = user_remaining
        else:
            remaining = min(user_remaining, global_remaining)
        
        can_call = user_can_call and global_can_call
        return can_call, max(0, remaining) if remaining >= 0 else -1
    
    def increment_chat_count(self, user_id: str) -> int:
        """增加对话调用次数（同时增加用户级和全局计数），返回用户当前次数"""
        # 用户级计数
        user_data = self._get_user_data(user_id)
        user_data["chat_count"] = user_data.get("chat_count", 0) + 1
        
        # 全局计数
        global_data = self._get_global_data()
        global_data["chat_count"] = global_data.get("chat_count", 0) + 1
        
        _usage_logger.info("chat_call_incremented", extra={"fields": {
            "user_id": user_id,
            "user_count": user_data["chat_count"],
            "user_limit": self.daily_chat_limit,
            "global_count": global_data["chat_count"],
            "global_limit": self.global_daily_chat_limit,
        }})
        return user_data["chat_count"]
    
    def increment_plan_count(self, user_id: str) -> int:
        """增加规划调用次数（同时增加用户级和全局计数），返回用户当前次数"""
        # 用户级计数
        user_data = self._get_user_data(user_id)
        user_data["plan_count"] = user_data.get("plan_count", 0) + 1
        
        # 全局计数
        global_data = self._get_global_data()
        global_data["plan_count"] = global_data.get("plan_count", 0) + 1
        
        _usage_logger.info("plan_call_incremented", extra={"fields": {
            "user_id": user_id,
            "user_count": user_data["plan_count"],
            "user_limit": self.daily_plan_limit,
            "global_count": global_data["plan_count"],
            "global_limit": self.global_daily_plan_limit,
        }})
        return user_data["plan_count"]
    
    def get_usage_info(self, user_id: str) -> Dict:
        """获取用户的调用使用情况（包含用户级和全局使用情况）"""
        user_data = self._get_user_data(user_id)
        global_data = self._get_global_data()
        
        chat_count = user_data.get("chat_count", 0)
        plan_count = user_data.get("plan_count", 0)
        global_chat_count = global_data.get("chat_count", 0)
        global_plan_count = global_data.get("plan_count", 0)
        
        return {
            "date": self._get_today_str(),
            "chat": {
                "used": chat_count,
                "limit": self.daily_chat_limit,
                "remaining": max(0, self.daily_chat_limit - chat_count) if self.daily_chat_limit > 0 else -1,
            },
            "plan": {
                "used": plan_count,
                "limit": self.daily_plan_limit,
                "remaining": max(0, self.daily_plan_limit - plan_count) if self.daily_plan_limit > 0 else -1,
            },
            "global": {
                "chat": {
                    "used": global_chat_count,
                    "limit": self.global_daily_chat_limit,
                    "remaining": max(0, self.global_daily_chat_limit - global_chat_count) if self.global_daily_chat_limit > 0 else -1,
                },
                "plan": {
                    "used": global_plan_count,
                    "limit": self.global_daily_plan_limit,
                    "remaining": max(0, self.global_daily_plan_limit - global_plan_count) if self.global_daily_plan_limit > 0 else -1,
                },
            },
        }
    
    def get_chat_limit_message(self, user_id: str) -> str:
        """获取对话次数超限的提示信息（区分用户级和全局超限）"""
        user_data = self._get_user_data(user_id)
        global_data = self._get_global_data()
        
        user_exceeded = self.daily_chat_limit > 0 and user_data.get("chat_count", 0) >= self.daily_chat_limit
        global_exceeded = self.global_daily_chat_limit > 0 and global_data.get("chat_count", 0) >= self.global_daily_chat_limit
        
        if user_exceeded and global_exceeded:
            return f"今日对话次数已用完（个人上限 {self.daily_chat_limit} 次，全局上限 {self.global_daily_chat_limit} 次），明天再来探索世界吧～"
        elif user_exceeded:
            return f"今日对话次数已用完（个人上限 {self.daily_chat_limit} 次），明天再来探索世界吧～"
        elif global_exceeded:
            return f"今日全局对话次数已用完（全局上限 {self.global_daily_chat_limit} 次），明天再来探索世界吧～"
        else:
            return "今日对话次数已用完，明天再来探索世界吧～"
    
    def get_plan_limit_message(self, user_id: str) -> str:
        """获取规划次数超限的提示信息（区分用户级和全局超限）"""
        user_data = self._get_user_data(user_id)
        global_data = self._get_global_data()
        
        user_exceeded = self.daily_plan_limit > 0 and user_data.get("plan_count", 0) >= self.daily_plan_limit
        global_exceeded = self.global_daily_plan_limit > 0 and global_data.get("plan_count", 0) >= self.global_daily_plan_limit
        
        if user_exceeded and global_exceeded:
            return f"今日规划次数已用完（个人上限 {self.daily_plan_limit} 次，全局上限 {self.global_daily_plan_limit} 次），明天再来规划新的旅程吧～"
        elif user_exceeded:
            return f"今日规划次数已用完（个人上限 {self.daily_plan_limit} 次），明天再来规划新的旅程吧～"
        elif global_exceeded:
            return f"今日全局规划次数已用完（全局上限 {self.global_daily_plan_limit} 次），明天再来规划新的旅程吧～"
        else:
            return "今日规划次数已用完，明天再来规划新的旅程吧～"
    
    def reset_user_limit(self, user_id: str) -> None:
        """重置用户的调用次数（管理员功能）"""
        if user_id in self._cache:
            del self._cache[user_id]
        _usage_logger.info("user_limit_reset", extra={"fields": {"user_id": user_id}})


# 单例
_usage_limit_service: Optional[UsageLimitService] = None


def get_usage_limit_service() -> UsageLimitService:
    """获取调用次数限制服务单例"""
    global _usage_limit_service
    if _usage_limit_service is None:
        _usage_limit_service = UsageLimitService()
    return _usage_limit_service
