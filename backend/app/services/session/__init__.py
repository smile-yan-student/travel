"""
会话与行程工作记忆模块
- ItineraryWorkspace: 行程工作记忆（完整行程+参数+修改记录+用户偏好）
- SessionStore: 会话存储（内存缓存+文件持久化+LRU淘汰）
- IncrementalEditor: 增量修改器（局部修改不全局重刷）
"""
from .itinerary_workspace import ItineraryWorkspace, ModificationRecord, UserPreferences
from .session_store import SessionStore, get_session_store
from .incremental_editor import IncrementalEditor, get_incremental_editor

__all__ = [
    "ItineraryWorkspace",
    "ModificationRecord",
    "UserPreferences",
    "SessionStore",
    "get_session_store",
    "IncrementalEditor",
    "get_incremental_editor",
]
