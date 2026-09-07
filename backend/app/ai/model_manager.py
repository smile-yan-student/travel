# -*- coding: utf-8 -*-
"""
模型管理模块。

统一管理AI模型，支持：
1. 多模型注册和配置
2. 模型性能监控（响应时间、调用次数、成功率）
3. 模型降级策略（主模型不可用时自动切换到备用模型）
4. 模型路由（不同任务使用不同模型，如意图识别用小模型，规划用大模型）
5. 运行时动态切换模型

设计原则：
- 统一管理所有模型，避免散落在各个文件中
- 支持性能监控，便于优化和调优
- 支持降级策略，提高系统稳定性
- 支持模型路由，根据任务类型选择最合适的模型

功能特性：
- ModelConfig：模型配置数据类（名称、大小、描述、性能指标、状态）
- ModelRouter：模型路由配置（不同任务类型使用不同模型）
- ModelManager：模型管理器（统一管理所有AI模型）
- 模型注册和注销
- 模型可用性检查
- 模型性能统计
- 模型降级和恢复
- 运行时动态切换模型

使用方式：
    from app.ai.model_manager import ModelManager, get_model_manager

    # 获取模型管理器单例
    manager = get_model_manager()

    # 检查模型是否可用
    available = manager.is_model_available("qwen2:7b")

    # 获取指定任务的模型
    model = manager.get_model_for_task("plan")

    # 记录模型调用
    manager.record_call("qwen2:7b", success=True, latency_ms=1200.5)
"""
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

from ..infrastructure.logger import get_logger

logger = get_logger("model_manager")


@dataclass
class ModelConfig:
    """模型配置。"""
    name: str  # 模型名称（如 "qwen2:7b"）
    display_name: str  # 显示名称（如 "Qwen2 7B"）
    size_gb: float = 0  # 模型大小（GB）
    description: str = ""  # 模型描述
    max_tokens: int = 2048  # 最大token数
    temperature: float = 0.7  # 默认温度
    # 性能指标
    call_count: int = 0  # 调用次数
    success_count: int = 0  # 成功次数
    failure_count: int = 0  # 失败次数
    total_latency_ms: float = 0  # 总延迟（毫秒）
    avg_latency_ms: float = 0  # 平均延迟（毫秒）
    last_called_at: float = 0  # 最后调用时间
    # 状态
    available: bool = True  # 是否可用
    failure_streak: int = 0  # 连续失败次数
    last_failure_reason: str = ""  # 最后失败原因


@dataclass
class ModelRouter:
    """模型路由配置：不同任务类型使用不同模型。"""
    # 任务类型 -> 模型名称
    task_models: Dict[str, str] = field(default_factory=lambda: {
        "chat": "qwen2:7b",  # 普通对话
        "intent": "qwen2.5:3b",  # 意图识别（用小模型，更快）
        "plan": "qwen2:7b",  # 行程规划（用大模型，更准确）
        "optimize": "qwen2:7b",  # 行程优化
        "rag": "qwen2.5:3b",  # RAG问答（用小模型，更快）
        "default": "qwen2:7b",  # 默认模型
    })

    def get_model_for_task(self, task_type: str) -> str:
        """获取指定任务类型的模型。"""
        return self.task_models.get(task_type, self.task_models["default"])

    def set_model_for_task(self, task_type: str, model_name: str) -> None:
        """设置指定任务类型的模型。"""
        self.task_models[task_type] = model_name


class ModelManager:
    """模型管理器，统一管理所有AI模型。"""

    def __init__(self, ollama_base_url: str = "http://127.0.0.1:11434"):
        """初始化模型管理器。

        参数：
            ollama_base_url: Ollama服务地址
        """
        self._ollama_base_url = ollama_base_url.rstrip("/")
        self._models: Dict[str, ModelConfig] = {}
        self._router = ModelRouter()
        self._lock = threading.Lock()
        self._primary_model: str = "qwen2:7b"
        self._fallback_models: List[str] = ["qwen2.5:3b"]

        # 初始化：从Ollama获取可用模型
        self._refresh_available_models()

        logger.info("model_manager_initialized", extra={
            "fields": {
                "model_count": len(self._models),
                "primary_model": self._primary_model,
                "fallback_models": self._fallback_models,
            }
        })

    def _refresh_available_models(self) -> None:
        """从Ollama刷新可用模型列表。"""
        try:
            with httpx.Client(timeout=10) as client:
                r = client.get(f"{self._ollama_base_url}/api/tags")
                r.raise_for_status()
                models_data = r.json().get("models", [])

                with self._lock:
                    for model_data in models_data:
                        name = model_data.get("name", "")
                        if not name:
                            continue
                        size = model_data.get("size", 0)
                        size_gb = size / (1024**3) if size > 0 else 0

                        if name not in self._models:
                            # 新模型，创建配置
                            display_name = self._get_display_name(name)
                            description = self._get_model_description(name)
                            self._models[name] = ModelConfig(
                                name=name,
                                display_name=display_name,
                                size_gb=size_gb,
                                description=description,
                            )
                        else:
                            # 已有模型，更新大小
                            self._models[name].size_gb = size_gb

                    # 标记不在列表中的模型为不可用
                    available_names = {m.get("name", "") for m in models_data}
                    for name, config in self._models.items():
                        if name not in available_names:
                            config.available = False

        except Exception as e:
            logger.warning("model_manager_refresh_failed", extra={
                "fields": {"error": str(e)}
            })

    def _get_display_name(self, model_name: str) -> str:
        """获取模型的显示名称。"""
        name_map = {
            "qwen2:7b": "Qwen2 7B",
            "qwen2.5:3b": "Qwen2.5 3B",
            "qwen2.5:7b": "Qwen2.5 7B",
            "Lusizo/qwen2.5-7b-instruct-1m:latest": "Qwen2.5 7B Instruct 1M",
        }
        return name_map.get(model_name, model_name)

    def _get_model_description(self, model_name: str) -> str:
        """获取模型描述。"""
        if "3b" in model_name.lower():
            return "轻量级模型，响应速度快，适合意图识别、简单问答等任务"
        elif "7b" in model_name.lower():
            return "中等规模模型，平衡速度和质量，适合对话、规划等任务"
        else:
            return "通用模型"

    def get_model(self, task_type: str = "default") -> Optional[str]:
        """获取指定任务类型的模型，支持降级策略。

        参数：
            task_type: 任务类型（chat、intent、plan、optimize、rag等）

        返回：
            str: 模型名称，如果没有可用模型返回None
        """
        # 先尝试任务指定的模型
        preferred_model = self._router.get_model_for_task(task_type)

        with self._lock:
            # 检查首选模型是否可用
            if preferred_model in self._models and self._models[preferred_model].available:
                return preferred_model

            # 首选模型不可用，尝试主模型
            if self._primary_model in self._models and self._models[self._primary_model].available:
                logger.info("model_manager_fallback", extra={
                    "fields": {
                        "task_type": task_type,
                        "preferred_model": preferred_model,
                        "fallback_model": self._primary_model,
                    }
                })
                return self._primary_model

            # 主模型不可用，尝试备用模型
            for fallback_model in self._fallback_models:
                if fallback_model in self._models and self._models[fallback_model].available:
                    logger.info("model_manager_fallback", extra={
                        "fields": {
                            "task_type": task_type,
                            "preferred_model": preferred_model,
                            "fallback_model": fallback_model,
                        }
                    })
                    return fallback_model

            # 所有备用模型都不可用，返回任意可用模型
            for name, config in self._models.items():
                if config.available:
                    return name

        return None

    def record_call(self, model_name: str, success: bool, latency_ms: float, error_reason: str = "") -> None:
        """记录模型调用结果，用于性能监控。

        参数：
            model_name: 模型名称
            success: 是否成功
            latency_ms: 延迟（毫秒）
            error_reason: 失败原因（可选）
        """
        with self._lock:
            if model_name not in self._models:
                return

            config = self._models[model_name]
            config.call_count += 1
            config.last_called_at = time.time()

            if success:
                config.success_count += 1
                config.failure_streak = 0
                config.total_latency_ms += latency_ms
                config.avg_latency_ms = config.total_latency_ms / config.success_count
            else:
                config.failure_count += 1
                config.failure_streak += 1
                config.last_failure_reason = error_reason

                # 连续失败超过3次，标记模型为不可用
                if config.failure_streak >= 3:
                    config.available = False
                    logger.warning("model_manager_model_disabled", extra={
                        "fields": {
                            "model": model_name,
                            "failure_streak": config.failure_streak,
                            "last_failure_reason": error_reason,
                        }
                    })

    def set_primary_model(self, model_name: str) -> bool:
        """设置主模型。

        参数：
            model_name: 模型名称

        返回：
            bool: 是否设置成功
        """
        with self._lock:
            if model_name not in self._models:
                logger.warning("model_manager_set_primary_failed", extra={
                    "fields": {"model": model_name, "reason": "model not found"}
                })
                return False
            self._primary_model = model_name
            logger.info("model_manager_primary_set", extra={
                "fields": {"model": model_name}
            })
            return True

    def set_fallback_models(self, models: List[str]) -> None:
        """设置备用模型列表。"""
        with self._lock:
            self._fallback_models = models
            logger.info("model_manager_fallback_set", extra={
                "fields": {"models": models}
            })

    def set_model_for_task(self, task_type: str, model_name: str) -> bool:
        """设置指定任务类型的模型。"""
        with self._lock:
            if model_name not in self._models:
                return False
            self._router.set_model_for_task(task_type, model_name)
            return True

    def list_models(self) -> List[Dict[str, Any]]:
        """列出所有模型及其状态。"""
        with self._lock:
            return [
                {
                    "name": config.name,
                    "display_name": config.display_name,
                    "size_gb": round(config.size_gb, 2),
                    "description": config.description,
                    "available": config.available,
                    "call_count": config.call_count,
                    "success_count": config.success_count,
                    "failure_count": config.failure_count,
                    "success_rate": round(config.success_count / config.call_count * 100, 2) if config.call_count > 0 else 0,
                    "avg_latency_ms": round(config.avg_latency_ms, 2),
                    "failure_streak": config.failure_streak,
                }
                for config in self._models.values()
            ]

    def get_model_stats(self, model_name: str) -> Optional[Dict[str, Any]]:
        """获取指定模型的统计信息。"""
        with self._lock:
            if model_name not in self._models:
                return None
            config = self._models[model_name]
            return {
                "name": config.name,
                "display_name": config.display_name,
                "available": config.available,
                "call_count": config.call_count,
                "success_count": config.success_count,
                "failure_count": config.failure_count,
                "success_rate": round(config.success_count / config.call_count * 100, 2) if config.call_count > 0 else 0,
                "avg_latency_ms": round(config.avg_latency_ms, 2),
                "total_latency_ms": round(config.total_latency_ms, 2),
                "last_called_at": config.last_called_at,
                "failure_streak": config.failure_streak,
                "last_failure_reason": config.last_failure_reason,
            }

    def get_router_config(self) -> Dict[str, str]:
        """获取模型路由配置。"""
        with self._lock:
            return dict(self._router.task_models)

    def reset_model_stats(self, model_name: str) -> bool:
        """重置指定模型的统计信息。"""
        with self._lock:
            if model_name not in self._models:
                return False
            config = self._models[model_name]
            config.call_count = 0
            config.success_count = 0
            config.failure_count = 0
            config.total_latency_ms = 0
            config.avg_latency_ms = 0
            config.failure_streak = 0
            config.last_failure_reason = ""
            config.available = True
            return True

    def health_check(self) -> Dict[str, Any]:
        """健康检查：返回模型管理器的整体状态。"""
        with self._lock:
            total_models = len(self._models)
            available_models = sum(1 for c in self._models.values() if c.available)
            total_calls = sum(c.call_count for c in self._models.values())
            total_success = sum(c.success_count for c in self._models.values())
            overall_success_rate = round(total_success / total_calls * 100, 2) if total_calls > 0 else 0

            return {
                "status": "healthy" if available_models > 0 else "unhealthy",
                "total_models": total_models,
                "available_models": available_models,
                "primary_model": self._primary_model,
                "fallback_models": self._fallback_models,
                "total_calls": total_calls,
                "total_success": total_success,
                "overall_success_rate": overall_success_rate,
            }


# 全局模型管理器实例
_model_manager: Optional[ModelManager] = None
_model_manager_lock = threading.Lock()


def get_model_manager() -> ModelManager:
    """获取全局模型管理器实例（单例）。"""
    global _model_manager
    if _model_manager is None:
        with _model_manager_lock:
            if _model_manager is None:
                from ..config import settings
                _model_manager = ModelManager(ollama_base_url=settings.ollama_base_url)
    return _model_manager


def get_model_for_task(task_type: str = "default") -> Optional[str]:
    """便捷函数：获取指定任务类型的模型。"""
    return get_model_manager().get_model(task_type)


def record_model_call(model_name: str, success: bool, latency_ms: float, error_reason: str = "") -> None:
    """便捷函数：记录模型调用结果。"""
    get_model_manager().record_call(model_name, success, latency_ms, error_reason)
