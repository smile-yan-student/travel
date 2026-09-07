#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强版导入路径修复脚本 - 处理相对导入。
"""
import os
import re

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def fix_file(file_path):
    """修复单个文件的导入路径"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content
    rel_path = os.path.relpath(file_path, APP_DIR)

    # 根据文件位置确定相对层级
    depth = rel_path.count(os.sep)
    # 顶层文件: from .xxx -> from .新位置.xxx
    # 一级目录: from ..xxx -> from ..新位置.xxx
    # 二级目录: from ...xxx -> from ...新位置.xxx

    # 通用替换规则（适用于所有层级）
    rules = [
        # from .ai.llm import * -> from .ai.llm import * as ai_mod 的处理比较复杂，先处理简单的
        (r'from \.cache import', 'from .infrastructure.cache import'),
        (r'from \.logger import', 'from .infrastructure.logger import'),
        (r'from \.metrics import', 'from .infrastructure.metrics import'),
        (r'from \.exceptions import', 'from .infrastructure.exceptions import'),
        (r'from \.circuit_breaker import', 'from .infrastructure.circuit_breaker import'),
        (r'from \.redis_client import', 'from .infrastructure.redis_client import'),
        (r'from \.login_security import', 'from .security.login_security import'),
        (r'from \.db_security import', 'from .security.db_security import'),
        (r'from \.rate_limiter import', 'from .security.rate_limiter import'),
        (r'from \.security_middleware import', 'from .security.security_middleware import'),
        (r'from \.database import', 'from .data.database import'),
        (r'from \.models import', 'from .data.models import'),
        (r'from \.userstore import', 'from .data.userstore import'),
        (r'from \.admin_store import', 'from .data.admin_store import'),
        (r'from \.dict_store import', 'from .data.dict_store import'),
        (r'from \.amap import', 'from .map.client import'),
        (r'from \.geo_local import', 'from .map.geo_local import'),
        (r'from \.ai import', 'from .ai.llm import'),
        (r'from \.intent import', 'from .ai.intent import'),
        (r'from \.planner import', 'from .core.planner_engine import'),
        (r'from \.responses import', 'from .utils.responses import'),
        (r'from \.health import', 'from .api.health import'),
        (r'from \.admin_router import', 'from .api.admin.admin_router import'),
        (r'from \.routers\.', 'from .api.'),
        (r'from \.services\.map\.', 'from .map.'),
        (r'from \.services\.planner\.', 'from .core.planner.'),
        (r'from \.services\.orchestrator\.', 'from .core.orchestrator.'),
        (r'from \.services\.session\.', 'from .core.session.'),
        (r'from \.services\.rag\.', 'from .ai.rag.'),

        # 双点相对导入 (..)
        (r'from \.\.cache import', 'from ..infrastructure.cache import'),
        (r'from \.\.logger import', 'from ..infrastructure.logger import'),
        (r'from \.\.metrics import', 'from ..infrastructure.metrics import'),
        (r'from \.\.exceptions import', 'from ..infrastructure.exceptions import'),
        (r'from \.\.circuit_breaker import', 'from ..infrastructure.circuit_breaker import'),
        (r'from \.\.redis_client import', 'from ..infrastructure.redis_client import'),
        (r'from \.\.login_security import', 'from ..security.login_security import'),
        (r'from \.\.db_security import', 'from ..security.db_security import'),
        (r'from \.\.rate_limiter import', 'from ..security.rate_limiter import'),
        (r'from \.\.security_middleware import', 'from ..security.security_middleware import'),
        (r'from \.\.database import', 'from ..data.database import'),
        (r'from \.\.models import', 'from ..data.models import'),
        (r'from \.\.userstore import', 'from ..data.userstore import'),
        (r'from \.\.admin_store import', 'from ..data.admin_store import'),
        (r'from \.\.dict_store import', 'from ..data.dict_store import'),
        (r'from \.\.amap import', 'from ..map.client import'),
        (r'from \.\.geo_local import', 'from ..map.geo_local import'),
        (r'from \.\.ai import', 'from ..ai.llm import'),
        (r'from \.\.intent import', 'from ..ai.intent import'),
        (r'from \.\.planner import', 'from ..core.planner_engine import'),
        (r'from \.\.responses import', 'from ..utils.responses import'),
        (r'from \.\.health import', 'from ..api.health import'),
        (r'from \.\.admin_router import', 'from ..api.admin.admin_router import'),
        (r'from \.\.routers\.', 'from ..api.'),
        (r'from \.\.services\.map\.', 'from ..map.'),
        (r'from \.\.services\.planner\.', 'from ..core.planner.'),
        (r'from \.\.services\.orchestrator\.', 'from ..core.orchestrator.'),
        (r'from \.\.services\.session\.', 'from ..core.session.'),
        (r'from \.\.services\.rag\.', 'from ..ai.rag.'),

        # 三点相对导入 (...)
        (r'from \.\.\.cache import', 'from ...infrastructure.cache import'),
        (r'from \.\.\.logger import', 'from ...infrastructure.logger import'),
        (r'from \.\.\.database import', 'from ...data.database import'),
        (r'from \.\.\.models import', 'from ...data.models import'),
        (r'from \.\.\.dict_store import', 'from ...data.dict_store import'),
        (r'from \.\.\.admin_store import', 'from ...data.admin_store import'),
        (r'from \.\.\.amap import', 'from ...map.client import'),
        (r'from \.\.\.geo_local import', 'from ...map.geo_local import'),
        (r'from \.\.\.ai import', 'from ...ai.llm import'),
        (r'from \.\.\.intent import', 'from ...ai.intent import'),
        (r'from \.\.\.planner import', 'from ...core.planner_engine import'),
        (r'from \.\.\.responses import', 'from ...utils.responses import'),
        (r'from \.\.\.exceptions import', 'from ...infrastructure.exceptions import'),
        (r'from \.\.\.metrics import', 'from ...infrastructure.metrics import'),
        (r'from \.\.\.rate_limiter import', 'from ...security.rate_limiter import'),
        (r'from \.\.\.routers\.', 'from ...api.'),
    ]

    count = 0
    for pattern, replacement in rules:
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            count += len(re.findall(pattern, content))
            content = new_content

    # 特殊处理: from .ai.llm import * as ai_mod -> 需要改为导入具体模块
    # 这种形式比较复杂，先记录下来，后面手动处理
    special_imports = re.findall(r'from \. import (\w+) as (\w+)', content)
    if special_imports:
        for orig, alias in special_imports:
            # 映射到新位置
            new_module = {
                'ai': 'ai.llm',
                'amap': 'map.client',
                'intent': 'ai.intent',
                'admin_store': 'data.admin_store',
                'logger': 'infrastructure.logger',
                'cache': 'infrastructure.cache',
                'database': 'data.database',
                'dict_store': 'data.dict_store',
                'userstore': 'data.userstore',
                'geo_local': 'map.geo_local',
                'planner': 'core.planner_engine',
                'responses': 'utils.responses',
                'exceptions': 'infrastructure.exceptions',
                'metrics': 'infrastructure.metrics',
                'rate_limiter': 'security.rate_limiter',
                'circuit_breaker': 'infrastructure.circuit_breaker',
            }.get(orig)
            if new_module:
                old = f'from . import {orig} as {alias}'
                new = f'from .{new_module} import * as {alias}'
                content = content.replace(old, new)
                count += 1

    # 双点: from .. import xxx as yyy
    special_imports2 = re.findall(r'from \.\. import (\w+) as (\w+)', content)
    if special_imports2:
        for orig, alias in special_imports2:
            new_module = {
                'ai': 'ai.llm',
                'amap': 'map.client',
                'intent': 'ai.intent',
                'admin_store': 'data.admin_store',
                'logger': 'infrastructure.logger',
                'cache': 'infrastructure.cache',
                'database': 'data.database',
                'dict_store': 'data.dict_store',
                'userstore': 'data.userstore',
                'geo_local': 'map.geo_local',
                'planner': 'core.planner_engine',
                'responses': 'utils.responses',
                'exceptions': 'infrastructure.exceptions',
                'metrics': 'infrastructure.metrics',
                'rate_limiter': 'security.rate_limiter',
            }.get(orig)
            if new_module:
                old = f'from .. import {orig} as {alias}'
                new = f'from ..{new_module} import * as {alias}'
                content = content.replace(old, new)
                count += 1

    # from . import xxx (没有别名)
    simple_imports = re.findall(r'from \. import (\w+)(?!\s+as)', content)
    if simple_imports:
        for orig in simple_imports:
            new_module = {
                'ai': 'ai.llm',
                'amap': 'map.client',
                'intent': 'ai.intent',
                'admin_store': 'data.admin_store',
                'logger': 'infrastructure.logger',
                'cache': 'infrastructure.cache',
                'database': 'data.database',
                'dict_store': 'data.dict_store',
                'userstore': 'data.userstore',
                'geo_local': 'map.geo_local',
                'planner': 'core.planner_engine',
                'responses': 'utils.responses',
                'exceptions': 'infrastructure.exceptions',
                'metrics': 'infrastructure.metrics',
                'rate_limiter': 'security.rate_limiter',
            }.get(orig)
            if new_module:
                old = f'from . import {orig}'
                new = f'from .{new_module} import *'
                content = content.replace(old, new)
                count += 1

    # from .. import xxx (没有别名)
    simple_imports2 = re.findall(r'from \.\. import (\w+)(?!\s+as)', content)
    if simple_imports2:
        for orig in simple_imports2:
            new_module = {
                'ai': 'ai.llm',
                'amap': 'map.client',
                'intent': 'ai.intent',
                'admin_store': 'data.admin_store',
                'logger': 'infrastructure.logger',
                'cache': 'infrastructure.cache',
                'database': 'data.database',
                'dict_store': 'data.dict_store',
                'userstore': 'data.userstore',
                'geo_local': 'map.geo_local',
                'planner': 'core.planner_engine',
                'responses': 'utils.responses',
                'exceptions': 'infrastructure.exceptions',
                'metrics': 'infrastructure.metrics',
                'rate_limiter': 'security.rate_limiter',
            }.get(orig)
            if new_module:
                old = f'from .. import {orig}'
                new = f'from ..{new_module} import *'
                content = content.replace(old, new)
                count += 1

    if content != original:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True, count
    return False, 0


def main():
    print("=" * 60)
    print("增强版导入路径修复")
    print("=" * 60)

    modified = []
    total = 0

    for root, dirs, files in os.walk(APP_DIR):
        if '__pycache__' in root or '.venv' in root:
            continue
        for f in files:
            if f.endswith('.py'):
                path = os.path.join(root, f)
                ok, count = fix_file(path)
                if ok:
                    rel = os.path.relpath(path, APP_DIR)
                    modified.append(rel)
                    total += count
                    print(f"  ✅ {rel} ({count} 处)")

    print(f"\n完成: {len(modified)} 文件, {total} 处替换")


if __name__ == '__main__':
    main()
