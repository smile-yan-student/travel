#!/usr/bin/env python3
"""
从阿里云DataV导入全国行政区域数据到数据库。

数据来源：https://datav.aliyun.com/portal/school/atlas/area_selector
API: https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json

数据包含：省/市/区县三级行政区域，包括adcode、name、center（中心点坐标）等。
"""
import sys
import os

# 添加backend目录到Python模块搜索路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import time
import httpx
import pymysql
from app.config import settings


def get_regions_by_adcode(adcode):
    """根据adcode获取下级行政区域数据。"""
    url = f"https://geo.datav.aliyun.com/areas_v3/bound/{adcode}_full.json"
    try:
        with httpx.Client(timeout=30) as client:
            r = client.get(url)
            if r.status_code != 200:
                return []
            data = r.json()
        return data.get("features", [])
    except Exception as e:
        print(f"  获取 {adcode} 下级数据失败: {e}")
        return []


def get_all_regions():
    """从阿里云DataV逐级获取全国行政区域数据。"""
    all_regions = []

    # 1. 获取省级数据
    print("1. 获取省级数据...")
    province_features = get_regions_by_adcode("100000")
    print(f"  获取到 {len(province_features)} 个省级数据")

    for province_feature in province_features:
        province = parse_region(province_feature, level="province")
        all_regions.append(province)

        # 2. 获取市级数据
        print(f"2. 获取 {province['name']} 的市级数据...")
        city_features = get_regions_by_adcode(province["adcode"])
        print(f"  获取到 {len(city_features)} 个市级数据")

        for city_feature in city_features:
            city = parse_region(city_feature, level="city", parent_adcode=province["adcode"])
            all_regions.append(city)

            # 3. 获取区县级数据
            print(f"3. 获取 {city['name']} 的区县级数据...")
            district_features = get_regions_by_adcode(city["adcode"])
            print(f"  获取到 {len(district_features)} 个区县级数据")

            for district_feature in district_features:
                district = parse_region(district_feature, level="district", parent_adcode=city["adcode"])
                all_regions.append(district)

    print(f"\n获取完成，共 {len(all_regions)} 条行政区域数据")
    return all_regions


def parse_region(feature, level="province", parent_adcode=""):
    """解析GeoJSON feature，返回行政区域信息。"""
    properties = feature.get("properties", {})
    geometry = feature.get("geometry", {})

    adcode = str(properties.get("adcode", ""))
    name = properties.get("name", "")
    center = properties.get("center", "")

    # 解析中心点坐标
    lng = None
    lat = None
    if center and isinstance(center, list) and len(center) >= 2:
        lng = center[0]
        lat = center[1]
    elif center and isinstance(center, str):
        parts = center.split(",")
        if len(parts) >= 2:
            try:
                lng = float(parts[0])
                lat = float(parts[1])
            except ValueError:
                pass

    return {
        "adcode": adcode,
        "name": name,
        "level": level,
        "parent_adcode": parent_adcode,
        "lng": lng,
        "lat": lat,
        "center": center if isinstance(center, str) else (",".join(map(str, center)) if center else ""),
    }


def insert_regions(cursor, regions):
    """批量插入行政区域数据。"""
    if not regions:
        return 0

    sql = """
    INSERT INTO admin_regions (adcode, name, level, parent_adcode, lng, lat, center)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
        name = VALUES(name),
        level = VALUES(level),
        parent_adcode = VALUES(parent_adcode),
        lng = VALUES(lng),
        lat = VALUES(lat),
        center = VALUES(center)
    """

    values = []
    for r in regions:
        values.append((
            r["adcode"],
            r["name"],
            r["level"],
            r["parent_adcode"],
            r["lng"],
            r["lat"],
            r["center"],
        ))

    cursor.executemany(sql, values)
    return len(values)


def main():
    # 连接数据库
    conn = pymysql.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
        charset='utf8mb4'
    )
    cursor = conn.cursor()

    try:
        # 获取全国行政区域数据（get_all_regions已经返回解析好的all_regions列表）
        all_regions = get_all_regions()

        # 统计各级别数据量
        province_count = sum(1 for r in all_regions if r["level"] == "province")
        city_count = sum(1 for r in all_regions if r["level"] == "city")
        district_count = sum(1 for r in all_regions if r["level"] == "district")

        print(f"\n数据统计：")
        print(f"  省级：{province_count} 个")
        print(f"  市级：{city_count} 个")
        print(f"  区县级：{district_count} 个")
        print(f"  总计：{len(all_regions)} 个")

        # 批量插入数据（每500条一批）
        print(f"\n开始导入数据到数据库...")
        batch_size = 500
        total_inserted = 0
        for i in range(0, len(all_regions), batch_size):
            batch = all_regions[i:i+batch_size]
            inserted = insert_regions(cursor, batch)
            total_inserted += inserted
            print(f"  已导入 {total_inserted}/{len(all_regions)} 条")

        conn.commit()
        print(f"\n✅ 数据导入完成！共导入 {total_inserted} 条行政区域数据")

        # 验证数据
        cursor.execute("SELECT level, COUNT(*) FROM admin_regions GROUP BY level")
        print(f"\n数据库中的数据统计：")
        for row in cursor.fetchall():
            print(f"  {row[0]}: {row[1]} 个")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ 数据导入失败：{e}")
        import traceback
        traceback.print_exc()
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()
