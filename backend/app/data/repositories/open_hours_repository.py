"""
景区开放时间数据访问层（Repository）。

提供景点开放时间的查询、管理功能，用于规划时检查景点是否在开放时间内。

功能特性：
- 景点开放时间查询（按景点名称、城市）
- 景点开放状态检查（指定日期是否开放）
- 开放时间添加
- 开放时间列表（分页）
- 开放时间删除
- 默认开放时间初始化（著名景点）

使用方式：
    from app.data.repositories.open_hours_repository import OpenHoursRepository

    # 获取景点开放时间
    hours = OpenHoursRepository.get_open_hours("西湖", "杭州")

    # 检查景点在指定日期是否开放
    from datetime import date
    is_open, open_time, close_time, note = OpenHoursRepository.is_open_on_day(
        "西湖", date(2026, 8, 30), "杭州"
    )

    # 添加开放时间
    record_id = OpenHoursRepository.add_open_hours(
        "西湖", "杭州", 0, "00:00", "23:59", False, "", "全天开放"
    )
"""
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from ..database import get_conn, read_connection, transaction


class OpenHoursRepository:
    """
    景区开放时间数据访问类。

    提供景点开放时间的查询、管理功能。

    Example:
        >>> hours = OpenHoursRepository.get_open_hours("西湖", "杭州")
        >>> print(len(hours))
        1
    """

    @staticmethod
    def get_open_hours(poi_name: str, city: str = "") -> List[Dict[str, Any]]:
        """
        获取景点的开放时间列表。

        Args:
            poi_name: 景点名称
            city: 所在城市（可选，用于区分同名景点）

        Returns:
            List[Dict[str, Any]]: 开放时间列表，每个元素包含
                day_of_week, open_time, close_time, is_closed, note, special_date

        Example:
            >>> hours = OpenHoursRepository.get_open_hours("西湖", "杭州")
            >>> print(hours[0]["open_time"])
            00:00
        """
        with read_connection() as conn:
            with conn.cursor() as cur:
                sql = "SELECT * FROM poi_open_hours WHERE poi_name = %s"
                params = [poi_name]
                if city:
                    sql += " AND (poi_city = %s OR poi_city = '')"
                    params.append(city)
                sql += " ORDER BY day_of_week ASC, special_date ASC"
                cur.execute(sql, params)
                return cur.fetchall()

    @staticmethod
    def is_open_on_day(
        poi_name: str, check_date: date, city: str = ""
    ) -> Tuple[bool, str, str, str]:
        """
        检查景点在指定日期是否开放。

        检查优先级：
        1. 特殊日期（special_date）
        2. 每天（day_of_week=0）
        3. 指定星期（day_of_week=1-7）

        如果没有配置开放时间，默认开放。

        Args:
            poi_name: 景点名称
            check_date: 检查日期
            city: 所在城市（可选）

        Returns:
            Tuple[bool, str, str, str]: (是否开放, 开放时间, 关闭时间, 备注)

        Example:
            >>> from datetime import date
            >>> is_open, open_time, close_time, note = OpenHoursRepository.is_open_on_day(
            ...     "西湖", date(2026, 8, 30), "杭州"
            ... )
            >>> print(is_open, open_time, close_time)
            True 00:00 23:59
        """
        open_hours = OpenHoursRepository.get_open_hours(poi_name, city)
        if not open_hours:
            return (True, "", "", "")  # 没有配置开放时间，默认开放

        day_of_week = check_date.isoweekday()  # 1=周一，7=周日

        # 先检查特殊日期
        for oh in open_hours:
            if oh.get("special_date") and oh["special_date"] == check_date:
                if oh["is_closed"]:
                    return (False, "", "", oh.get("note", "特殊日期闭馆"))
                return (
                    True,
                    str(oh["open_time"]),
                    str(oh["close_time"]),
                    oh.get("note", ""),
                )

        # 检查每天（day_of_week=0）
        for oh in open_hours:
            if oh["day_of_week"] == 0:
                if oh["is_closed"]:
                    return (False, "", "", oh.get("note", "每天闭馆"))
                return (
                    True,
                    str(oh["open_time"]),
                    str(oh["close_time"]),
                    oh.get("note", ""),
                )

        # 检查指定星期
        for oh in open_hours:
            if oh["day_of_week"] == day_of_week:
                if oh["is_closed"]:
                    return (False, "", "", oh.get("note", f"周{day_of_week}闭馆"))
                return (
                    True,
                    str(oh["open_time"]),
                    str(oh["close_time"]),
                    oh.get("note", ""),
                )

        return (True, "", "", "")  # 没有配置该天的开放时间，默认开放

    @staticmethod
    def add_open_hours(
        poi_name: str,
        city: str,
        day_of_week: int,
        open_time: str,
        close_time: str,
        is_closed: bool = False,
        special_date: str = "",
        note: str = "",
    ) -> int:
        """
        添加开放时间。

        Args:
            poi_name: 景点名称
            city: 所在城市
            day_of_week: 星期几（1-7，0=每天）
            open_time: 开放时间（HH:MM）
            close_time: 关闭时间（HH:MM）
            is_closed: 是否闭馆
            special_date: 特殊日期（YYYY-MM-DD）
            note: 备注

        Returns:
            int: 记录ID

        Example:
            >>> record_id = OpenHoursRepository.add_open_hours(
            ...     "西湖", "杭州", 0, "00:00", "23:59", False, "", "全天开放"
            ... )
            >>> print(record_id)
            1
        """
        with transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO poi_open_hours
                       (poi_name, poi_city, day_of_week, open_time, close_time, is_closed, special_date, note)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        poi_name,
                        city,
                        day_of_week,
                        open_time,
                        close_time,
                        is_closed,
                        special_date,
                        note,
                    ),
                )
                return cur.lastrowid

    @staticmethod
    def list_open_hours(
        poi_name: Optional[str] = None,
        city: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        获取开放时间列表（分页）。

        Args:
            poi_name: 景点名称（可选，模糊匹配）
            city: 所在城市（可选，模糊匹配）
            page: 页码（从1开始）
            page_size: 每页大小

        Returns:
            Tuple[List[Dict[str, Any]], int]: (开放时间列表, 总数)

        Example:
            >>> hours, total = OpenHoursRepository.list_open_hours(
            ...     poi_name="西湖", page=1, page_size=10
            ... )
            >>> print(total)
            1
        """
        with read_connection() as conn:
            with conn.cursor() as cur:
                conditions = []
                params = []
                if poi_name:
                    conditions.append("poi_name LIKE %s")
                    params.append(f"%{poi_name}%")
                if city:
                    conditions.append("poi_city LIKE %s")
                    params.append(f"%{city}%")
                where = " AND ".join(conditions) if conditions else "1=1"

                cur.execute(
                    f"SELECT COUNT(*) as total FROM poi_open_hours WHERE {where}",
                    params,
                )
                total = cur.fetchone()["total"]

                offset = (page - 1) * page_size
                cur.execute(
                    f"SELECT * FROM poi_open_hours WHERE {where} ORDER BY poi_name, day_of_week LIMIT %s OFFSET %s",
                    params + [page_size, offset],
                )
                return cur.fetchall(), total

    @staticmethod
    def delete_open_hours(record_id: int) -> bool:
        """
        删除开放时间记录。

        Args:
            record_id: 记录ID

        Returns:
            bool: 是否删除成功

        Example:
            >>> success = OpenHoursRepository.delete_open_hours(1)
            >>> print(success)
            True
        """
        with transaction() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM poi_open_hours WHERE id = %s", (record_id,))
                return cur.rowcount > 0

    @staticmethod
    def init_default_open_hours() -> None:
        """
        初始化默认的景点开放时间（一些著名景点）。

        包含北京、杭州、济南等城市的著名景点开放时间。
        如果记录已存在（重复插入），则跳过。
        """
        default_hours = [
            # 北京景点
            (
                "故宫博物院",
                "北京",
                0,
                "08:30",
                "17:00",
                False,
                "",
                "旺季8:30-17:00，淡季8:30-16:30，周一闭馆",
            ),
            ("故宫博物院", "北京", 1, "", "", True, "", "周一闭馆"),
            ("天安门广场", "北京", 0, "05:00", "22:00", False, "", "升旗时间随日出变化"),
            ("颐和园", "北京", 0, "06:30", "18:00", False, "", "旺季6:30-18:00，淡季7:00-17:00"),
            ("天坛公园", "北京", 0, "06:00", "22:00", False, "", "景点内祈年殿等8:00-17:30"),
            # 杭州景点
            ("西湖", "杭州", 0, "00:00", "23:59", False, "", "全天开放"),
            ("灵隐寺", "杭州", 0, "07:00", "18:15", False, "", "旺季7:00-18:15，淡季7:30-17:45"),
            ("雷峰塔", "杭州", 0, "08:00", "20:30", False, "", "旺季8:00-20:30，淡季8:00-17:30"),
            # 济南景点
            ("大明湖", "济南", 0, "06:00", "22:00", False, "", "全天开放，超然楼等景点8:30-17:00"),
            ("趵突泉", "济南", 0, "07:00", "19:00", False, "", "旺季7:00-19:00，淡季7:00-18:00"),
            ("千佛山", "济南", 0, "06:30", "18:00", False, "", "旺季6:30-18:00，淡季7:00-17:30"),
        ]

        for (
            poi_name,
            city,
            day_of_week,
            open_time,
            close_time,
            is_closed,
            special_date,
            note,
        ) in default_hours:
            try:
                OpenHoursRepository.add_open_hours(
                    poi_name,
                    city,
                    day_of_week,
                    open_time,
                    close_time,
                    is_closed,
                    special_date,
                    note,
                )
            except Exception:
                pass
