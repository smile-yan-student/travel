#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
字典数据存储模块。

用于管理系统字典数据，如旅行风格、预算档位、出行方式等枚举值。
当前为内存实现，后续可扩展为数据库驱动的字典管理。

功能特性：
- 内置字典数据（旅行风格、预算档位、出行方式）
- 字典数据查询（按编码获取字典、获取字典项）
- 字典编码列表
- 字典数据重新加载

使用方式：
    from app.data.dict_store import DictStore

    # 创建字典存储实例
    store = DictStore()

    # 获取旅行风格字典
    styles = store.get_dict("travel_style")

    # 获取特定字典项
    item = store.get_dict_item("travel_style", "classic")

    # 列出所有字典编码
    codes = store.list_dict_codes()

    # 重新加载字典数据
    store.reload()
"""
from typing import Any, Dict, List, Optional


class DictStore:
    """
    字典数据存储类。

    提供系统字典数据的查询和管理能力。
    当前为内存实现，后续可扩展为数据库驱动。

    Example:
        >>> store = DictStore()
        >>> styles = store.get_dict("travel_style")
        >>> print(styles[0]["name"])
        经典打卡
    """

    def __init__(self) -> None:
        """初始化字典存储，加载内置字典数据。"""
        self._dicts: Dict[str, List[Dict[str, Any]]] = self._load_builtin_dicts()

    def _load_builtin_dicts(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        加载内置字典数据。

        Returns:
            Dict[str, List[Dict[str, Any]]]: 内置字典数据，键为字典编码，值为字典项列表
        """
        return {
            "travel_style": [
                {"code": "classic", "name": "经典打卡", "desc": "必去景点全覆盖"},
                {"code": "foodie", "name": "美食之旅", "desc": "以美食为核心"},
                {"code": "culture", "name": "人文历史", "desc": "深度文化体验"},
                {"code": "nature", "name": "自然风光", "desc": "户外自然景观"},
                {"code": "family", "name": "亲子游", "desc": "适合家庭出行"},
                {"code": "romantic", "name": "浪漫之旅", "desc": "情侣出行首选"},
            ],
            "budget_level": [
                {"code": "economy", "name": "经济实惠", "desc": "预算有限"},
                {"code": "moderate", "name": "适中", "desc": "平衡舒适与预算"},
                {"code": "comfort", "name": "舒适", "desc": "注重体验"},
                {"code": "luxury", "name": "豪华", "desc": "高端享受"},
            ],
            "travel_mode": [
                {"code": "public", "name": "公共交通", "desc": "地铁公交为主"},
                {"code": "self_drive", "name": "自驾", "desc": "私家车出行"},
                {"code": "cycling", "name": "骑行", "desc": "自行车出行"},
                {"code": "walking", "name": "步行", "desc": "徒步出行"},
                {"code": "mixed", "name": "混合", "desc": "多种方式结合"},
            ],
        }

    def get_dict(self, dict_code: str) -> Optional[List[Dict[str, Any]]]:
        """
        根据字典编码获取字典数据。

        Args:
            dict_code: 字典编码（如 "travel_style"、"budget_level"、"travel_mode"）

        Returns:
            Optional[List[Dict[str, Any]]]: 字典数据列表，不存在返回 None

        Example:
            >>> store = DictStore()
            >>> styles = store.get_dict("travel_style")
            >>> print(len(styles))
            6
        """
        return self._dicts.get(dict_code)

    def get_dict_item(
        self, dict_code: str, item_code: str
    ) -> Optional[Dict[str, Any]]:
        """
        根据字典编码和项编码获取字典项。

        Args:
            dict_code: 字典编码
            item_code: 项编码（如 "classic"、"economy"、"public"）

        Returns:
            Optional[Dict[str, Any]]: 字典项，不存在返回 None

        Example:
            >>> store = DictStore()
            >>> item = store.get_dict_item("travel_style", "classic")
            >>> print(item["name"])
            经典打卡
        """
        items = self.get_dict(dict_code)
        if not items:
            return None
        for item in items:
            if item.get("code") == item_code:
                return item
        return None

    def list_dict_codes(self) -> List[str]:
        """
        列出所有字典编码。

        Returns:
            List[str]: 所有字典编码的列表

        Example:
            >>> store = DictStore()
            >>> codes = store.list_dict_codes()
            >>> print(codes)
            ['travel_style', 'budget_level', 'travel_mode']
        """
        return list(self._dicts.keys())

    def reload(self) -> None:
        """
        重新加载字典数据。

        用于字典数据更新后刷新内存中的字典缓存。
        """
        self._dicts = self._load_builtin_dicts()
