#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
字典数据导入导出工具。

支持将数据库中的字典数据导出为JSON文件，或从JSON文件导入数据。

使用方式：
    # 导出所有数据
    ./.venv/bin/python scripts/export_dict_data.py --export --output data/dict_export.json

    # 导入数据
    ./.venv/bin/python scripts/export_dict_data.py --import --input data/dict_export.json

    # 导出指定类型
    ./.venv/bin/python scripts/export_dict_data.py --export --types must_visit,poi_hierarchy --output data/partial.json
"""
import sys
import os
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.data.database import get_conn
from app.data.dict_store import invalidate_all_cache


ALL_TYPES = ['must_visit', 'poi_hierarchy', 'site_config', 'dict_brand_copy']


def export_data(types=None, output_file=None):
    """导出数据到JSON文件"""
    if types is None:
        types = ALL_TYPES

    conn = get_conn()
    result = {}
    try:
        with conn.cursor() as cur:
            for table in types:
                if table not in ALL_TYPES:
                    print(f"  跳过未知类型: {table}")
                    continue
                cur.execute(f"SELECT * FROM {table}")
                rows = cur.fetchall()
                result[table] = [dict(row) for row in rows]
                print(f"  导出 {table}: {len(result[table])} 条")
    finally:
        conn.close()

    if output_file:
        os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n数据已导出到: {output_file}")
    else:
        print("\n导出数据预览:")
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str)[:2000])

    return result


def import_data(input_file, types=None, overwrite=False):
    """从JSON文件导入数据"""
    if not os.path.exists(input_file):
        print(f"错误: 文件不存在 - {input_file}")
        return False

    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if types is None:
        types = [t for t in ALL_TYPES if t in data]

    conn = get_conn()
    total_imported = 0
    try:
        with conn.cursor() as cur:
            for table in types:
                if table not in data:
                    print(f"  跳过 {table}: 文件中无此数据")
                    continue

                items = data[table]
                imported = 0
                skipped = 0

                for item in items:
                    try:
                        if table == 'must_visit':
                            if overwrite:
                                cur.execute("DELETE FROM must_visit WHERE city=%s AND name=%s", (item.get('city'), item.get('name')))
                            else:
                                cur.execute("SELECT id FROM must_visit WHERE city=%s AND name=%s", (item.get('city'), item.get('name')))
                                if cur.fetchone():
                                    skipped += 1
                                    continue
                            cur.execute("""
                                INSERT INTO must_visit (city, name, kw, category, rating, priority, adcode, lng, lat)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """, (item.get('city',''), item.get('name',''), item.get('kw', item.get('name','')),
                                  item.get('category','景点'), item.get('rating',4.5), item.get('priority',50),
                                  item.get('adcode',''), item.get('lng'), item.get('lat')))
                            imported += 1

                        elif table == 'poi_hierarchy':
                            name = item.get('name', '')
                            if overwrite:
                                cur.execute("DELETE FROM poi_hierarchy WHERE name=%s", (name,))
                            else:
                                cur.execute("SELECT id FROM poi_hierarchy WHERE name=%s", (name,))
                                if cur.fetchone():
                                    skipped += 1
                                    continue
                            cur.execute("""
                                INSERT INTO poi_hierarchy (name, alias, city, district, province, level, adcode,
                                    lng, lat, description, best_time, is_large_scenic,
                                    inner_route, nearby_attractions, avoid_tips, priority)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """, (name, json.dumps(item.get('alias',[]), ensure_ascii=False),
                                  item.get('city',''), item.get('district',''), item.get('province',''),
                                  item.get('level',''), item.get('adcode',''), item.get('lng'), item.get('lat'),
                                  item.get('description',''), item.get('best_time',''),
                                  1 if item.get('is_large_scenic') else 0,
                                  json.dumps(item.get('inner_route',[]), ensure_ascii=False),
                                  json.dumps(item.get('nearby_attractions',[]), ensure_ascii=False),
                                  json.dumps(item.get('avoid_tips',[]), ensure_ascii=False),
                                  item.get('priority',50)))
                            imported += 1

                        elif table == 'site_config':
                            k = item.get('k', '')
                            cur.execute("SELECT k FROM site_config WHERE k=%s", (k,))
                            if cur.fetchone():
                                if overwrite:
                                    cur.execute("UPDATE site_config SET v=%s, description=%s WHERE k=%s",
                                              (item.get('v',''), item.get('description',''), k))
                                    imported += 1
                                else:
                                    skipped += 1
                            else:
                                cur.execute("INSERT INTO site_config (k, v, description) VALUES (%s, %s, %s)",
                                          (k, item.get('v',''), item.get('description','')))
                                imported += 1

                        elif table == 'dict_brand_copy':
                            if overwrite and item.get('id'):
                                cur.execute("DELETE FROM dict_brand_copy WHERE id=%s", (item.get('id'),))
                            cur.execute("""
                                INSERT INTO dict_brand_copy (kind, keyword, content, priority)
                                VALUES (%s, %s, %s, %s)
                            """, (item.get('kind',''), item.get('keyword',''), item.get('content',''), item.get('priority',50)))
                            imported += 1

                    except Exception as e:
                        print(f"    导入失败 {table}: {item.get('name') or item.get('k') or item.get('id')} - {e}")
                        skipped += 1

                conn.commit()
                total_imported += imported
                print(f"  导入 {table}: 新增{imported}条, 跳过{skipped}条")

        invalidate_all_cache()
        print(f"\n导入完成，共新增 {total_imported} 条数据")
        return True
    except Exception as e:
        conn.rollback()
        print(f"导入失败: {e}")
        return False
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description='字典数据导入导出工具')
    parser.add_argument('--export', action='store_true', help='导出数据')
    parser.add_argument('--import', dest='do_import', action='store_true', help='导入数据')
    parser.add_argument('--input', type=str, help='输入文件路径（导入时使用）')
    parser.add_argument('--output', type=str, default='data/dict_export.json', help='输出文件路径（导出时使用）')
    parser.add_argument('--types', type=str, help='数据类型，逗号分隔（must_visit,poi_hierarchy,site_config,dict_brand_copy）')
    parser.add_argument('--overwrite', action='store_true', help='导入时覆盖已存在数据')

    args = parser.parse_args()

    types = args.types.split(',') if args.types else None

    print("=" * 60)
    print("字典数据导入导出工具")
    print("=" * 60)

    if args.export:
        print(f"\n导出数据，类型: {types or '全部'}")
        export_data(types, args.output)
    elif args.do_import:
        if not args.input:
            print("错误: 导入时必须指定 --input 文件路径")
            sys.exit(1)
        print(f"\n导入数据，文件: {args.input}")
        print(f"覆盖模式: {'是' if args.overwrite else '否'}")
        import_data(args.input, types, args.overwrite)
    else:
        parser.print_help()
        print("\n示例:")
        print("  导出全部: python scripts/export_dict_data.py --export")
        print("  导出指定: python scripts/export_dict_data.py --export --types must_visit,poi_hierarchy")
        print("  导入数据: python scripts/export_dict_data.py --import --input data/dict_export.json")
        print("  覆盖导入: python scripts/export_dict_data.py --import --input data/dict_export.json --overwrite")


if __name__ == "__main__":
    main()
