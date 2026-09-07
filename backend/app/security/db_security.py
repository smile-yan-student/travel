"""
数据库安全工具：防止 SQL 注入的统一校验函数。

所有动态拼接的 SQL 字段名、表名、排序字段、LIMIT/OFFSET 必须经过本模块校验。
用户输入的值一律通过参数化查询（%s 占位符）传入，禁止直接拼接。

功能特性：
- 字段白名单校验
- 排序方向校验
- LIMIT/OFFSET 安全转换
- 分页参数安全转换
- LIKE 查询参数构造
- WHERE 子句安全构造
- UPDATE SET 子句安全构造

使用方式：
    from app.security.db_security import (
        validate_field, validate_sort_dir, safe_limit, safe_offset,
        safe_page, like_param, build_where, build_update_set
    )

    # 校验排序字段
    order_by = validate_field(sort_field, USERS_ALLOWED_FIELDS)
    sort_dir = validate_sort_dir(sort_dir)

    # 安全分页
    limit, offset = safe_page(page, size)

    # 构造 WHERE 子句
    conditions = [("username", "LIKE", like_param(kw)), ("enabled", "=", 1)]
    where = build_where(conditions, params)

    # 构造 UPDATE SET 子句
    updates = build_update_set(data, MUST_VISIT_ALLOWED_UPDATE, params)
"""
from typing import Any, Dict, Iterable, List, Optional, Tuple


# ---------------- 字段白名单 ----------------

# users 表允许排序/筛选的字段
USERS_ALLOWED_FIELDS = {
    "id",
    "username",
    "enabled",
    "created_at",
    "updated_at",
    "last_login_at",
}

# trips 表允许排序/筛选的字段
TRIPS_ALLOWED_FIELDS = {
    "id",
    "user_id",
    "destination",
    "days",
    "style",
    "created_at",
    "updated_at",
}

# conversations 表允许排序/筛选的字段
CONVERSATIONS_ALLOWED_FIELDS = {
    "id",
    "user_id",
    "title",
    "created_at",
    "updated_at",
}

# must_visit 表允许更新的字段
MUST_VISIT_ALLOWED_UPDATE = {
    "name",
    "kw",
    "category",
    "rating",
    "priority",
    "city",
    "adcode",
    "lng",
    "lat",
}

# 通用排序方向
ALLOWED_SORT_DIRS = {"ASC", "DESC"}

# 允许的 SQL 操作符
ALLOWED_OPS = {
    "=",
    "!=",
    ">",
    "<",
    ">=",
    "<=",
    "LIKE",
    "IN",
    "NOT IN",
    "IS NULL",
    "IS NOT NULL",
}


def validate_field(field: str, allowed: Iterable[str]) -> str:
    """
    校验字段名是否在白名单中，不在则抛出 ValueError。

    Args:
        field: 字段名
        allowed: 允许的字段名集合

    Returns:
        str: 校验通过的字段名

    Raises:
        ValueError: 字段名不在白名单中

    Example:
        >>> order_by = validate_field("username", USERS_ALLOWED_FIELDS)
        >>> cur.execute(f"SELECT * FROM users ORDER BY {order_by} {sort_dir}", params)
    """
    if field not in allowed:
        raise ValueError(f"非法字段名: {field}")
    return field


def validate_sort_dir(sort_dir: str) -> str:
    """
    校验排序方向，返回大写的 ASC/DESC。

    Args:
        sort_dir: 排序方向（ASC/DESC，不区分大小写）

    Returns:
        str: 大写的排序方向

    Raises:
        ValueError: 排序方向不合法
    """
    d = (sort_dir or "DESC").upper()
    if d not in ALLOWED_SORT_DIRS:
        raise ValueError(f"非法排序方向: {sort_dir}")
    return d


def safe_limit(limit: Any, max_limit: int = 100, default: int = 20) -> int:
    """
    安全转换 LIMIT 值，强制为正整数且不超过 max_limit。

    Args:
        limit: 原始 LIMIT 值（可能是字符串或 None）
        max_limit: 最大允许值，默认 100
        default: 默认值，默认 20

    Returns:
        int: 安全的 LIMIT 值（1 ~ max_limit）
    """
    try:
        v = int(limit)
    except (TypeError, ValueError):
        v = default
    return max(1, min(v, max_limit))


def safe_offset(offset: Any, default: int = 0) -> int:
    """
    安全转换 OFFSET 值，强制为非负整数。

    Args:
        offset: 原始 OFFSET 值（可能是字符串或 None）
        default: 默认值，默认 0

    Returns:
        int: 安全的 OFFSET 值（>= 0）
    """
    try:
        v = int(offset)
    except (TypeError, ValueError):
        v = default
    return max(0, v)


def safe_page(page: Any, size: Any, max_size: int = 100) -> Tuple[int, int]:
    """
    安全转换分页参数，返回 (limit, offset)。

    Args:
        page: 页码（从 1 开始）
        size: 每页大小
        max_size: 最大每页大小，默认 100

    Returns:
        Tuple[int, int]: (limit, offset)
    """
    limit = safe_limit(size, max_limit=max_size)
    try:
        p = max(1, int(page))
    except (TypeError, ValueError):
        p = 1
    return limit, (p - 1) * limit


def like_param(keyword: str) -> str:
    """
    构造 LIKE 查询的参数值（在 Python 层拼接 %，SQL 中用 %s 占位）。

    Args:
        keyword: 搜索关键词

    Returns:
        str: 带 % 包裹的关键词

    Example:
        >>> cur.execute("SELECT * FROM users WHERE username LIKE %s", (like_param("admin"),))
    """
    return f"%{keyword}%"


def build_where(
    conditions: List[Tuple[str, str, Any]], params: List[Any]
) -> str:
    """
    安全构造 WHERE 子句。

    conditions: [(字段名, 操作符, 值), ...]
    字段名必须是常量（不接受用户输入），操作符必须在白名单中。

    Args:
        conditions: 条件列表，每个元素为 (字段名, 操作符, 值)
        params: 参数列表（会被追加值）

    Returns:
        str: WHERE 子句（包含 "WHERE " 前缀，如果没有条件则返回空字符串）

    Raises:
        ValueError: 操作符不合法

    Example:
        >>> conditions = [("username", "LIKE", like_param(kw)), ("enabled", "=", 1)]
        >>> params = []
        >>> where = build_where(conditions, params)
        >>> cur.execute(f"SELECT * FROM users {where}", params)
    """
    clauses: List[str] = []
    for field, op, value in conditions:
        op_upper = op.upper()
        if op_upper not in ALLOWED_OPS:
            raise ValueError(f"非法操作符: {op}")
        if op_upper in ("IS NULL", "IS NOT NULL"):
            clauses.append(f"{field} {op_upper}")
        elif op_upper in ("IN", "NOT IN"):
            placeholders = ",".join(["%s"] * len(value))
            clauses.append(f"{field} {op_upper} ({placeholders})")
            params.extend(value)
        else:
            clauses.append(f"{field} {op_upper} %s")
            params.append(value)
    return "WHERE " + " AND ".join(clauses) if clauses else ""


def build_update_set(
    fields: Dict[str, Any], allowed: Iterable[str], params: List[Any]
) -> str:
    """
    安全构造 UPDATE SET 子句，字段名必须在白名单中。

    Args:
        fields: 要更新的字段字典
        allowed: 允许更新的字段名集合
        params: 参数列表（会被追加值）

    Returns:
        str: SET 子句（不包含 "SET " 前缀）

    Raises:
        ValueError: 没有合法的更新字段

    Example:
        >>> updates = build_update_set(data, MUST_VISIT_ALLOWED_UPDATE, params)
        >>> params.append(mid)
        >>> cur.execute(f"UPDATE must_visit SET {updates} WHERE id=%s", params)
    """
    allowed_set = set(allowed)
    clauses: List[str] = []
    for k, v in fields.items():
        if k in allowed_set:
            clauses.append(f"{k}=%s")
            params.append(v)
    if not clauses:
        raise ValueError("没有合法的更新字段")
    return ", ".join(clauses)
