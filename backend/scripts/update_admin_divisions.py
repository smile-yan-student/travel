#!/usr/bin/env python3
"""全量更新行政区域数据：从高德 district_query 拉取全国省/市/区县，生成 admin_divisions.json。

使用方式：
  python scripts/update_admin_divisions.py              # 全量更新（需要 AMAP_KEY）
  python scripts/update_admin_divisions.py --dry-run    # 只拉取不写入

数据来源：高德 Web服务 district_query（subdistrict=3 一次拉取省→市→区县三级）
更新频率：建议每月一次（行政区域变更不频繁），或手动触发。
"""
import argparse
import asyncio
import json
import sys
from datetime import date
from pathlib import Path

# 确保能 import app 模块
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import amap  # noqa: E402
from app import geo_local  # noqa: E402

DATA_PATH = Path(__file__).resolve().parent.parent / "app" / "data" / "admin_divisions.json"


async def fetch_all_divisions() -> dict:
    """从高德 district_query 拉取全国省→市→区县三级行政区域。

    返回 {by_name, by_adcode} 结构。
    """
    # 高德 district_query: keywords=中国, subdistrict=3 一次返回省→市→区县
    url = f"{amap.AMAP_BASE}/config/district"
    params = {"keywords": "中国", "subdistrict": 3, "extensions": "base"}
    data = await amap._get(url, params)
    if not data or not data.get("districts"):
        raise RuntimeError("高德 district_query 返回空数据，请检查 AMAP_KEY")

    by_name = {}
    by_adcode = {}

    def add(name, adcode, level, lng, lat, parent=None):
        entry = {
            "name": name,
            "adcode": adcode or "",
            "level": level,
            "lng": float(lng),
            "lat": float(lat),
            "parent": parent,
        }
        by_name[name] = entry
        # 别名：去后缀
        for suffix in ["市", "省", "区", "县", "自治州", "盟"]:
            if name.endswith(suffix):
                alias = name[: -len(suffix)]
                if alias and alias != name:
                    by_name.setdefault(alias, entry)
        if adcode:
            by_adcode[adcode] = entry

    def parse_district(d, level, parent=None):
        """递归解析 district 节点"""
        name = d.get("name", "")
        adcode = d.get("adcode", "")
        center = d.get("center", "")
        if not name or not center:
            return
        try:
            lng, lat = center.split(",")
            lng, lat = float(lng), float(lat)
        except (ValueError, AttributeError):
            return
        add(name, adcode, level, lng, lat, parent=parent)
        # 递归子级
        children = d.get("districts", [])
        if children:
            child_level = {"province": "city", "city": "district"}.get(level, "district")
            for child in children:
                parse_district(child, child_level, parent=name)

    # 第一层是"中国"，其 districts 是省
    china = data["districts"][0]
    for prov in china.get("districts", []):
        parse_district(prov, "province")

    return {"by_name": by_name, "by_adcode": by_adcode}


def main():
    parser = argparse.ArgumentParser(description="全量更新行政区域数据")
    parser.add_argument("--dry-run", action="store_true", help="只拉取不写入")
    args = parser.parse_args()

    if not amap.settings.amap_key:
        print("错误：未配置 AMAP_KEY，无法从高德拉取全量数据")
        print("请在 .env 中设置 AMAP_KEY，或使用 convert_admin_divisions.py 从现有数据转换")
        sys.exit(1)

    print("正在从高德 district_query 拉取全国行政区域数据（省→市→区县三级）...")
    result = asyncio.run(fetch_all_divisions())

    by_name = result["by_name"]
    by_adcode = result["by_adcode"]
    stats = {
        "province": sum(1 for e in by_name.values() if e["level"] == "province"),
        "city": sum(1 for e in by_name.values() if e["level"] == "city"),
        "district": sum(1 for e in by_name.values() if e["level"] == "district"),
        "with_adcode": sum(1 for e in by_name.values() if e["adcode"]),
    }
    print(f"拉取完成：{len(by_name)} 条（含别名），{len(by_adcode)} 个 adcode")
    print(f"  省: {stats['province']}, 市: {stats['city']}, 区县: {stats['district']}")
    print(f"  含 adcode: {stats['with_adcode']}")

    if args.dry_run:
        print("dry-run 模式，不写入文件")
        return

    # 备份旧版本
    if DATA_PATH.exists():
        backup = DATA_PATH.with_suffix(f".json.bak.{date.today().isoformat()}")
        DATA_PATH.rename(backup)
        print(f"已备份旧版本到 {backup.name}")

    # 写入新版本
    output = {
        "version": f"amap-{date.today().isoformat()}",
        "updated_at": date.today().isoformat(),
        "source": "高德 district_query 全量拉取",
        "by_name": by_name,
        "by_adcode": by_adcode,
        "stats": stats,
    }
    DATA_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    geo_local._reload()
    print(f"已写入 {DATA_PATH}")
    print("全量更新完成！")


if __name__ == "__main__":
    main()
