"""
登录安全模块：失败次数限制 + 账号临时锁定。

策略：
- 同一用户名连续失败 5 次 → 锁定 15 分钟
- 同一 IP 连续失败 10 次 → 锁定 30 分钟
- 登录成功后重置该用户名的失败计数
- 用内存字典实现，重启后重置（生产环境建议用 Redis）

使用方式：
    from app.security.login_security import (
        check_login_locked, record_login_failure,
        record_login_success, get_login_status
    )

    # 检查是否被锁定
    locked, message = check_login_locked(username, client_ip)
    if locked:
        return error(message)

    # 记录登录失败
    locked, message = record_login_failure(username, client_ip)

    # 记录登录成功
    record_login_success(username, client_ip)

    # 获取登录安全状态
    status = get_login_status(username, client_ip)
"""
import threading
import time
from typing import Any, Dict, Optional, Tuple

# 配置常量
MAX_FAILED_BY_USER: int = 5  # 同用户名最大失败次数
LOCK_TIME_USER: int = 15 * 60  # 用户名锁定时间（秒）
MAX_FAILED_BY_IP: int = 10  # 同 IP 最大失败次数
LOCK_TIME_IP: int = 30 * 60  # IP 锁定时间（秒）

# 内存存储（线程安全）
_lock = threading.Lock()
# key -> (count, last_ts)
_fail_counts: Dict[str, Tuple[int, float]] = {}
# key -> expire_ts
_locks: Dict[str, float] = {}


def _cleanup_expired() -> None:
    """
    清理过期的失败计数和锁定（调用方持锁）。

    清理规则：
    - 失败计数超过 LOCK_TIME_USER 秒后清理
    - 锁定时间过期后清理
    """
    now = time.time()
    expired_keys = [k for k, (_, ts) in _fail_counts.items() if now - ts > LOCK_TIME_USER]
    for k in expired_keys:
        _fail_counts.pop(k, None)
    expired_locks = [k for k, exp in _locks.items() if now > exp]
    for k in expired_locks:
        _locks.pop(k, None)


def _get_fail_count(key: str) -> int:
    """
    获取失败计数（线程安全）。

    Args:
        key: 键（用户名或 IP）

    Returns:
        int: 失败计数
    """
    with _lock:
        _cleanup_expired()
        item = _fail_counts.get(key)
        return item[0] if item else 0


def _incr_fail(key: str) -> int:
    """
    增加失败计数（线程安全）。

    Args:
        key: 键（用户名或 IP）

    Returns:
        int: 增加后的失败计数
    """
    with _lock:
        _cleanup_expired()
        item = _fail_counts.get(key)
        new_count = (item[0] if item else 0) + 1
        _fail_counts[key] = (new_count, time.time())
        return new_count


def _reset_fail(key: str) -> None:
    """
    重置失败计数（线程安全）。

    Args:
        key: 键（用户名或 IP）
    """
    with _lock:
        _fail_counts.pop(key, None)


def _is_locked(key: str) -> Tuple[bool, Optional[int]]:
    """
    检查是否被锁定（线程安全）。

    Args:
        key: 键（用户名或 IP）

    Returns:
        Tuple[bool, Optional[int]]: (是否锁定, 剩余秒数)
    """
    with _lock:
        _cleanup_expired()
        exp = _locks.get(key)
        if exp:
            remaining = int(exp - time.time())
            if remaining > 0:
                return True, remaining
            _locks.pop(key, None)
    return False, None


def _lock_key(key: str, lock_seconds: int) -> None:
    """
    锁定键（线程安全）。

    Args:
        key: 键（用户名或 IP）
        lock_seconds: 锁定时间（秒）
    """
    with _lock:
        _locks[key] = time.time() + lock_seconds


# ---------------- 对外接口 ----------------


def check_login_locked(username: str, client_ip: str = "") -> Tuple[bool, str]:
    """
    检查用户名或 IP 是否被锁定。

    检查顺序：先检查用户名，再检查 IP。

    Args:
        username: 用户名
        client_ip: 客户端 IP，可选

    Returns:
        Tuple[bool, str]: (是否锁定, 提示信息)
    """
    # 检查用户名锁定
    locked, remaining = _is_locked(f"user:{username}")
    if locked:
        mins = (remaining + 59) // 60
        return True, f"账号已临时锁定，请 {mins} 分钟后再试（连续失败过多）"

    # 检查 IP 锁定
    if client_ip:
        locked, remaining = _is_locked(f"ip:{client_ip}")
        if locked:
            mins = (remaining + 59) // 60
            return True, f"该网络环境已临时锁定，请 {mins} 分钟后再试"

    return False, ""


def record_login_failure(username: str, client_ip: str = "") -> Tuple[bool, str]:
    """
    记录一次登录失败，返回 (是否触发锁定, 提示信息)。

    处理逻辑：
    1. 增加用户名失败计数，达到阈值时锁定
    2. 增加 IP 失败计数，达到阈值时锁定
    3. 返回锁定状态或剩余尝试次数

    Args:
        username: 用户名
        client_ip: 客户端 IP，可选

    Returns:
        Tuple[bool, str]: (是否触发锁定, 提示信息)
    """
    # 用户名失败计数
    user_count = _incr_fail(f"user:{username}")
    user_locked = False
    if user_count >= MAX_FAILED_BY_USER:
        _lock_key(f"user:{username}", LOCK_TIME_USER)
        _reset_fail(f"user:{username}")
        user_locked = True

    # IP 失败计数
    ip_locked = False
    if client_ip:
        ip_count = _incr_fail(f"ip:{client_ip}")
        if ip_count >= MAX_FAILED_BY_IP:
            _lock_key(f"ip:{client_ip}", LOCK_TIME_IP)
            _reset_fail(f"ip:{client_ip}")
            ip_locked = True

    if user_locked:
        return True, f"连续失败 {MAX_FAILED_BY_USER} 次，账号已锁定 15 分钟"
    if ip_locked:
        return True, f"该网络环境连续失败过多，已锁定 30 分钟"

    remaining = MAX_FAILED_BY_USER - user_count
    return False, f"邮箱或密码错误，还可尝试 {remaining} 次"


def record_login_success(username: str, client_ip: str = "") -> None:
    """
    登录成功，重置失败计数。

    Args:
        username: 用户名
        client_ip: 客户端 IP，可选
    """
    _reset_fail(f"user:{username}")
    if client_ip:
        _reset_fail(f"ip:{client_ip}")


def get_login_status(username: str, client_ip: str = "") -> Dict[str, Any]:
    """
    获取登录安全状态（供管理后台查看）。

    Args:
        username: 用户名
        client_ip: 客户端 IP，可选

    Returns:
        Dict[str, Any]: 登录安全状态字典，包含用户名和 IP 的失败计数、锁定状态等
    """
    user_fail = _get_fail_count(f"user:{username}")
    user_locked, user_remaining = _is_locked(f"user:{username}")
    ip_fail = _get_fail_count(f"ip:{client_ip}") if client_ip else 0
    ip_locked, ip_remaining = (
        _is_locked(f"ip:{client_ip}") if client_ip else (False, None)
    )

    return {
        "username": username,
        "user_fail_count": user_fail,
        "user_locked": user_locked,
        "user_lock_remaining": user_remaining,
        "ip": client_ip,
        "ip_fail_count": ip_fail,
        "ip_locked": ip_locked,
        "ip_lock_remaining": ip_remaining,
    }
