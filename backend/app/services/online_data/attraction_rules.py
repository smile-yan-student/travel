"""
景点预约规则管理 - 存储和管理景点的预约规则、开放时间、票价等信息

核心功能：
1. 景点预约规则的CRUD（增删改查）
2. 预约规则的批量导入
3. 按目的地查询景点预约规则
4. 预约规则的缓存

数据来源：
- 景区官方公告（预约渠道、放票时间、开放时间、票价、闭馆日）
- 支持后台人工配置和维护

设计理念：
- 将景点的硬性规则（预约、闭馆、票价）从攻略文本中提取出来，结构化存储
- 规划引擎可以直接使用这些规则，生成预约提醒
- 支持后台配置，便于人工维护和更新
"""
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AttractionRule:
    """景点预约规则"""
    id: Optional[int] = None
    attraction_name: str = ""  # 景点名称
    destination: str = ""  # 所属目的地（城市）
    reservation_channel: str = ""  # 预约渠道（公众号/小程序/APP/官网）
    reservation_url: str = ""  # 预约链接
    ticket_release_time: str = ""  # 放票时间（如：提前7天20:00）
    opening_hours: str = ""  # 开放时间（如：08:30-17:00，16:00停止入场）
    closing_days: str = ""  # 闭馆日（如：每周一）
    ticket_price: str = ""  # 票价信息（如：旺季60元，淡季40元，学生半价）
    visitor_route: str = ""  # 游览路线（如：午门进，神武门出）
    daily_limit: str = ""  # 每日限流（如：每日最大接待8万人）
    tips: str = ""  # 其他提示
    source: str = ""  # 数据来源（官方/人工/搜索）
    is_active: bool = True  # 是否启用
    created_at: float = 0
    updated_at: float = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "attraction_name": self.attraction_name,
            "destination": self.destination,
            "reservation_channel": self.reservation_channel,
            "reservation_url": self.reservation_url,
            "ticket_release_time": self.ticket_release_time,
            "opening_hours": self.opening_hours,
            "closing_days": self.closing_days,
            "ticket_price": self.ticket_price,
            "visitor_route": self.visitor_route,
            "daily_limit": self.daily_limit,
            "tips": self.tips,
            "source": self.source,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class AttractionRules:
    """景点预约规则管理"""

    def __init__(self):
        self._initialized = False
        self._db_available = False
        self._cache: Dict[str, AttractionRule] = {}  # 内存缓存

    async def _initialize(self):
        """初始化（懒加载）"""
        if self._initialized:
            return
        try:
            from app.data.database import execute_query
            # 尝试查询，确认表存在
            execute_query(
                "SELECT COUNT(*) as cnt FROM attraction_rules",
                fetch="one",
            )
            self._db_available = True
            logger.info("景点预约规则数据库初始化成功")
        except Exception as e:
            logger.warning(f"景点预约规则数据库不可用: {e}")
            self._db_available = False
        self._initialized = True

    async def get_by_name(self, attraction_name: str) -> Optional[AttractionRule]:
        """
        根据景点名称查询预约规则

        Args:
            attraction_name: 景点名称

        Returns:
            景点预约规则，不存在返回 None
        """
        await self._initialize()

        # 检查缓存
        if attraction_name in self._cache:
            return self._cache[attraction_name]

        if not self._db_available:
            return None

        try:
            from app.data.database import execute_query

            result = execute_query(
                """
                SELECT * FROM attraction_rules
                WHERE attraction_name = %s AND is_active = 1
                LIMIT 1
                """,
                (attraction_name,),
                fetch="one",
            )

            if result:
                rule = self._row_to_rule(result)
                # 写入缓存
                self._cache[attraction_name] = rule
                return rule

            return None
        except Exception as e:
            logger.warning(f"查询景点预约规则失败: {attraction_name}, 错误: {e}")
            return None

    async def get_by_destination(self, destination: str) -> List[AttractionRule]:
        """
        根据目的地查询所有景点的预约规则

        Args:
            destination: 目的地（城市）

        Returns:
            景点预约规则列表
        """
        await self._initialize()

        if not self._db_available:
            return []

        try:
            from app.data.database import execute_query

            results = execute_query(
                """
                SELECT * FROM attraction_rules
                WHERE destination = %s AND is_active = 1
                ORDER BY attraction_name
                """,
                (destination,),
                fetch="all",
            )

            rules = [self._row_to_rule(row) for row in results]

            # 写入缓存
            for rule in rules:
                self._cache[rule.attraction_name] = rule

            return rules
        except Exception as e:
            logger.warning(f"查询目的地预约规则失败: {destination}, 错误: {e}")
            return []

    async def create(self, rule: AttractionRule) -> Optional[int]:
        """
        创建景点预约规则

        Args:
            rule: 景点预约规则

        Returns:
            新创建的规则ID，失败返回 None
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
            rule.created_at = now_ts
            rule.updated_at = now_ts

            result = execute_update(
                """
                INSERT INTO attraction_rules
                (attraction_name, destination, reservation_channel, reservation_url,
                 ticket_release_time, opening_hours, closing_days, ticket_price,
                 visitor_route, daily_limit, tips, source, is_active, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    rule.attraction_name,
                    rule.destination,
                    rule.reservation_channel,
                    rule.reservation_url,
                    rule.ticket_release_time,
                    rule.opening_hours,
                    rule.closing_days,
                    rule.ticket_price,
                    rule.visitor_route,
                    rule.daily_limit,
                    rule.tips,
                    rule.source,
                    1 if rule.is_active else 0,
                    now_dt,
                    now_dt,
                ),
            )

            # 清除缓存
            if rule.attraction_name in self._cache:
                del self._cache[rule.attraction_name]

            logger.info(f"创建景点预约规则: {rule.attraction_name}")
            return result
        except Exception as e:
            logger.warning(f"创建景点预约规则失败: {rule.attraction_name}, 错误: {e}")
            return None

    async def update(self, rule: AttractionRule) -> bool:
        """
        更新景点预约规则

        Args:
            rule: 景点预约规则（需要包含id）

        Returns:
            是否更新成功
        """
        await self._initialize()

        if not self._db_available or not rule.id:
            return False

        try:
            from app.data.database import execute_update
            from datetime import datetime
            import time

            now_dt = datetime.now()
            rule.updated_at = time.time()

            execute_update(
                """
                UPDATE attraction_rules SET
                attraction_name = %s,
                destination = %s,
                reservation_channel = %s,
                reservation_url = %s,
                ticket_release_time = %s,
                opening_hours = %s,
                closing_days = %s,
                ticket_price = %s,
                visitor_route = %s,
                daily_limit = %s,
                tips = %s,
                source = %s,
                is_active = %s,
                updated_at = %s
                WHERE id = %s
                """,
                (
                    rule.attraction_name,
                    rule.destination,
                    rule.reservation_channel,
                    rule.reservation_url,
                    rule.ticket_release_time,
                    rule.opening_hours,
                    rule.closing_days,
                    rule.ticket_price,
                    rule.visitor_route,
                    rule.daily_limit,
                    rule.tips,
                    rule.source,
                    1 if rule.is_active else 0,
                    now_dt,
                    rule.id,
                ),
            )

            # 清除缓存
            if rule.attraction_name in self._cache:
                del self._cache[rule.attraction_name]

            logger.info(f"更新景点预约规则: {rule.attraction_name}")
            return True
        except Exception as e:
            logger.warning(f"更新景点预约规则失败: {rule.attraction_name}, 错误: {e}")
            return False

    async def delete(self, rule_id: int) -> bool:
        """
        删除景点预约规则（软删除，设置is_active=0）

        Args:
            rule_id: 规则ID

        Returns:
            是否删除成功
        """
        await self._initialize()

        if not self._db_available:
            return False

        try:
            from app.data.database import execute_update

            # 先查询景点名称，用于清除缓存
            rule = await self.get_by_id(rule_id)

            execute_update(
                "UPDATE attraction_rules SET is_active = 0 WHERE id = %s",
                (rule_id,),
            )

            # 清除缓存
            if rule and rule.attraction_name in self._cache:
                del self._cache[rule.attraction_name]

            logger.info(f"删除景点预约规则: {rule_id}")
            return True
        except Exception as e:
            logger.warning(f"删除景点预约规则失败: {rule_id}, 错误: {e}")
            return False

    async def get_by_id(self, rule_id: int) -> Optional[AttractionRule]:
        """根据ID查询"""
        await self._initialize()

        if not self._db_available:
            return None

        try:
            from app.data.database import execute_query

            result = execute_query(
                "SELECT * FROM attraction_rules WHERE id = %s",
                (rule_id,),
                fetch="one",
            )

            if result:
                return self._row_to_rule(result)
            return None
        except Exception as e:
            logger.warning(f"查询景点预约规则失败: {rule_id}, 错误: {e}")
            return None

    async def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        await self._initialize()

        if not self._db_available:
            return {"available": False}

        try:
            from app.data.database import execute_query

            total = execute_query(
                "SELECT COUNT(*) as cnt FROM attraction_rules WHERE is_active = 1",
                fetch="one",
            )["cnt"]

            by_destination = execute_query(
                "SELECT destination, COUNT(*) as cnt FROM attraction_rules WHERE is_active = 1 GROUP BY destination",
                fetch="all",
            )

            return {
                "available": True,
                "total": total,
                "by_destination": {item["destination"]: item["cnt"] for item in by_destination},
            }
        except Exception as e:
            logger.warning(f"获取统计信息失败: {e}")
            return {"available": False, "error": str(e)}

    def _row_to_rule(self, row: Dict[str, Any]) -> AttractionRule:
        """将数据库行转换为AttractionRule对象"""
        # 处理时间字段（可能是datetime对象或浮点数）
        created_at = row.get("created_at", 0)
        updated_at = row.get("updated_at", 0)
        if hasattr(created_at, 'timestamp'):
            created_at = created_at.timestamp()
        if hasattr(updated_at, 'timestamp'):
            updated_at = updated_at.timestamp()

        return AttractionRule(
            id=row.get("id"),
            attraction_name=row.get("attraction_name", ""),
            destination=row.get("destination", ""),
            reservation_channel=row.get("reservation_channel", ""),
            reservation_url=row.get("reservation_url", ""),
            ticket_release_time=row.get("ticket_release_time", ""),
            opening_hours=row.get("opening_hours", ""),
            closing_days=row.get("closing_days", ""),
            ticket_price=row.get("ticket_price", ""),
            visitor_route=row.get("visitor_route", ""),
            daily_limit=row.get("daily_limit", ""),
            tips=row.get("tips", ""),
            source=row.get("source", ""),
            is_active=bool(row.get("is_active", 1)),
            created_at=float(created_at) if created_at else 0,
            updated_at=float(updated_at) if updated_at else 0,
        )


# 单例
_attraction_rules: Optional[AttractionRules] = None


def get_attraction_rules() -> AttractionRules:
    """获取景点预约规则管理单例"""
    global _attraction_rules
    if _attraction_rules is None:
        _attraction_rules = AttractionRules()
    return _attraction_rules
