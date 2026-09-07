#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
字典数据校验工具。

检查数据库中字典数据的完整性和一致性：
1. must_visit：检查必填字段、评分范围、优先级范围
2. poi_hierarchy：检查必填字段、JSON格式、内部动线完整性
3. site_config：检查配置键是否存在、值格式是否正确
4. dict_brand_copy：检查必填字段、文案内容非空

执行方式：
    cd backend
    ./.venv/bin/python scripts/validate_dict_data.py
"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.data.database import get_conn


def validate_must_visit():
    """校验必去景点数据"""
    print("\n=== 1. 必去景点数据校验 ===")
    errors = []
    warnings = []

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM must_visit")
            rows = cur.fetchall()

            print(f"  总记录数: {len(rows)}")

            for row in rows:
                item = dict(row)
                item_id = item.get("id")
                name = item.get("name", "")
                city = item.get("city", "")

                # 检查必填字段
                if not name:
                    errors.append(f"  [错误] ID={item_id}: 景点名称为空")
                if not city:
                    errors.append(f"  [错误] ID={item_id} ({name}): 城市为空")

                # 检查评分范围
                rating = item.get("rating", 0)
                if rating < 0 or rating > 5:
                    errors.append(f"  [错误] ID={item_id} ({name}): 评分 {rating} 超出范围 (0-5)")

                # 检查优先级范围
                priority = item.get("priority", 50)
                if priority < 0 or priority > 100:
                    warnings.append(f"  [警告] ID={item_id} ({name}): 优先级 {priority} 超出建议范围 (0-100)")

                # 检查经纬度
                lng = item.get("lng")
                lat = item.get("lat")
                if (lng is None) != (lat is None):
                    warnings.append(f"  [警告] ID={item_id} ({name}): 经纬度不完整（lng={lng}, lat={lat}）")

            # 检查重复数据
            cur.execute("SELECT city, name, COUNT(*) as cnt FROM must_visit GROUP BY city, name HAVING cnt > 1")
            duplicates = cur.fetchall()
            if duplicates:
                for dup in duplicates:
                    warnings.append(f"  [警告] 重复数据: {dup.get('city')} - {dup.get('name')} ({dup.get('cnt')}条)")

    finally:
        conn.close()

    print(f"  错误: {len(errors)} 个")
    print(f"  警告: {len(warnings)} 个")
    for e in errors[:10]:
        print(e)
    for w in warnings[:10]:
        print(w)

    return len(errors) == 0


def validate_poi_hierarchy():
    """校验景点层级关系数据"""
    print("\n=== 2. 景点层级关系数据校验 ===")
    errors = []
    warnings = []

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM poi_hierarchy WHERE enabled = 1")
            rows = cur.fetchall()

            print(f"  总记录数: {len(rows)}")

            for row in rows:
                item = dict(row)
                item_id = item.get("id")
                name = item.get("name", "")

                # 检查必填字段
                if not name:
                    errors.append(f"  [错误] ID={item_id}: 景点名称为空")

                # 检查 JSON 字段格式
                for json_field in ["alias", "inner_route", "nearby_attractions", "avoid_tips"]:
                    value = item.get(json_field)
                    if value:
                        try:
                            parsed = json.loads(value)
                            if not isinstance(parsed, list):
                                warnings.append(f"  [警告] ID={item_id} ({name}): {json_field} 不是数组格式")
                        except (json.JSONDecodeError, TypeError):
                            errors.append(f"  [错误] ID={item_id} ({name}): {json_field} JSON 格式错误")

                # 检查内部动线完整性
                inner_route = item.get("inner_route", "[]")
                if inner_route:
                    try:
                        route = json.loads(inner_route)
                        for i, point in enumerate(route):
                            if isinstance(point, dict):
                                if not point.get("name"):
                                    warnings.append(f"  [警告] ID={item_id} ({name}): 内部动线第{i+1}个点名称为空")
                            else:
                                warnings.append(f"  [警告] ID={item_id} ({name}): 内部动线第{i+1}个点格式错误")
                    except (json.JSONDecodeError, TypeError):
                        pass

                # 检查大型景区标记
                if item.get("is_large_scenic") and not item.get("level"):
                    warnings.append(f"  [警告] ID={item_id} ({name}): 标记为大型景区但未填写等级")

            # 检查重复名称
            cur.execute("SELECT name, COUNT(*) as cnt FROM poi_hierarchy WHERE enabled = 1 GROUP BY name HAVING cnt > 1")
            duplicates = cur.fetchall()
            if duplicates:
                for dup in duplicates:
                    errors.append(f"  [错误] 重复景点名称: {dup.get('name')} ({dup.get('cnt')}条)")

    finally:
        conn.close()

    print(f"  错误: {len(errors)} 个")
    print(f"  警告: {len(warnings)} 个")
    for e in errors[:10]:
        print(e)
    for w in warnings[:10]:
        print(w)

    return len(errors) == 0


def validate_site_config():
    """校验配置常量数据"""
    print("\n=== 3. 配置常量数据校验 ===")
    errors = []
    warnings = []

    # 必需的配置键
    required_keys = [
        "cluster_max_dist", "scope_max_range", "closed_markers",
        "aux_food_bad_names", "landmark_words", "scope_keywords"
    ]

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT k, v FROM site_config")
            rows = cur.fetchall()
            configs = {row.get("k"): row.get("v") for row in rows}

            print(f"  总配置数: {len(configs)}")

            # 检查必需配置
            for key in required_keys:
                if key not in configs:
                    errors.append(f"  [错误] 缺少必需配置: {key}")
                else:
                    value = configs[key]
                    # 检查 JSON 格式配置
                    if key in ["closed_markers", "aux_food_bad_names", "landmark_words", "scope_keywords"]:
                        try:
                            parsed = json.loads(value)
                            if not isinstance(parsed, (list, dict)):
                                warnings.append(f"  [警告] {key}: 值不是数组/对象格式")
                        except (json.JSONDecodeError, TypeError):
                            errors.append(f"  [错误] {key}: JSON 格式错误")

                    # 检查数值配置
                    if key in ["cluster_max_dist", "scope_max_range"]:
                        try:
                            num = int(value)
                            if num <= 0:
                                errors.append(f"  [错误] {key}: 值 {num} 必须大于0")
                        except (ValueError, TypeError):
                            errors.append(f"  [错误] {key}: 值 {value} 不是有效数字")

    finally:
        conn.close()

    print(f"  错误: {len(errors)} 个")
    print(f"  警告: {len(warnings)} 个")
    for e in errors[:10]:
        print(e)
    for w in warnings[:10]:
        print(w)

    return len(errors) == 0


def validate_brand_copy():
    """校验品牌文案数据"""
    print("\n=== 4. 品牌文案数据校验 ===")
    errors = []
    warnings = []

    valid_kinds = ["departure_message", "daily_inspiration"]

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM dict_brand_copy WHERE enabled = 1")
            rows = cur.fetchall()

            print(f"  总记录数: {len(rows)}")

            for row in rows:
                item = dict(row)
                item_id = item.get("id")
                kind = item.get("kind", "")
                content = item.get("content", "")

                # 检查类型
                if kind not in valid_kinds:
                    errors.append(f"  [错误] ID={item_id}: 类型 {kind} 无效（应为 {valid_kinds}）")

                # 检查内容
                if not content or not content.strip():
                    errors.append(f"  [错误] ID={item_id}: 文案内容为空")

                # 检查优先级
                priority = item.get("priority", 50)
                if priority < 0 or priority > 100:
                    warnings.append(f"  [警告] ID={item_id}: 优先级 {priority} 超出建议范围 (0-100)")

            # 按类型统计
            for kind in valid_kinds:
                cur.execute("SELECT COUNT(*) as cnt FROM dict_brand_copy WHERE kind = %s AND enabled = 1", (kind,))
                count = cur.fetchone().get("cnt", 0)
                print(f"  {kind}: {count} 条")

    finally:
        conn.close()

    print(f"  错误: {len(errors)} 个")
    print(f"  警告: {len(warnings)} 个")
    for e in errors[:10]:
        print(e)
    for w in warnings[:10]:
        print(w)

    return len(errors) == 0


def main():
    print("=" * 60)
    print("字典数据校验工具")
    print("=" * 60)

    results = []
    results.append(validate_must_visit())
    results.append(validate_poi_hierarchy())
    results.append(validate_site_config())
    results.append(validate_brand_copy())

    print("\n" + "=" * 60)
    if all(results):
        print("校验完成：所有数据校验通过！")
    else:
        print("校验完成：存在错误，请检查上述错误信息")
    print("=" * 60)

    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
