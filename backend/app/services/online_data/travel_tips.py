"""
旅游避坑提示管理 - 存储和管理目的地的旅游避坑提示、防骗建议、交通美食等信息

核心功能：
1. 旅游避坑提示的CRUD（增删改查）
2. 按目的地和类别查询提示
3. 提示的批量导入
4. 提示的缓存

数据来源：
- 游客真实经验（从攻略中提取的高频踩坑点）
- 支持后台人工配置和维护

设计理念：
- 将目的地的避坑提示结构化存储，规划引擎可以直接使用
- 支持按类别筛选（预约、防骗、交通、美食、住宿等）
- 支持后台配置，便于人工维护和更新
"""
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TravelTip:
    """旅游避坑提示"""
    id: Optional[int] = None
    destination: str = ""  # 目的地（城市）
    tip: str = ""  # 提示内容
    category: str = "general"  # 类别：general/reservation/anti_fraud/traffic/food/accommodation/weather
    severity: str = "info"  # 严重程度：info/warning/danger
    source: str = ""  # 数据来源（搜索/人工/官方）
    is_active: bool = True  # 是否启用
    sort_order: int = 0  # 排序权重（越大越靠前）
    created_at: float = 0
    updated_at: float = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "destination": self.destination,
            "tip": self.tip,
            "category": self.category,
            "severity": self.severity,
            "source": self.source,
            "is_active": self.is_active,
            "sort_order": self.sort_order,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class TravelTips:
    """旅游避坑提示管理"""

    # 提示类别
    CATEGORIES = {
        "general": "通用提示",
        "reservation": "预约提醒",
        "anti_fraud": "防骗提示",
        "traffic": "交通提示",
        "food": "美食提示",
        "accommodation": "住宿提示",
        "weather": "天气提示",
        "safety": "安全提示",
    }

    # 严重程度
    SEVERITIES = {
        "info": "信息",
        "warning": "警告",
        "danger": "危险",
    }

    def __init__(self):
        self._initialized = False
        self._db_available = False
        self._cache: Dict[str, List[TravelTip]] = {}  # 内存缓存（按目的地）

    async def _initialize(self):
        """初始化（懒加载）"""
        if self._initialized:
            return
        try:
            from app.data.database import execute_query
            # 尝试查询，确认表存在
            execute_query(
                "SELECT COUNT(*) as cnt FROM travel_tips",
                fetch="one",
            )
            self._db_available = True
            logger.info("旅游避坑提示数据库初始化成功")
        except Exception as e:
            logger.warning(f"旅游避坑提示数据库不可用: {e}")
            self._db_available = False
        self._initialized = True

    async def get_by_destination(
        self,
        destination: str,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> List[TravelTip]:
        """
        根据目的地查询避坑提示

        Args:
            destination: 目的地（城市）
            category: 提示类别（可选）
            limit: 返回数量限制

        Returns:
            避坑提示列表
        """
        await self._initialize()

        # 检查缓存（只缓存全量查询，不缓存按类别查询）
        cache_key = f"{destination}_all"
        if category is None and cache_key in self._cache:
            return self._cache[cache_key][:limit]

        if not self._db_available:
            return []

        try:
            from app.data.database import execute_query

            if category:
                results = execute_query(
                    """
                    SELECT * FROM travel_tips
                    WHERE destination = %s AND category = %s AND is_active = 1
                    ORDER BY sort_order DESC, created_at DESC
                    LIMIT %s
                    """,
                    (destination, category, limit),
                    fetch="all",
                )
            else:
                results = execute_query(
                    """
                    SELECT * FROM travel_tips
                    WHERE destination = %s AND is_active = 1
                    ORDER BY sort_order DESC, created_at DESC
                    LIMIT %s
                    """,
                    (destination, limit),
                    fetch="all",
                )

            tips = [self._row_to_tip(row) for row in results]

            # 写入缓存（只缓存全量查询）
            if category is None:
                self._cache[cache_key] = tips

            return tips
        except Exception as e:
            logger.warning(f"查询目的地避坑提示失败: {destination}, 错误: {e}")
            return []

    async def get_by_id(self, tip_id: int) -> Optional[TravelTip]:
        """根据ID查询"""
        await self._initialize()

        if not self._db_available:
            return None

        try:
            from app.data.database import execute_query

            result = execute_query(
                "SELECT * FROM travel_tips WHERE id = %s",
                (tip_id,),
                fetch="one",
            )

            if result:
                return self._row_to_tip(result)
            return None
        except Exception as e:
            logger.warning(f"查询避坑提示失败: {tip_id}, 错误: {e}")
            return None

    async def create(self, tip: TravelTip) -> Optional[int]:
        """
        创建避坑提示

        Args:
            tip: 避坑提示

        Returns:
            新创建的提示ID，失败返回 None
        """
        await self._initialize()

        if not self._db_available:
            return None

        try:
            from app.data.database import execute_update
            from datetime import datetime
            import time

            now_dt = datetime.now()
            now_ts = time.time()
            tip.created_at = now_ts
            tip.updated_at = now_ts

            result = execute_update(
                """
                INSERT INTO travel_tips
                (destination, tip, category, severity, source, is_active, sort_order, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    tip.destination,
                    tip.tip,
                    tip.category,
                    tip.severity,
                    tip.source,
                    1 if tip.is_active else 0,
                    tip.sort_order,
                    now_dt,
                    now_dt,
                ),
            )

            # 清除缓存
            cache_key = f"{tip.destination}_all"
            if cache_key in self._cache:
                del self._cache[cache_key]

            logger.info(f"创建避坑提示: {tip.destination} - {tip.tip[:30]}")
            return result
        except Exception as e:
            logger.warning(f"创建避坑提示失败: {tip.destination}, 错误: {e}")
            return None

    async def update(self, tip: TravelTip) -> bool:
        """
        更新避坑提示

        Args:
            tip: 避坑提示（需要包含id）

        Returns:
            是否更新成功
        """
        await self._initialize()

        if not self._db_available or not tip.id:
            return False

        try:
            from app.data.database import execute_update
            from datetime import datetime
            import time

            now_dt = datetime.now()
            tip.updated_at = time.time()

            # 先查询旧数据，用于清除缓存
            old_tip = await self.get_by_id(tip.id)

            execute_update(
                """
                UPDATE travel_tips SET
                destination = %s,
                tip = %s,
                category = %s,
                severity = %s,
                source = %s,
                is_active = %s,
                sort_order = %s,
                updated_at = %s
                WHERE id = %s
                """,
                (
                    tip.destination,
                    tip.tip,
                    tip.category,
                    tip.severity,
                    tip.source,
                    1 if tip.is_active else 0,
                    tip.sort_order,
                    now_dt,
                    tip.id,
                ),
            )

            # 清除缓存（旧目的地和新目的地都要清除）
            if old_tip:
                old_cache_key = f"{old_tip.destination}_all"
                if old_cache_key in self._cache:
                    del self._cache[old_cache_key]

            new_cache_key = f"{tip.destination}_all"
            if new_cache_key in self._cache:
                del self._cache[new_cache_key]

            logger.info(f"更新避坑提示: {tip.id}")
            return True
        except Exception as e:
            logger.warning(f"更新避坑提示失败: {tip.id}, 错误: {e}")
            return False

    async def delete(self, tip_id: int) -> bool:
        """
        删除避坑提示（软删除，设置is_active=0）

        Args:
            tip_id: 提示ID

        Returns:
            是否删除成功
        """
        await self._initialize()

        if not self._db_available:
            return False

        try:
            from app.data.database import execute_update

            # 先查询，用于清除缓存
            tip = await self.get_by_id(tip_id)

            execute_update(
                "UPDATE travel_tips SET is_active = 0 WHERE id = %s",
                (tip_id,),
            )

            # 清除缓存
            if tip:
                cache_key = f"{tip.destination}_all"
                if cache_key in self._cache:
                    del self._cache[cache_key]

            logger.info(f"删除避坑提示: {tip_id}")
            return True
        except Exception as e:
            logger.warning(f"删除避坑提示失败: {tip_id}, 错误: {e}")
            return False

    async def batch_create(self, tips: List[TravelTip]) -> int:
        """
        批量创建避坑提示

        Args:
            tips: 避坑提示列表

        Returns:
            成功创建的数量
        """
        success_count = 0
        for tip in tips:
            result = await self.create(tip)
            if result:
                success_count += 1
        return success_count

    async def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        await self._initialize()

        if not self._db_available:
            return {"available": False}

        try:
            from app.data.database import execute_query

            total = execute_query(
                "SELECT COUNT(*) as cnt FROM travel_tips WHERE is_active = 1",
                fetch="one",
            )["cnt"]

            by_destination = execute_query(
                "SELECT destination, COUNT(*) as cnt FROM travel_tips WHERE is_active = 1 GROUP BY destination",
                fetch="all",
            )

            by_category = execute_query(
                "SELECT category, COUNT(*) as cnt FROM travel_tips WHERE is_active = 1 GROUP BY category",
                fetch="all",
            )

            return {
                "available": True,
                "total": total,
                "by_destination": {item["destination"]: item["cnt"] for item in by_destination},
                "by_category": {item["category"]: item["cnt"] for item in by_category},
                "categories": self.CATEGORIES,
                "severities": self.SEVERITIES,
            }
        except Exception as e:
            logger.warning(f"获取统计信息失败: {e}")
            return {"available": False, "error": str(e)}

    def _row_to_tip(self, row: Dict[str, Any]) -> TravelTip:
        """将数据库行转换为TravelTip对象"""
        # 处理时间字段（可能是datetime对象或浮点数）
        created_at = row.get("created_at", 0)
        updated_at = row.get("updated_at", 0)
        if hasattr(created_at, 'timestamp'):
            created_at = created_at.timestamp()
        if hasattr(updated_at, 'timestamp'):
            updated_at = updated_at.timestamp()

        return TravelTip(
            id=row.get("id"),
            destination=row.get("destination", ""),
            tip=row.get("tip", ""),
            category=row.get("category", "general"),
            severity=row.get("severity", "info"),
            source=row.get("source", ""),
            is_active=bool(row.get("is_active", 1)),
            sort_order=int(row.get("sort_order", 0)),
            created_at=float(created_at) if created_at else 0,
            updated_at=float(updated_at) if updated_at else 0,
        )


# 单例
_travel_tips: Optional[TravelTips] = None


def get_travel_tips() -> TravelTips:
    """获取旅游避坑提示管理单例"""
    global _travel_tips
    if _travel_tips is None:
        _travel_tips = TravelTips()
    return _travel_tips
