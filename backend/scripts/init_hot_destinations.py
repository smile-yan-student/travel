"""
热门目的地数据预置脚本

预置热门城市的预约规则和避坑提示，可一键导入数据库。

使用方式：
    cd backend
    ./.venv/bin/python scripts/init_hot_destinations.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.online_data import (
    get_attraction_rules,
    get_travel_tips,
    AttractionRule,
    TravelTip,
)


# ========== 预约规则预置数据 ==========

RESERVATION_RULES = [
    {
        "attraction_name": "故宫博物院",
        "destination": "北京",
        "reservation_channel": "故宫博物院官方公众号",
        "ticket_release_time": "提前7天20:00放票",
        "opening_hours": "08:30-17:00（16:00停止入场）",
        "closing_days": "每周一闭馆（法定节假日除外）",
        "ticket_price": "旺季60元，淡季40元，学生半价",
        "visitor_route": "午门进，神武门出",
        "daily_limit": "每日限流8万人",
        "tips": "建议提前预约，旺季一票难求；带好身份证，入口需核验",
        "reservation_url": "https://www.dpm.org.cn/",
        "source": "preset",
    },
    {
        "attraction_name": "天安门广场",
        "destination": "北京",
        "reservation_channel": "天安门广场预约参观小程序",
        "ticket_release_time": "提前1-9天预约",
        "opening_hours": "05:00-22:00（升旗时间为准）",
        "closing_days": "无固定闭馆日",
        "ticket_price": "免费",
        "visitor_route": "从东侧或西侧安检入口进入",
        "daily_limit": "按区域限流",
        "tips": "看升旗需提前1-2小时到达；带好身份证，安检严格",
        "reservation_url": "",
        "source": "preset",
    },
    {
        "attraction_name": "八达岭长城",
        "destination": "北京",
        "reservation_channel": "八达岭长城官方公众号",
        "ticket_release_time": "提前7天预约",
        "opening_hours": "07:30-17:30（旺季）",
        "closing_days": "无固定闭馆日",
        "ticket_price": "旺季40元，淡季35元",
        "visitor_route": "建议北门上，北门下（人少）",
        "daily_limit": "每日限流6.5万人",
        "tips": "不要参加路边的长城一日游，多为黑导游；穿舒适的运动鞋",
        "reservation_url": "",
        "source": "preset",
    },
    {
        "attraction_name": "颐和园",
        "destination": "北京",
        "reservation_channel": "颐和园官方公众号",
        "ticket_release_time": "可现场购票，建议提前预约",
        "opening_hours": "06:30-18:00（旺季）",
        "closing_days": "无固定闭馆日",
        "ticket_price": "旺季30元，淡季20元（联票60元）",
        "visitor_route": "东宫门进，北宫门出",
        "daily_limit": "",
        "tips": "园区很大，建议预留3-4小时；可乘船游昆明湖",
        "reservation_url": "",
        "source": "preset",
    },
    {
        "attraction_name": "天坛公园",
        "destination": "北京",
        "reservation_channel": "天坛公园官方公众号",
        "ticket_release_time": "可现场购票",
        "opening_hours": "06:00-22:00（景点8:00-17:30）",
        "closing_days": "无固定闭馆日",
        "ticket_price": "门票15元，联票34元",
        "visitor_route": "南门进，北门出",
        "daily_limit": "",
        "tips": "建议早上来，有很多当地人晨练；回音壁很有趣",
        "reservation_url": "",
        "source": "preset",
    },
    {
        "attraction_name": "上海迪士尼乐园",
        "destination": "上海",
        "reservation_channel": "上海迪士尼官方公众号/APP",
        "ticket_release_time": "建议提前7-30天购票",
        "opening_hours": "08:30-20:30（具体以官方为准）",
        "closing_days": "无固定闭馆日",
        "ticket_price": "平日399元，高峰599元，假期699元",
        "visitor_route": "建议先玩热门项目，下午看花车巡游，晚上看烟花",
        "daily_limit": "按购票数量限流",
        "tips": "下载官方APP查看排队时间；建议购买尊享卡减少排队；带好雨衣",
        "reservation_url": "https://www.shanghaidisneyresort.com/",
        "source": "preset",
    },
    {
        "attraction_name": "东方明珠",
        "destination": "上海",
        "reservation_channel": "东方明珠官方公众号",
        "ticket_release_time": "可现场购票，建议提前预约",
        "opening_hours": "09:00-21:00",
        "closing_days": "无固定闭馆日",
        "ticket_price": "看登球高度，160-220元",
        "visitor_route": "",
        "daily_limit": "",
        "tips": "建议傍晚去，可以看日落和夜景；玻璃栈道很刺激",
        "reservation_url": "",
        "source": "preset",
    },
    {
        "attraction_name": "上海博物馆",
        "destination": "上海",
        "reservation_channel": "上海博物馆官方公众号",
        "ticket_release_time": "提前7天预约",
        "opening_hours": "09:00-17:00（16:00停止入场）",
        "closing_days": "每周一闭馆",
        "ticket_price": "免费",
        "visitor_route": "",
        "daily_limit": "每日限流",
        "tips": "免费但需预约；青铜器和陶瓷馆是精华；建议预留2-3小时",
        "reservation_url": "",
        "source": "preset",
    },
    {
        "attraction_name": "西湖",
        "destination": "杭州",
        "reservation_channel": "无需预约（部分景点需预约）",
        "ticket_release_time": "",
        "opening_hours": "全天开放",
        "closing_days": "无",
        "ticket_price": "免费（部分景点收费）",
        "visitor_route": "建议断桥→白堤→孤山→苏堤→花港观鱼→雷峰塔",
        "daily_limit": "",
        "tips": "建议早上或傍晚去，人少景美；可租自行车环湖；坐船游湖更惬意",
        "reservation_url": "",
        "source": "preset",
    },
    {
        "attraction_name": "灵隐寺",
        "destination": "杭州",
        "reservation_channel": "灵隐寺官方公众号",
        "ticket_release_time": "可现场购票，建议提前预约",
        "opening_hours": "07:00-18:15",
        "closing_days": "无固定闭馆日",
        "ticket_price": "飞来峰45元，灵隐寺香花券30元",
        "visitor_route": "",
        "daily_limit": "",
        "tips": "需先买飞来峰门票才能进灵隐寺；早上人少，香火旺盛；素斋值得一试",
        "reservation_url": "",
        "source": "preset",
    },
    {
        "attraction_name": "秦始皇兵马俑博物馆",
        "destination": "西安",
        "reservation_channel": "秦始皇兵马俑博物馆官方公众号",
        "ticket_release_time": "提前7天预约",
        "opening_hours": "08:30-17:00",
        "closing_days": "无固定闭馆日",
        "ticket_price": "120元",
        "visitor_route": "建议1号坑→2号坑→3号坑→铜车马",
        "daily_limit": "每日限流6.5万人",
        "tips": "建议请讲解员或租讲解器，否则看不懂；距离市区约1小时车程；带好身份证",
        "reservation_url": "",
        "source": "preset",
    },
    {
        "attraction_name": "西安城墙",
        "destination": "西安",
        "reservation_channel": "西安城墙官方公众号",
        "ticket_release_time": "可现场购票",
        "opening_hours": "08:00-22:00",
        "closing_days": "无固定闭馆日",
        "ticket_price": "54元",
        "visitor_route": "建议从南门（永宁门）登城",
        "daily_limit": "",
        "tips": "建议傍晚去，可以看日落和夜景；可租自行车环城（约1.5小时）；穿舒适的鞋",
        "reservation_url": "",
        "source": "preset",
    },
    {
        "attraction_name": "陕西历史博物馆",
        "destination": "西安",
        "reservation_channel": "陕西历史博物馆官方公众号",
        "ticket_release_time": "提前3天18:00放票，非常难抢",
        "opening_hours": "09:00-17:30（16:30停止入场）",
        "closing_days": "每周一闭馆（法定节假日除外）",
        "ticket_price": "免费（基本陈列），大唐遗宝展30元",
        "visitor_route": "",
        "daily_limit": "每日限流",
        "tips": "免费票非常难抢，建议定闹钟；何家村遗宝展值得看；建议请讲解员",
        "reservation_url": "",
        "source": "preset",
    },
    {
        "attraction_name": "大唐不夜城",
        "destination": "西安",
        "reservation_channel": "无需预约",
        "ticket_release_time": "",
        "opening_hours": "全天开放（表演19:00-23:00）",
        "closing_days": "无",
        "ticket_price": "免费",
        "visitor_route": "建议从大雁塔南广场开始，向南步行",
        "daily_limit": "",
        "tips": "建议晚上去，灯光很美；不倒翁表演很火，需提前占位；人很多，注意保管财物",
        "reservation_url": "",
        "source": "preset",
    },
    {
        "attraction_name": "成都大熊猫繁育研究基地",
        "destination": "成都",
        "reservation_channel": "成都大熊猫繁育研究基地官方公众号",
        "ticket_release_time": "提前7天预约",
        "opening_hours": "07:30-18:00",
        "closing_days": "无固定闭馆日",
        "ticket_price": "55元",
        "visitor_route": "建议先去月亮产房/太阳产房看幼崽，再看成年熊猫",
        "daily_limit": "每日限流6万人",
        "tips": "建议早上7:30开门就去，熊猫早上最活跃；园区很大，可坐观光车；带好身份证",
        "reservation_url": "",
        "source": "preset",
    },
    {
        "attraction_name": "南京博物院",
        "destination": "南京",
        "reservation_channel": "南京博物院官方公众号",
        "ticket_release_time": "提前3天预约",
        "opening_hours": "09:00-17:00（16:00停止入场）",
        "closing_days": "每周一闭馆（法定节假日除外）",
        "ticket_price": "免费",
        "visitor_route": "",
        "daily_limit": "每日限流",
        "tips": "免费但需预约；民国馆很有特色；建议预留3小时；带好身份证",
        "reservation_url": "",
        "source": "preset",
    },
    {
        "attraction_name": "中山陵",
        "destination": "南京",
        "reservation_channel": "中山陵官方公众号",
        "ticket_release_time": "提前1天预约",
        "opening_hours": "08:30-17:00",
        "closing_days": "每周一闭馆（祭堂）",
        "ticket_price": "免费（需预约）",
        "visitor_route": "",
        "daily_limit": "每日限流",
        "tips": "免费但需预约；392级台阶，穿舒适的鞋；可与明孝陵、美龄宫一起安排",
        "reservation_url": "",
        "source": "preset",
    },
    {
        "attraction_name": "拙政园",
        "destination": "苏州",
        "reservation_channel": "拙政园官方公众号",
        "ticket_release_time": "提前7天预约",
        "opening_hours": "07:30-17:30",
        "closing_days": "无固定闭馆日",
        "ticket_price": "旺季80元，淡季70元",
        "visitor_route": "",
        "daily_limit": "每日限流",
        "tips": "中国四大名园之首；建议早上开门就去，人少；可与苏州博物馆、狮子林一起安排",
        "reservation_url": "",
        "source": "preset",
    },
    {
        "attraction_name": "苏州博物馆",
        "destination": "苏州",
        "reservation_channel": "苏州博物馆官方公众号",
        "ticket_release_time": "提前7天预约，非常难抢",
        "opening_hours": "09:00-17:00（16:00停止入场）",
        "closing_days": "每周一闭馆",
        "ticket_price": "免费",
        "visitor_route": "",
        "daily_limit": "每日限流",
        "tips": "贝聿铭设计，建筑本身就是艺术品；免费但非常难预约；建议定闹钟抢票",
        "reservation_url": "",
        "source": "preset",
    },
    {
        "attraction_name": "广州塔（小蛮腰）",
        "destination": "广州",
        "reservation_channel": "广州塔官方公众号",
        "ticket_release_time": "可现场购票，建议提前预约",
        "opening_hours": "09:30-22:30",
        "closing_days": "无固定闭馆日",
        "ticket_price": "150-398元（按高度和项目）",
        "visitor_route": "",
        "daily_limit": "",
        "tips": "建议傍晚去，可以看日落和夜景；摩天轮和速降体验很刺激；提前买票有优惠",
        "reservation_url": "",
        "source": "preset",
    },
    {
        "attraction_name": "洪崖洞",
        "destination": "重庆",
        "reservation_channel": "无需预约",
        "ticket_release_time": "",
        "opening_hours": "全天开放（灯光18:00-23:00）",
        "closing_days": "无",
        "ticket_price": "免费",
        "visitor_route": "建议从顶层（11楼）往下逛，最后到江边",
        "daily_limit": "",
        "tips": "建议晚上去，灯光很美；人非常多，注意保管财物；千厮门大桥是最佳拍摄点；里面吃的比较贵",
        "reservation_url": "",
        "source": "preset",
    },
]


# ========== 避坑提示预置数据 ==========

TRAVEL_TIPS = [
    {"destination": "北京", "tip": "不要参加路边的长城一日游，多为黑导游，会带去购物点", "category": "anti_fraud", "severity": "danger", "sort_order": 100, "source": "preset"},
    {"destination": "北京", "tip": "北京地铁发达，景点间优先选择地铁出行，避免堵车", "category": "traffic", "severity": "info", "sort_order": 90, "source": "preset"},
    {"destination": "北京", "tip": "故宫、国博、天安门等热门景点需要提前预约，旺季一票难求", "category": "reservation", "severity": "warning", "sort_order": 95, "source": "preset"},
    {"destination": "北京", "tip": "南锣鼓巷商业化严重，不建议购买特产，价格贵且不正宗", "category": "food", "severity": "info", "sort_order": 70, "source": "preset"},
    {"destination": "北京", "tip": "北京气候干燥，注意补水和防晒；春秋季温差大，带件外套", "category": "weather", "severity": "info", "sort_order": 60, "source": "preset"},
    {"destination": "北京", "tip": "天安门广场安检严格，带好身份证，不要携带违禁品", "category": "safety", "severity": "warning", "sort_order": 85, "source": "preset"},
    {"destination": "北京", "tip": "八达岭长城人多，可选择慕田峪长城，人少体验好", "category": "general", "severity": "info", "sort_order": 75, "source": "preset"},
    {"destination": "上海", "tip": "迪士尼建议提前下载官方APP，查看排队时间和演出安排", "category": "general", "severity": "info", "sort_order": 90, "source": "preset"},
    {"destination": "上海", "tip": "迪士尼热门项目排队时间长，建议购买尊享卡或早享卡", "category": "general", "severity": "warning", "sort_order": 85, "source": "preset"},
    {"destination": "上海", "tip": "外滩夜景很美，但人很多，注意保管财物，建议错峰前往", "category": "safety", "severity": "info", "sort_order": 70, "source": "preset"},
    {"destination": "上海", "tip": "南京路步行街游客多，特产店价格偏高，建议去正规商场购买", "category": "food", "severity": "info", "sort_order": 65, "source": "preset"},
    {"destination": "上海", "tip": "上海地铁非常方便，建议办理交通卡或使用手机扫码乘车", "category": "traffic", "severity": "info", "sort_order": 80, "source": "preset"},
    {"destination": "杭州", "tip": "西湖免费，但部分景点（雷峰塔、灵隐寺等）需要单独购票", "category": "general", "severity": "info", "sort_order": 80, "source": "preset"},
    {"destination": "杭州", "tip": "西湖节假日人非常多，建议早上或傍晚前往，体验更好", "category": "general", "severity": "info", "sort_order": 75, "source": "preset"},
    {"destination": "杭州", "tip": "灵隐寺需要先购买飞来峰景区门票才能进入，不要只买灵隐寺香花券", "category": "reservation", "severity": "warning", "sort_order": 90, "source": "preset"},
    {"destination": "杭州", "tip": "杭州菜偏清淡，西湖醋鱼很多人吃不惯，点餐前可先了解", "category": "food", "severity": "info", "sort_order": 60, "source": "preset"},
    {"destination": "杭州", "tip": "龙井茶很多假货，建议去正规茶店或龙井村茶农家购买", "category": "anti_fraud", "severity": "warning", "sort_order": 85, "source": "preset"},
    {"destination": "西安", "tip": "兵马俑建议请讲解员或租讲解器，否则只能看泥人，了解不到历史", "category": "general", "severity": "info", "sort_order": 95, "source": "preset"},
    {"destination": "西安", "tip": "陕西历史博物馆免费票非常难抢，建议定闹钟提前3天18:00抢票", "category": "reservation", "severity": "danger", "sort_order": 100, "source": "preset"},
    {"destination": "西安", "tip": "回民街游客多，价格偏高，本地人更多去洒金桥吃美食", "category": "food", "severity": "info", "sort_order": 80, "source": "preset"},
    {"destination": "西安", "tip": "西安景点之间距离较远，建议合理安排路线，避免来回奔波", "category": "traffic", "severity": "info", "sort_order": 75, "source": "preset"},
    {"destination": "西安", "tip": "大唐不夜城人非常多，不倒翁表演需要提前占位，注意保管财物", "category": "safety", "severity": "warning", "sort_order": 85, "source": "preset"},
    {"destination": "成都", "tip": "大熊猫基地建议早上7:30开门就去，熊猫早上最活跃，下午都在睡觉", "category": "general", "severity": "warning", "sort_order": 100, "source": "preset"},
    {"destination": "成都", "tip": "成都美食很多，但很辣，不能吃辣的朋友记得说微辣或不辣", "category": "food", "severity": "info", "sort_order": 80, "source": "preset"},
    {"destination": "成都", "tip": "宽窄巷子和锦里商业化严重，不建议在里面吃正餐，价格贵且不正宗", "category": "food", "severity": "info", "sort_order": 75, "source": "preset"},
    {"destination": "成都", "tip": "都江堰和青城山距离市区较远，建议安排一整天，不要和市区景点混在一起", "category": "traffic", "severity": "info", "sort_order": 85, "source": "preset"},
    {"destination": "南京", "tip": "南京博物院免费但需预约，建议提前3天预约，民国馆很有特色", "category": "reservation", "severity": "warning", "sort_order": 90, "source": "preset"},
    {"destination": "南京", "tip": "中山陵免费但需预约，392级台阶，穿舒适的鞋子", "category": "general", "severity": "info", "sort_order": 75, "source": "preset"},
    {"destination": "南京", "tip": "夫子庙秦淮河夜景很美，但周边美食价格偏高，建议谨慎选择", "category": "food", "severity": "info", "sort_order": 70, "source": "preset"},
    {"destination": "苏州", "tip": "苏州博物馆免费但非常难预约，建议提前7天定闹钟抢票", "category": "reservation", "severity": "danger", "sort_order": 100, "source": "preset"},
    {"destination": "苏州", "tip": "拙政园、狮子林等园林建议早上开门就去，人少景美，体验更好", "category": "general", "severity": "info", "sort_order": 85, "source": "preset"},
    {"destination": "苏州", "tip": "苏州园林很多，不必全部去，建议选1-2个代表性的即可", "category": "general", "severity": "info", "sort_order": 70, "source": "preset"},
    {"destination": "广州", "tip": "广州美食很多，建议去老城区的茶楼体验早茶，性价比高", "category": "food", "severity": "info", "sort_order": 85, "source": "preset"},
    {"destination": "广州", "tip": "广州气候炎热潮湿，注意防暑降温，随身携带雨伞（阵雨多）", "category": "weather", "severity": "info", "sort_order": 75, "source": "preset"},
    {"destination": "重庆", "tip": "重庆是8D魔幻城市，导航经常失灵，建议多问路，当地人很热情", "category": "traffic", "severity": "info", "sort_order": 90, "source": "preset"},
    {"destination": "重庆", "tip": "洪崖洞里面吃的比较贵，建议只逛不吃，周边有很多好吃的", "category": "food", "severity": "info", "sort_order": 80, "source": "preset"},
    {"destination": "重庆", "tip": "重庆火锅很辣，不能吃辣的朋友记得点鸳鸯锅或微辣", "category": "food", "severity": "info", "sort_order": 75, "source": "preset"},
    {"destination": "重庆", "tip": "重庆地形复杂，穿舒适的运动鞋，很多地方需要爬坡上坎", "category": "general", "severity": "info", "sort_order": 85, "source": "preset"},
]


async def init_reservation_rules():
    """初始化预约规则。"""
    rules_service = get_attraction_rules()
    print(f"\n开始导入预约规则，共 {len(RESERVATION_RULES)} 条...")

    success_count = 0
    skip_count = 0

    for rule_data in RESERVATION_RULES:
        existing = await rules_service.get_by_name(rule_data["attraction_name"])
        if existing:
            print(f"  跳过（已存在）: {rule_data['attraction_name']}")
            skip_count += 1
            continue

        rule = AttractionRule(**rule_data)
        rule_id = await rules_service.create(rule)
        if rule_id:
            print(f"  ✓ 导入成功: {rule_data['attraction_name']} (ID: {rule_id})")
            success_count += 1
        else:
            print(f"  ✗ 导入失败: {rule_data['attraction_name']}")

    print(f"\n预约规则导入完成：成功 {success_count} 条，跳过 {skip_count} 条")
    return success_count


async def init_travel_tips():
    """初始化避坑提示。"""
    tips_service = get_travel_tips()
    print(f"\n开始导入避坑提示，共 {len(TRAVEL_TIPS)} 条...")

    success_count = 0
    skip_count = 0

    for tip_data in TRAVEL_TIPS:
        existing_tips = await tips_service.get_by_destination(tip_data["destination"])
        exists = any(t.tip == tip_data["tip"] for t in existing_tips)

        if exists:
            print(f"  跳过（已存在）: [{tip_data['destination']}] {tip_data['tip'][:30]}...")
            skip_count += 1
            continue

        tip = TravelTip(**tip_data)
        tip_id = await tips_service.create(tip)
        if tip_id:
            print(f"  ✓ 导入成功: [{tip_data['destination']}] {tip_data['tip'][:30]}...")
            success_count += 1
        else:
            print(f"  ✗ 导入失败: [{tip_data['destination']}] {tip_data['tip'][:30]}...")

    print(f"\n避坑提示导入完成：成功 {success_count} 条，跳过 {skip_count} 条")
    return success_count


async def main():
    """主函数。"""
    print("=" * 60)
    print("热门目的地数据预置脚本")
    print("=" * 60)

    rules_count = await init_reservation_rules()
    tips_count = await init_travel_tips()

    print("\n" + "=" * 60)
    print("数据预置完成！")
    print(f"  预约规则：新增 {rules_count} 条")
    print(f"  避坑提示：新增 {tips_count} 条")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
