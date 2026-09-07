#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
补充大型景区等级字段。

基于常见景区等级知识，为 poi_hierarchy 表中标记为大型景区但缺少等级字段的记录补充等级。

等级说明：
- 5A：国家5A级旅游景区（最高等级）
- 4A：国家4A级旅游景区
- 世界遗产：世界文化/自然遗产
- 无等级：未评定等级的知名景区
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.data.database import get_conn
from app.data.dict_store import invalidate_all_cache


# 已知景区等级映射（基于公开资料）
SCENIC_LEVELS = {
    # 北京
    "故宫博物院": "5A/世界遗产",
    "天安门广场": "无等级",
    "八达岭长城": "5A/世界遗产",
    "慕田峪长城": "5A",
    "颐和园": "5A/世界遗产",
    "天坛公园": "5A/世界遗产",
    "圆明园": "5A",
    "南锣鼓巷": "无等级",
    "什刹海": "4A",
    "798艺术区": "4A",
    "十三陵": "5A/世界遗产",
    "香山": "4A",
    # 上海
    "外滩": "无等级",
    "东方明珠": "5A",
    "豫园": "4A",
    "田子坊": "无等级",
    "武康路": "无等级",
    "迪士尼": "无等级",
    # 西安
    "兵马俑": "5A/世界遗产",
    "秦始皇兵马俑": "5A/世界遗产",
    "华清宫": "5A",
    "大雁塔": "5A",
    "西安城墙": "5A",
    "钟楼": "无等级",
    "大唐不夜城": "5A",
    "大唐芙蓉园": "5A",
    # 杭州
    "西湖": "5A/世界遗产",
    "灵隐寺": "4A",
    "雷峰塔": "4A",
    "西溪湿地": "5A",
    "乌镇": "5A",
    "千岛湖": "5A",
    # 济南
    "大明湖": "5A",
    "趵突泉": "5A",
    "千佛山": "4A",
    "黑虎泉": "无等级",
    "泉城广场": "无等级",
    # 成都
    "锦里": "4A",
    "武侯祠": "4A",
    "杜甫草堂": "4A",
    "大熊猫基地": "4A",
    "宽窄巷子": "无等级",
    "都江堰": "5A/世界遗产",
    "青城山": "5A/世界遗产",
    # 南京
    "秦淮河": "5A",
    "夫子庙": "5A",
    "明孝陵": "5A/世界遗产",
    "中山陵": "5A",
    # 苏州
    "留园": "5A/世界遗产",
    "虎丘": "5A",
    "拙政园": "5A/世界遗产",
    # 其他知名景区
    "泰山": "5A/世界遗产",
    "黄山": "5A/世界遗产",
    "九寨沟": "5A/世界遗产",
    "张家界": "5A/世界遗产",
    "峨眉山": "5A/世界遗产",
    "乐山大佛": "5A/世界遗产",
    "布达拉宫": "5A/世界遗产",
    "鼓浪屿": "5A/世界遗产",
    "洱海": "无等级",
    "玉龙雪山": "5A",
    "泸沽湖": "4A",
    "洪崖洞": "4A",
    "漓江": "5A",
    "阳朔": "无等级",
    "天涯海角": "4A",
    "亚龙湾": "无等级",
    "蜈支洲": "5A",
    "莫高窟": "5A/世界遗产",
    "敦煌": "无等级",
    "鸣沙山": "5A",
    "五台山": "5A/世界遗产",
    "普陀山": "5A",
    "平遥": "5A/世界遗产",
    "凤凰古城": "4A",
    "丽江古城": "5A/世界遗产",
    "大理古城": "4A",
    "少林寺": "5A",
    "黄鹤楼": "5A",
    "岳阳楼": "5A",
    "橘子洲": "5A",
    "岳麓山": "5A",
    "三星堆": "4A",
    "三坊七巷": "5A",
    "哈尔滨冰雪大世界": "4A",
    "长白山": "5A",
    "天池": "5A",
    "雪乡": "4A",
    "呼伦贝尔": "无等级",
    "喀纳斯": "5A",
    "那拉提": "5A",
}


def main():
    print("=" * 60)
    print("补充大型景区等级字段")
    print("=" * 60)

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # 查询需要补充等级的大型景区
            cur.execute("""
                SELECT id, name FROM poi_hierarchy
                WHERE is_large_scenic = 1 AND (level IS NULL OR level = '')
            """)
            rows = cur.fetchall()
            print(f"\n需要补充等级的大型景区: {len(rows)} 个")

            updated = 0
            not_found = []

            for row in rows:
                poi_id = row.get('id')
                name = row.get('name', '')

                # 精确匹配
                level = SCENIC_LEVELS.get(name)

                # 模糊匹配（去除后缀）
                if not level:
                    for key, val in SCENIC_LEVELS.items():
                        if key in name or name in key:
                            level = val
                            break

                if level:
                    cur.execute("UPDATE poi_hierarchy SET level = %s WHERE id = %s", (level, poi_id))
                    updated += 1
                    print(f"  ✅ {name}: {level}")
                else:
                    not_found.append(name)
                    print(f"  ⚠️  {name}: 未找到等级信息")

            conn.commit()
            print(f"\n更新完成: 成功 {updated} 个, 未找到 {len(not_found)} 个")

            if not_found:
                print(f"\n未找到等级的景区: {not_found}")

        # 清除缓存
        invalidate_all_cache()
        print("\n缓存已清除")

    except Exception as e:
        conn.rollback()
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

    print("\n" + "=" * 60)
    print("完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
