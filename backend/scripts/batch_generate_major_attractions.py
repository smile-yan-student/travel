"""
批量生成主要景点数据脚本

使用AI批量生成旅游城市的主要景点数据，然后导入到数据库中。
优先添加旅游热门城市，每个城市至少5-10个主要景点。

使用方式：
    cd backend
    ./.venv/bin/python scripts/batch_generate_major_attractions.py
"""
import asyncio
import json
import sys
from pathlib import Path
from typing import List, Dict, Any

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ai import ai as ai_mod
from app.services.map.geocode import geocode


# 优先添加的旅游城市列表（按旅游热度排序）
PRIORITY_CITIES = [
    # 安徽省
    {"city": "黄山市", "province": "安徽省", "famous_for": "黄山、徽州文化、古村落"},
    {"city": "合肥市", "province": "安徽省", "famous_for": "包公文化、巢湖、三国遗址"},
    # 浙江省
    {"city": "宁波市", "province": "浙江省", "famous_for": "天一阁、奉化溪口、东钱湖"},
    {"city": "温州市", "province": "浙江省", "famous_for": "雁荡山、楠溪江、江心屿"},
    {"city": "绍兴市", "province": "浙江省", "famous_for": "鲁迅故里、沈园、兰亭"},
    # 江苏省
    {"city": "无锡市", "province": "江苏省", "famous_for": "太湖、灵山大佛、鼋头渚"},
    {"city": "扬州市", "province": "江苏省", "famous_for": "瘦西湖、个园、何园"},
    # 四川省
    {"city": "乐山市", "province": "四川省", "famous_for": "乐山大佛、峨眉山"},
    {"city": "九寨沟县", "province": "四川省", "famous_for": "九寨沟、黄龙"},
    # 云南省
    {"city": "大理市", "province": "云南省", "famous_for": "洱海、大理古城、苍山"},
    {"city": "香格里拉市", "province": "云南省", "famous_for": "普达措、松赞林寺、虎跳峡"},
    # 湖南省
    {"city": "张家界市", "province": "湖南省", "famous_for": "张家界国家森林公园、天门山"},
    {"city": "凤凰县", "province": "湖南省", "famous_for": "凤凰古城、沱江"},
    # 福建省
    {"city": "泉州市", "province": "福建省", "famous_for": "开元寺、清源山、惠安女"},
    # 山东省
    {"city": "泰安市", "province": "山东省", "famous_for": "泰山、岱庙"},
    {"city": "曲阜市", "province": "山东省", "famous_for": "三孔（孔庙、孔府、孔林）"},
    # 陕西省
    {"city": "渭南市", "province": "陕西省", "famous_for": "华山、兵马俑"},
    # 甘肃省
    {"city": "敦煌市", "province": "甘肃省", "famous_for": "莫高窟、鸣沙山月牙泉"},
    # 新疆
    {"city": "乌鲁木齐市", "province": "新疆维吾尔自治区", "famous_for": "天山天池、国际大巴扎"},
    {"city": "喀什市", "province": "新疆维吾尔自治区", "famous_for": "喀什古城、艾提尕尔清真寺"},
    # 西藏
    {"city": "拉萨市", "province": "西藏自治区", "famous_for": "布达拉宫、大昭寺、八廓街"},
    # 青海省
    {"city": "西宁市", "province": "青海省", "famous_for": "青海湖、塔尔寺"},
    # 海南省
    {"city": "三亚市", "province": "海南省", "famous_for": "天涯海角、亚龙湾、蜈支洲岛"},
]

# 每个城市生成的景点数量
ATTRACTIONS_PER_CITY = 8


async def generate_attractions_for_city(
    city_info: Dict[str, str],
    count: int = ATTRACTIONS_PER_CITY,
) -> List[Dict[str, Any]]:
    """
    使用AI为指定城市生成主要景点数据

    Args:
        city_info: 城市信息（city, province, famous_for）
        count: 生成的景点数量

    Returns:
        景点数据列表
    """
    city = city_info["city"]
    province = city_info["province"]
    famous_for = city_info.get("famous_for", "")

    prompt = f"""请为{province}{city}生成{count}个最值得游览的主要景点数据。

{city}以{famous_for}闻名。

请以JSON数组格式返回，每个景点包含以下字段：
- name: 景点名称（字符串）
- aliases: 别名/曾用名（数组，没有则为空数组）
- district: 所在区县（字符串）
- level: 景点等级（5A/4A/3A/无，字符串）
- category: 景点类别（自然风光/历史古迹/文化体验/主题乐园/宗教圣地，字符串）
- description: 景点简介（50-100字，字符串）
- recommended_duration: 建议游览时长（小时，整数）
- must_visit: 是否必去（布尔值，最著名的2-3个设为true）
- hot: 是否热门（布尔值，游客较多的设为true）
- tags: 标签（数组，如["世界遗产","摄影圣地","亲子游"]）
- best_time: 最佳游览时间（字符串，如"春秋两季"）
- priority: 优先级（整数，1-10，最著名的设为10）

请确保景点数据真实准确，是{city}最具代表性的景点。
只返回JSON数组，不要返回其他内容。"""

    try:
        # 使用AI模块的chat函数生成景点数据
        messages = [
            {"role": "system", "content": "你是一个专业的旅游规划师，熟悉中国各地的旅游景点。请只返回JSON格式的数据，不要返回其他内容。"},
            {"role": "user", "content": prompt}
        ]

        # 调用AI模块的chat函数
        response = await ai_mod.chat_reply([prompt])
        content = response if isinstance(response, str) else str(response)

        # 尝试提取JSON数组
        json_start = content.find("[")
        json_end = content.rfind("]") + 1
        if json_start >= 0 and json_end > json_start:
            json_str = content[json_start:json_end]
            attractions = json.loads(json_str)
        else:
            attractions = json.loads(content)

        # 富化数据：添加省份、城市、坐标等信息
        for attr in attractions:
            attr["province"] = province
            attr["city"] = city
            attr["source"] = "ai_generated"
            attr["is_active"] = 1

            # 确保字段类型正确
            attr["must_visit"] = 1 if attr.get("must_visit", False) else 0
            attr["hot"] = 1 if attr.get("hot", False) else 0
            attr["recommended_duration"] = int(attr.get("recommended_duration", 2))
            attr["priority"] = int(attr.get("priority", 5))

            # 确保aliases和tags是数组
            if not isinstance(attr.get("aliases"), list):
                attr["aliases"] = []
            if not isinstance(attr.get("tags"), list):
                attr["tags"] = []

        return attractions

    except Exception as e:
        print(f"  ❌ 生成{city}景点数据失败: {e}")
        import traceback
        traceback.print_exc()
        return []


async def geocode_attractions(attractions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    为景点数据添加地理坐标

    Args:
        attractions: 景点数据列表

    Returns:
        添加了坐标的景点数据列表
    """
    for attr in attractions:
        name = attr.get("name", "")
        city = attr.get("city", "")

        if name and city:
            try:
                # 使用地理编码获取坐标
                geo_result = await geocode(f"{city}{name}")
                if geo_result:
                    attr["lng"] = float(geo_result.get("lng", 0))
                    attr["lat"] = float(geo_result.get("lat", 0))
                    print(f"    ✅ {name}: 坐标获取成功 ({attr['lng']}, {attr['lat']})")
                else:
                    print(f"    ⚠️  {name}: 坐标获取失败，使用城市中心坐标")
                    # 使用城市中心坐标
                    city_geo = await geocode(city)
                    if city_geo:
                        attr["lng"] = float(city_geo.get("lng", 0))
                        attr["lat"] = float(city_geo.get("lat", 0))
            except Exception as e:
                print(f"    ❌ {name}: 坐标获取异常: {e}")

        # 如果还是没有坐标，设置默认值
        if "lng" not in attr or "lat" not in attr:
            attr["lng"] = 0.0
            attr["lat"] = 0.0

    return attractions


def save_to_database(attractions: List[Dict[str, Any]]) -> int:
    """
    将景点数据保存到数据库

    Args:
        attractions: 景点数据列表

    Returns:
        成功保存的数量
    """
    import pymysql
    from app.config import settings

    conn = pymysql.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
        charset='utf8mb4'
    )
    cursor = conn.cursor()

    saved_count = 0
    for attr in attractions:
        try:
            # 检查是否已存在（按名称和城市）
            cursor.execute(
                "SELECT id FROM major_attractions WHERE name = %s AND city = %s",
                (attr["name"], attr["city"])
            )
            existing = cursor.fetchone()

            if existing:
                print(f"  ⚠️  {attr['name']} ({attr['city']}) 已存在，跳过")
                continue

            # 插入新记录
            sql = """
            INSERT INTO major_attractions
            (name, aliases, city, district, province, level, category, description,
             recommended_duration, lng, lat, must_visit, hot, tags, best_time,
             source, priority, is_active, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            """
            cursor.execute(sql, (
                attr["name"],
                json.dumps(attr.get("aliases", []), ensure_ascii=False),
                attr["city"],
                attr.get("district", ""),
                attr["province"],
                attr.get("level", ""),
                attr.get("category", ""),
                attr.get("description", ""),
                attr.get("recommended_duration", 2),
                attr.get("lng", 0.0),
                attr.get("lat", 0.0),
                attr.get("must_visit", 0),
                attr.get("hot", 0),
                json.dumps(attr.get("tags", []), ensure_ascii=False),
                attr.get("best_time", ""),
                attr.get("source", "ai_generated"),
                attr.get("priority", 5),
                attr.get("is_active", 1),
            ))
            saved_count += 1
            print(f"  ✅ {attr['name']} ({attr['city']}) 保存成功")

        except Exception as e:
            print(f"  ❌ {attr['name']} ({attr['city']}) 保存失败: {e}")
            conn.rollback()

    conn.commit()
    conn.close()

    return saved_count


async def main():
    """主函数：批量生成主要景点数据"""
    print("=" * 60)
    print("批量生成主要景点数据")
    print("=" * 60)

    total_generated = 0
    total_saved = 0

    for i, city_info in enumerate(PRIORITY_CITIES, 1):
        city = city_info["city"]
        print(f"\n[{i}/{len(PRIORITY_CITIES)}] 正在生成 {city} 的景点数据...")

        # 生成景点数据
        attractions = await generate_attractions_for_city(city_info)
        print(f"  📝 生成了 {len(attractions)} 个景点")

        if not attractions:
            continue

        total_generated += len(attractions)

        # 获取地理坐标
        print(f"  📍 正在获取地理坐标...")
        attractions = await geocode_attractions(attractions)

        # 保存到数据库
        print(f"  💾 正在保存到数据库...")
        saved = save_to_database(attractions)
        total_saved += saved
        print(f"  ✅ 成功保存 {saved} 个景点")

    print("\n" + "=" * 60)
    print(f"批量生成完成！")
    print(f"  生成景点总数: {total_generated}")
    print(f"  成功保存数: {total_saved}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
