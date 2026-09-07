#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据初始化脚本：将代码中的硬编码数据导入数据库。

执行方式：
    cd backend
    ./.venv/bin/python scripts/init_dict_data.py

导入内容：
1. must_visit 必去景点数据（data/must_visit.py → must_visit 表）
2. poi_hierarchy 景点层级关系（合并4个文件 → poi_hierarchy 表）
3. site_config 规划配置常量（planner_constants.py → site_config 表）
4. dict_brand_copy 品牌文案（代码中的文案 → dict_brand_copy 表）
"""
import sys
import os
import json

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.data.database import get_conn, init_db


def import_must_visit():
    """导入必去景点数据"""
    print("\n=== 1. 导入必去景点数据 ===")
    try:
        from app.data.must_visit import MUST_VISIT
    except ImportError as e:
        print(f"  跳过：无法导入 must_visit 模块 ({e})")
        return

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # 清空现有数据（可选，保留则注释掉）
            # cur.execute("DELETE FROM must_visit")

            count = 0
            for city, spots in MUST_VISIT.items():
                for spot in spots:
                    name = spot.get("name", "")
                    if not name:
                        continue
                    # 检查是否已存在
                    cur.execute(
                        "SELECT id FROM must_visit WHERE city = %s AND name = %s",
                        (city, name)
                    )
                    if cur.fetchone():
                        continue

                    cur.execute("""
                        INSERT INTO must_visit (city, name, kw, category, rating, priority, adcode, lng, lat)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        city,
                        name,
                        spot.get("kw", name),
                        spot.get("category", "景点"),
                        spot.get("rating", 4.5),
                        50,
                        spot.get("adcode", ""),
                        spot.get("lng"),
                        spot.get("lat"),
                    ))
                    count += 1

            conn.commit()
            print(f"  成功导入 {count} 条必去景点数据")
    except Exception as e:
        conn.rollback()
        print(f"  导入失败：{e}")
    finally:
        conn.close()


def import_poi_hierarchy():
    """导入景点层级关系数据（合并4个文件）"""
    print("\n=== 2. 导入景点层级关系数据 ===")

    # 收集所有主景点数据
    all_pois = {}

    # 2.1 从 poi_hierarchy.py 导入
    try:
        from app.data.poi_hierarchy import POI_HIERARCHY
        for name, poi in POI_HIERARCHY.items():
            all_pois[name] = {
                "name": poi.name,
                "alias": poi.alias,
                "city": poi.city,
                "district": poi.district,
                "level": poi.level,
                "description": poi.description,
                "best_time": poi.best_time,
                "inner_route": [ir.__dict__ if hasattr(ir, '__dict__') else dict(ir) for ir in poi.inner_route],
                "nearby_attractions": [na.__dict__ if hasattr(na, '__dict__') else dict(na) for na in poi.nearby_attractions],
                "avoid_tips": poi.avoid_tips,
                "is_large_scenic": 1,
            }
        print(f"  从 poi_hierarchy.py 导入 {len(POI_HIERARCHY)} 个主景点")
    except ImportError as e:
        print(f"  跳过 poi_hierarchy.py：{e}")

    # 2.2 从 poi_hierarchy_extra.py 导入
    try:
        from app.data.poi_hierarchy_extra import EXTRA_POI_HIERARCHY
        for name, poi in EXTRA_POI_HIERARCHY.items():
            if name not in all_pois:
                all_pois[name] = {
                    "name": poi.name,
                    "alias": poi.alias,
                    "city": poi.city,
                    "district": poi.district,
                    "level": poi.level,
                    "description": poi.description,
                    "best_time": poi.best_time,
                    "inner_route": [ir.__dict__ if hasattr(ir, '__dict__') else dict(ir) for ir in poi.inner_route],
                    "nearby_attractions": [na.__dict__ if hasattr(na, '__dict__') else dict(na) for na in poi.nearby_attractions],
                    "avoid_tips": poi.avoid_tips,
                    "is_large_scenic": 1,
                }
        print(f"  从 poi_hierarchy_extra.py 导入 {len(EXTRA_POI_HIERARCHY)} 个补充主景点")
    except ImportError as e:
        print(f"  跳过 poi_hierarchy_extra.py：{e}")

    # 2.3 从 large_scenic_areas.py 导入（补充大型景区标记和坐标）
    try:
        from app.data.large_scenic_areas import LARGE_SCENIC_AREAS
        for name, city in LARGE_SCENIC_AREAS.items():
            if name not in all_pois:
                all_pois[name] = {
                    "name": name,
                    "alias": [],
                    "city": city,
                    "district": "",
                    "level": "",
                    "description": "",
                    "best_time": "",
                    "inner_route": [],
                    "nearby_attractions": [],
                    "avoid_tips": [],
                    "is_large_scenic": 1,
                }
            else:
                all_pois[name]["is_large_scenic"] = 1
                if not all_pois[name].get("city"):
                    all_pois[name]["city"] = city
        print(f"  从 large_scenic_areas.py 补充 {len(LARGE_SCENIC_AREAS)} 个大型景区标记")
    except ImportError as e:
        print(f"  跳过 large_scenic_areas.py：{e}")

    # 2.4 从 famous_landmarks.py 导入（补充坐标）
    try:
        from app.data.famous_landmarks import FAMOUS_LANDMARKS
        for name, info in FAMOUS_LANDMARKS.items():
            if name in all_pois:
                all_pois[name]["lng"] = info.get("lng")
                all_pois[name]["lat"] = info.get("lat")
                all_pois[name]["adcode"] = info.get("adcode", "")
                all_pois[name]["province"] = info.get("province", "")
                if not all_pois[name].get("city"):
                    all_pois[name]["city"] = info.get("city", "")
            else:
                all_pois[name] = {
                    "name": name,
                    "alias": [],
                    "city": info.get("city", ""),
                    "district": "",
                    "province": info.get("province", ""),
                    "level": "",
                    "adcode": info.get("adcode", ""),
                    "lng": info.get("lng"),
                    "lat": info.get("lat"),
                    "description": "",
                    "best_time": "",
                    "inner_route": [],
                    "nearby_attractions": [],
                    "avoid_tips": [],
                    "is_large_scenic": 0,
                }
        print(f"  从 famous_landmarks.py 补充 {len(FAMOUS_LANDMARKS)} 个景点坐标")
    except ImportError as e:
        print(f"  跳过 famous_landmarks.py：{e}")

    # 2.5 写入数据库
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            count = 0
            for name, poi in all_pois.items():
                # 检查是否已存在
                cur.execute("SELECT id FROM poi_hierarchy WHERE name = %s", (name,))
                if cur.fetchone():
                    continue

                cur.execute("""
                    INSERT INTO poi_hierarchy (
                        name, alias, city, district, province, level, adcode,
                        lng, lat, description, best_time, is_large_scenic,
                        inner_route, nearby_attractions, avoid_tips, priority
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    poi.get("name", ""),
                    json.dumps(poi.get("alias", []), ensure_ascii=False),
                    poi.get("city", ""),
                    poi.get("district", ""),
                    poi.get("province", ""),
                    poi.get("level", ""),
                    poi.get("adcode", ""),
                    poi.get("lng"),
                    poi.get("lat"),
                    poi.get("description", ""),
                    poi.get("best_time", ""),
                    poi.get("is_large_scenic", 0),
                    json.dumps(poi.get("inner_route", []), ensure_ascii=False),
                    json.dumps(poi.get("nearby_attractions", []), ensure_ascii=False),
                    json.dumps(poi.get("avoid_tips", []), ensure_ascii=False),
                    50,
                ))
                count += 1

            conn.commit()
            print(f"  成功导入 {count} 条景点层级关系数据（总计 {len(all_pois)} 个）")
    except Exception as e:
        conn.rollback()
        print(f"  导入失败：{e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


def import_site_config():
    """导入规划配置常量"""
    print("\n=== 3. 导入规划配置常量 ===")

    configs = {
        # 聚类距离上限（米）
        "cluster_max_dist": ("12000", "区域聚类距离上限（米）：短距离的点位归为同一天"),
        # 省内景点距离市中心上限（米）
        "scope_max_range": ("150000", "省内景点距离市中心上限（米）"),
        # 闭馆/停业标记
        "closed_markers": (
            json.dumps(["暂停开放", "暂停营业", "停止开放", "停止营业", "闭园", "维修中", "建设中"], ensure_ascii=False),
            "闭馆/停业标记词：高德有时把状态写进名称，不能排进行程"
        ),
        # 美食辅助点名称护栏
        "aux_food_bad_names": (
            json.dumps(["植物园", "动物园", "公园", "湿地", "景区", "博物馆"], ensure_ascii=False),
            "美食辅助点的名称护栏：这些不是餐厅"
        ),
        # 全国知名地标特征词
        "landmark_words": (
            json.dumps([
                "长城", "故宫", "天安门", "颐和园", "天坛", "圆明园", "十三陵", "香山",
                "外滩", "迪士尼", "豫园", "东方明珠", "田子坊", "武康路",
                "兵马俑", "华清宫", "大雁塔", "不夜城", "西安城墙", "钟楼",
                "西湖", "灵隐寺", "雷峰塔", "西溪", "乌镇", "千岛湖",
                "泰山", "黄山", "九寨沟", "张家界", "峨眉山", "乐山大佛", "布达拉宫",
                "鼓浪屿", "洱海", "玉龙雪山", "泸沽湖", "洪崖洞", "武侯祠", "宽窄巷子",
                "都江堰", "青城山", "漓江", "阳朔", "天涯海角", "亚龙湾", "蜈支洲",
                "莫高窟", "敦煌", "鸣沙山", "五台山", "普陀山", "平遥", "凤凰古城",
                "丽江古城", "大理古城", "少林寺", "黄鹤楼", "岳阳楼", "橘子洲", "岳麓山",
                "三星堆", "大熊猫基地", "三坊七巷", "夫子庙", "中山陵", "明孝陵",
                "哈尔滨冰雪大世界", "长白山", "天池", "雪乡", "呼伦贝尔", "喀纳斯", "那拉提",
            ], ensure_ascii=False),
            "全国知名地标特征词：名称命中即视为「城市名片」，优先进入规划"
        ),
        # 行政分级景点枚举关键词
        "scope_keywords": (
            json.dumps({
                "区县": ["景区", "5A", "博物馆", "公园", "古镇"],
                "市": ["景区", "5A", "博物馆", "公园", "古镇"],
                "省": ["5A", "旅游度假区", "古镇", "国家级风景名胜区"],
            }, ensure_ascii=False),
            "行政分级 → 景点枚举关键词（区/县 → 市 → 省，逐级扩大）"
        ),
    }

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            count = 0
            for k, (v, desc) in configs.items():
                cur.execute("SELECT k FROM site_config WHERE k = %s", (k,))
                if cur.fetchone():
                    continue
                cur.execute(
                    "INSERT INTO site_config (k, v, description) VALUES (%s, %s, %s)",
                    (k, v, desc)
                )
                count += 1
            conn.commit()
            print(f"  成功导入 {count} 条配置常量（总计 {len(configs)} 个）")
    except Exception as e:
        conn.rollback()
        print(f"  导入失败：{e}")
    finally:
        conn.close()


def import_brand_copy():
    """导入品牌文案数据"""
    print("\n=== 4. 导入品牌文案数据 ===")

    # 出发宣言模板
    departure_messages = [
        ("", "你要去的{destination}，正等着你的脚步。出发吧，勇气都在路上。"),
        ("北京", "北京的故事，藏在红墙黄瓦里，也藏在胡同的烟火气中。出发吧，去触摸这座城市的脉搏。"),
        ("上海", "上海的魅力，在于传统与现代的交融。出发吧，去感受这座城市的节奏。"),
        ("杭州", "上有天堂，下有苏杭。杭州的美，需要你用脚步去丈量。出发吧！"),
        ("西安", "千年古都，长安常在。西安的每一寸土地，都诉说着历史的故事。出发吧！"),
        ("成都", "成都，一座来了就不想走的城市。慢生活、美食、茶馆，都在等你。出发吧！"),
    ]

    # 每日寄语模板
    daily_inspirations = [
        ("", "旅行最好的开始，就是你决定出发的这一刻。{destination}见。"),
        ("", "世界很大，风景很美，不要只在屏幕前看。走出去，才是真正的拥有。"),
        ("", "每一次出发，都是一次与自己的对话。今天的行程，会给你带来新的感悟。"),
        ("", "旅行的意义，不在于去了多少地方，而在于经历了多少故事。今天，去创造属于你的故事吧。"),
        ("", "脚步丈量世界，心灵感受美好。今天的{destination}，会给你留下难忘的回忆。"),
    ]

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            count = 0
            # 导入出发宣言
            for keyword, content in departure_messages:
                cur.execute(
                    "SELECT id FROM dict_brand_copy WHERE kind = 'departure_message' AND keyword = %s AND content = %s",
                    (keyword, content)
                )
                if cur.fetchone():
                    continue
                cur.execute(
                    "INSERT INTO dict_brand_copy (kind, keyword, content, priority) VALUES (%s, %s, %s, %s)",
                    ("departure_message", keyword, content, 50)
                )
                count += 1

            # 导入每日寄语
            for keyword, content in daily_inspirations:
                cur.execute(
                    "SELECT id FROM dict_brand_copy WHERE kind = 'daily_inspiration' AND keyword = %s AND content = %s",
                    (keyword, content)
                )
                if cur.fetchone():
                    continue
                cur.execute(
                    "INSERT INTO dict_brand_copy (kind, keyword, content, priority) VALUES (%s, %s, %s, %s)",
                    ("daily_inspiration", keyword, content, 50)
                )
                count += 1

            conn.commit()
            print(f"  成功导入 {count} 条品牌文案")
    except Exception as e:
        conn.rollback()
        print(f"  导入失败：{e}")
    finally:
        conn.close()


def verify_data():
    """验证数据导入结果"""
    print("\n=== 5. 验证数据导入结果 ===")
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            tables = ["must_visit", "poi_hierarchy", "site_config", "dict_brand_copy"]
            for table in tables:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                count = cur.fetchone()[0]
                print(f"  {table}: {count} 条记录")
    except Exception as e:
        print(f"  验证失败：{e}")
    finally:
        conn.close()


def main():
    print("=" * 60)
    print("数据初始化脚本：将硬编码数据导入数据库")
    print("=" * 60)

    # 初始化数据库表
    print("\n初始化数据库表...")
    init_db()
    print("数据库表初始化完成")

    # 导入数据
    import_must_visit()
    import_poi_hierarchy()
    import_site_config()
    import_brand_copy()

    # 验证结果
    verify_data()

    print("\n" + "=" * 60)
    print("数据初始化完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
