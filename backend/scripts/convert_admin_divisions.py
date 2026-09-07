#!/usr/bin/env python3
"""从 place_geo.json 转换生成 admin_divisions.json（初始版本）。

后续可通过 update_admin_divisions.py 从高德 district_query 拉取全量数据补充 adcode。
"""
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "app" / "data"


def main():
    with open(DATA_DIR / "place_geo.json", encoding="utf-8") as f:
        src = json.load(f)

    by_name = {}
    by_adcode = {}

    def add_entry(name, adcode, level, lng, lat, parent=None):
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
        for suffix in ["市", "省", "区", "县"]:
            alias = name.rstrip(suffix) if name.endswith(suffix) else name
            if alias and alias != name:
                by_name.setdefault(alias, entry)
        if adcode:
            by_adcode[adcode] = entry

    # 1) 省（34 条）
    for name, coord in src.get("provinces", {}).items():
        add_entry(name, "", "province", coord[0], coord[1])

    # 2) 地级市（363 条）
    for name, coord in src.get("cities", {}).items():
        add_entry(name, "", "city", coord[0], coord[1])

    # 3) 精确区县（112 条，有坐标）
    district_to_city = src.get("district_to_city", {})
    for name, coord in src.get("districts_geo", {}).items():
        parent = district_to_city.get(name)
        add_entry(name, "", "district", coord[0], coord[1], parent=parent)

    # 4) 区县→城市映射中无坐标的区县（3147-112 条），用所属城市坐标近似
    districts_with_geo = set(src.get("districts_geo", {}).keys())
    city_coords = src.get("cities", {})
    for district, city in district_to_city.items():
        if district in districts_with_geo:
            continue
        coord = city_coords.get(city)
        if not coord:
            continue
        add_entry(district, "", "district", coord[0], coord[1], parent=city)

    result = {
        "version": "1.0-initial",
        "updated_at": "2026-08-28",
        "source": "place_geo.json 转换（adcode 待补充）",
        "by_name": by_name,
        "by_adcode": by_adcode,
        "stats": {
            "province": sum(1 for e in by_name.values() if e["level"] == "province"),
            "city": sum(1 for e in by_name.values() if e["level"] == "city"),
            "district": sum(1 for e in by_name.values() if e["level"] == "district"),
            "with_adcode": sum(1 for e in by_name.values() if e["adcode"]),
        },
    }

    out = DATA_DIR / "admin_divisions.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已生成 {out}")
    print(f"  by_name: {len(by_name)} 条")
    print(f"  by_adcode: {len(by_adcode)} 条")
    print(f"  stats: {result['stats']}")


if __name__ == "__main__":
    main()
