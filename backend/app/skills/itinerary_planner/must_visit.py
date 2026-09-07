"""
行程规划引擎 - 必去地标注入模块。

从 planner.py 抽出的必去地标注入函数：
- inject_must_visit_attrs：把「必打卡」知名地标解析后注入主线景点池并置前

功能特性：
- 从数据库读取 must_visit 表（必去地标知识库）
- 按真实坐标解析后置入 attrs 头部
- 评分高自然成为聚类种子
- 保证热门城市经典地标稳进规划
- 放宽其距离约束（标记 hot）
- 同名地标已在行政枚举结果里：不打重复，但补打 must_visit/hot 权重与评分
- resolve_poi 失败时用城市中心坐标构建近似 POI（地图 API 恢复后自动返回真实坐标）

使用方式：
    from app.services.planner.must_visit import inject_must_visit_attrs

    # 注入必去地标
    attrs = await inject_must_visit_attrs("北京", attrs)
    # attrs 头部会包含故宫、天安门、长城等必去地标
"""
from typing import Any, Dict, List

from ...services import map as amap
from .utils import is_closed as _is_closed


async def inject_must_visit_attrs(
    city: str, attrs: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    把「必打卡」知名地标（must_visit 知识库）解析后注入主线景点池并置前。

    行政枚举(attrs)依赖高德关键词召回，容易漏掉八达岭长城/颐和园这类顶级地标
    （北京等直辖市还因 adcode 层级跳过市级/省级枚举，召回更依赖区县关键词）；
    知识库地标按真实坐标解析后置入 attrs 头部，评分高自然成为聚类种子，
    保证热门城市经典地标稳进规划，并放宽其距离约束（标记 hot）。

    Args:
        city: 城市名称
        attrs: 行政枚举得到的景点池

    Returns:
        List[Dict[str, Any]]: 注入必去地标后的景点池（必去地标在头部）

    Example:
        >>> attrs = await inject_must_visit_attrs("北京", attrs)
        >>> # attrs 头部会包含故宫、天安门、长城等必去地标
    """
    key = city.rstrip("市")
    try:
        # 从数据库读取 must_visit 表
        from ...data.repositories.admin_repository import get_must_visit

        entries = get_must_visit(key) or get_must_visit(city) or []
    except Exception:
        return attrs
    entries = [e for e in entries if e.get("category", "景点") == "景点"]
    if not entries:
        return attrs
    seen = {a["name"] for a in attrs}
    hot: List[Dict[str, Any]] = []
    for e in entries:
        name = e.get("name", "")
        if not name:
            continue
        # 同名地标已在行政枚举结果里：不打重复，但补打 must_visit/hot 权重与评分，
        # 确保「天安门/故宫」这类本就在候选池的顶级地标也能获得排序加成进入规划。
        if name in seen:
            for a in attrs:
                if a["name"] == name:
                    a["must_visit"] = True
                    a["hot"] = True
                    # 【必去景点优先级】传递priority字段，用于P0/P1/P2分级
                    # priority: 1=P0（顶级地标，必须安排），2=P1（重要景点，优先安排），3=P2（推荐景点，时间充裕时安排）
                    a["must_visit_priority"] = int(e.get("priority", 2))
                    a["rating"] = max(
                        a.get("rating") or 0, float(e.get("rating", 4.8))
                    )
            continue
        rp = await amap.resolve_poi(city, e.get("kw") or name, "景点")
        if not rp:
            # resolve_poi 失败（如地图 API 配额耗尽）：用城市中心坐标构建近似 POI，
            # 确保 must_visit 地标能进入候选池，LLM 优化与规划引擎可正常运行；
            # 地图 API 恢复后 resolve_poi 自动返回真实坐标，无需改代码。
            try:
                geo = await amap.geocode(city)
                rp = {
                    "id": f"must_{name}",
                    "name": name,
                    "category": "景点",
                    "lng": float(geo["lng"]),
                    "lat": float(geo["lat"]),
                    "rating": float(e.get("rating", 4.8)),
                    "address": "",
                    "district": "",
                    "cityname": city,
                    "approximate": True,
                }
            except Exception:
                continue
        if _is_closed(rp):
            continue
        rp["rating"] = max(rp["rating"], float(e.get("rating", 4.8)))
        rp["hot"] = True  # 放宽距离约束（amap 侧已对 hot 放行 100km）
        rp["must_visit"] = True  # 标记知识库地标，便于后续优先级/主题处理
        # 【必去景点优先级】传递priority字段，用于P0/P1/P2分级
        rp["must_visit_priority"] = int(e.get("priority", 2))
        seen.add(rp["name"])
        hot.append(rp)
    return hot + attrs
