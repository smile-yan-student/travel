"""
用户与出行记录存储（MySQL + bcrypt + JWT，生产方案）。

- 数据库：MySQL（pymysql），连接信息来自 config.Settings。
- 密码：bcrypt 哈希；兼容旧 sha256 格式（登录校验通过后自动升级为 bcrypt，业界标准哈希升级）。
- 会话：JWT（HS256）带 exp 过期时间，无状态、不落库；过期自动失效。
- 对话历史：conversations 表按用户存储（messages JSON，含行程 plan），未登录会话存前端本地。
- 未登录不记录任何出行；登录后通过 JWT 定位用户，数据仅对本人可见。

功能特性：
- 用户管理（注册、登录、用户名检查、凭证校验）
- 密码管理（bcrypt 哈希、旧 sha256 兼容升级）
- JWT 管理（创建 token、校验 token）
- 出行记录管理（添加、汇总）
- 对话历史管理（列表、获取、保存、删除、流式加载）
- 数据库初始化（创建表、添加列）

使用方式：
    from app.data.repositories.user_repository import (
        register, login, create_token, user_by_token,
        add_trip, trips_summary,
        list_conversations, get_conversation, save_conversation, delete_conversation
    )

    # 注册
    user, err = register("username", "Password123!")

    # 登录
    result = login("username", "Password123!")
    if result:
        token, user = result

    # 创建 token
    token = create_token(1, "username")

    # 校验 token
    user = user_by_token(token)

    # 添加出行记录
    add_trip(1, "杭州", 3, "美食+人文", 120.15, 30.28, 150.5)

    # 获取出行汇总
    summary = trips_summary(1)

    # 对话历史
    conversations = list_conversations(1)
    conversation = get_conversation(1, 1)
    conversation = save_conversation(1, None, "新对话", [])
    success = delete_conversation(1, 1)
"""
import datetime
import hashlib
import json
import re
from typing import Any, Dict, List, Optional, Tuple

import bcrypt
import jwt
import pymysql

from ...config import settings
from ..database import get_conn, read_connection, transaction

# bcrypt 哈希前缀（$2a/$2b/$2y）
BCRYPT_PREFIX = "$2"
# 旧 sha256 存储格式：salt$hash
LEGACY_SEP = "$"

# 特殊字符集（密码组合校验用）
_PASSWORD_SPECIAL = set("~!@#$%^&*()_+-=[]{}|;:,.<>?/")


def init_db() -> None:
    """
    初始化数据库：创建所有表（幂等）。

    创建的表：
    - users：用户表
    - trips：出行记录表
    - conversations：对话历史表
    - admins：管理员表
    - must_visit：必去景点表
    - site_config：站点配置表
    - generation_log：生成日志表

    同时会为 users 表添加 enabled 列（如果不存在）。
    """
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(20) UNIQUE NOT NULL,
                    password_hash VARCHAR(100) NOT NULL,
                    created_at DATETIME NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS trips (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    destination VARCHAR(50) NOT NULL,
                    days INT NOT NULL DEFAULT 1,
                    style VARCHAR(50) DEFAULT '',
                    lng DOUBLE DEFAULT 0,
                    lat DOUBLE DEFAULT 0,
                    distance_km DOUBLE DEFAULT 0,
                    created_at DATETIME NOT NULL,
                    INDEX idx_trips_user (user_id),
                    CONSTRAINT fk_trips_user FOREIGN KEY (user_id)
                        REFERENCES users(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    title VARCHAR(60) NOT NULL DEFAULT '未命名对话',
                    messages JSON NOT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    INDEX idx_convo_user (user_id),
                    CONSTRAINT fk_convo_user FOREIGN KEY (user_id)
                        REFERENCES users(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
            # 管理后台相关表
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS admins (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(32) UNIQUE NOT NULL,
                    password_hash VARCHAR(100) NOT NULL,
                    role VARCHAR(16) NOT NULL DEFAULT 'ops',
                    enabled TINYINT(1) NOT NULL DEFAULT 1,
                    created_at DATETIME NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS must_visit (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    city VARCHAR(50) NOT NULL,
                    name VARCHAR(100) NOT NULL,
                    kw VARCHAR(100) NOT NULL DEFAULT '',
                    category VARCHAR(20) NOT NULL DEFAULT '景点',
                    rating DOUBLE NOT NULL DEFAULT 4.5,
                    priority INT NOT NULL DEFAULT 50,
                    created_at DATETIME NOT NULL,
                    INDEX idx_mv_city (city)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS site_config (
                    k VARCHAR(64) PRIMARY KEY,
                    v VARCHAR(500) NOT NULL DEFAULT '',
                    updated_at DATETIME NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS generation_log (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    kind VARCHAR(20) NOT NULL,
                    model VARCHAR(50) NOT NULL DEFAULT '',
                    status VARCHAR(16) NOT NULL DEFAULT 'ok',
                    ms INT NOT NULL DEFAULT 0,
                    detail VARCHAR(500) NOT NULL DEFAULT '',
                    created_at DATETIME NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
            # users 表增加 enabled 列（幂等）
            cur.execute(
                "SELECT COUNT(*) AS c FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA=%s AND TABLE_NAME='users' AND COLUMN_NAME='enabled'",
                (settings.db_name,),
            )
            if cur.fetchone()["c"] == 0:
                cur.execute(
                    "ALTER TABLE users ADD COLUMN enabled TINYINT(1) NOT NULL DEFAULT 1"
                )


# ---------------- 密码（bcrypt + 旧 sha256 兼容升级） ----------------


def _bcrypt_hash(password: str) -> str:
    """
    使用 bcrypt 哈希密码。

    Args:
        password: 明文密码

    Returns:
        str: bcrypt 哈希值
    """
    return bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt(rounds=12)
    ).decode("utf-8")


def _legacy_sha256(password: str, salt: str) -> str:
    """
    使用旧的 sha256 方式哈希密码（兼容旧格式）。

    Args:
        password: 明文密码
        salt: 盐值

    Returns:
        str: sha256 哈希值
    """
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


def _verify_and_maybe_upgrade(
    password: str, stored: str
) -> Tuple[bool, Optional[str]]:
    """
    校验密码。

    返回 (是否通过, 新哈希)。新哈希非 None 时表示旧格式已通过、需写入 bcrypt 升级。

    Args:
        password: 明文密码
        stored: 存储的哈希值

    Returns:
        Tuple[bool, Optional[str]]: (是否通过, 新哈希（如果需要升级）)
    """
    if stored.startswith(BCRYPT_PREFIX):
        try:
            return (
                bcrypt.checkpw(password.encode("utf-8"), stored.encode("utf-8")),
                None,
            )
        except ValueError:
            return False, None
    if LEGACY_SEP in stored:
        salt, h = stored.split(LEGACY_SEP, 1)
        if _legacy_sha256(password, salt) == h:
            return True, _bcrypt_hash(password)  # 通过 → 升级为 bcrypt
    return False, None


# ---------------- JWT ----------------


def create_token(user_id: int, username: str) -> str:
    """
    创建 JWT token。

    Args:
        user_id: 用户ID
        username: 用户名

    Returns:
        str: JWT token
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": str(user_id),
        "username": username,
        "iat": now,
        "exp": now + datetime.timedelta(hours=settings.token_expire_hours),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def user_by_token(token: str) -> Optional[Dict[str, Any]]:
    """
    校验 JWT（含过期、黑名单），返回用户；无效/过期/不存在/已停用/已登出返回 None。

    Args:
        token: JWT token

    Returns:
        Optional[Dict[str, Any]]: 用户信息（id, username），无效返回 None
    """
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        uid = int(payload["sub"])
        exp = payload.get("exp")
    except (jwt.ExpiredSignatureError, jwt.PyJWTError, KeyError, ValueError):
        return None

    # 检查Token是否在黑名单中（已登出）
    if is_token_blacklisted(token):
        return None

    with read_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username FROM users WHERE id=%s AND enabled=1", (uid,)
            )
            return cur.fetchone()


def is_token_blacklisted(token: str) -> bool:
    """
    检查Token是否在黑名单中（已登出）。

    Args:
        token: JWT token

    Returns:
        bool: 是否在黑名单中
    """
    try:
        with read_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM token_blacklist WHERE token=%s AND expires_at > NOW() LIMIT 1",
                    (token,)
                )
                return cur.fetchone() is not None
    except Exception:
        return False


def blacklist_token(token: str, user_id: int) -> bool:
    """
    将Token加入黑名单（登出）。

    Args:
        token: JWT token
        user_id: 用户ID

    Returns:
        bool: 是否成功
    """
    try:
        # 解析Token获取过期时间
        try:
            payload = jwt.decode(
                token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
            )
            exp_timestamp = payload.get("exp")
            if exp_timestamp:
                expires_at = datetime.datetime.fromtimestamp(exp_timestamp)
            else:
                expires_at = datetime.datetime.now() + datetime.timedelta(hours=settings.token_expire_hours)
        except Exception:
            expires_at = datetime.datetime.now() + datetime.timedelta(hours=settings.token_expire_hours)

        with transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO token_blacklist(token, user_id, expires_at, created_at) VALUES(%s,%s,%s,%s)",
                    (token, user_id, expires_at, datetime.datetime.now())
                )
                return True
    except Exception as e:
        print(f"Token加入黑名单失败: {e}")
        return False


def change_password(user_id: int, old_password: str, new_password: str) -> Tuple[bool, Optional[str]]:
    """
    修改用户密码。

    Args:
        user_id: 用户ID
        old_password: 旧密码
        new_password: 新密码

    Returns:
        Tuple[bool, Optional[str]]: (是否成功, 错误信息)
    """
    with read_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT password_hash FROM users WHERE id=%s", (user_id,))
            row = cur.fetchone()
            if not row:
                return False, "用户不存在"
            if not bcrypt.checkpw(old_password.encode('utf-8'), row['password_hash'].encode('utf-8')):
                return False, "旧密码不正确"

    # 验证新密码强度
    if len(new_password) < 8 or len(new_password) > 64:
        return False, "密码长度需为8-64个字符"

    # 密码复杂度检查
    has_upper = any(c.isupper() for c in new_password)
    has_lower = any(c.islower() for c in new_password)
    has_digit = any(c.isdigit() for c in new_password)
    has_special = any(c in '~!@#$%^&*()_+-=[]{}|;:,.<>?' for c in new_password)
    type_count = sum([has_upper, has_lower, has_digit, has_special])
    if type_count < 3:
        return False, "密码需包含大写字母、小写字母、数字、特殊字符中的至少三种"

    # 更新密码
    new_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET password_hash=%s, updated_at=NOW() WHERE id=%s",
                (new_hash, user_id)
            )
            return True, None


# ---------------- 用户 ----------------


def register(
    username: str, password: str
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    注册。成功返回 (user, None)；校验失败/用户名占用返回 (None, 错误信息)。

    Args:
        username: 用户名
        password: 密码

    Returns:
        Tuple[Optional[Dict[str, Any]], Optional[str]]: (用户信息, 错误信息)
    """
    username = (username or "").strip()
    err = validate_credentials(username, password or "")
    if err:
        return None, err
    pw_hash = _bcrypt_hash(password)
    try:
        with transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users(username, password_hash, created_at) VALUES(%s,%s,%s)",
                    (username, pw_hash, datetime.datetime.now()),
                )
                uid = cur.lastrowid
    except pymysql.IntegrityError:
        return None, "用户名已被占用，换一个试试吧"
    return {"id": uid, "username": username}, None


def register_with_email(
    username: str, email: str, password: str
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    带邮箱的注册。成功返回 (user, None)；校验失败/用户名或邮箱占用返回 (None, 错误信息)。

    Args:
        username: 用户名
        email: 邮箱
        password: 密码

    Returns:
        Tuple[Optional[Dict[str, Any]], Optional[str]]: (用户信息, 错误信息)
    """
    username = (username or "").strip()
    email = (email or "").strip().lower()
    err = validate_credentials(username, password or "")
    if err:
        return None, err
    # 邮箱格式校验
    import re
    if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
        return None, "邮箱格式不正确"
    pw_hash = _bcrypt_hash(password)
    try:
        with transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users(username, email, password_hash, created_at) VALUES(%s, %s, %s, %s)",
                    (username, email, pw_hash, datetime.datetime.now()),
                )
                uid = cur.lastrowid
    except pymysql.IntegrityError as e:
        # 判断是用户名重复还是邮箱重复
        if "email" in str(e).lower() or "idx_email" in str(e).lower():
            return None, "该邮箱已被注册，请直接登录"
        return None, "用户名已被占用，换一个试试吧"
    return {"id": uid, "username": username, "email": email}, None


def username_exists(username: str) -> bool:
    """
    用户名是否已占用（不区分大小写）。

    Args:
        username: 用户名

    Returns:
        bool: 是否已占用
    """
    with read_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM users WHERE LOWER(username)=LOWER(%s) LIMIT 1",
                (username or "",),
            )
            return cur.fetchone() is not None


def validate_credentials(username: str, password: str) -> Optional[str]:
    """
    注册密码/用户名规则校验，通过返回 None，否则返回错误提示。

    规则：
    - 用户名 6~20 个字符
    - 密码 8~64 个字符
    - 密码至少包含 大写字母/小写字母/数字/特殊字符 中的三种
    - 密码不能与用户名相同、不能是用户名倒序、不能包含超过两个连续的用户名字符

    Args:
        username: 用户名
        password: 密码

    Returns:
        Optional[str]: 错误信息，通过返回 None
    """
    if not (6 <= len(username) <= 20):
        return "用户名长度需为 6~20 个字符"
    if not (8 <= len(password) <= 64):
        return "密码长度需为 8~64 个字符"
    # 关联性（优先提示，如"与用户名相同"这种明确违规）
    if password == username:
        return "密码不能与用户名相同"
    if password == username[::-1]:
        return "密码不能是用户名的倒序"
    low_pw = password.lower()
    low_un = username.lower()
    for i in range(len(low_un) - 2):
        if low_un[i : i + 3] in low_pw:
            return "密码不能包含超过两个连续的用户名字符"
    # 字符组合：至少 3 类
    classes = 0
    if re.search(r"[A-Z]", password):
        classes += 1
    if re.search(r"[a-z]", password):
        classes += 1
    if re.search(r"\d", password):
        classes += 1
    if any(ch in _PASSWORD_SPECIAL for ch in password):
        classes += 1
    if classes < 3:
        return "密码需包含大写字母、小写字母、数字、特殊字符中的至少三种"
    return None


def login(username: str, password: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """
    登录成功返回 (token, user)；失败返回 None（含已停用账号）。旧格式密码通过后自动升级 bcrypt。

    Args:
        username: 用户名
        password: 密码

    Returns:
        Optional[Tuple[str, Dict[str, Any]]]: (token, user)，失败返回 None
    """
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, password_hash, enabled FROM users WHERE username=%s",
                (username.strip(),),
            )
            row = cur.fetchone()
            if not row or not row["enabled"]:
                return None
            ok, new_hash = _verify_and_maybe_upgrade(password, row["password_hash"])
            if not ok:
                return None
            if new_hash:
                cur.execute(
                    "UPDATE users SET password_hash=%s WHERE id=%s",
                    (new_hash, row["id"]),
                )
            user = {"id": row["id"], "username": row["username"]}
            return create_token(row["id"], row["username"]), user


def login_by_email_password(
    email: str, password: str
) -> Optional[Tuple[str, Dict[str, Any]]]:
    """
    使用邮箱和密码登录。成功返回 (token, user)；失败返回 None。

    Args:
        email: 邮箱
        password: 密码

    Returns:
        Optional[Tuple[str, Dict[str, Any]]]: (token, user)，失败返回 None
    """
    email = (email or "").strip().lower()
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, email, password_hash, enabled FROM users WHERE email=%s",
                (email,),
            )
            row = cur.fetchone()
            if not row or not row["enabled"]:
                return None
            ok, new_hash = _verify_and_maybe_upgrade(password, row["password_hash"])
            if not ok:
                return None
            if new_hash:
                cur.execute(
                    "UPDATE users SET password_hash=%s WHERE id=%s",
                    (new_hash, row["id"]),
                )
            user = {"id": row["id"], "username": row["username"], "email": row["email"]}
            return create_token(row["id"], row["username"]), user


# ---------------- 手机号验证码登录/注册 ----------------


def phone_exists(phone: str) -> bool:
    """
    手机号是否已注册。

    Args:
        phone: 手机号

    Returns:
        bool: 是否已注册
    """
    if not phone:
        return False
    with read_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM users WHERE phone=%s LIMIT 1",
                (phone.strip(),),
            )
            return cur.fetchone() is not None


def get_user_by_phone(phone: str) -> Optional[Dict[str, Any]]:
    """
    根据手机号获取用户信息。

    Args:
        phone: 手机号

    Returns:
        Optional[Dict[str, Any]]: 用户信息，不存在返回 None
    """
    if not phone:
        return None
    with read_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, phone, enabled FROM users WHERE phone=%s LIMIT 1",
                (phone.strip(),),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {"id": row["id"], "username": row["username"], "phone": row["phone"]}


def register_by_phone(phone: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    通过手机号注册用户。

    自动生成用户名（user_ + 手机号后6位），密码为空（手机号登录不需要密码）。

    Args:
        phone: 手机号

    Returns:
        Tuple[Optional[Dict[str, Any]], Optional[str]]: (用户信息, 错误信息)
    """
    phone = (phone or "").strip()
    if not phone:
        return None, "手机号不能为空"

    # 检查手机号是否已注册
    if phone_exists(phone):
        return None, "该手机号已注册，请直接登录"

    # 自动生成用户名（user_ + 手机号后6位）
    username = f"user_{phone[-6:]}"
    # 如果用户名已存在，添加随机后缀
    suffix = 1
    while username_exists(username):
        username = f"user_{phone[-6:]}_{suffix}"
        suffix += 1

    try:
        with transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users(username, phone, password_hash, created_at) VALUES(%s, %s, %s, %s)",
                    (username, phone, "", datetime.datetime.now()),
                )
                uid = cur.lastrowid
    except pymysql.IntegrityError:
        return None, "该手机号已注册，请直接登录"

    return {"id": uid, "username": username, "phone": phone}, None


def login_by_phone(phone: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """
    通过手机号登录（验证码已验证通过后调用）。

    如果手机号未注册，自动注册新用户。

    Args:
        phone: 手机号

    Returns:
        Optional[Tuple[str, Dict[str, Any]]]: (token, user)，失败返回 None
    """
    phone = (phone or "").strip()
    if not phone:
        return None

    # 查找用户
    user = get_user_by_phone(phone)
    if not user:
        # 未注册，自动注册
        user, err = register_by_phone(phone)
        if err or not user:
            return None

    # 检查账号是否启用
    with read_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, phone, enabled FROM users WHERE id=%s",
                (user["id"],),
            )
            row = cur.fetchone()
            if not row or not row["enabled"]:
                return None

    return create_token(row["id"], row["username"]), {"id": row["id"], "username": row["username"], "phone": row["phone"]}


# ---------------- 邮箱验证码登录/注册 ----------------


def email_exists(email: str) -> bool:
    """
    邮箱是否已注册。

    Args:
        email: 邮箱

    Returns:
        bool: 是否已注册
    """
    if not email:
        return False
    with read_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM users WHERE email=%s LIMIT 1",
                (email.strip(),),
            )
            return cur.fetchone() is not None


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """
    根据邮箱获取用户信息。

    Args:
        email: 邮箱

    Returns:
        Optional[Dict[str, Any]]: 用户信息，不存在返回 None
    """
    if not email:
        return None
    with read_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, email, enabled FROM users WHERE email=%s LIMIT 1",
                (email.strip(),),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {"id": row["id"], "username": row["username"], "email": row["email"]}


def register_by_email(email: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    通过邮箱注册用户。

    自动生成用户名（user_ + 邮箱前缀前6位），密码为空（邮箱登录不需要密码）。

    Args:
        email: 邮箱

    Returns:
        Tuple[Optional[Dict[str, Any]], Optional[str]]: (用户信息, 错误信息)
    """
    email = (email or "").strip().lower()
    if not email:
        return None, "邮箱不能为空"

    # 检查邮箱是否已注册
    if email_exists(email):
        return None, "该邮箱已注册，请直接登录"

    # 自动生成用户名（user_ + 邮箱前缀前6位）
    email_prefix = email.split("@")[0]
    username = f"user_{email_prefix[:6]}"
    # 如果用户名已存在，添加随机后缀
    suffix = 1
    while username_exists(username):
        username = f"user_{email_prefix[:6]}_{suffix}"
        suffix += 1

    try:
        with transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users(username, email, password_hash, created_at) VALUES(%s, %s, %s, %s)",
                    (username, email, "", datetime.datetime.now()),
                )
                uid = cur.lastrowid
    except pymysql.IntegrityError:
        return None, "该邮箱已注册，请直接登录"

    return {"id": uid, "username": username, "email": email}, None


def login_by_email(email: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """
    通过邮箱登录（验证码已验证通过后调用）。

    如果邮箱未注册，自动注册新用户。

    Args:
        email: 邮箱

    Returns:
        Optional[Tuple[str, Dict[str, Any]]]: (token, user)，失败返回 None
    """
    email = (email or "").strip().lower()
    if not email:
        return None

    # 查找用户
    user = get_user_by_email(email)
    if not user:
        # 未注册，自动注册
        user, err = register_by_email(email)
        if err or not user:
            return None

    # 检查账号是否启用
    with read_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, email, enabled FROM users WHERE id=%s",
                (user["id"],),
            )
            row = cur.fetchone()
            if not row or not row["enabled"]:
                return None

    return create_token(row["id"], row["username"]), {"id": row["id"], "username": row["username"], "email": row["email"]}


# ---------------- 出行记录 ----------------


def add_trip(
    user_id: int,
    destination: str,
    days: int,
    style: str,
    lng: float,
    lat: float,
    distance_km: float,
    conversation_id: Optional[int] = None,
) -> None:
    """
    添加出行记录。

    Args:
        user_id: 用户ID
        destination: 目的地
        days: 天数
        style: 旅行风格
        lng: 经度
        lat: 纬度
        distance_km: 距离（公里）
        conversation_id: 关联的会话ID
    """
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO trips(user_id, conversation_id, destination, days, style, lng, lat, distance_km, created_at) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    user_id,
                    conversation_id,
                    destination,
                    days,
                    style,
                    lng,
                    lat,
                    distance_km,
                    datetime.datetime.now(),
                ),
            )


def trips_summary(user_id: int) -> Dict[str, Any]:
    """
    本人出行记录 + 汇总：次数、点亮城市数、累计探索里程（km，到参考城市直线距离）。

    Args:
        user_id: 用户ID

    Returns:
        Dict[str, Any]: 出行汇总（trip_count, city_count, total_km, trips）
    """
    with read_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, destination, days, style, distance_km, created_at "
                "FROM trips WHERE user_id=%s ORDER BY created_at DESC",
                (user_id,),
            )
            rows = cur.fetchall()
    trips = []
    for r in rows:
        t = dict(r)
        t["created_at"] = t["created_at"].strftime("%Y-%m-%d %H:%M:%S")
        trips.append(t)
    cities = {t["destination"] for t in trips}
    total_km = round(sum(t["distance_km"] or 0 for t in trips), 1)
    return {
        "trip_count": len(trips),
        "city_count": len(cities),
        "total_km": total_km,
        "trips": trips,
    }


# ---------------- 对话历史（按用户存储） ----------------


def _conv_dt(ts: Any) -> str:
    """
    格式化对话时间戳。

    Args:
        ts: 时间戳

    Returns:
        str: 格式化后的时间字符串
    """
    return ts.strftime("%Y-%m-%d %H:%M:%S") if ts else ""


def list_conversations(
    user_id: int, before_id: Optional[int] = None, limit: int = 20
) -> List[Dict[str, Any]]:
    """
    会话列表（不含 messages 正文，含标题/时间/消息数），按最近更新倒序。

    - 默认返回最新 limit 条（含"当天"会话，由前端按日期分组）。
    - 传 before_id 返回更早（id < before_id）的 limit 条，用于时间线上拉加载更多。

    Args:
        user_id: 用户ID
        before_id: 起始会话ID（返回更早的会话）
        limit: 返回数量

    Returns:
        List[Dict[str, Any]]: 会话列表
    """
    with read_connection() as conn:
        with conn.cursor() as cur:
            sql = (
                "SELECT id, title, created_at, updated_at, "
                "JSON_LENGTH(messages) AS msg_count "
                "FROM conversations WHERE user_id=%s"
            )
            params: List[Any] = [user_id]
            if before_id is not None:
                sql += " AND id < %s"
                params.append(before_id)
            sql += " ORDER BY updated_at DESC, id DESC LIMIT %s"
            params.append(int(limit))
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["created_at"] = _conv_dt(d["created_at"])
        d["updated_at"] = _conv_dt(d["updated_at"])
        out.append(d)
    return out


def get_conversation(user_id: int, conv_id: int) -> Optional[Dict[str, Any]]:
    """
    获取单个会话（含 messages 正文）。

    Args:
        user_id: 用户ID
        conv_id: 会话ID

    Returns:
        Optional[Dict[str, Any]]: 会话信息，不存在返回 None
    """
    with read_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, title, messages, created_at, updated_at "
                "FROM conversations WHERE id=%s AND user_id=%s",
                (conv_id, user_id),
            )
            row = cur.fetchone()
    if not row:
        return None
    d = dict(row)
    d["messages"] = json.loads(d["messages"] or "[]")
    d["created_at"] = _conv_dt(d["created_at"])
    d["updated_at"] = _conv_dt(d["updated_at"])
    return d


def get_conversation_stream(
    user_id: int, before_id: Optional[int] = None, limit: int = 10
) -> List[Dict[str, Any]]:
    """
    统一对话流的会话消息分页（倒序，最新在前，含 messages）。

    - 不传 before_id 返回最近 limit 个会话；传 before_id 返回更早（id < before_id）。
    - 前端把各会话 messages 拼成同一个消息流，滚动加载更早历史。

    Args:
        user_id: 用户ID
        before_id: 起始会话ID（返回更早的会话）
        limit: 返回数量

    Returns:
        List[Dict[str, Any]]: 会话列表（含 messages）
    """
    with read_connection() as conn:
        with conn.cursor() as cur:
            sql = (
                "SELECT id, title, messages, updated_at "
                "FROM conversations WHERE user_id=%s"
            )
            params: List[Any] = [user_id]
            if before_id is not None:
                sql += " AND id < %s"
                params.append(before_id)
            sql += " ORDER BY updated_at DESC, id DESC LIMIT %s"
            params.append(int(limit))
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["messages"] = json.loads(d["messages"] or "[]")
        d["updated_at"] = _conv_dt(d["updated_at"])
        out.append(d)
    return out


def save_conversation(
    user_id: int,
    conv_id: Optional[int],
    title: str,
    messages: List[Any],
) -> Dict[str, Any]:
    """
    创建或更新会话（upsert）。返回完整会话。

    Args:
        user_id: 用户ID
        conv_id: 会话ID（None 表示创建新会话）
        title: 会话标题
        messages: 消息列表

    Returns:
        Dict[str, Any]: 完整会话信息
    """
    title = (title or "未命名对话").strip()[:60] or "未命名对话"
    messages_json = json.dumps(messages, ensure_ascii=False)
    now = datetime.datetime.now()
    with transaction() as conn:
        with conn.cursor() as cur:
            if conv_id:
                cur.execute(
                    "UPDATE conversations SET title=%s, messages=%s, updated_at=%s "
                    "WHERE id=%s AND user_id=%s",
                    (title, messages_json, now, conv_id, user_id),
                )
                if cur.rowcount == 0:
                    conv_id = None
            if not conv_id:
                cur.execute(
                    "INSERT INTO conversations(user_id, title, messages, created_at, updated_at) "
                    "VALUES(%s,%s,%s,%s,%s)",
                    (user_id, title, messages_json, now, now),
                )
                conv_id = cur.lastrowid
    return get_conversation(user_id, conv_id)


def delete_conversation(user_id: int, conv_id: int) -> bool:
    """
    删除会话。

    Args:
        user_id: 用户ID
        conv_id: 会话ID

    Returns:
        bool: 是否删除成功
    """
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM conversations WHERE id=%s AND user_id=%s",
                (conv_id, user_id),
            )
            return cur.rowcount > 0
