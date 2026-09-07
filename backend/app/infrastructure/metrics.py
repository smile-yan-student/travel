"""
轻量级指标收集模块（无外部依赖）。

收集请求指标（QPS、延迟、错误率）和业务指标，提供 /metrics 接口。
支持 Prometheus 文本格式和 JSON 格式输出。

指标类型：
- Counter：计数器（请求总数、错误总数）
- Gauge：瞬时值（活跃连接数、缓存大小）
- Histogram：直方图（请求延迟分布）

使用方式：
    from app.infrastructure.metrics import metrics, MetricsMiddleware

    # 添加中间件
    app.add_middleware(MetricsMiddleware)

    # 手动记录业务指标
    metrics.increment("plan_generated", labels={"destination": "北京"})
    metrics.observe("plan_duration_seconds", 2.5, labels={"destination": "北京"})

    # 导出指标
    prometheus_text = metrics.to_prometheus()
    json_data = metrics.to_json()
"""
import time
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Tuple

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from . import logger as log_mod

# 指标日志记录器
_metrics_logger = log_mod.get_logger("metrics")

# 标签类型
Labels = Dict[str, str]
# 标签键类型（排序后的元组）
LabelKey = Tuple[Tuple[str, str], ...]


class Counter:
    """
    计数器：单调递增。

    用于统计请求总数、错误总数等只增不减的指标。

    Example:
        >>> counter = Counter("http_requests_total", "Total HTTP requests")
        >>> counter.inc(labels={"method": "GET", "path": "/"})
        >>> print(counter.get(labels={"method": "GET", "path": "/"}))
        1.0
    """

    def __init__(self, name: str, help_text: str = "") -> None:
        """
        初始化计数器。

        Args:
            name: 指标名称
            help_text: 指标帮助文本（用于 Prometheus 导出）
        """
        self.name = name
        self.help = help_text
        self._values: Dict[LabelKey, float] = defaultdict(float)

    def inc(self, amount: float = 1.0, labels: Optional[Labels] = None) -> None:
        """
        增加计数器值。

        Args:
            amount: 增加的数量，默认 1.0
            labels: 标签字典，默认 None
        """
        key = tuple(sorted((labels or {}).items()))
        self._values[key] += amount

    def get(self, labels: Optional[Labels] = None) -> float:
        """
        获取计数器值。

        Args:
            labels: 标签字典，默认 None

        Returns:
            float: 计数器值
        """
        key = tuple(sorted((labels or {}).items()))
        return self._values.get(key, 0.0)

    def items(self) -> List[Tuple[LabelKey, float]]:
        """
        获取所有计数器值。

        Returns:
            List[Tuple[LabelKey, float]]: 所有计数器值列表
        """
        return list(self._values.items())


class Gauge:
    """
    瞬时值：可增可减。

    用于统计活跃连接数、缓存大小等可以上下波动的指标。

    Example:
        >>> gauge = Gauge("http_active_requests", "Active HTTP requests")
        >>> gauge.inc()
        >>> print(gauge.get())
        1.0
        >>> gauge.dec()
        >>> print(gauge.get())
        0.0
    """

    def __init__(self, name: str, help_text: str = "") -> None:
        """
        初始化瞬时值指标。

        Args:
            name: 指标名称
            help_text: 指标帮助文本（用于 Prometheus 导出）
        """
        self.name = name
        self.help = help_text
        self._values: Dict[LabelKey, float] = defaultdict(float)

    def set(self, value: float, labels: Optional[Labels] = None) -> None:
        """
        设置瞬时值。

        Args:
            value: 要设置的值
            labels: 标签字典，默认 None
        """
        key = tuple(sorted((labels or {}).items()))
        self._values[key] = value

    def inc(self, amount: float = 1.0, labels: Optional[Labels] = None) -> None:
        """
        增加瞬时值。

        Args:
            amount: 增加的数量，默认 1.0
            labels: 标签字典，默认 None
        """
        key = tuple(sorted((labels or {}).items()))
        self._values[key] += amount

    def dec(self, amount: float = 1.0, labels: Optional[Labels] = None) -> None:
        """
        减少瞬时值。

        Args:
            amount: 减少的数量，默认 1.0
            labels: 标签字典，默认 None
        """
        key = tuple(sorted((labels or {}).items()))
        self._values[key] -= amount

    def get(self, labels: Optional[Labels] = None) -> float:
        """
        获取瞬时值。

        Args:
            labels: 标签字典，默认 None

        Returns:
            float: 瞬时值
        """
        key = tuple(sorted((labels or {}).items()))
        return self._values.get(key, 0.0)

    def items(self) -> List[Tuple[LabelKey, float]]:
        """
        获取所有瞬时值。

        Returns:
            List[Tuple[LabelKey, float]]: 所有瞬时值列表
        """
        return list(self._values.items())


class Histogram:
    """
    直方图：统计值的分布。

    用于统计请求延迟分布等需要了解数据分布情况的指标。

    默认桶（秒）：0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0

    Example:
        >>> histogram = Histogram("http_request_duration_seconds", "HTTP request duration")
        >>> histogram.observe(0.25, labels={"method": "GET"})
        >>> print(histogram.get_count(labels={"method": "GET"}))
        1.0
        >>> print(histogram.get_sum(labels={"method": "GET"}))
        0.25
    """

    # 默认桶（秒）
    DEFAULT_BUCKETS: Tuple[float, ...] = (
        0.005,
        0.01,
        0.025,
        0.05,
        0.1,
        0.25,
        0.5,
        1.0,
        2.5,
        5.0,
        10.0,
    )

    def __init__(
        self,
        name: str,
        help_text: str = "",
        buckets: Optional[Tuple[float, ...]] = None,
    ) -> None:
        """
        初始化直方图。

        Args:
            name: 指标名称
            help_text: 指标帮助文本（用于 Prometheus 导出）
            buckets: 桶边界元组，默认使用 DEFAULT_BUCKETS
        """
        self.name = name
        self.help = help_text
        self.buckets = buckets or self.DEFAULT_BUCKETS
        self._sum: Dict[LabelKey, float] = defaultdict(float)
        self._count: Dict[LabelKey, float] = defaultdict(float)
        self._bucket_counts: Dict[LabelKey, Dict[float, float]] = defaultdict(
            lambda: defaultdict(float)
        )

    def observe(self, value: float, labels: Optional[Labels] = None) -> None:
        """
        记录观测值。

        Args:
            value: 观测值
            labels: 标签字典，默认 None
        """
        key = tuple(sorted((labels or {}).items()))
        self._sum[key] += value
        self._count[key] += 1
        for bucket in self.buckets:
            if value <= bucket:
                self._bucket_counts[key][bucket] += 1

    def get_sum(self, labels: Optional[Labels] = None) -> float:
        """
        获取观测值总和。

        Args:
            labels: 标签字典，默认 None

        Returns:
            float: 观测值总和
        """
        key = tuple(sorted((labels or {}).items()))
        return self._sum.get(key, 0.0)

    def get_count(self, labels: Optional[Labels] = None) -> float:
        """
        获取观测次数。

        Args:
            labels: 标签字典，默认 None

        Returns:
            float: 观测次数
        """
        key = tuple(sorted((labels or {}).items()))
        return self._count.get(key, 0.0)

    def items(self) -> List[Tuple[LabelKey, float, float, Dict[float, float]]]:
        """
        获取所有直方图数据。

        Returns:
            List[Tuple[LabelKey, float, float, Dict[float, float]]]:
                所有直方图数据列表，每个元素为 (标签键, 总和, 次数, 桶计数)
        """
        keys = set(self._sum.keys()) | set(self._count.keys()) | set(self._bucket_counts.keys())
        return [
            (
                k,
                self._sum.get(k, 0),
                self._count.get(k, 0),
                dict(self._bucket_counts.get(k, {})),
            )
            for k in keys
        ]


class MetricsRegistry:
    """
    指标注册表：管理所有指标。

    提供 Counter、Gauge、Histogram 三种指标类型的创建和管理，
    支持导出为 Prometheus 文本格式和 JSON 格式。

    Example:
        >>> registry = MetricsRegistry()
        >>> counter = registry.counter("test_counter", "Test counter")
        >>> counter.inc()
        >>> print(registry.to_json()["counters"]["test_counter"]["values"])
        [{'labels': {}, 'value': 1.0}]
    """

    def __init__(self) -> None:
        """初始化指标注册表。"""
        self._counters: Dict[str, Counter] = {}
        self._gauges: Dict[str, Gauge] = {}
        self._histograms: Dict[str, Histogram] = {}
        self._start_time = time.time()

    def counter(self, name: str, help_text: str = "") -> Counter:
        """
        获取或创建计数器。

        Args:
            name: 指标名称
            help_text: 指标帮助文本，默认 ""

        Returns:
            Counter: 计数器实例
        """
        if name not in self._counters:
            self._counters[name] = Counter(name, help_text)
        return self._counters[name]

    def gauge(self, name: str, help_text: str = "") -> Gauge:
        """
        获取或创建瞬时值指标。

        Args:
            name: 指标名称
            help_text: 指标帮助文本，默认 ""

        Returns:
            Gauge: 瞬时值指标实例
        """
        if name not in self._gauges:
            self._gauges[name] = Gauge(name, help_text)
        return self._gauges[name]

    def histogram(
        self,
        name: str,
        help_text: str = "",
        buckets: Optional[Tuple[float, ...]] = None,
    ) -> Histogram:
        """
        获取或创建直方图。

        Args:
            name: 指标名称
            help_text: 指标帮助文本，默认 ""
            buckets: 桶边界元组，默认 None（使用默认桶）

        Returns:
            Histogram: 直方图实例
        """
        if name not in self._histograms:
            self._histograms[name] = Histogram(name, help_text, buckets)
        return self._histograms[name]

    def increment(
        self,
        name: str,
        amount: float = 1.0,
        labels: Optional[Labels] = None,
        help_text: str = "",
    ) -> None:
        """
        快捷方法：增加计数器。

        Args:
            name: 指标名称
            amount: 增加的数量，默认 1.0
            labels: 标签字典，默认 None
            help_text: 指标帮助文本，默认 ""
        """
        self.counter(name, help_text).inc(amount, labels)

    def observe(
        self,
        name: str,
        value: float,
        labels: Optional[Labels] = None,
        help_text: str = "",
        buckets: Optional[Tuple[float, ...]] = None,
    ) -> None:
        """
        快捷方法：记录直方图观测值。

        Args:
            name: 指标名称
            value: 观测值
            labels: 标签字典，默认 None
            help_text: 指标帮助文本，默认 ""
            buckets: 桶边界元组，默认 None
        """
        self.histogram(name, help_text, buckets).observe(value, labels)

    def to_prometheus(self) -> str:
        """
        导出为 Prometheus 文本格式。

        Returns:
            str: Prometheus 格式的指标文本
        """
        lines: List[str] = []

        # 导出计数器
        for name, counter in self._counters.items():
            if counter.help:
                lines.append(f"# HELP {name} {counter.help}")
            lines.append(f"# TYPE {name} counter")
            for labels, value in counter.items():
                label_str = ",".join(f'{k}="{v}"' for k, v in labels) if labels else ""
                lines.append(f"{name}{{{label_str}}} {value}")

        # 导出瞬时值
        for name, gauge in self._gauges.items():
            if gauge.help:
                lines.append(f"# HELP {name} {gauge.help}")
            lines.append(f"# TYPE {name} gauge")
            for labels, value in gauge.items():
                label_str = ",".join(f'{k}="{v}"' for k, v in labels) if labels else ""
                lines.append(f"{name}{{{label_str}}} {value}")

        # 导出直方图
        for name, histogram in self._histograms.items():
            if histogram.help:
                lines.append(f"# HELP {name} {histogram.help}")
            lines.append(f"# TYPE {name} histogram")
            for labels, sum_val, count_val, bucket_counts in histogram.items():
                label_str = ",".join(f'{k}="{v}"' for k, v in labels) if labels else ""
                for bucket in histogram.buckets:
                    le_label = f'le="{bucket}"'
                    full_label = f"{le_label},{label_str}" if label_str else le_label
                    lines.append(f"{name}_bucket{{{full_label}}} {bucket_counts.get(bucket, 0)}")
                lines.append(f"{name}_sum{{{label_str}}} {sum_val}")
                lines.append(f"{name}_count{{{label_str}}} {count_val}")

        # 进程运行时间
        lines.append("# HELP process_uptime_seconds Process uptime in seconds")
        lines.append("# TYPE process_uptime_seconds gauge")
        lines.append(f"process_uptime_seconds {time.time() - self._start_time}")

        return "\n".join(lines) + "\n"

    def to_json(self) -> Dict[str, Any]:
        """
        导出为 JSON 格式。

        Returns:
            Dict[str, Any]: JSON 格式的指标数据
        """
        return {
            "counters": {
                name: {
                    "help": counter.help,
                    "values": [
                        {"labels": dict(labels), "value": value}
                        for labels, value in counter.items()
                    ],
                }
                for name, counter in self._counters.items()
            },
            "gauges": {
                name: {
                    "help": gauge.help,
                    "values": [
                        {"labels": dict(labels), "value": value}
                        for labels, value in gauge.items()
                    ],
                }
                for name, gauge in self._gauges.items()
            },
            "histograms": {
                name: {
                    "help": histogram.help,
                    "buckets": histogram.buckets,
                    "values": [
                        {
                            "labels": dict(labels),
                            "sum": sum_val,
                            "count": count_val,
                            "bucket_counts": bucket_counts,
                        }
                        for labels, sum_val, count_val, bucket_counts in histogram.items()
                    ],
                }
                for name, histogram in self._histograms.items()
            },
            "uptime_seconds": time.time() - self._start_time,
        }


# 全局指标注册表
metrics = MetricsRegistry()

# 预定义常用指标
REQUESTS_TOTAL: Counter = metrics.counter("http_requests_total", "Total HTTP requests")
REQUESTS_ERRORS: Counter = metrics.counter(
    "http_requests_errors_total", "Total HTTP request errors"
)
REQUEST_DURATION: Histogram = metrics.histogram(
    "http_request_duration_seconds", "HTTP request duration in seconds"
)
ACTIVE_REQUESTS: Gauge = metrics.gauge("http_active_requests", "Active HTTP requests")


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    请求指标收集中间件。

    收集：
    - 请求总数（按方法、路径、状态码）
    - 请求错误数（5xx）
    - 请求延迟（直方图）
    - 活跃请求数

    跳过路径：/metrics, /health, /health/detailed（避免噪音）

    Example:
        >>> from fastapi import FastAPI
        >>> app = FastAPI()
        >>> app.add_middleware(MetricsMiddleware)
    """

    async def dispatch(self, request: Request, call_next: Callable[..., Any]) -> Response:
        """
        中间件调度方法：收集请求指标。

        Args:
            request: 请求对象
            call_next: 下一个中间件或路由处理函数

        Returns:
            Response: 响应对象

        Raises:
            Exception: 处理过程中的异常（会被记录后重新抛出）
        """
        method = request.method
        path = request.url.path

        # 跳过指标接口自身和健康检查，避免噪音
        if path in ("/metrics", "/health", "/health/detailed"):
            return await call_next(request)

        ACTIVE_REQUESTS.inc()
        start = time.time()

        try:
            response = await call_next(request)
            duration = time.time() - start
            status = response.status_code

            labels = {"method": method, "path": path, "status": str(status)}
            REQUESTS_TOTAL.inc(labels=labels)
            REQUEST_DURATION.observe(duration, labels={"method": method, "path": path})

            if status >= 500:
                REQUESTS_ERRORS.inc(labels=labels)

            return response
        except Exception as e:
            duration = time.time() - start
            labels = {"method": method, "path": path, "status": "500"}
            REQUESTS_TOTAL.inc(labels=labels)
            REQUESTS_ERRORS.inc(labels=labels)
            REQUEST_DURATION.observe(duration, labels={"method": method, "path": path})
            raise
        finally:
            ACTIVE_REQUESTS.dec()
