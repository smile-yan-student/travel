#!/usr/bin/env python3
"""从阿里云 DataV 拉取全国行政区域数据（省→市→区县三级），生成完整的 admin_divisions.json。

DataV 数据来源：https://datav.aliyun.com/portal/school/atlas/area_selector
API 格式：
  - 全国省级：https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json
  - 某省市级：https://geo.datav.aliyun.com/areas_v3/bound/{省adcode}_full.json
  - 某市区县：https://geo.datav.aliyun.com/areas_v3/bound/{市adcode}_full.json

数据包含：name, adcode, level(province/city/district), center=[lng,lat]
"""
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

DATA_PATH = Path(__file__).resolve().parent.parent / "app" / "data" / "admin_divisions.json"
BASE_URL = "https://geo.datav.aliyun.com/areas_v3/bound"
CONCURRENCY = 5  # 并发请求数，避免被限流
RETRY = 3
TIMEOUT = 15


async def fetch_json(client: httpx.AsyncClient, url: str) -> dict:
    """拉取 JSON，带重试"""
    for attempt in range(RETRY):
        try:
            resp = await client.get(url, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            if attempt == RETRY - 1:
                print(f"  失败 {url}: {e}")
                return {}
            await asyncio.sleep(1 * (attempt + 1))
    return {}


def extract_features(data: dict) -> list:
    """从 GeoJSON FeatureCollection 提取 features 的 properties"""
    features = data.get("features", [])
    results = []
    for f in features:
        props = f.get("properties", {})
        name = props.get("name", "")
        adcode = str(props.get("adcode", ""))
        level = props.get("level", "")
        center = props.get("center", [])
        if name and adcode and len(center) == 2:
            results.append({
                "name": name,
                "adcode": adcode,
                "level": level,
                "lng": float(center[0]),
                "lat": float(center[1]),
            })
    return results


async def main():
    start = time.time()
    print("=== 从阿里云 DataV 拉取全国行政区域数据 ===")

    # 并发控制
    semaphore = asyncio.Semaphore(CONCURRENCY)

    async def fetch_with_sem(client, url):
        async with semaphore:
            return await fetch_json(client, url)

    async with httpx.AsyncClient() as client:
        # 1) 拉取全国省级
        print("1) 拉取全国省级数据...")
        nation_data = await fetch_with_sem(client, f"{BASE_URL}/100000_full.json")
        provinces = extract_features(nation_data)
        print(f"   省级: {len(provinces)} 个")

        # 2) 并发拉取每个省的市级数据
        print(f"2) 并发拉取 {len(provinces)} 个省的市级数据...")
        city_tasks = []
        for prov in provinces:
            url = f"{BASE_URL}/{prov['adcode']}_full.json"
            city_tasks.append(fetch_with_sem(client, url))
        city_results = await asyncio.gather(*city_tasks)

        all_cities = []
        province_cities = {}  # adcode -> [cities]
        for prov, city_data in zip(provinces, city_results):
            cities = extract_features(city_data)
            for c in cities:
                c["parent"] = prov["name"]
            all_cities.extend(cities)
            province_cities[prov["adcode"]] = cities
        print(f"   市级: {len(all_cities)} 个")

        # 3) 并发拉取每个市的区县级数据
        print(f"3) 并发拉取 {len(all_cities)} 个市的区县级数据...")
        district_tasks = []
        for city in all_cities:
            url = f"{BASE_URL}/{city['adcode']}_full.json"
            district_tasks.append(fetch_with_sem(client, url))
        district_results = await asyncio.gather(*district_tasks)

        all_districts = []
        for city, dist_data in zip(all_cities, district_results):
            districts = extract_features(dist_data)
            for d in districts:
                d["parent"] = city["name"]
            all_districts.extend(districts)
        print(f"   区县级: {len(all_districts)} 个")

    # 4) 构建 by_name（支持同名地点 list）和 by_adcode
    print("4) 构建数据结构...")
    by_name = {}
    by_adcode = {}

    def add_entry(entry):
        name = entry["name"]
        adcode = entry["adcode"]
        # by_adcode
        by_adcode[adcode] = entry
        # by_name（同名地点存为 list）
        if name in by_name:
            existing = by_name[name]
            if isinstance(existing, list):
                # 检查是否已存在相同 adcode
                if not any(e["adcode"] == adcode for e in existing):
                    existing.append(entry)
            else:
                if existing["adcode"] != adcode:
                    by_name[name] = [existing, entry]
        else:
            by_name[name] = entry
        # 别名（去后缀）
        for suffix in ["市", "省", "区", "县", "自治州", "盟", "旗", "林区"]:
            if name.endswith(suffix):
                alias = name[:-len(suffix)]
                if alias and alias not in by_name:
                    by_name[alias] = entry
                break

    for prov in provinces:
        prov["parent"] = None
        add_entry(prov)
    for city in all_cities:
        add_entry(city)
    for district in all_districts:
        add_entry(district)

    # 5) 统计
    ambiguous_count = sum(1 for v in by_name.values() if isinstance(v, list))
    stats = {
        "province": len(provinces),
        "city": len(all_cities),
        "district": len(all_districts),
        "with_adcode": len(by_adcode),
        "ambiguous_names": ambiguous_count,
    }

    output = {
        "version": "datav-2026",
        "updated_at": time.strftime("%Y-%m-%d"),
        "source": "阿里云 DataV 全国行政区域数据（省→市→区县三级）",
        "source_url": "https://datav.aliyun.com/portal/school/atlas/area_selector",
        "by_name": by_name,
        "by_adcode": by_adcode,
        "stats": stats,
    }

    # 6) 备份旧文件并写入
    if DATA_PATH.exists():
        backup = DATA_PATH.with_suffix(f".json.bak.{time.strftime('%Y%m%d_%H%M%S')}")
        DATA_PATH.rename(backup)
        print(f"   已备份旧文件: {backup.name}")

    DATA_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    elapsed = time.time() - start
    print()
    print(f"=== 完成！耗时 {elapsed:.1f}s ===")
    print(f"总条目(by_name): {len(by_name)}")
    print(f"adcode 条目: {len(by_adcode)}")
    print(f"同名地点: {ambiguous_count} 组")
    print(f"统计: {stats}")
    print(f"文件: {DATA_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
