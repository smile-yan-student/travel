#!/usr/bin/env python3
"""修复 admin_divisions.json 的关联关系：
1. 补充市级 parent（最近省份中心点法）
2. 修复 level=1 异常数据（香港/台北改为 province）
3. 修复区县 parent 缺失（重庆/香港的区）
4. 修复 parent=自己的条目（省直辖县级市改为所属省，标记 direct_control）
5. 重新统计
"""
import json
import math
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "app" / "data" / "admin_divisions.json"


def haversine(lng1, lat1, lng2, lat2):
    R = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def main():
    with open(DATA_PATH, encoding="utf-8") as f:
        d = json.load(f)
    by_name = d.get("by_name", {})

    # ---------- 1. 修复 level=1 异常数据（香港/台北）----------
    fixed_level = 0
    for name, entry in by_name.items():
        if entry.get("level") == "1":
            entry["level"] = "province"
            fixed_level += 1
    print(f"修复 level=1 异常数据: {fixed_level} 条")

    # ---------- 2. 收集省级条目（中心点）----------
    provinces = {}
    for name, entry in by_name.items():
        if entry.get("level") == "province" and entry.get("lng") and entry.get("lat"):
            # 去重：用名称（去后缀）作为 key
            base = name.rstrip("市").rstrip("省").rstrip("自治区")
            if base not in provinces or len(name) < len(provinces[base]["name"]):
                provinces[base] = {"name": name, "lng": entry["lng"], "lat": entry["lat"]}
    print(f"省级中心点: {len(provinces)} 个")

    # ---------- 3. 补充市级 parent（最近省份中心点法）----------
    fixed_city_parent = 0
    for name, entry in by_name.items():
        if entry.get("level") == "city" and not entry.get("parent"):
            if not entry.get("lng") or not entry.get("lat"):
                continue
            # 找最近的省
            best_prov = None
            best_dist = float("inf")
            for prov_name, prov in provinces.items():
                dist = haversine(entry["lng"], entry["lat"], prov["lng"], prov["lat"])
                if dist < best_dist:
                    best_dist = dist
                    best_prov = prov["name"]
            if best_prov:
                entry["parent"] = best_prov
                fixed_city_parent += 1
    print(f"补充市级 parent: {fixed_city_parent} 条")

    # ---------- 4. 修复区县 parent 缺失 ----------
    # 重庆的区：parent=重庆市
    # 香港的区：parent=香港特别行政区
    fixed_district_parent = 0
    for name, entry in by_name.items():
        if entry.get("level") == "district" and not entry.get("parent"):
            if not entry.get("lng") or not entry.get("lat"):
                continue
            # 找最近的省（区县级也用最近省法，因为直辖市的区直接属于省）
            best_prov = None
            best_dist = float("inf")
            for prov_name, prov in provinces.items():
                dist = haversine(entry["lng"], entry["lat"], prov["lng"], prov["lat"])
                if dist < best_dist:
                    best_dist = dist
                    best_prov = prov["name"]
            if best_prov and best_dist < 500_000:  # 500km 内才认为有效
                entry["parent"] = best_prov
                fixed_district_parent += 1
    print(f"补充区县 parent: {fixed_district_parent} 条")

    # ---------- 5. 修复 parent=自己的条目（省直辖县级市）----------
    fixed_self_parent = 0
    for name, entry in by_name.items():
        if entry.get("parent") == name:
            if not entry.get("lng") or not entry.get("lat"):
                continue
            # 找最近的省
            best_prov = None
            best_dist = float("inf")
            for prov_name, prov in provinces.items():
                dist = haversine(entry["lng"], entry["lat"], prov["lng"], prov["lat"])
                if dist < best_dist:
                    best_dist = dist
                    best_prov = prov["name"]
            if best_prov:
                entry["parent"] = best_prov
                entry["direct_control"] = True  # 标记为省直辖
                fixed_self_parent += 1
    print(f"修复 parent=自己（省直辖）: {fixed_self_parent} 条")

    # ---------- 6. 重新统计 ----------
    levels = {}
    for name, entry in by_name.items():
        lvl = entry.get("level", "unknown")
        has_parent = bool(entry.get("parent"))
        levels.setdefault(lvl, {"total": 0, "with_parent": 0, "without_parent": 0})
        levels[lvl]["total"] += 1
        if has_parent:
            levels[lvl]["with_parent"] += 1
        else:
            levels[lvl]["without_parent"] += 1

    d["stats"] = {
        "province": levels.get("province", {}).get("total", 0),
        "city": levels.get("city", {}).get("total", 0),
        "district": levels.get("district", {}).get("total", 0),
        "with_adcode": sum(1 for e in by_name.values() if e.get("adcode")),
        "with_parent": sum(1 for e in by_name.values() if e.get("parent")),
        "direct_control": sum(1 for e in by_name.values() if e.get("direct_control")),
    }
    d["version"] = "1.1-fixed-relations"
    d["updated_at"] = "2026-08-28"

    # 写回
    DATA_PATH.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")

    print()
    print("=== 修复后统计 ===")
    for lvl, info in sorted(levels.items()):
        pct = info["with_parent"] / info["total"] * 100 if info["total"] else 0
        print(f"  {lvl:10s}: 总数={info['total']:5d}, 有parent={info['with_parent']:5d} ({pct:.1f}%), 无parent={info['without_parent']:5d}")
    print(f"  with_adcode: {d['stats']['with_adcode']}")
    print(f"  direct_control（省直辖）: {d['stats']['direct_control']}")

    # 验证几个例子
    print()
    print("=== 验证样本 ===")
    samples = ["杭州市", "成都市", "西安市", "东莞市", "济源市", "渝北区", "香港"]
    for s in samples:
        if s in by_name:
            e = by_name[s]
            print(f"  {s}: level={e.get('level')}, parent={e.get('parent')}, direct_control={e.get('direct_control', False)}")


if __name__ == "__main__":
    main()
