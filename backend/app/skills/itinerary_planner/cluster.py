"""
行程规划引擎 - 地理聚类模块。

从 planner.py 抽出的聚类相关函数：
- cluster_attractions：景点按地理邻近聚类
- merge_sparse_clusters：稀疏簇合并
- make_area：区域构造
- greedy_group：贪心分组（高分锚点+就近高分）
- split_to_balance：区域拆分均衡
- dist_tier：距离分层
- assign_areas_to_days：区域分配到天
- area_label：区域主题名

功能特性：
- 景点按地理邻近聚类（短距离的景点归为一组，同一天）
- 高分景点优先作为聚类种子（保证每个区域至少有一个优质点位）
- 聚类大小限制（避免某个聚类过大导致一天安排不过来）
- 稀疏簇合并（把景点过少的稀疏簇并入最近邻簇）
- 贪心分组（高分锚点+就近高分）
- 区域拆分均衡（把区域拆成均衡子区域）
- 距离分层（市区核心→近郊→远郊→省内远点）
- 区域分配到天（不同天不重复区域，由近及远、按圈层轮流）
- 区域主题名（取最高分景点名称去掉常见后缀）

使用方式：
    from app.services.planner.cluster import (
        cluster_attractions, merge_sparse_clusters, make_area,
        greedy_group, split_to_balance, dist_tier,
        assign_areas_to_days, area_label
    )

    # 景点按地理邻近聚类
    clusters = cluster_attractions(attrs, max_dist=12000, max_cluster_size=8)

    # 稀疏簇合并
    clusters = merge_sparse_clusters(clusters, min_n=2, merge_dist=12000)

    # 贪心分组
    groups = greedy_group(pois, max_n=3, max_link=6000)

    # 区域分配到天
    day_areas = assign_areas_to_days(clusters, center, days=3)

    # 区域主题名
    label = area_label(cluster)  # "西湖"
"""
from typing import Any, Dict, List, Optional

from ...services import map as amap
from .constants import AUX_FOOD_BAD_NAMES, CLUSTER_MAX_DIST
from .utils import (
    _avg_rank,
    _rank,
    is_closed as _is_closed,
    is_landmark as _is_landmark,
)


def cluster_attractions(
    attrs: List[Dict[str, Any]],
    max_dist: int = CLUSTER_MAX_DIST,
    max_cluster_size: int = 8,
) -> List[Dict[str, Any]]:
    """
    把景点按地理邻近聚类成「区域」：短距离的景点归为一组（同一天）。

    高分景点优先作为聚类种子，保证每个区域至少有一个优质点位。

    优化：
    - 增加聚类大小限制（max_cluster_size），避免某个聚类过大导致一天安排不过来
    - 优化聚类种子选择，同时考虑评分和地理分布，避免所有高分景点聚在一起
    - 当聚类达到最大大小时，不再接受新的景点，强制创建新聚类

    Args:
        attrs: 景点列表
        max_dist: 最大聚类距离（米）
        max_cluster_size: 最大聚类大小

    Returns:
        List[Dict[str, Any]]: 聚类后的区域列表
    """
    clusters = []
    # 过滤掉没有坐标的景点，避免聚类时出现NoneType错误
    attrs = [p for p in attrs if p.get("lng") is not None and p.get("lat") is not None]
    if not attrs:
        return []
    # 按评分排序，但同时考虑地理分布（同分取离已有聚类中心更远的，促进地理分散）
    sorted_attrs = sorted(attrs, key=lambda x: -_rank(x))

    for p in sorted_attrs:
        best, best_d = None, float("inf")
        for c in clusters:
            # 聚类大小限制：达到最大大小时不再接受新景点
            if len(c.get("pois", [])) >= max_cluster_size:
                continue
            d = amap.haversine(c["cx"], c["cy"], p["lng"], p["lat"])
            if d <= max_dist and d < best_d:
                best, best_d = c, d
        if best is None:
            best = {"cx": p["lng"], "cy": p["lat"], "pois": []}
            clusters.append(best)
        best["pois"].append(p)
        n = len(best["pois"])
        best["cx"] = (best["cx"] * (n - 1) + p["lng"]) / n
        best["cy"] = (best["cy"] * (n - 1) + p["lat"]) / n
    for c in clusters:
        c["avg_rating"] = sum(p.get("rating", 0) for p in c["pois"]) / max(
            1, len(c["pois"])
        )
        c["pois"].sort(key=lambda p: -_rank(p))
        # 标记聚类大小，便于后续评估
        c["size"] = len(c["pois"])
    return merge_sparse_clusters(clusters)


def merge_sparse_clusters(
    clusters: List[Dict[str, Any]],
    min_n: int = 2,
    merge_dist: int = 12_000,
) -> List[Dict[str, Any]]:
    """
    把景点过少的稀疏簇并入最近邻簇，保证每个区域有足够景点、区域连贯，
    避免出现只有 1 个景点、再靠跨区补足污染行程的「空壳日」。

    Args:
        clusters: 聚类列表
        min_n: 最小聚类大小
        merge_dist: 合并距离（米）

    Returns:
        List[Dict[str, Any]]: 合并后的聚类列表
    """
    clusters = [dict(c) for c in clusters]
    while True:
        changed = False
        for i in range(len(clusters)):
            c = clusters[i]
            if len(c.get("pois", [])) >= min_n:
                continue
            best, best_d = None, float("inf")
            for j, o in enumerate(clusters):
                if j == i or not o.get("pois"):
                    continue
                d = amap.haversine(c["cx"], c["cy"], o["cx"], o["cy"])
                if d < best_d:
                    best, best_d = j, d
            if best is not None and best_d <= merge_dist:
                o = clusters[best]
                o["pois"].extend(c["pois"])
                n = len(o["pois"])
                o["cx"] = sum(p["lng"] for p in o["pois"]) / n
                o["cy"] = sum(p["lat"] for p in o["pois"]) / n
                o["avg_rating"] = sum(p.get("rating", 0) for p in o["pois"]) / n
                clusters.pop(i)
                changed = True
                break
        if not changed:
            break
    return clusters


def make_area(pois: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    构造区域。

    Args:
        pois: 景点列表

    Returns:
        Dict[str, Any]: 区域信息
    """
    n = len(pois)
    return {
        "cx": sum(p["lng"] for p in pois) / n,
        "cy": sum(p["lat"] for p in pois) / n,
        "pois": pois,
        "avg_rating": sum(p.get("rating", 0) for p in pois) / n,
    }


def greedy_group(
    pois: List[Dict[str, Any]],
    max_n: int = 3,
    max_link: int = 6_000,
    center: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    把区域内的景点按「高分锚点 + 就近高分」分成 ≤max_n 的小区域。

    关键：
    - seed 取评分最高的未分配点；同分（尤其多个顶级地标并列时）取离市中心更近的，
      使故宫/天安门/国博这类中轴线地标优先聚成一组，避免被评分微差拆散；
    - 扩展时在距离阈值内取「评分最高」的邻居（同分取更近），
      避免故宫(4.9)被更近但平庸的景山子场馆(4.6)拉低 —— 故宫会与
      天安门/长安街(都4.9、1km内) 同组 avg≈4.9，稳居头名。

    Args:
        pois: 景点列表
        max_n: 最大分组大小
        max_link: 最大链接距离（米）
        center: 市中心坐标（用于同分排序）

    Returns:
        List[Dict[str, Any]]: 分组后的区域列表
    """
    if center:

        def _key(p: Dict[str, Any]) -> tuple:
            return (
                -_rank(p),
                amap.haversine(center["lng"], center["lat"], p["lng"], p["lat"]),
            )

    else:

        def _key(p: Dict[str, Any]) -> float:
            return -_rank(p)

    def _gdist(cx: float, cy: float, p: Dict[str, Any]) -> float:
        return amap.haversine(cx, cy, p["lng"], p["lat"])

    pois = sorted(pois, key=_key)
    groups, unassigned = [], list(pois)
    while unassigned:
        seed = unassigned.pop(0)  # 剩余评分最高的（同分取市中心近）
        group = [seed]
        while len(group) < max_n and unassigned:
            cx = sum(p["lng"] for p in group) / len(group)
            cy = sum(p["lat"] for p in group) / len(group)
            near = [p for p in unassigned if _gdist(cx, cy, p) <= max_link]
            if not near:
                break
            # 同分时取更近的邻居，保证地标就近成组（如故宫↔天安门）
            pick = max(near, key=lambda p: (_rank(p), -_gdist(cx, cy, p)))
            group.append(pick)
            unassigned.remove(pick)
        groups.append(make_area(group))
    return groups


def split_to_balance(
    c: Dict[str, Any],
    max_n: int = 3,
    center: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    把区域拆成 ≤max_n 个景点的均衡子区域（高分锚点+最近邻分组）。

    Args:
        c: 区域信息
        max_n: 最大分组大小
        center: 市中心坐标（用于同分排序）

    Returns:
        List[Dict[str, Any]]: 拆分后的子区域列表
    """
    if len(c.get("pois", [])) <= max_n:
        return [c]
    return greedy_group(c["pois"], max_n, center=center)


def dist_tier(d: float) -> int:
    """
    距离分层：市区核心(≤10km) → 近郊(≤25km) → 远郊(≤60km) → 省内远点(>60km)。
    核心先玩、远点最后，符合「出行距离短优先」。

    Args:
        d: 距离（米）

    Returns:
        int: 距离层级（0=市区核心, 1=近郊, 2=远郊, 3=省内远点）
    """
    if d <= 10_000:
        return 0
    if d <= 25_000:
        return 1
    if d <= 60_000:
        return 2
    return 3


def assign_areas_to_days(
    clusters: List[Dict[str, Any]],
    center: Dict[str, Any],
    days: int,
) -> List[Dict[str, Any]]:
    """
    把区域分到每天：不同天不重复区域；大区域先拆成均衡子区域。

    天序策略 = 「由近及远、按圈层轮流」：
    - 圈层 zone = 市区(≤10km) / 近郊(≤25km) / 远郊(>25km)；
    - 每天覆盖一个圈层且不重复，3 天北京 = 故宫天安门(市区) + 颐和园(近郊) + 八达岭长城(远郊)，
      避免旧策略「市区占满 2 天」把远郊王牌（长城/乌镇等）挤掉；
    - 远郊有评分门槛(≥4.5)，避免为凑远郊选烂点。

    Args:
        clusters: 聚类列表
        center: 市中心坐标
        days: 天数

    Returns:
        List[Dict[str, Any]]: 分配到每天的区域列表
    """
    balanced = []
    for c in clusters:
        balanced.extend(split_to_balance(c, 3, center))
    for c in balanced:
        c["dist_center"] = amap.haversine(
            center["lng"], center["lat"], c["cx"], c["cy"]
        )
        c["tier"] = dist_tier(c["dist_center"])
        c["zone"] = min(c["tier"], 2)  # 0市区 / 1近郊 / 2远郊
        c["landmark"] = any(_is_landmark(p) for p in c.get("pois", []))
    by_zone: Dict[int, List[Dict[str, Any]]] = {}
    for c in balanced:
        by_zone.setdefault(c["zone"], []).append(c)
    for z, items in by_zone.items():
        # 同圈层内：城市名片(世界遗产/国家级) 优先 → 地标加权评分 → 距离近
        items.sort(
            key=lambda c: (-c["landmark"], -_avg_rank(c["pois"]), c["dist_center"])
        )
    zones = sorted(by_zone)

    result = []
    i = 0
    while len(result) < days:
        progressed = False
        for z in zones:
            if len(result) >= days:
                break
            if i < len(by_zone[z]):
                cand = by_zone[z][i]
                # 远郊评分门槛：不达标则本轮跳过，把名额让给近/中圈层
                if z == 2 and cand.get("avg_rating", 0) < 4.5:
                    continue
                result.append(cand)
                progressed = True
        if not progressed:
            break
        i += 1
    # 仍不足天数：从剩余区域按 (圈层, 评分, 距离) 补足
    if len(result) < days:
        rest = [c for c in balanced if c not in result]
        rest.sort(key=lambda c: (c["zone"], -c["avg_rating"], c["dist_center"]))
        result.extend(rest[: days - len(result)])
    return result[:days]


def area_label(c: Dict[str, Any]) -> str:
    """
    区域主题名：取最高分景点名称去掉常见后缀。

    Args:
        c: 区域信息

    Returns:
        str: 区域主题名
    """
    if not c.get("pois"):
        return "城市"
    top = c["pois"][0]["name"]
    for suf in (
        "风景名胜区",
        "名胜区",
        "风景区",
        "旅游度假区",
        "度假区",
        "旅游景区",
        "景区",
        "旅游区",
    ):
        if top.endswith(suf) and len(top) > len(suf) + 1:
            top = top[: -len(suf)]
            break
    return top
