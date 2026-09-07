#!/usr/bin/env python3
"""补充本地行政区域库中缺少的知名同名地点。

使用 geo_local.save_entry 添加，自动处理同名地点（存储为 list）。
坐标为近似值（后续全量更新可覆盖）。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import geo_local

# 补充的知名同名地点（近似坐标）
SUPPLEMENT = [
    # 北京朝阳区（同名：长春朝阳区、辽宁朝阳市）
    {"name": "朝阳区", "adcode": "110105", "level": "district", "lng": 116.443, "lat": 39.921, "parent": "北京市"},
    # 南京鼓楼区（同名：福州鼓楼区、开封鼓楼区）
    {"name": "鼓楼区", "adcode": "320106", "level": "district", "lng": 118.778, "lat": 32.062, "parent": "南京市"},
    # 福州鼓楼区
    {"name": "鼓楼区", "adcode": "350102", "level": "district", "lng": 119.300, "lat": 26.075, "parent": "福州市"},
    # 杭州西湖区（同名：南昌西湖区）
    {"name": "西湖区", "adcode": "330106", "level": "district", "lng": 120.129, "lat": 30.259, "parent": "杭州市"},
    # 北京海淀区
    {"name": "海淀区", "adcode": "110108", "level": "district", "lng": 116.298, "lat": 39.959, "parent": "北京市"},
    # 上海浦东新区
    {"name": "浦东新区", "adcode": "310115", "level": "district", "lng": 121.544, "lat": 31.222, "parent": "上海市"},
    # 广州天河区
    {"name": "天河区", "adcode": "440106", "level": "district", "lng": 113.361, "lat": 23.124, "parent": "广州市"},
    # 深圳南山区
    {"name": "南山区", "adcode": "440305", "level": "district", "lng": 113.930, "lat": 22.533, "parent": "深圳市"},
    # 成都武侯区
    {"name": "武侯区", "adcode": "510107", "level": "district", "lng": 104.043, "lat": 30.642, "parent": "成都市"},
    # 西安雁塔区
    {"name": "雁塔区", "adcode": "610113", "level": "district", "lng": 108.948, "lat": 34.222, "parent": "西安市"},
    # 武汉武昌区
    {"name": "武昌区", "adcode": "420106", "level": "district", "lng": 114.305, "lat": 30.554, "parent": "武汉市"},
    # 南京玄武区
    {"name": "玄武区", "adcode": "320102", "level": "district", "lng": 118.797, "lat": 32.048, "parent": "南京市"},
    # 杭州余杭区
    {"name": "余杭区", "adcode": "330110", "level": "district", "lng": 120.299, "lat": 30.418, "parent": "杭州市"},
    # 苏州姑苏区
    {"name": "姑苏区", "adcode": "320508", "level": "district", "lng": 120.619, "lat": 31.318, "parent": "苏州市"},
    # 厦门思明区
    {"name": "思明区", "adcode": "350203", "level": "district", "lng": 118.089, "lat": 24.448, "parent": "厦门市"},
    # 长沙岳麓区
    {"name": "岳麓区", "adcode": "430104", "level": "district", "lng": 112.938, "lat": 28.235, "parent": "长沙市"},
    # 重庆渝中区
    {"name": "渝中区", "adcode": "500103", "level": "district", "lng": 106.583, "lat": 29.552, "parent": "重庆市"},
    # 天津和平区（同名：沈阳和平区）
    {"name": "和平区", "adcode": "120101", "level": "district", "lng": 117.214, "lat": 39.117, "parent": "天津市"},
    # 沈阳和平区
    {"name": "和平区", "adcode": "210102", "level": "district", "lng": 123.411, "lat": 41.799, "parent": "沈阳市"},
    # 青岛市南区
    {"name": "市南区", "adcode": "370202", "level": "district", "lng": 120.383, "lat": 36.067, "parent": "青岛市"},
    # 大连中山区
    {"name": "中山区", "adcode": "210202", "level": "district", "lng": 121.645, "lat": 38.918, "parent": "大连市"},
    # 宁波鄞州区
    {"name": "鄞州区", "adcode": "330212", "level": "district", "lng": 121.546, "lat": 29.818, "parent": "宁波市"},
    # 无锡梁溪区
    {"name": "梁溪区", "adcode": "320213", "level": "district", "lng": 120.312, "lat": 31.573, "parent": "无锡市"},
    # 北京丰台区
    {"name": "丰台区", "adcode": "110106", "level": "district", "lng": 116.287, "lat": 39.858, "parent": "北京市"},
    # 北京石景山区
    {"name": "石景山区", "adcode": "110107", "level": "district", "lng": 116.222, "lat": 39.906, "parent": "北京市"},
    # 北京通州区
    {"name": "通州区", "adcode": "110112", "level": "district", "lng": 116.658, "lat": 39.902, "parent": "北京市"},
    # 上海黄浦区
    {"name": "黄浦区", "adcode": "310101", "level": "district", "lng": 121.490, "lat": 31.222, "parent": "上海市"},
    # 上海静安区
    {"name": "静安区", "adcode": "310106", "level": "district", "lng": 121.448, "lat": 31.229, "parent": "上海市"},
    # 广州越秀区
    {"name": "越秀区", "adcode": "440104", "level": "district", "lng": 113.267, "lat": 23.129, "parent": "广州市"},
    # 深圳福田区
    {"name": "福田区", "adcode": "440304", "level": "district", "lng": 114.055, "lat": 22.521, "parent": "深圳市"},
    # 成都锦江区
    {"name": "锦江区", "adcode": "510104", "level": "district", "lng": 104.083, "lat": 30.657, "parent": "成都市"},
    # 西安碑林区
    {"name": "碑林区", "adcode": "610103", "level": "district", "lng": 108.947, "lat": 34.234, "parent": "西安市"},
    # 武汉江汉区
    {"name": "江汉区", "adcode": "420103", "level": "district", "lng": 114.270, "lat": 30.601, "parent": "武汉市"},
    # 南京秦淮区
    {"name": "秦淮区", "adcode": "320104", "level": "district", "lng": 118.797, "lat": 32.018, "parent": "南京市"},
    # 杭州上城区
    {"name": "上城区", "adcode": "330102", "level": "district", "lng": 120.169, "lat": 30.242, "parent": "杭州市"},
    # 苏州工业园区（功能区，近似）
    {"name": "工业园区", "adcode": "320571", "level": "district", "lng": 120.754, "lat": 31.326, "parent": "苏州市"},
]


def main():
    added = 0
    for entry in SUPPLEMENT:
        if geo_local.save_entry(entry):
            added += 1
    print(f"补充了 {added} 条知名同名地点")
    print(f"统计: {geo_local.stats()}")

    # 验证同名消歧
    print()
    print("=== 验证同名消歧 ===")
    for name in ['朝阳', '鼓楼', '西湖', '和平']:
        all_results = geo_local.lookup_all(name)
        is_amb = geo_local.is_ambiguous(name)
        print(f"  「{name}」: ambiguous={is_amb}, 候选数={len(all_results)}")
        for r in all_results:
            print(f"    {r['name']} (level={r.get('level')}, parent={r.get('parent')})")

    print()
    print("=== 上下文消歧 ===")
    for name, ctx in [('朝阳', '北京'), ('朝阳', '吉林'), ('鼓楼', '南京'), ('鼓楼', '福州')]:
        entry, cands, resolved = geo_local.lookup_with_context(name, context_province=ctx)
        if entry:
            print(f"  {name}(ctx={ctx}): resolved={resolved}, 选中={entry['name']}(parent={entry.get('parent')})")
        else:
            print(f"  {name}(ctx={ctx}): resolved={resolved}, 候选数={len(cands)}")


if __name__ == "__main__":
    main()
