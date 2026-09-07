"""
在线数据服务模块测试脚本

测试内容：
1. 搜索缓存的读写
2. 景点预约规则的CRUD
3. 旅游避坑提示的CRUD
4. 数据提纯的基础功能
"""
import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def test_search_cache():
    """测试搜索缓存"""
    print("\n" + "="*60)
    print("测试1：搜索缓存")
    print("="*60)

    from app.services.online_data import get_search_cache

    cache = get_search_cache()

    # 测试写入
    test_keyword = "北京3天攻略"
    test_results = [
        {
            "title": "北京3天旅游攻略",
            "url": "https://example.com/beijing",
            "content": "故宫、天安门、长城、颐和园",
            "source": "example.com",
            "relevance_score": 0.9,
        }
    ]

    result = await cache.set(test_keyword, test_results, category="guide")
    print(f"写入缓存: {'成功' if result else '失败'}")

    # 测试读取
    cached = await cache.get(test_keyword, category="guide")
    if cached:
        print(f"读取缓存: 成功，共 {len(cached)} 条结果")
        print(f"第一条结果标题: {cached[0]['title']}")
    else:
        print("读取缓存: 失败（未命中）")

    # 测试统计
    stats = await cache.get_stats()
    print(f"缓存统计: {stats}")

    # 清理测试数据
    await cache.delete(test_keyword, category="guide")
    print("清理测试数据: 完成")

    return True


async def test_attraction_rules():
    """测试景点预约规则"""
    print("\n" + "="*60)
    print("测试2：景点预约规则")
    print("="*60)

    from app.services.online_data import get_attraction_rules, AttractionRule

    rules = get_attraction_rules()

    # 测试创建
    test_rule = AttractionRule(
        attraction_name="故宫博物院",
        destination="北京",
        reservation_channel="故宫博物院官方公众号",
        reservation_url="https://www.dpm.org.cn",
        ticket_release_time="提前7天20:00放票",
        opening_hours="08:30-17:00（16:00停止入场）",
        closing_days="每周一闭馆（法定节假日除外）",
        ticket_price="旺季60元，淡季40元，学生半价",
        visitor_route="午门进，神武门出",
        daily_limit="每日最大接待8万人",
        tips="建议提前预约，旺季一票难求",
        source="manual",
    )

    rule_id = await rules.create(test_rule)
    print(f"创建预约规则: {'成功，ID=' + str(rule_id) if rule_id else '失败'}")

    # 测试查询
    if rule_id:
        # 按名称查询
        rule = await rules.get_by_name("故宫博物院")
        if rule:
            print(f"按名称查询: 成功")
            print(f"  景点名称: {rule.attraction_name}")
            print(f"  预约渠道: {rule.reservation_channel}")
            print(f"  放票时间: {rule.ticket_release_time}")
            print(f"  开放时间: {rule.opening_hours}")
            print(f"  闭馆日: {rule.closing_days}")
            print(f"  票价: {rule.ticket_price}")
            print(f"  游览路线: {rule.visitor_route}")
        else:
            print("按名称查询: 失败")

        # 按目的地查询
        dest_rules = await rules.get_by_destination("北京")
        print(f"按目的地查询: 成功，共 {len(dest_rules)} 条规则")

        # 测试更新
        rule.tips = "建议提前7天预约，旺季（4-10月）一票难求"
        update_result = await rules.update(rule)
        print(f"更新预约规则: {'成功' if update_result else '失败'}")

        # 测试删除
        delete_result = await rules.delete(rule_id)
        print(f"删除预约规则: {'成功' if delete_result else '失败'}")

    # 测试统计
    stats = await rules.get_stats()
    print(f"预约规则统计: {stats}")

    return True


async def test_travel_tips():
    """测试旅游避坑提示"""
    print("\n" + "="*60)
    print("测试3：旅游避坑提示")
    print("="*60)

    from app.services.online_data import get_travel_tips, TravelTip

    tips = get_travel_tips()

    # 测试创建
    test_tips = [
        TravelTip(
            destination="北京",
            tip="故宫提前7天20:00在官方公众号预约，周一闭馆",
            category="reservation",
            severity="warning",
            source="manual",
            sort_order=10,
        ),
        TravelTip(
            destination="北京",
            tip="不要参加路边的'长城一日游'，多为黑导游强制消费",
            category="anti_fraud",
            severity="danger",
            source="manual",
            sort_order=9,
        ),
        TravelTip(
            destination="北京",
            tip="北京地铁发达，景点间优先选择地铁出行",
            category="traffic",
            severity="info",
            source="manual",
            sort_order=5,
        ),
    ]

    created_ids = []
    for tip in test_tips:
        tip_id = await tips.create(tip)
        if tip_id:
            created_ids.append(tip_id)
            print(f"创建避坑提示: 成功，ID={tip_id} - {tip.tip[:30]}...")
        else:
            print(f"创建避坑提示: 失败 - {tip.tip[:30]}...")

    # 测试查询
    if created_ids:
        # 按目的地查询
        dest_tips = await tips.get_by_destination("北京", limit=10)
        print(f"\n按目的地查询: 成功，共 {len(dest_tips)} 条提示")
        for tip in dest_tips[:3]:
            print(f"  [{tip.category}/{tip.severity}] {tip.tip[:50]}...")

        # 按类别查询
        anti_fraud_tips = await tips.get_by_destination("北京", category="anti_fraud")
        print(f"\n按类别查询（防骗）: 成功，共 {len(anti_fraud_tips)} 条提示")

        # 测试更新
        if dest_tips:
            tip_to_update = dest_tips[0]
            tip_to_update.tip = tip_to_update.tip + "（已更新）"
            update_result = await tips.update(tip_to_update)
            print(f"\n更新避坑提示: {'成功' if update_result else '失败'}")

        # 测试删除
        for tip_id in created_ids:
            delete_result = await tips.delete(tip_id)
            print(f"删除避坑提示 ID={tip_id}: {'成功' if delete_result else '失败'}")

    # 测试统计
    stats = await tips.get_stats()
    print(f"\n避坑提示统计: {stats}")

    return True


async def test_data_extractor():
    """测试数据提纯"""
    print("\n" + "="*60)
    print("测试4：数据提纯（基础功能）")
    print("="*60)

    from app.services.online_data import get_data_extractor

    extractor = get_data_extractor()

    # 模拟搜索结果
    mock_search_results = [
        {
            "title": "北京3天旅游攻略",
            "url": "https://example.com/beijing-guide",
            "content": """
第一天：天安门广场 → 故宫博物院 → 景山公园 → 什刹海
故宫博物院需要提前7天预约，开放时间08:30-17:00，周一闭馆，门票60元。
游览故宫大约需要3-4小时，建议午门进神武门出。

第二天：慕田峪长城
长城距离市区较远，建议单独安排一天，游览时间约4-5小时。
不要参加路边的长城一日游，多为黑导游。

第三天：颐和园 → 天坛公园 → 前门大街
颐和园游览时间约2-3小时，天坛约1-2小时。
北京地铁发达，景点间优先选择地铁出行。
            """,
            "source": "example.com",
            "relevance_score": 0.9,
        },
        {
            "title": "北京必去景点推荐",
            "url": "https://example.com/beijing-attractions",
            "content": """
北京必去景点：
1. 故宫博物院 - 必去，提前预约
2. 天安门广场 - 免费，看升旗需要早起
3. 长城 - 推荐慕田峪，人少体验好
4. 颐和园 - 皇家园林，风景优美
5. 天坛公园 - 古代祭天场所
6. 什刹海 - 老北京风情
7. 南锣鼓巷 - 商业化较严重，可快速通过

避坑提示：
- 故宫提前7天20:00放票
- 不要参加黑导游的长城一日游
- 南锣鼓巷商业化严重
- 北京地铁方便，建议办交通卡
            """,
            "source": "example.com",
            "relevance_score": 0.85,
        },
    ]

    # 执行提纯
    extracted = await extractor.extract("北京", mock_search_results)

    print(f"提纯完成:")
    print(f"  目的地: {extracted.destination}")
    print(f"  攻略数量: {extracted.total_guides}")
    print(f"  置信度: {extracted.confidence:.2f}")
    print(f"  提取景点数: {len(extracted.attractions)}")
    print(f"  每日行程数: {len(extracted.daily_itineraries)}")
    print(f"  避坑提示数: {len(extracted.tips)}")

    # 打印景点信息
    print("\n提取的景点（按频率排序）:")
    sorted_attractions = sorted(
        extracted.attractions.values(),
        key=lambda x: x.frequency,
        reverse=True,
    )
    for attr in sorted_attractions[:10]:
        must_visit = "★必去" if attr.is_must_visit else ("☆可选" if attr.is_optional else "")
        duration = f"{attr.avg_duration}分钟" if attr.avg_duration > 0 else "未知"
        print(f"  {attr.name}: 频率={attr.frequency}, 时长={duration}, {must_visit}")

    # 打印每日行程
    if extracted.daily_itineraries:
        print("\n每日行程:")
        for itinerary in extracted.daily_itineraries:
            print(f"  第{itinerary.day}天: {' → '.join(itinerary.attractions)}")

    # 打印避坑提示
    if extracted.tips:
        print("\n避坑提示:")
        for tip in extracted.tips[:5]:
            print(f"  [{tip.category}] {tip.tip[:60]}...")

    return True


async def main():
    """主测试函数"""
    print("="*60)
    print("在线数据服务模块 - 功能测试")
    print("="*60)

    results = {}

    # 测试1：搜索缓存
    try:
        results["search_cache"] = await test_search_cache()
    except Exception as e:
        print(f"搜索缓存测试异常: {e}")
        import traceback
        traceback.print_exc()
        results["search_cache"] = False

    # 测试2：景点预约规则
    try:
        results["attraction_rules"] = await test_attraction_rules()
    except Exception as e:
        print(f"预约规则测试异常: {e}")
        import traceback
        traceback.print_exc()
        results["attraction_rules"] = False

    # 测试3：旅游避坑提示
    try:
        results["travel_tips"] = await test_travel_tips()
    except Exception as e:
        print(f"避坑提示测试异常: {e}")
        import traceback
        traceback.print_exc()
        results["travel_tips"] = False

    # 测试4：数据提纯
    try:
        results["data_extractor"] = await test_data_extractor()
    except Exception as e:
        print(f"数据提纯测试异常: {e}")
        import traceback
        traceback.print_exc()
        results["data_extractor"] = False

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
