"""全局配置：从环境变量 / .env 读取。

支持多环境配置：
- 通过 ENV 环境变量指定运行环境（dev/staging/prod），默认 dev
- 按优先级加载配置文件：.env.{ENV} > .env > 环境变量
- 不同环境可配置不同的日志级别、调试模式、数据库连接等

配置风格参考 caasm_server：
- 使用 dataclass 定义配置类
- 配置项按功能分组（App、API、Auth、DB、AI、Map、Cache、Log）
- 配置项有明确的类型注解和默认值
- 增加配置验证方法
"""
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# 运行环境：dev / staging / prod，默认 dev
ENV = os.getenv("ENV", "dev").strip().lower()
if ENV not in ("dev", "staging", "prod"):
    ENV = "dev"

# 按优先级加载配置文件：.env.{ENV} > .env
# 先加载 .env（基础配置），再加载 .env.{ENV}（环境特定配置，覆盖基础配置）
load_dotenv(BASE_DIR / ".env", override=False)
_env_file = BASE_DIR / f".env.{ENV}"
if _env_file.exists():
    load_dotenv(_env_file, override=True)


def _get_bool(key: str, default: bool = False) -> bool:
    """从环境变量读取布尔值"""
    return os.getenv(key, str(default)).lower() in ("true", "1", "yes", "on")


def _get_int(key: str, default: int = 0) -> int:
    """从环境变量读取整数值"""
    try:
        return int(os.getenv(key, str(default)))
    except (ValueError, TypeError):
        return default


def _get_str(key: str, default: str = "") -> str:
    """从环境变量读取字符串值"""
    return os.getenv(key, default).strip()


def _get_list(key: str, default: str = "", separator: str = ",") -> List[str]:
    """从环境变量读取列表值"""
    value = os.getenv(key, default)
    return [item.strip() for item in value.split(separator) if item.strip()]


# ============================================================
# 地图 Key 运行时状态（启动探测 / 后台覆盖）
# ============================================================

# 高德 Key 实际可用性（None=未探测，True/False=探测结果）
_AMAP_EFFECTIVE: Optional[bool] = None
# 腾讯 Key 实际可用性（None=未探测，True/False=探测结果）
_TENCENT_EFFECTIVE: Optional[bool] = None

# 后台可动态覆盖的高德 Key（None=未覆盖，使用环境变量）
_AMAP_KEY_OVERRIDE: Optional[str] = None
# 后台可动态覆盖的腾讯 Key（None=未覆盖，使用环境变量）
_TENCENT_KEY_OVERRIDE: Optional[str] = None


def set_amap_effective(ok: bool) -> None:
    """由启动探测写入：高德 Key 是否真的可用（Key 类型不符 / 未配置 → False）"""
    global _AMAP_EFFECTIVE
    _AMAP_EFFECTIVE = ok


def set_tencent_effective(ok: bool) -> None:
    """由启动探测写入：腾讯 Key 是否真的可用（未配置 / 无效 → False）"""
    global _TENCENT_EFFECTIVE
    _TENCENT_EFFECTIVE = ok


def set_amap_key(key: str) -> None:
    """后台保存 Key 后运行时覆盖；传空串则清除覆盖、回退环境变量。"""
    global _AMAP_KEY_OVERRIDE
    _AMAP_KEY_OVERRIDE = (key or "").strip() or None


def set_tencent_key(key: str) -> None:
    """后台保存腾讯 Key 后运行时覆盖；传空串则清除覆盖、回退环境变量。"""
    global _TENCENT_KEY_OVERRIDE
    _TENCENT_KEY_OVERRIDE = (key or "").strip() or None


def amap_key_source() -> str:
    """当前高德 Key 来源：site=后台配置 / env=环境变量 / none=未配置"""
    if _AMAP_KEY_OVERRIDE:
        return "site"
    return "env" if os.getenv("AMAP_KEY", "").strip() else "none"


def tencent_key_source() -> str:
    """当前腾讯 Key 来源：site=后台配置 / env=环境变量 / none=未配置"""
    if _TENCENT_KEY_OVERRIDE:
        return "site"
    return "env" if os.getenv("TENCENT_KEY", "").strip() else "none"


# ============================================================
# 配置分组类（按功能划分）
# ============================================================

@dataclass
class AppConfig:
    """应用基础配置"""
    name: str = "AI 旅行行程规划"
    version: str = "0.1.0"
    env: str = ENV  # dev / staging / prod
    debug: bool = field(default_factory=lambda: _get_bool("DEBUG", ENV == "dev"))


@dataclass
class APIConfig:
    """API 配置"""
    cors_origins: List[str] = field(
        default_factory=lambda: _get_list(
            "CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173" if ENV == "dev" else "*",
        )
    )


@dataclass
class AuthConfig:
    """认证配置（JWT）

    注意：jwt_secret 为敏感配置，必须在环境变量中配置，不使用硬编码默认值。
    生产环境未配置时将抛出异常，开发环境未配置时将给出警告。
    """
    jwt_secret: str = field(default_factory=lambda: _get_str("JWT_SECRET"))
    jwt_algorithm: str = field(default_factory=lambda: _get_str("JWT_ALGORITHM", "HS256"))
    token_expire_hours: int = field(default_factory=lambda: _get_int("TOKEN_EXPIRE_HOURS", 24))


@dataclass
class DBConfig:
    """数据库配置（MySQL + 连接池）

    注意：password 为敏感配置，必须在环境变量中配置，不使用硬编码默认值。
    生产环境未配置时将抛出异常，开发环境未配置时将给出警告。
    """
    # 基础连接
    host: str = field(default_factory=lambda: _get_str("DB_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: _get_int("DB_PORT", 3306))
    user: str = field(default_factory=lambda: _get_str("DB_USER", "travel"))
    password: str = field(default_factory=lambda: _get_str("DB_PASSWORD"))
    name: str = field(default_factory=lambda: _get_str("DB_NAME", "travel_app"))

    # 连接池配置
    pool_max_connections: int = field(default_factory=lambda: _get_int("DB_POOL_MAX_CONNECTIONS", 10))
    pool_min_cached: int = field(default_factory=lambda: _get_int("DB_POOL_MIN_CACHED", 2))
    pool_max_cached: int = field(default_factory=lambda: _get_int("DB_POOL_MAX_CACHED", 5))
    pool_max_shared: int = field(default_factory=lambda: _get_int("DB_POOL_MAX_SHARED", 5))
    pool_blocking: bool = field(default_factory=lambda: _get_bool("DB_POOL_BLOCKING", True))
    pool_max_usage: int = field(default_factory=lambda: _get_int("DB_POOL_MAX_USAGE", 0))  # 0=不限制

    # 超时配置
    connect_timeout: int = field(default_factory=lambda: _get_int("DB_CONNECT_TIMEOUT", 5))
    read_timeout: int = field(default_factory=lambda: _get_int("DB_READ_TIMEOUT", 30))
    write_timeout: int = field(default_factory=lambda: _get_int("DB_WRITE_TIMEOUT", 30))

    @property
    def dsn(self) -> str:
        """数据库连接 DSN"""
        return f"mysql+pymysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}?charset=utf8mb4"


@dataclass
class AIConfig:
    """AI 模型配置（支持本地Ollama和线上OpenAI兼容API）"""
    # 模型提供方：ollama（本地）/ openai（线上OpenAI兼容API）
    ai_provider: str = field(default_factory=lambda: _get_str("AI_PROVIDER", "ollama"))
    
    # 本地Ollama配置
    ollama_base_url: str = field(
        default_factory=lambda: _get_str("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    )
    ollama_model: str = field(default_factory=lambda: _get_str("OLLAMA_MODEL", "qwen2.5:3b"))
    
    # 线上OpenAI兼容API配置（DeepSeek、通义千问、智谱AI等）
    openai_base_url: str = field(
        default_factory=lambda: _get_str("OPENAI_BASE_URL", "https://api.deepseek.com/v1").rstrip("/")
    )
    openai_api_key: str = field(default_factory=lambda: _get_str("OPENAI_API_KEY", ""))
    openai_model: str = field(default_factory=lambda: _get_str("OPENAI_MODEL", "deepseek-chat"))
    
    # 每日调用次数限制（按用户），0表示不限制
    daily_chat_limit: int = field(default_factory=lambda: _get_int("DAILY_CHAT_LIMIT", 50))
    # 每日规划次数限制（按用户），0表示不限制
    daily_plan_limit: int = field(default_factory=lambda: _get_int("DAILY_PLAN_LIMIT", 10))
    
    # 全局每日调用次数限制（所有用户共享），0表示不限制
    global_daily_chat_limit: int = field(default_factory=lambda: _get_int("GLOBAL_DAILY_CHAT_LIMIT", 0))
    global_daily_plan_limit: int = field(default_factory=lambda: _get_int("GLOBAL_DAILY_PLAN_LIMIT", 0))


@dataclass
class SMSConfig:
    """短信验证码服务配置（互亿无线）"""
    # 是否启用短信验证码服务
    sms_enabled: bool = field(default_factory=lambda: _get_bool("SMS_ENABLED", False))
    # 互亿无线API地址
    sms_api_url: str = field(default_factory=lambda: _get_str("SMS_API_URL", "https://106.ihuyi.com/webservice/sms.php?method=Submit"))
    # 互亿无线APIID（账号）
    sms_api_id: str = field(default_factory=lambda: _get_str("SMS_API_ID", ""))
    # 互亿无线APIKey（密钥）
    sms_api_key: str = field(default_factory=lambda: _get_str("SMS_API_KEY", ""))
    # 短信签名（如：【去见山海】）
    sms_sign: str = field(default_factory=lambda: _get_str("SMS_SIGN", "【去见山海】"))
    # 验证码有效期（秒），默认5分钟
    sms_code_expire: int = field(default_factory=lambda: _get_int("SMS_CODE_EXPIRE", 300))
    # 同一手机号发送间隔（秒），默认60秒
    sms_send_interval: int = field(default_factory=lambda: _get_int("SMS_SEND_INTERVAL", 60))
    # 同一手机号每天最大发送次数
    sms_daily_limit: int = field(default_factory=lambda: _get_int("SMS_DAILY_LIMIT", 10))


@dataclass
class EmailConfig:
    """邮箱验证码服务配置（SMTP）"""
    # 是否启用邮箱验证码服务
    email_enabled: bool = field(default_factory=lambda: _get_bool("EMAIL_ENABLED", False))
    # SMTP服务器地址
    smtp_host: str = field(default_factory=lambda: _get_str("SMTP_HOST", "smtp.qq.com"))
    # SMTP服务器端口
    smtp_port: int = field(default_factory=lambda: _get_int("SMTP_PORT", 465))
    # SMTP用户名（邮箱地址）
    smtp_user: str = field(default_factory=lambda: _get_str("SMTP_USER", ""))
    # SMTP密码（授权码，不是邮箱密码）
    smtp_password: str = field(default_factory=lambda: _get_str("SMTP_PASSWORD", ""))
    # 发件人名称
    sender_name: str = field(default_factory=lambda: _get_str("EMAIL_SENDER_NAME", "去见山海"))
    # 验证码有效期（秒），默认10分钟
    email_code_expire: int = field(default_factory=lambda: _get_int("EMAIL_CODE_EXPIRE", 600))
    # 同一邮箱发送间隔（秒），默认60秒
    email_send_interval: int = field(default_factory=lambda: _get_int("EMAIL_SEND_INTERVAL", 60))
    # 同一邮箱每天最大发送次数
    email_daily_limit: int = field(default_factory=lambda: _get_int("EMAIL_DAILY_LIMIT", 10))


@dataclass
class MapConfig:
    """地图服务配置（高德 + 腾讯）"""

    @property
    def amap_key(self) -> str:
        """当前生效的高德 Web 服务 Key：后台配置优先，其次环境变量。"""
        if _AMAP_KEY_OVERRIDE:
            return _AMAP_KEY_OVERRIDE
        return _get_str("AMAP_KEY")

    @property
    def tencent_key(self) -> str:
        """当前生效的腾讯地图 Key：后台配置优先，其次环境变量。"""
        if _TENCENT_KEY_OVERRIDE:
            return _TENCENT_KEY_OVERRIDE
        return _get_str("TENCENT_KEY")

    @property
    def tencent_sk(self) -> str:
        """腾讯地图签名密钥（环境变量 TENCENT_SK）。"""
        return _get_str("TENCENT_SK")

    @property
    def amap_ready(self) -> bool:
        """高德 Key 是否真实可用（配置且通过启动探测；否则标记为不可用）"""
        if not self.amap_key:
            return False
        if _AMAP_EFFECTIVE is None:
            # 尚未探测（极少见）：先按已配置处理，启动探测会尽快覆盖
            return True
        return _AMAP_EFFECTIVE

    @property
    def tencent_ready(self) -> bool:
        """腾讯 Key 是否真实可用（配置且通过启动探测）"""
        if not self.tencent_key:
            return False
        if _TENCENT_EFFECTIVE is None:
            return True
        return _TENCENT_EFFECTIVE


@dataclass
class CacheConfig:
    """缓存配置（Redis + 内存缓存）"""
    # Redis 配置
    redis_enabled: bool = field(default_factory=lambda: _get_bool("REDIS_ENABLED", False))
    redis_host: str = field(default_factory=lambda: _get_str("REDIS_HOST", "127.0.0.1"))
    redis_port: int = field(default_factory=lambda: _get_int("REDIS_PORT", 6379))
    redis_password: str = field(default_factory=lambda: _get_str("REDIS_PASSWORD"))
    redis_db: int = field(default_factory=lambda: _get_int("REDIS_DB", 0))
    redis_max_connections: int = field(default_factory=lambda: _get_int("REDIS_MAX_CONNECTIONS", 10))
    redis_socket_timeout: int = field(default_factory=lambda: _get_int("REDIS_SOCKET_TIMEOUT", 5))
    redis_socket_connect_timeout: int = field(
        default_factory=lambda: _get_int("REDIS_SOCKET_CONNECT_TIMEOUT", 5)
    )
    redis_key_prefix: str = field(default_factory=lambda: _get_str("REDIS_KEY_PREFIX", "travel:"))


@dataclass
class LogConfig:
    """日志配置"""
    level: str = field(
        default_factory=lambda: _get_str("LOG_LEVEL", "DEBUG" if ENV == "dev" else "INFO").upper()
    )
    format: str = field(
        default_factory=lambda: _get_str("LOG_FORMAT", "json" if ENV == "prod" else "text").lower()
    )
    dir: str = field(default_factory=lambda: _get_str("LOG_DIR", ""))


# ============================================================
# 主配置类（组合所有配置分组，保持向后兼容性）
# ============================================================

@dataclass
class Settings:
    """全局配置主类

    按功能分组配置，同时保持向后兼容性（支持 settings.xxx 的访问方式）。
    """

    # 配置分组
    app: AppConfig = field(default_factory=AppConfig)
    api: APIConfig = field(default_factory=APIConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)
    db: DBConfig = field(default_factory=DBConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    map: MapConfig = field(default_factory=MapConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    log: LogConfig = field(default_factory=LogConfig)
    sms: SMSConfig = field(default_factory=SMSConfig)
    email: EmailConfig = field(default_factory=EmailConfig)

    # ============================================================
    # 向后兼容属性（保持原有 settings.xxx 的访问方式）
    # ============================================================

    # ---- 应用基础 ----
    @property
    def app_name(self) -> str:
        return self.app.name

    @property
    def version(self) -> str:
        return self.app.version

    @property
    def env(self) -> str:
        return self.app.env

    @property
    def debug(self) -> bool:
        return self.app.debug

    # ---- 日志 ----
    @property
    def log_level(self) -> str:
        return self.log.level

    @property
    def log_format(self) -> str:
        return self.log.format

    # ---- CORS ----
    @property
    def cors_origins(self) -> List[str]:
        return self.api.cors_origins

    # ---- 高德地图 ----
    @property
    def amap_key(self) -> str:
        return self.map.amap_key

    @property
    def amap_ready(self) -> bool:
        return self.map.amap_ready

    # ---- 腾讯地图 ----
    @property
    def tencent_key(self) -> str:
        return self.map.tencent_key

    @property
    def tencent_sk(self) -> str:
        return self.map.tencent_sk

    @property
    def tencent_ready(self) -> bool:
        return self.map.tencent_ready

    # ---- AI 模型 ----
    @property
    def ollama_base_url(self) -> str:
        return self.ai.ollama_base_url

    @property
    def ollama_model(self) -> str:
        return self.ai.ollama_model

    # ---- MySQL ----
    @property
    def db_host(self) -> str:
        return self.db.host

    @property
    def db_port(self) -> int:
        return self.db.port

    @property
    def db_user(self) -> str:
        return self.db.user

    @property
    def db_password(self) -> str:
        return self.db.password

    @property
    def db_name(self) -> str:
        return self.db.name

    # ---- 数据库连接池 ----
    @property
    def db_pool_max_connections(self) -> int:
        return self.db.pool_max_connections

    @property
    def db_pool_min_cached(self) -> int:
        return self.db.pool_min_cached

    @property
    def db_pool_max_cached(self) -> int:
        return self.db.pool_max_cached

    @property
    def db_pool_max_shared(self) -> int:
        return self.db.pool_max_shared

    @property
    def db_pool_blocking(self) -> bool:
        return self.db.pool_blocking

    @property
    def db_pool_max_usage(self) -> int:
        return self.db.pool_max_usage

    @property
    def db_connect_timeout(self) -> int:
        return self.db.connect_timeout

    @property
    def db_read_timeout(self) -> int:
        return self.db.read_timeout

    @property
    def db_write_timeout(self) -> int:
        return self.db.write_timeout

    # ---- JWT ----
    @property
    def jwt_secret(self) -> str:
        return self.auth.jwt_secret

    @property
    def jwt_algorithm(self) -> str:
        return self.auth.jwt_algorithm

    @property
    def token_expire_hours(self) -> int:
        return self.auth.token_expire_hours

    # ---- Redis ----
    @property
    def redis_enabled(self) -> bool:
        return self.cache.redis_enabled

    @property
    def redis_host(self) -> str:
        return self.cache.redis_host

    @property
    def redis_port(self) -> int:
        return self.cache.redis_port

    @property
    def redis_password(self) -> str:
        return self.cache.redis_password

    @property
    def redis_db(self) -> int:
        return self.cache.redis_db

    @property
    def redis_max_connections(self) -> int:
        return self.cache.redis_max_connections

    @property
    def redis_socket_timeout(self) -> int:
        return self.cache.redis_socket_timeout

    @property
    def redis_socket_connect_timeout(self) -> int:
        return self.cache.redis_socket_connect_timeout

    @property
    def redis_key_prefix(self) -> str:
        return self.cache.redis_key_prefix

    # ============================================================
    # 配置验证
    # ============================================================

    def validate(self) -> List[str]:
        """验证配置有效性，返回警告列表（空列表表示无警告）

        注意：敏感配置（如 JWT_SECRET、DB_PASSWORD）未配置时，
        开发环境给出警告，生产环境应视为严重错误。
        """
        warnings = []

        # 生产环境安全检查
        if self.app.env == "prod":
            if not self.auth.jwt_secret:
                warnings.append("【严重】生产环境 JWT_SECRET 未配置，用户认证将无法正常工作")
            if not self.db.password:
                warnings.append("【严重】生产环境 DB_PASSWORD 未配置，数据库连接将失败")
            if self.app.debug:
                warnings.append("生产环境不应该开启 DEBUG 模式")
            if self.log.level == "DEBUG":
                warnings.append("生产环境日志级别不应该是 DEBUG")
        else:
            # 开发环境警告
            if not self.auth.jwt_secret:
                warnings.append("【警告】开发环境 JWT_SECRET 未配置，使用空值可能导致认证问题")
            if not self.db.password:
                warnings.append("【警告】开发环境 DB_PASSWORD 未配置，数据库连接可能失败")

        # 数据库配置检查
        if not self.db.host:
            warnings.append("数据库主机地址未配置")
        if not self.db.name:
            warnings.append("数据库名称未配置")
        if not self.db.user:
            warnings.append("数据库用户名未配置")

        # AI 模型配置检查
        if not self.ai.ollama_base_url:
            warnings.append("Ollama 服务地址未配置")
        if not self.ai.ollama_model:
            warnings.append("Ollama 模型名称未配置")

        # 地图服务配置检查
        if not self.map.amap_key and not self.map.tencent_key:
            warnings.append("高德和腾讯地图 Key 都未配置，地图相关功能将不可用")

        return warnings

    def validate_strict(self) -> None:
        """严格验证配置，如果有严重错误则抛出异常

        用于生产环境启动时的配置检查，确保所有必要配置都已设置。
        """
        warnings = self.validate()
        critical_errors = [w for w in warnings if w.startswith("【严重】")]
        if critical_errors:
            error_msg = "配置验证失败，存在以下严重错误：\n" + "\n".join(critical_errors)
            raise ValueError(error_msg)

    def get_config_summary(self) -> dict:
        """获取配置摘要（用于日志输出，不包含敏感信息）"""
        return {
            "app": {
                "name": self.app.name,
                "version": self.app.version,
                "env": self.app.env,
                "debug": self.app.debug,
            },
            "log": {
                "level": self.log.level,
                "format": self.log.format,
            },
            "db": {
                "host": self.db.host,
                "port": self.db.port,
                "name": self.db.name,
                "pool_max_connections": self.db.pool_max_connections,
            },
            "ai": {
                "ollama_base_url": self.ai.ollama_base_url,
                "ollama_model": self.ai.ollama_model,
            },
            "map": {
                "amap_key_configured": bool(self.map.amap_key),
                "amap_ready": self.map.amap_ready,
                "tencent_key_configured": bool(self.map.tencent_key),
                "tencent_ready": self.map.tencent_ready,
            },
            "cache": {
                "redis_enabled": self.cache.redis_enabled,
                "redis_host": self.cache.redis_host if self.cache.redis_enabled else None,
            },
        }


# 全局配置单例
settings = Settings()
