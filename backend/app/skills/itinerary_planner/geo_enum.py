"""
行程规划引擎 - 地理枚举模块。

从 planner.py 抽出的地理相关函数：
- 中国境内判断
- 省份最佳出行季节知识库
- 目的地→省份解析
- 大时间跨度月度分配摘要
- 行政区域景点枚举

功能特性：
- 中国境内判断（本地命中、province字段、经纬度范围三级判断）
- 省份最佳出行月份知识库（34个省级行政区，带缓存）
- 目的地→省份解析（geo.province、本地行政区域库、常见城市→省映射、destination本身四级解析）
- 月份列表转中文描述（连续月份用范围表示）
- 省级目的地判断（直辖市排除、level判断、adcode判断）
- 按行政编码检索某一级（区县/市/省）的景点候选
- 枚举目的地行政范围内的景点（区县→市→省三级，含跨城污染过滤）
- 过滤属于某个主景点的内部子景点（避免子景点作为独立规划点位）

使用方式：
    from app.services.planner.geo_enum import (
        is_in_china, resolve_province, is_province,
        enumerate_scoped_attractions, months_str
    )

    # 判断是否在中国境内
    in_china = is_in_china(geo)

    # 解析目的地所属省份
    province = resolve_province("杭州", geo)

    # 判断是否为省级目的地
    is_prov = is_province(geo)

    # 枚举目的地行政范围内的景点
    attractions = await enumerate_scoped_attractions(geo, center)

    # 月份列表转中文描述
    desc = months_str([3, 4, 5])  # "3-5月"
"""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from ...data.models.models import PlanRequest
from ...services import map as amap


def is_in_china(geo: Dict[str, Any]) -> bool:
    """
    判断地理编码结果是否在中国境内（含港澳台）。

    判断优先级：
    1. 本地命中（source=local）：本地行政区域库只有中国数据，默认中国
    2. 第三方返回 province 字段非空：高德/腾讯返回中国地址时 province 有值
    3. 经纬度范围判断：中国大致范围 73°-135.5°E, 17.5°-54°N（含港澳台及南海诸岛）

    Args:
        geo: 地理编码结果

    Returns:
        bool: 是否在中国境内
    """
    if not geo:
        return False
    # 1) 本地命中：只有中国数据
    if geo.get("source") == "local":
        return True
    # 2) province 非空
    if geo.get("province"):
        return True
    # 3) 经纬度范围（含港澳台、南海诸岛）
    lng = geo.get("lng")
    lat = geo.get("lat")
    if lng is not None and lat is not None:
        return 73.0 <= float(lng) <= 135.5 and 17.5 <= float(lat) <= 54.0
    return False


# ========== 大时间跨度（月/年）规划：按省/月合理分配 ==========

_PROVINCE_SEASON_CACHE: Optional[Dict[str, Any]] = None


def load_province_best_season() -> Dict[str, Any]:
    """
    加载省份最佳出行月份知识库（34个省级行政区）。

    Returns:
        Dict[str, Any]: 省份最佳出行月份数据
    """
    global _PROVINCE_SEASON_CACHE
    if _PROVINCE_SEASON_CACHE is not None:
        return _PROVINCE_SEASON_CACHE
    try:
        path = Path(__file__).resolve().parent.parent / "data" / "province_best_season.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            # 去掉 _comment 等非省份键
            _PROVINCE_SEASON_CACHE = {
                k: v for k, v in data.items() if not k.startswith("_")
            }
        else:
            _PROVINCE_SEASON_CACHE = {}
    except Exception:
        _PROVINCE_SEASON_CACHE = {}
    return _PROVINCE_SEASON_CACHE


def resolve_province(destination: str, geo: Dict[str, Any]) -> str:
    """
    确定目的地所属省级行政区名称。

    优先级：geo.province → 本地行政区域库 lookup（向上追溯到省级）→ 常见城市→省映射 → destination 本身

    Args:
        destination: 目的地名称
        geo: 地理编码结果

    Returns:
        str: 省级行政区名称
    """
    # 1) geocode 返回的 province
    prov = (geo or {}).get("province", "")
    if prov:
        return prov
    # 2) 本地行政区域库：从目的地向上追溯到省级
    try:
        from ...core import geo_local

        entry = geo_local.lookup(destination)
        if entry:
            if entry.get("level") == "province":
                return entry["name"]
            parent = entry.get("parent")
            visited = set()
            while parent and parent not in visited:
                visited.add(parent)
                p_entry = geo_local.lookup(parent)
                if p_entry:
                    if p_entry.get("level") == "province":
                        return p_entry["name"]
                    parent = p_entry.get("parent")
                else:
                    break
    except Exception:
        pass
    # 3) 常见旅游城市→省份映射（覆盖本地数据 parent 缺失的情况）
    CITY_TO_PROVINCE = {
        "北京": "北京市",
        "天津": "天津市",
        "上海": "上海市",
        "重庆": "重庆市",
        "杭州": "浙江省",
        "宁波": "浙江省",
        "温州": "浙江省",
        "绍兴": "浙江省",
        "嘉兴": "浙江省",
        "金华": "浙江省",
        "台州": "浙江省",
        "湖州": "浙江省",
        "丽水": "浙江省",
        "衢州": "浙江省",
        "舟山": "浙江省",
        "南京": "江苏省",
        "苏州": "江苏省",
        "无锡": "江苏省",
        "常州": "江苏省",
        "徐州": "江苏省",
        "南通": "江苏省",
        "扬州": "江苏省",
        "镇江": "江苏省",
        "泰州": "江苏省",
        "盐城": "江苏省",
        "淮安": "江苏省",
        "连云港": "江苏省",
        "宿迁": "江苏省",
        "成都": "四川省",
        "绵阳": "四川省",
        "乐山": "四川省",
        "宜宾": "四川省",
        "泸州": "四川省",
        "南充": "四川省",
        "德阳": "四川省",
        "自贡": "四川省",
        "攀枝花": "四川省",
        "广元": "四川省",
        "遂宁": "四川省",
        "内江": "四川省",
        "眉山": "四川省",
        "广安": "四川省",
        "达州": "四川省",
        "雅安": "四川省",
        "巴中": "四川省",
        "资阳": "四川省",
        "阿坝": "四川省",
        "甘孜": "四川省",
        "凉山": "四川省",
        "西安": "陕西省",
        "咸阳": "陕西省",
        "宝鸡": "陕西省",
        "渭南": "陕西省",
        "延安": "陕西省",
        "汉中": "陕西省",
        "安康": "陕西省",
        "商洛": "陕西省",
        "铜川": "陕西省",
        "武汉": "湖北省",
        "宜昌": "湖北省",
        "襄阳": "湖北省",
        "荆州": "湖北省",
        "黄冈": "湖北省",
        "十堰": "湖北省",
        "孝感": "湖北省",
        "荆门": "湖北省",
        "鄂州": "湖北省",
        "黄石": "湖北省",
        "咸宁": "湖北省",
        "随州": "湖北省",
        "恩施": "湖北省",
        "长沙": "湖南省",
        "张家界": "湖南省",
        "岳阳": "湖南省",
        "湘潭": "湖南省",
        "株洲": "湖南省",
        "衡阳": "湖南省",
        "常德": "湖南省",
        "益阳": "湖南省",
        "郴州": "湖南省",
        "永州": "湖南省",
        "怀化": "湖南省",
        "娄底": "湖南省",
        "邵阳": "湖南省",
        "湘西": "湖南省",
        "广州": "广东省",
        "深圳": "广东省",
        "珠海": "广东省",
        "汕头": "广东省",
        "佛山": "广东省",
        "韶关": "广东省",
        "湛江": "广东省",
        "肇庆": "广东省",
        "江门": "广东省",
        "茂名": "广东省",
        "惠州": "广东省",
        "梅州": "广东省",
        "汕尾": "广东省",
        "河源": "广东省",
        "阳江": "广东省",
        "清远": "广东省",
        "东莞": "广东省",
        "中山": "广东省",
        "潮州": "广东省",
        "揭阳": "广东省",
        "云浮": "广东省",
        "厦门": "福建省",
        "福州": "福建省",
        "泉州": "福建省",
        "漳州": "福建省",
        "莆田": "福建省",
        "龙岩": "福建省",
        "三明": "福建省",
        "南平": "福建省",
        "宁德": "福建省",
        "青岛": "山东省",
        "济南": "山东省",
        "烟台": "山东省",
        "威海": "山东省",
        "潍坊": "山东省",
        "临沂": "山东省",
        "济宁": "山东省",
        "淄博": "山东省",
        "泰安": "山东省",
        "日照": "山东省",
        "东营": "山东省",
        "滨州": "山东省",
        "德州": "山东省",
        "聊城": "山东省",
        "菏泽": "山东省",
        "枣庄": "山东省",
        "郑州": "河南省",
        "洛阳": "河南省",
        "开封": "河南省",
        "南阳": "河南省",
        "新乡": "河南省",
        "安阳": "河南省",
        "焦作": "河南省",
        "平顶山": "河南省",
        "许昌": "河南省",
        "漯河": "河南省",
        "三门峡": "河南省",
        "商丘": "河南省",
        "信阳": "河南省",
        "周口": "河南省",
        "驻马店": "河南省",
        "济源": "河南省",
        "鹤壁": "河南省",
        "濮阳": "河南省",
        "昆明": "云南省",
        "大理": "云南省",
        "丽江": "云南省",
        "西双版纳": "云南省",
        "香格里拉": "云南省",
        "腾冲": "云南省",
        "玉溪": "云南省",
        "曲靖": "云南省",
        "保山": "云南省",
        "昭通": "云南省",
        "普洱": "云南省",
        "临沧": "云南省",
        "楚雄": "云南省",
        "红河": "云南省",
        "文山": "云南省",
        "德宏": "云南省",
        "怒江": "云南省",
        "迪庆": "云南省",
        "贵阳": "贵州省",
        "遵义": "贵州省",
        "安顺": "贵州省",
        "毕节": "贵州省",
        "铜仁": "贵州省",
        "六盘水": "贵州省",
        "黔东南": "贵州省",
        "黔南": "贵州省",
        "黔西南": "贵州省",
        "南宁": "广西壮族自治区",
        "桂林": "广西壮族自治区",
        "柳州": "广西壮族自治区",
        "北海": "广西壮族自治区",
        "玉林": "广西壮族自治区",
        "梧州": "广西壮族自治区",
        "钦州": "广西壮族自治区",
        "防城港": "广西壮族自治区",
        "贵港": "广西壮族自治区",
        "百色": "广西壮族自治区",
        "贺州": "广西壮族自治区",
        "河池": "广西壮族自治区",
        "来宾": "广西壮族自治区",
        "崇左": "广西壮族自治区",
        "哈尔滨": "黑龙江省",
        "长春": "吉林省",
        "沈阳": "辽宁省",
        "大连": "辽宁省",
        "鞍山": "辽宁省",
        "抚顺": "辽宁省",
        "本溪": "辽宁省",
        "丹东": "辽宁省",
        "锦州": "辽宁省",
        "营口": "辽宁省",
        "阜新": "辽宁省",
        "辽阳": "辽宁省",
        "盘锦": "辽宁省",
        "铁岭": "辽宁省",
        "朝阳": "辽宁省",
        "葫芦岛": "辽宁省",
        "呼和浩特": "内蒙古自治区",
        "包头": "内蒙古自治区",
        "鄂尔多斯": "内蒙古自治区",
        "赤峰": "内蒙古自治区",
        "通辽": "内蒙古自治区",
        "呼伦贝尔": "内蒙古自治区",
        "乌兰察布": "内蒙古自治区",
        "巴彦淖尔": "内蒙古自治区",
        "乌海": "内蒙古自治区",
        "兴安盟": "内蒙古自治区",
        "锡林郭勒盟": "内蒙古自治区",
        "阿拉善盟": "内蒙古自治区",
        "兰州": "甘肃省",
        "敦煌": "甘肃省",
        "嘉峪关": "甘肃省",
        "天水": "甘肃省",
        "白银": "甘肃省",
        "武威": "甘肃省",
        "张掖": "甘肃省",
        "平凉": "甘肃省",
        "酒泉": "甘肃省",
        "庆阳": "甘肃省",
        "定西": "甘肃省",
        "陇南": "甘肃省",
        "临夏": "甘肃省",
        "甘南": "甘肃省",
        "金昌": "甘肃省",
        "西宁": "青海省",
        "海东": "青海省",
        "海北": "青海省",
        "黄南": "青海省",
        "海南州": "青海省",
        "果洛": "青海省",
        "玉树": "青海省",
        "海西": "青海省",
        "银川": "宁夏回族自治区",
        "石嘴山": "宁夏回族自治区",
        "吴忠": "宁夏回族自治区",
        "固原": "宁夏回族自治区",
        "中卫": "宁夏回族自治区",
        "乌鲁木齐": "新疆维吾尔自治区",
        "喀什": "新疆维吾尔自治区",
        "伊犁": "新疆维吾尔自治区",
        "吐鲁番": "新疆维吾尔自治区",
        "哈密": "新疆维吾尔自治区",
        "昌吉": "新疆维吾尔自治区",
        "博尔塔拉": "新疆维吾尔自治区",
        "巴音郭楞": "新疆维吾尔自治区",
        "阿克苏": "新疆维吾尔自治区",
        "克孜勒苏": "新疆维吾尔自治区",
        "和田": "新疆维吾尔自治区",
        "塔城": "新疆维吾尔自治区",
        "阿勒泰": "新疆维吾尔自治区",
        "石河子": "新疆维吾尔自治区",
        "阿拉尔": "新疆维吾尔自治区",
        "图木舒克": "新疆维吾尔自治区",
        "五家渠": "新疆维吾尔自治区",
        "拉萨": "西藏自治区",
        "日喀则": "西藏自治区",
        "昌都": "西藏自治区",
        "林芝": "西藏自治区",
        "山南": "西藏自治区",
        "那曲": "西藏自治区",
        "阿里": "西藏自治区",
        "三亚": "海南省",
        "海口": "海南省",
        "三沙": "海南省",
        "儋州": "海南省",
        "五指山": "海南省",
        "琼海": "海南省",
        "文昌": "海南省",
        "万宁": "海南省",
        "东方": "海南省",
        "定安": "海南省",
        "屯昌": "海南省",
        "澄迈": "海南省",
        "临高": "海南省",
        "白沙": "海南省",
        "昌江": "海南省",
        "乐东": "海南省",
        "陵水": "海南省",
        "保亭": "海南省",
        "琼中": "海南省",
        "香港": "香港特别行政区",
        "澳门": "澳门特别行政区",
        "台北": "台湾省",
        "高雄": "台湾省",
        "台中": "台湾省",
        "台南": "台湾省",
        "石家庄": "河北省",
        "唐山": "河北省",
        "秦皇岛": "河北省",
        "邯郸": "河北省",
        "邢台": "河北省",
        "保定": "河北省",
        "张家口": "河北省",
        "承德": "河北省",
        "沧州": "河北省",
        "廊坊": "河北省",
        "衡水": "河北省",
        "太原": "山西省",
        "大同": "山西省",
        "平遥": "山西省",
        "运城": "山西省",
        "临汾": "山西省",
        "晋中": "山西省",
        "长治": "山西省",
        "晋城": "山西省",
        "朔州": "山西省",
        "忻州": "山西省",
        "吕梁": "山西省",
        "阳泉": "山西省",
        "合肥": "安徽省",
        "黄山": "安徽省",
        "芜湖": "安徽省",
        "蚌埠": "安徽省",
        "淮南": "安徽省",
        "马鞍山": "安徽省",
        "淮北": "安徽省",
        "铜陵": "安徽省",
        "安庆": "安徽省",
        "滁州": "安徽省",
        "阜阳": "安徽省",
        "宿州": "安徽省",
        "六安": "安徽省",
        "亳州": "安徽省",
        "池州": "安徽省",
        "宣城": "安徽省",
        "南昌": "江西省",
        "九江": "江西省",
        "景德镇": "江西省",
        "萍乡": "江西省",
        "新余": "江西省",
        "鹰潭": "江西省",
        "赣州": "江西省",
        "吉安": "江西省",
        "宜春": "江西省",
        "抚州": "江西省",
        "上饶": "江西省",
    }
    # 模糊匹配：目的地以某个城市名开头
    for city, prov_name in CITY_TO_PROVINCE.items():
        if destination.startswith(city) or city in destination:
            return prov_name
    # 4) destination 本身（可能就是省级）
    return destination


def months_str(months: List[int]) -> str:
    """
    月份列表转中文描述（如 [3,4,5] → "3-5月"）。

    Args:
        months: 月份列表

    Returns:
        str: 中文描述
    """
    if not months:
        return "全年"
    if len(months) == 1:
        return f"{months[0]}月"
    if len(months) == 12:
        return "全年"
    # 连续月份用范围表示
    sorted_m = sorted(months)
    ranges = []
    start = sorted_m[0]
    end = sorted_m[0]
    for m in sorted_m[1:]:
        if m == end + 1:
            end = m
        else:
            ranges.append(f"{start}-{end}月" if start != end else f"{start}月")
            start = m
            end = m
    ranges.append(f"{start}-{end}月" if start != end else f"{start}月")
    return "、".join(ranges)


def is_province(geo: Dict[str, Any]) -> bool:
    """
    目的地是否为省级（省/自治区）：省级目标按市分隔做路径规划。

    直辖市（北京/上海/天津/重庆）视作单城市，不走按市分隔
    （高德把直辖市 level 也标为「省」，须用 adcode 排除）。
    兼容腾讯：腾讯 adcode 为 6 位（省级以 0000 结尾），level 为数字、无「省」字样。

    Args:
        geo: 地理编码结果

    Returns:
        bool: 是否为省级目的地
    """
    ac = (geo.get("adcode") or "").strip()
    if ac in ("110000", "120000", "310000", "500000"):
        return False
    level = (geo.get("level") or "").strip()
    if "省" in level or "自治区" in level:
        return True
    if ac.isdigit():
        if len(ac) <= 2:
            return True
        if len(ac) >= 4 and ac.endswith("0000"):
            return True
    return False


async def scope_attrs(adcode: str, scope: str, limit: int = 80) -> List[Dict[str, Any]]:
    """
    按行政编码检索某一级（区县/市/省）的景点候选。

    Args:
        adcode: 行政编码
        scope: 范围级别（district/city/province）
        limit: 返回数量限制

    Returns:
        List[Dict[str, Any]]: 景点候选列表
    """
    from .constants import SCOPE_KEYWORDS

    kws = SCOPE_KEYWORDS.get(scope, ["景区"])
    attrs = await amap.search_attractions(adcode, kws, limit=limit)
    for p in attrs:
        p["scope"] = scope
    return attrs


async def enumerate_scoped_attractions(
    geo: Dict[str, Any], center: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    枚举目的地行政范围内的景点（区县→市→省三级，含跨城污染过滤）。

    策略：
    - 市级/区级/地点级：先枚举当前级，再向上枚举至省级作为补充
    - 省级：枚举省下所有市的景点
    - 跨城污染过滤：cityname 不属于当前城市的景点过滤掉

    Args:
        geo: 地理编码结果
        center: 中心点坐标

    Returns:
        List[Dict[str, Any]]: 景点列表
    """
    from .constants import SCOPE_KEYWORDS

    adcode = (geo.get("adcode") or "").strip()
    level = (geo.get("level") or "").strip()
    city_name = (geo.get("city") or geo.get("name") or "").strip()

    all_attrs = []
    seen_ids = set()

    def _add_attrs(attrs: List[Dict[str, Any]], scope: str) -> None:
        """添加景点到列表，去重并过滤跨城污染。"""
        for p in attrs:
            pid = p.get("id") or p.get("name")
            if pid and pid not in seen_ids:
                # 跨城污染过滤：cityname 不属于当前城市
                p_city = (p.get("cityname") or p.get("city") or "").strip()
                if city_name and p_city and city_name not in p_city and p_city not in city_name:
                    # 省级目的地允许跨城
                    if not is_province(geo):
                        continue
                p["scope"] = scope
                all_attrs.append(p)
                seen_ids.add(pid)

    # 1) 当前级枚举
    if adcode:
        try:
            attrs = await scope_attrs(
                adcode, "district" if "区" in level or "县" in level else "city"
            )
            _add_attrs(attrs, "current")
        except Exception:
            pass

    # 2) 向上枚举至省级（市级/区级/地点级）
    if not is_province(geo):
        try:
            from ...core import geo_local

            entry = geo_local.lookup(city_name)
            if entry:
                parent = entry.get("parent")
                visited = set()
                while parent and parent not in visited:
                    visited.add(parent)
                    p_entry = geo_local.lookup(parent)
                    if p_entry:
                        p_adcode = p_entry.get("adcode", "")
                        if p_adcode:
                            try:
                                attrs = await scope_attrs(
                                    p_adcode,
                                    "province"
                                    if p_entry.get("level") == "province"
                                    else "city",
                                )
                                _add_attrs(attrs, "parent")
                            except Exception:
                                pass
                        if p_entry.get("level") == "province":
                            break
                        parent = p_entry.get("parent")
                    else:
                        break
        except Exception:
            pass

    # 3) 子景点过滤：识别并过滤掉属于某个主景点的内部子景点
    #    子景点（如大明湖的超然楼、铁公祠）不作为独立规划点位，
    #    只作为主景点的内部动线在行程展示时展开
    all_attrs = _filter_inner_sub_pois(all_attrs, city_name)

    return all_attrs


def _filter_inner_sub_pois(
    attrs: List[Dict[str, Any]], city_name: str = ""
) -> List[Dict[str, Any]]:
    """
    过滤属于某个主景点的内部子景点，避免子景点作为独立规划点位。

    策略：
    1. 从poi_hierarchy获取所有主景点的内部子景点名称集合
    2. 如果一个POI的名称匹配某个主景点的内部子景点，则过滤掉
    3. 但如果该主景点本身不在候选池中，则保留子景点（降级处理）
    4. 同时确保主景点的优先级提升（如果主景点在候选池中）

    Args:
        attrs: 候选景点列表
        city_name: 当前城市名称（用于限定范围）

    Returns:
        List[Dict[str, Any]]: 过滤后的景点列表
    """
    try:
        from ...data.repositories.poi_hierarchy_repository import PoiHierarchyRepository

        repo = PoiHierarchyRepository()
        # 从数据库获取所有主POI（简化处理，获取前100个）
        all_main_pois, _ = repo.list_main_pois(city=city_name, page_size=100)
    except Exception:
        return attrs

    if not attrs:
        return attrs

    # 构建子景点名称 → 主景点名称的映射
    sub_to_main: Dict[str, str] = {}
    main_poi_names = set()
    for main_poi in all_main_pois:
        main_name = main_poi["name"]
        main_poi_names.add(main_name)
        # 添加主景点别名
        alias = main_poi.get("alias") or []
        if isinstance(alias, str):
            try:
                alias = json.loads(alias)
            except Exception:
                alias = []
        for a in alias:
            main_poi_names.add(a)
        # 获取子景点并添加映射
        inner_pois = repo.list_inner_pois(main_poi["id"])
        for inner_poi in inner_pois:
            sub_to_main[inner_poi["name"]] = main_name
            # 子景点别名（简化处理，去掉常见后缀）
            simple_name = (
                inner_poi["name"]
                .replace("景区", "")
                .replace("公园", "")
                .replace("楼", "")
                .strip()
            )
            if simple_name and simple_name != inner_poi["name"]:
                sub_to_main[simple_name] = main_name

    if not sub_to_main:
        return attrs

    # 检查候选池中是否有主景点
    has_main_in_pool = False
    for attr in attrs:
        attr_name = (attr.get("name") or "").strip()
        if attr_name in main_poi_names:
            has_main_in_pool = True
            break

    # 过滤子景点
    filtered = []
    filtered_count = 0
    for attr in attrs:
        attr_name = (attr.get("name") or "").strip()
        # 检查是否是子景点
        if attr_name in sub_to_main:
            main_name = sub_to_main[attr_name]
            # 如果主景点在候选池中，则过滤掉子景点
            if has_main_in_pool:
                filtered_count += 1
                continue
            # 如果主景点不在候选池中，保留子景点但标记为子景点
            attr["is_sub_poi"] = True
            attr["parent_poi"] = main_name
        filtered.append(attr)

    # 如果过滤了子景点，且主景点在候选池中，提升主景点优先级
    if filtered_count > 0 and has_main_in_pool:
        for attr in filtered:
            attr_name = (attr.get("name") or "").strip()
            if attr_name in main_poi_names:
                # 提升主景点评分（确保被排进规划）
                current_rating = float(attr.get("rating") or 0)
                attr["rating"] = max(current_rating, 4.8)  # 至少4.8分
                attr["is_main_poi"] = True
                # 标记为必去景点
                attr["must_visit"] = True

    return filtered
