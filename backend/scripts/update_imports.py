#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量更新后端代码中的导入路径。

根据新的目录结构，将所有旧的导入路径替换为新的导入路径。
"""
import os
import re
import sys

# 项目根目录
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 导入路径替换规则（按优先级排序，长的在前）
IMPORT_REPLACEMENTS = [
    # services 子模块（最长的先替换）
    (r'from app\.services\.map\.', 'from app.map.'),
    (r'from app\.services\.planner\.', 'from app.core.planner.'),
    (r'from app\.services\.orchestrator\.', 'from app.core.orchestrator.'),
    (r'from app\.services\.session\.', 'from app.core.session.'),
    (r'from app\.services\.rag\.', 'from app.ai.rag.'),
    (r'from app\.services\.user_profile', 'from app.core.user_profile'),

    # routers
    (r'from app\.routers\.', 'from app.api.'),
    (r'import app\.routers\.', 'import app.api.'),

    # 顶层模块 -> infrastructure
    (r'from app\.cache import', 'from app.infrastructure.cache import'),
    (r'from app\.logger import', 'from app.infrastructure.logger import'),
    (r'from app\.metrics import', 'from app.infrastructure.metrics import'),
    (r'from app\.exceptions import', 'from app.infrastructure.exceptions import'),
    (r'from app\.circuit_breaker import', 'from app.infrastructure.circuit_breaker import'),
    (r'from app\.redis_client import', 'from app.infrastructure.redis_client import'),

    # 顶层模块 -> security
    (r'from app\.login_security import', 'from app.security.login_security import'),
    (r'from app\.db_security import', 'from app.security.db_security import'),
    (r'from app\.rate_limiter import', 'from app.security.rate_limiter import'),
    (r'from app\.security_middleware import', 'from app.security.security_middleware import'),

    # 顶层模块 -> data
    (r'from app\.database import', 'from app.data.database import'),
    (r'from app\.models import', 'from app.data.models import'),
    (r'from app\.userstore import', 'from app.data.userstore import'),
    (r'from app\.admin_store import', 'from app.data.admin_store import'),
    (r'from app\.dict_store import', 'from app.data.dict_store import'),

    # 顶层模块 -> map
    (r'from app\.amap import', 'from app.map.client import'),
    (r'from app\.geo_local import', 'from app.map.geo_local import'),

    # 顶层模块 -> ai
    (r'from app\.ai import', 'from app.ai.llm import'),
    (r'from app\.intent import', 'from app.ai.intent import'),

    # 顶层模块 -> core
    (r'from app\.planner import', 'from app.core.planner_engine import'),

    # 顶层模块 -> utils
    (r'from app\.responses import', 'from app.utils.responses import'),

    # 顶层模块 -> api
    (r'from app\.health import', 'from app.api.health import'),
    (r'from app\.admin_router import', 'from app.api.admin.admin_router import'),

    # import 形式
    (r'import app\.cache', 'import app.infrastructure.cache'),
    (r'import app\.logger', 'import app.infrastructure.logger'),
    (r'import app\.database', 'import app.data.database'),
    (r'import app\.amap', 'import app.map.client'),
    (r'import app\.planner', 'import app.core.planner_engine'),
]

# 相对导入替换规则（根据文件所在目录）
def get_relative_replacements(file_path):
    """根据文件所在目录生成相对导入替换规则"""
    rel_path = os.path.relpath(file_path, APP_DIR)
    parts = rel_path.split(os.sep)
    directory = '/'.join(parts[:-1]) if len(parts) > 1 else ''

    replacements = []

    # 在 api/ 目录下
    if directory.startswith('api'):
        replacements.extend([
            (r'from \.\.cache import', 'from ..infrastructure.cache import'),
            (r'from \.\.logger import', 'from ..infrastructure.logger import'),
            (r'from \.\.database import', 'from ..data.database import'),
            (r'from \.\.dict_store import', 'from ..data.dict_store import'),
            (r'from \.\.admin_store import', 'from ..data.admin_store import'),
            (r'from \.\.userstore import', 'from ..data.userstore import'),
            (r'from \.\.amap import', 'from ..map.client import'),
            (r'from \.\.geo_local import', 'from ..map.geo_local import'),
            (r'from \.\.ai import', 'from ..ai.llm import'),
            (r'from \.\.intent import', 'from ..ai.intent import'),
            (r'from \.\.planner import', 'from ..core.planner_engine import'),
            (r'from \.\.responses import', 'from ..utils.responses import'),
            (r'from \.\.exceptions import', 'from ..infrastructure.exceptions import'),
            (r'from \.\.metrics import', 'from ..infrastructure.metrics import'),
            (r'from \.\.rate_limiter import', 'from ..security.rate_limiter import'),
            (r'from \.\.login_security import', 'from ..security.login_security import'),
            (r'from \.\.db_security import', 'from ..security.db_security import'),
            (r'from \.\.circuit_breaker import', 'from ..infrastructure.circuit_breaker import'),
        ])
        # api/admin/ 目录下
        if directory.startswith('api/admin'):
            replacements.extend([
                (r'from \.\.\.cache import', 'from ...infrastructure.cache import'),
                (r'from \.\.\.logger import', 'from ...infrastructure.logger import'),
                (r'from \.\.\.database import', 'from ...data.database import'),
                (r'from \.\.\.dict_store import', 'from ...data.dict_store import'),
                (r'from \.\.\.admin_store import', 'from ...data.admin_store import'),
                (r'from \.\.\.amap import', 'from ...map.client import'),
                (r'from \.\.\.planner import', 'from ...core.planner_engine import'),
                (r'from \.\.\.responses import', 'from ...utils.responses import'),
            ])

    # 在 core/ 目录下
    elif directory.startswith('core'):
        replacements.extend([
            (r'from \.\.cache import', 'from ..infrastructure.cache import'),
            (r'from \.\.logger import', 'from ..infrastructure.logger import'),
            (r'from \.\.database import', 'from ..data.database import'),
            (r'from \.\.dict_store import', 'from ..data.dict_store import'),
            (r'from \.\.admin_store import', 'from ..data.admin_store import'),
            (r'from \.\.amap import', 'from ..map.client import'),
            (r'from \.\.geo_local import', 'from ..map.geo_local import'),
            (r'from \.\.ai import', 'from ..ai.llm import'),
            (r'from \.\.intent import', 'from ..ai.intent import'),
            (r'from \.\.responses import', 'from ..utils.responses import'),
            (r'from \.\.exceptions import', 'from ..infrastructure.exceptions import'),
            (r'from \.\.metrics import', 'from ..infrastructure.metrics import'),
            (r'from \.\.models import', 'from ..data.models import'),
            (r'from \.\.userstore import', 'from ..data.userstore import'),
            (r'from \.\.circuit_breaker import', 'from ..infrastructure.circuit_breaker import'),
        ])
        # core/planner/ 目录下
        if directory.startswith('core/planner'):
            replacements.extend([
                (r'from \.\.\.cache import', 'from ...infrastructure.cache import'),
                (r'from \.\.\.logger import', 'from ...infrastructure.logger import'),
                (r'from \.\.\.database import', 'from ...data.database import'),
                (r'from \.\.\.dict_store import', 'from ...data.dict_store import'),
                (r'from \.\.\.amap import', 'from ...map.client import'),
                (r'from \.\.\.geo_local import', 'from ...map.geo_local import'),
                (r'from \.\.\.ai import', 'from ...ai.llm import'),
                (r'from \.\.\.responses import', 'from ...utils.responses import'),
                (r'from \.\.\.planner_constants import', 'from .planner_constants import'),
            ])

    # 在 ai/ 目录下
    elif directory.startswith('ai'):
        replacements.extend([
            (r'from \.\.cache import', 'from ..infrastructure.cache import'),
            (r'from \.\.logger import', 'from ..infrastructure.logger import'),
            (r'from \.\.database import', 'from ..data.database import'),
            (r'from \.\.dict_store import', 'from ..data.dict_store import'),
            (r'from \.\.amap import', 'from ..map.client import'),
            (r'from \.\.planner import', 'from ..core.planner_engine import'),
            (r'from \.\.responses import', 'from ..utils.responses import'),
            (r'from \.\.exceptions import', 'from ..infrastructure.exceptions import'),
        ])

    # 在 map/ 目录下
    elif directory.startswith('map'):
        replacements.extend([
            (r'from \.\.cache import', 'from ..infrastructure.cache import'),
            (r'from \.\.logger import', 'from ..infrastructure.logger import'),
            (r'from \.\.database import', 'from ..data.database import'),
            (r'from \.\.dict_store import', 'from ..data.dict_store import'),
            (r'from \.\.geo_local import', 'from .map.geo_local import'),
            (r'from \.\.responses import', 'from ..utils.responses import'),
            (r'from \.\.exceptions import', 'from ..infrastructure.exceptions import'),
            (r'from \.\.circuit_breaker import', 'from ..infrastructure.circuit_breaker import'),
            (r'from \.\.redis_client import', 'from ..infrastructure.redis_client import'),
        ])

    # 在 data/ 目录下
    elif directory.startswith('data'):
        replacements.extend([
            (r'from \.\.cache import', 'from ..infrastructure.cache import'),
            (r'from \.\.logger import', 'from ..infrastructure.logger import'),
            (r'from \.\.config import', 'from ..config import'),
            (r'from \.\.responses import', 'from ..utils.responses import'),
            (r'from \.\.exceptions import', 'from ..infrastructure.exceptions import'),
        ])

    # 在 security/ 目录下
    elif directory.startswith('security'):
        replacements.extend([
            (r'from \.\.cache import', 'from ..infrastructure.cache import'),
            (r'from \.\.logger import', 'from ..infrastructure.logger import'),
            (r'from \.\.database import', 'from ..data.database import'),
            (r'from \.\.responses import', 'from ..utils.responses import'),
            (r'from \.\.exceptions import', 'from ..infrastructure.exceptions import'),
        ])

    # 在 infrastructure/ 目录下
    elif directory.startswith('infrastructure'):
        replacements.extend([
            (r'from \.\.logger import', 'from .infrastructure.logger import'),
            (r'from \.\.cache import', 'from .infrastructure.cache import'),
            (r'from \.\.responses import', 'from ..utils.responses import'),
        ])

    return replacements


def process_file(file_path):
    """处理单个文件，替换导入路径"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content
    replacements = []

    # 应用绝对导入替换
    for pattern, replacement in IMPORT_REPLACEMENTS:
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            replacements.append((pattern, replacement))
            content = new_content

    # 应用相对导入替换
    rel_replacements = get_relative_replacements(file_path)
    for pattern, replacement in rel_replacements:
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            replacements.append((pattern, replacement))
            content = new_content

    # 特殊处理：from .data. 这种在core/planner_engine.py中的导入
    if 'core/planner_engine.py' in file_path:
        content = re.sub(r'from \.data\.', 'from ..data.', content)
        content = re.sub(r'from \.services\.', 'from .', content)

    # 写回文件
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True, replacements
    return False, []


def main():
    print("=" * 60)
    print("批量更新后端导入路径")
    print("=" * 60)

    modified_files = []
    total_replacements = 0

    # 遍历所有Python文件
    for root, dirs, files in os.walk(APP_DIR):
        # 跳过 __pycache__ 和 .venv
        if '__pycache__' in root or '.venv' in root:
            continue
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                modified, replacements = process_file(file_path)
                if modified:
                    rel_path = os.path.relpath(file_path, APP_DIR)
                    modified_files.append(rel_path)
                    total_replacements += len(replacements)
                    print(f"  ✅ {rel_path} ({len(replacements)} 处替换)")

    print("\n" + "=" * 60)
    print(f"处理完成:")
    print(f"  修改文件: {len(modified_files)} 个")
    print(f"  总替换数: {total_replacements} 处")
    print("=" * 60)


if __name__ == "__main__":
    main()
