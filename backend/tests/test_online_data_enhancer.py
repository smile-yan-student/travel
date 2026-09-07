"""
在线数据增强器集成测试

测试内容：
1. 在线数据加载（从数据库获取预约规则和避坑提示）
2. POI列表增强（合并在线数据中的景点）
3. 行程顺序增强（参考在线数据的游览顺序）
4. 耗时估算增强（参考在线数据的平均耗时）
5. 增强输出（预约提醒、避坑提示）
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def test_enhancer_load():
    """测试在线数据加载"""
    print("\n" + "="*60)
    print("测试1：在线数据加载")
    print("="*60)

    from app.services.online_data import get_online_data_enhancer

    enhancer = get_online_data_enhancer()

    # 测试加载北京的在线数据
    context = await enhancer.load_online_data(
        destination="北京",
        days=3,
        enable_search=False,
    )

    print(f"目的地: {context.destination}")
    print(f"天数: {context.days}")
    print(f"是否加载: {context.is_loaded}")
    print(f"加载耗时: {context.load_time:.2f}s")
    print(f"置信度: {context.confidence:.2f}")
    print(f"预约规则数: {len(context.attraction_rules)}")
    print(f"避坑提示数: {len(context.travel_tips)}")
    print(f"提取景点数: {len(context.extracted_attractions)}")
    print(f"提取行程数: {len(context.extracted_itineraries)}")
    print(f"提取提示数: {len(context.extracted_tips)}")

    # 打印预约规则
    if context.attraction_rules:
        print("\n预约规则示例:")
        for name, rule in list(context.attraction_rules.items())[:3]:
            print(f"  - {name}: {rule.get('reservation_channel', 'N/A')}")

    # 打印避坑提示
    if context.travel_tips:
        print("\n避坑提示示例:")
        for tip in context.travel_tips[:3]:
            print(f"  [{tip.get('category', 'general')}] {tip.get('tip', '')[:50]}...")

    return context


async def test_poi_enhancement(context):
    """测试POI列表增强"""
    print("\n" + "="*60)
    print("测试2：POI列表增强")
    print("="*60)

    from app.services.online_data import get_online_data_enhancer

    enhancer = get_online_data_enhancer()

    # 模拟原始POI列表
    original_pois = [
        {"name": "天安门广场", "category": "景点", "lng": 116.397, "lat": 39.908},
        {"name": "故宫博物院", "category": "景点", "lng": 116.397, "lat": 39.916},
        {"name": "天坛公园", "category": "景点", "lng": 116.406, "lat": 39.882},
    ]

    print(f"原始POI数量: {len(original_pois)}")
    print("原始POI:")
    for poi in original_pois:
        print(f"  - {poi['name']}")

    # 增强POI列表
    enhanced_pois = enhancer.enhance_poi_list(original_pois, context)

    print(f"\n增强后POI数量: {len(enhanced_pois)}")
    print("增强后POI:")
    for poi in enhanced_pois:
        source = poi.get("source", "original")
        is_must = poi.get("is_must_visit", False)
        marker = "★" if is_must else " "
        print(f"  {marker} {poi['name']} (来源: {source})")

    added_count = len(enhanced_pois) - len(original_pois)
    print(f"\n新增POI数量: {added_count}")

    return enhanced_pois


async def test_duration_enhancement(context):
    """测试耗时估算增强"""
    print("\n" + "="*60)
    print("测试3：耗时估算增强")
    print("="*60)

    from app.services.online_data import get_online_data_enhancer

    enhancer = get_online_data_enhancer()

    # 测试景点耗时
    test_attractions = ["天坛公园", "天安门广场", "故宫博物院", "不存在的景点"]

    print("景点耗时估算（在线数据60% + 默认值40%）:")
    for attraction in test_attractions:
        default_duration = 120  # 默认2小时
        enhanced_duration = enhancer.enhance_duration_estimation(
            attraction, default_duration, context
        )
        changed = "✓" if enhanced_duration != default_duration else " "
        print(f"  {changed} {attraction}: 默认={default_duration}分钟, 增强后={enhanced_duration}分钟")

    return True


async def test_enhanced_output(context):
    """测试增强输出"""
    print("\n" + "="*60)
    print("测试4：增强输出（预约提醒、避坑提示）")
    print("="*60)

    from app.services.online_data import get_online_data_enhancer

    enhancer = get_online_data_enhancer()

    # 获取增强输出
    output = enhancer.get_enhanced_output(context)

    print(f"预约提醒数: {len(output.get('reservation_alerts', []))}")
    print(f"避坑提示数: {len(output.get('travel_tips', []))}")
    print(f"提取提示数: {len(output.get('extracted_tips', []))}")
    print(f"在线数据元信息: {output.get('online_data_meta', {})}")

    # 打印预约提醒
    if output.get("reservation_alerts"):
        print("\n预约提醒示例:")
        for alert in output["reservation_alerts"][:2]:
            print(f"  - {alert.get('attraction', '')}:")
            print(f"    预约渠道: {alert.get('channel', 'N/A')}")
            print(f"    放票时间: {alert.get('ticket_release_time', 'N/A')}")
            print(f"    开放时间: {alert.get('opening_hours', 'N/A')}")
            print(f"    闭馆日: {alert.get('closing_days', 'N/A')}")
            print(f"    票价: {alert.get('ticket_price', 'N/A')}")

    # 打印避坑提示
    if output.get("travel_tips"):
        print("\n避坑提示示例:")
        for tip in output["travel_tips"][:3]:
            print(f"  [{tip.get('category', 'general')}/{tip.get('severity', 'info')}] {tip.get('tip', '')[:60]}...")

    return output


async def test_model_fields():
    """测试PlanResponse模型新增字段"""
    print("\n" + "="*60)
    print("测试5：PlanResponse模型新增字段")
    print("="*60)

    from app.data.models.models import PlanResponse

    # 创建一个带有新增字段的PlanResponse
    response = PlanResponse(
        request_id="test_001",
        destination="北京",
        city_center={"lng": 116.407, "lat": 39.904},
        days=3,
        group_type="情侣",
        budget_level="适中",
        style="综合",
        pace="适中",
        reservation_alerts=[
            {
                "attraction": "故宫博物院",
                "channel": "故宫博物院官方公众号",
                "ticket_release_time": "提前7天20:00放票",
                "opening_hours": "08:30-17:00",
                "closing_days": "每周一闭馆",
                "ticket_price": "旺季60元，淡季40元",
            }
        ],
        travel_tips=[
            {
                "tip": "不要参加路边的长城一日游，多为黑导游",
                "category": "anti_fraud",
                "severity": "danger",
            }
        ],
        online_data_meta={
            "is_loaded": True,
            "confidence": 0.75,
            "attraction_rules_count": 1,
            "travel_tips_count": 1,
        },
    )

    print("✓ PlanResponse创建成功")
    print(f"  预约提醒数: {len(response.reservation_alerts)}")
    print(f"  避坑提示数: {len(response.travel_tips)}")
    print(f"  在线数据元信息: {response.online_data_meta}")

    # 测试序列化为字典
    response_dict = response.model_dump()
    print(f"\n✓ 序列化为字典成功")
    print(f"  reservation_alerts存在: {'reservation_alerts' in response_dict}")
    print(f"  travel_tips存在: {'travel_tips' in response_dict}")
    print(f"  online_data_meta存在: {'online_data_meta' in response_dict}")

    return True


async def main():
    """主测试函数"""
    print("="*60)
    print("在线数据增强器 - 集成测试")
    print("="*60)

    results = {}

    # 测试1：在线数据加载
    try:
        context = await test_enhancer_load()
        results["load"] = True
    except Exception as e:
        print(f"在线数据加载测试异常: {e}")
        import traceback
        traceback.print_exc()
        results["load"] = False
        context = None

    # 测试2：POI列表增强
    try:
        if context:
            await test_poi_enhancement(context)
        results["poi_enhancement"] = True
    except Exception as e:
        print(f"POI列表增强测试异常: {e}")
        import traceback
        traceback.print_exc()
        results["poi_enhancement"] = False

    # 测试3：耗时估算增强
    try:
        if context:
            await test_duration_enhancement(context)
        results["duration_enhancement"] = True
    except Exception as e:
        print(f"耗时估算增强测试异常: {e}")
        import traceback
        traceback.print_exc()
        results["duration_enhancement"] = False

    # 测试4：增强输出
    try:
        if context:
            await test_enhanced_output(context)
        results["enhanced_output"] = True
    except Exception as e:
        print(f"增强输出测试异常: {e}")
        import traceback
        traceback.print_exc()
        results["enhanced_output"] = False

    # 测试5：模型字段
    try:
        await test_model_fields()
        results["model_fields"] = True
    except Exception as e:
        print(f"模型字段测试异常: {e}")
        import traceback
        traceback.print_exc()
        results["model_fields"] = False

    # 汇总
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    for name, result in results.items():
        status = "✓ 通过" if result else "✗ 失败"
        print(f"  {name}: {status}")

    all_passed = all(results.values())
    print(f"\n总体: {'全部通过 ✓' if all_passed else '存在失败 ✗'}")

    return all_passed


if __name__ == "__main__":
    asyncio.run(main())
