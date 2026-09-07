"""
结构化日志监控模块。

能力：
- JSON 格式日志文件（按天轮转，保留 N 天）+ 控制台人类可读输出
- 请求级 trace_id 贯穿，便于链路追踪
- 日志级别可配（LOG_LEVEL），日志目录/保留天数可配
- 敏感字段（密码/token/key）自动脱敏
- 后台可查询最近日志（GET /api/admin/logs）

日志目录：
- macOS: ~/Library/Logs/travel-app
- Linux: ~/.cache/travel-app 或 /var/log/travel-app
- Windows: %LOCALAPPDATA%/travel-app
- 可通过环境变量 LOG_DIR 覆盖

使用方式：
    from app.infrastructure.logger import get_logger, setup_logging, new_trace_id

    # 在应用启动时调用一次
    setup_logging()

    # 获取 logger
    logger = get_logger(__name__)

    # 记录日志（带业务字段）
    logger.info("plan_generated", extra={"fields": {"destination": "北京", "days": 3}})

    # 生成 trace_id
    trace_id = new_trace_id()
"""
import json
import logging
import os
import platform
import sys
import time
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from typing import Any, Dict, List, Optional

# 敏感字段脱敏（密码、token、key、secret 等不出现在日志中）
_SENSITIVE_KEYS = {
    "password",
    "pwd",
    "token",
    "access_token",
    "refresh_token",
    "amap_key",
    "tencent_key",
    "tencent_sk",
    "secret",
    "sk",
    "authorization",
    "cookie",
    "session",
}

# 敏感字段脱敏掩码
_SENSITIVE_MASK = "***"

# 第三方库噪音日志级别（降低这些库的日志级别，减少噪音）
_NOISY_LOGGERS = (
    "httpx",
    "httpcore",
    "urllib3",
    "uvicorn.access",
    "multipart",
)


def _mask_sensitive(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    递归脱敏 dict 中的敏感字段。

    遍历 dict 中的所有键值对，如果键在敏感字段列表中，则将值替换为掩码。
    对于嵌套的 dict，递归处理。

    Args:
        data: 要脱敏的 dict

    Returns:
        Dict[str, Any]: 脱敏后的 dict
    """
    if not isinstance(data, dict):
        return data
    out: Dict[str, Any] = {}
    for k, v in data.items():
        if k.lower() in _SENSITIVE_KEYS:
            out[k] = _SENSITIVE_MASK
        elif isinstance(v, dict):
            out[k] = _mask_sensitive(v)
        else:
            out[k] = v
    return out


class JsonFormatter(logging.Formatter):
    """
    JSON 日志格式化器：输出单行 JSON，含时间/级别/logger/消息/额外字段/异常。

    输出格式：
        {
            "ts": "2026-08-30 12:00:00.000",
            "level": "INFO",
            "logger": "app.core.planner",
            "msg": "plan_generated",
            "destination": "北京",
            "days": 3
        }

    特性：
    - 时间精确到毫秒
    - 自动脱敏敏感字段
    - 支持额外业务字段（通过 extra={"fields": {...}} 传入）
    - 支持异常堆栈信息
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        格式化日志记录为 JSON 字符串。

        Args:
            record: 日志记录对象

        Returns:
            str: JSON 格式的日志字符串
        """
        entry: Dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
            + f".{record.msecs:03.0f}",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # 额外业务字段（通过 extra={"fields": {...}} 传入）
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            entry.update(_mask_sensitive(fields))
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False, default=str)


def _default_log_dir() -> str:
    """
    获取默认日志目录（系统目录，不存放在项目中）。

    各平台默认目录：
    - macOS: ~/Library/Logs/travel-app
    - Linux: ~/.cache/travel-app 或 /var/log/travel-app
    - Windows: %LOCALAPPDATA%/travel-app

    可通过环境变量 LOG_DIR 覆盖。

    Returns:
        str: 默认日志目录路径
    """
    system = platform.system()
    if system == "Darwin":  # macOS
        base = os.path.expanduser("~/Library/Logs")
    elif system == "Windows":
        base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    else:  # Linux / Unix
        base = os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
    return os.path.join(base, "travel-app")


def setup_logging(
    level: Optional[str] = None,
    log_dir: Optional[str] = None,
    retention_days: Optional[int] = None,
) -> str:
    """
    初始化全局日志配置（应用启动时调用一次）。

    配置内容：
    1. 设置根 logger 级别
    2. 添加控制台 handler（人类可读格式）
    3. 添加文件 handler（JSON 格式，按天轮转，保留 N 天）
    4. 降低第三方库噪音日志级别

    Args:
        level: 日志级别（DEBUG/INFO/WARNING/ERROR），默认从环境变量 LOG_LEVEL 读取，默认 INFO
        log_dir: 日志目录，默认从环境变量 LOG_DIR 读取，默认使用系统目录
        retention_days: 日志保留天数，默认从环境变量 LOG_RETENTION_DAYS 读取，默认 7 天

    Returns:
        str: 日志目录路径

    Example:
        >>> log_dir = setup_logging(level="INFO", retention_days=7)
        >>> print(f"日志目录: {log_dir}")
    """
    level = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    log_dir = log_dir or os.getenv("LOG_DIR", _default_log_dir())
    retention_days = retention_days or int(os.getenv("LOG_RETENTION_DAYS", "7"))

    os.makedirs(log_dir, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(level)
    # 避免重复添加 handler（热重载时）
    root.handlers.clear()

    # 控制台：人类可读格式
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root.addHandler(console)

    # 文件：JSON 格式，按天轮转，保留 retention_days 天
    log_file = os.path.join(log_dir, "app.log")
    file_handler = TimedRotatingFileHandler(
        log_file,
        when="midnight",
        interval=1,
        backupCount=retention_days,
        encoding="utf-8",
    )
    file_handler.setFormatter(JsonFormatter())
    root.addHandler(file_handler)

    # 降低第三方库噪音
    for noisy in _NOISY_LOGGERS:
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logger = get_logger("logger")
    logger.info(
        "logging_initialized",
        extra={
            "fields": {
                "level": level,
                "log_dir": log_dir,
                "retention_days": retention_days,
            }
        },
    )
    return log_dir


def get_logger(name: str) -> logging.Logger:
    """
    获取命名 logger。

    Args:
        name: logger 名称（通常使用 __name__）

    Returns:
        logging.Logger: 命名 logger 对象

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("hello world")
    """
    return logging.getLogger(name)


def new_trace_id() -> str:
    """
    生成请求追踪 ID（时间戳+随机串）。

    格式：{毫秒时间戳}-{6位随机十六进制串}
    例如：1725000000000-a1b2c3

    Returns:
        str: 追踪 ID 字符串

    Example:
        >>> trace_id = new_trace_id()
        >>> print(trace_id)
        '1725000000000-a1b2c3'
    """
    return f"{int(time.time() * 1000)}-{os.urandom(3).hex()}"


def read_recent_logs(
    log_dir: Optional[str] = None,
    level: str = "",
    keyword: str = "",
    limit: int = 200,
) -> List[Dict[str, Any]]:
    """
    读取最近的日志文件，支持按级别/关键词过滤（供后台日志面板使用）。

    读取今天和昨天的日志文件（跨天场景），返回最新的 limit 条。

    Args:
        log_dir: 日志目录，默认从环境变量 LOG_DIR 读取，默认使用系统目录
        level: 日志级别过滤（DEBUG/INFO/WARNING/ERROR），空字符串表示不过滤
        keyword: 关键词过滤（在 msg 和所有字段值中搜索），空字符串表示不过滤
        limit: 返回的最大日志条数，默认 200

    Returns:
        List[Dict[str, Any]]: 日志条目列表，最新的在前

    Example:
        >>> logs = read_recent_logs(level="ERROR", limit=50)
        >>> print(f"找到 {len(logs)} 条错误日志")
    """
    log_dir = log_dir or os.getenv("LOG_DIR", _default_log_dir())
    if not os.path.isdir(log_dir):
        return []

    # 收集今天和昨天的日志文件（含轮转后缀）
    files: List[str] = []
    for f in sorted(os.listdir(log_dir), reverse=True):
        fpath = os.path.join(log_dir, f)
        if not os.path.isfile(fpath):
            continue
        # app.log 或 app.log.YYYY-MM-DD
        if f.startswith("app.log"):
            files.append(fpath)
        if len(files) >= 3:
            break

    entries: List[Dict[str, Any]] = []
    level_upper = level.upper()
    for fpath in files:
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if level_upper and entry.get("level") != level_upper:
                        continue
                    if keyword:
                        # 在 msg 和所有字段值中搜索
                        haystack = json.dumps(entry, ensure_ascii=False).lower()
                        if keyword.lower() not in haystack:
                            continue
                    entries.append(entry)
        except Exception:
            continue

    # 最新在前
    entries.reverse()
    return entries[:limit]
