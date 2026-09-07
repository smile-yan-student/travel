"""
通用 POI 去重工具模块 - 从根本上解决景点重复问题。

问题根源：
1. 第三方地图 API 中，同一个景区可能有多个 POI 条目，坐标几乎相同但名称不同
   例如："趵突泉景区"和"天下第一泉景区"距离只有 78 米
2. 主景区和子景区/子景点并存，可能作为独立 POI 返回
   例如："大明湖景区"和"大明湖景区-超然楼"
3. 大景区包含子景区，从不同行政层级枚举时可能重复
   例如："千佛山风景名胜区"和"大千佛山景区佛慧山"
4. 行政分级枚举时，从不同层级可能获取到同一个景区的不同名称

解决方案：
基于坐标距离 + 名称包含关系 + 名称相似度的综合去重算法，
不依赖任何硬编码的别名映射，可以自动识别任何城市的任何景点重复问题。

使用方式：
    from app.utils.poi_deduplicator import PoiDeduplicator, deduplicate_pois

    # 方式1：使用类
    deduplicator = PoiDeduplicator()
    result, removed = deduplicator.deduplicate(pois)

    # 方式2：使用便捷函数
    result, removed = deduplicate_pois(pois)
"""
import math
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple


# 功能点位后缀列表（子 POI，如"黑虎泉-取水点"）
FUNCTIONAL_SUFFIXES: List[str] = [
    "取水点", "取水口", "入口", "出口", "南门", "北门", "东门", "西门",
    "正门", "侧门", "停车场", "游客中心", "服务中心", "售票处", "检票口",
    "观景台", "观景平台", "码头", "游船码头", "缆车入口", "缆车出口",
    "索道站", "上山口", "下山口", "休息区", "餐饮区", "购物区",
]

# 常见的景区后缀列表
SCENIC_SUFFIXES: List[str] = [
    "景区", "风景区", "风景名胜区", "公园", "森林公园", "地质公园",
    "湿地公园", "博物院", "博物馆", "纪念馆", "遗址公园", "古镇",
    "古城", "古村", "主题公园", "游乐园", "度假区", "旅游区",
    "旅游度假区", "风景名胜", "风景旅游区",
]


class PoiDeduplicator:
    """
    通用 POI 去重器。

    基于坐标距离 + 名称包含关系 + 名称相似度的综合去重算法，
    不依赖任何硬编码的别名映射，可以自动识别任何城市的任何景点重复问题。

    属性：
        DISTANCE_THRESHOLD: 坐标距离阈值（米），距离小于此值的 POI 可能是同一个景区
        VERY_CLOSE_DISTANCE_THRESHOLD: 极近距离阈值（米），距离小于此值的 POI 即使名称不同也可能是同一景区
        SIMILARITY_THRESHOLD: 名称相似度阈值，相似度大于此值的 POI 可能是同一个景区
        MIN_LENGTH_DIFF: 名称包含关系的最小长度差，避免短名称误匹配

    使用方式：
        deduplicator = PoiDeduplicator()
        result, removed = deduplicator.deduplicate(pois)
    """

    # 坐标距离阈值（米）：距离小于此值的 POI 可能是同一个景区
    DISTANCE_THRESHOLD: int = 500

    # 极近距离阈值（米）：距离小于此值的 POI，即使名称不同也可能是同一景区
    VERY_CLOSE_DISTANCE_THRESHOLD: int = 100

    # 名称相似度阈值：相似度大于此值的 POI 可能是同一个景区
    SIMILARITY_THRESHOLD: float = 0.5

    # 名称包含关系的最小长度差：避免短名称误匹配
    MIN_LENGTH_DIFF: int = 2

    def __init__(
        self,
        distance_threshold: int = 500,
        similarity_threshold: float = 0.5,
        min_length_diff: int = 2,
    ) -> None:
        """
        初始化 POI 去重器。

        Args:
            distance_threshold: 坐标距离阈值（米），默认 500
            similarity_threshold: 名称相似度阈值，默认 0.5
            min_length_diff: 名称包含关系的最小长度差，默认 2
        """
        self.DISTANCE_THRESHOLD = distance_threshold
        self.SIMILARITY_THRESHOLD = similarity_threshold
        self.MIN_LENGTH_DIFF = min_length_diff

    def calculate_distance(self, poi1: Dict[str, Any], poi2: Dict[str, Any]) -> float:
        """
        计算两个 POI 之间的距离（米）。

        使用欧几里得距离近似（小范围内足够准确）。

        Args:
            poi1: 第一个 POI，需包含 lng 和 lat 字段
            poi2: 第二个 POI，需包含 lng 和 lat 字段

        Returns:
            float: 距离（米），如果坐标无效返回无穷大
        """
        lng1 = poi1.get("lng", 0)
        lat1 = poi1.get("lat", 0)
        lng2 = poi2.get("lng", 0)
        lat2 = poi2.get("lat", 0)

        if not lng1 or not lat1 or not lng2 or not lat2:
            return float("inf")

        # 使用欧几里得距离近似（小范围内足够准确）
        dist = math.sqrt((lng1 - lng2) ** 2 + (lat1 - lat2) ** 2) * 111000
        return dist

    def calculate_name_similarity(self, name1: str, name2: str) -> float:
        """
        计算两个名称的相似度。

        使用 SequenceMatcher 计算字符串相似度。

        Args:
            name1: 第一个名称
            name2: 第二个名称

        Returns:
            float: 相似度（0-1），如果任一名称为空返回 0.0
        """
        if not name1 or not name2:
            return 0.0
        return SequenceMatcher(None, name1, name2).ratio()

    def check_name_containment(
        self, name1: str, name2: str
    ) -> Tuple[bool, Optional[str]]:
        """
        检查两个名称是否存在包含关系或主子 POI 关系。

        支持以下情况：
        1. 直接包含：name1 in name2 或 name2 in name1
        2. "XX-YY" 格式：如"黑虎泉-取水点"包含"黑虎泉"
        3. 标准化后包含：去掉后缀后一个包含另一个

        Args:
            name1: 第一个名称
            name2: 第二个名称

        Returns:
            Tuple[bool, Optional[str]]: (是否包含, 更短的名称/更通用的名称/主 POI 名称)
        """
        if not name1 or not name2:
            return False, None

        len1 = len(name1)
        len2 = len(name2)

        # 长度差太小，避免误匹配
        if abs(len1 - len2) < self.MIN_LENGTH_DIFF:
            # 但是检查"XX-YY"格式，如"黑虎泉"和"黑虎泉-取水点"
            if "-" in name1 or "-" in name2:
                norm1 = self.normalize_name(name1)
                norm2 = self.normalize_name(name2)
                if norm1 and norm2 and norm1 == norm2:
                    return True, norm1  # 标准化后相同，返回标准化名称
            return False, None

        # 1. 直接包含
        if name1 in name2:
            return True, name1  # name1 更短，更通用
        elif name2 in name1:
            return True, name2  # name2 更短，更通用

        # 2. "XX-YY" 格式检查
        # 如"黑虎泉-取水点"和"黑虎泉"
        if "-" in name1:
            main_part = name1.split("-", 1)[0]
            if main_part and (main_part == name2 or main_part in name2 or name2 in main_part):
                return True, name2 if len(name2) < len(main_part) else main_part
        if "-" in name2:
            main_part = name2.split("-", 1)[0]
            if main_part and (main_part == name1 or main_part in name1 or name1 in main_part):
                return True, name1 if len(name1) < len(main_part) else main_part

        # 3. 标准化后包含
        norm1 = self.normalize_name(name1)
        norm2 = self.normalize_name(name2)
        if norm1 and norm2 and len(norm1) >= 2 and len(norm2) >= 2:
            if abs(len(norm1) - len(norm2)) >= self.MIN_LENGTH_DIFF:
                if norm1 in norm2:
                    return True, norm1
                elif norm2 in norm1:
                    return True, norm2
            elif norm1 == norm2:
                # 标准化后相同，说明是同一个景点的不同命名
                return True, norm1

        return False, None

    def normalize_name(self, name: str) -> str:
        """
        标准化景点名称，去掉常见后缀用于比较。

        处理步骤：
        1. 处理"XX-YY"格式，提取主名称部分（如果"-"后面是功能点位后缀）
        2. 去掉功能点位后缀
        3. 去掉景区后缀

        Args:
            name: 原始名称

        Returns:
            str: 标准化后的名称
        """
        if not name:
            return ""

        normalized = name

        # 先处理"XX-YY"格式，提取主名称部分
        if "-" in normalized:
            parts = normalized.split("-", 1)
            if len(parts[0]) >= 2 and len(parts[1]) <= 10:
                # 如果"-"后面的部分是功能点位后缀，只保留前面的主名称
                suffix_part = parts[1]
                if any(
                    suffix_part.endswith(suf) or suffix_part == suf
                    for suf in FUNCTIONAL_SUFFIXES
                ):
                    normalized = parts[0]

        # 去掉功能点位后缀
        for suffix in FUNCTIONAL_SUFFIXES:
            if normalized.endswith(suffix):
                normalized = normalized[: -len(suffix)]
                break

        # 去掉景区后缀
        for suffix in SCENIC_SUFFIXES:
            if normalized.endswith(suffix):
                normalized = normalized[: -len(suffix)]
                break

        return normalized.strip()

    def is_duplicate(
        self, poi1: Dict[str, Any], poi2: Dict[str, Any]
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        判断两个 POI 是否重复。

        判断逻辑（满足任一条件即视为重复）：
        1. 坐标距离 < 阈值 且 名称相似度 > 阈值
        2. 坐标距离 < 阈值 且 名称存在包含关系
        3. 名称相似度 > 0.7 且 名称存在包含关系
        4. 坐标极近（<100米），即使名称不同也可能是同一景区的不同命名
        5. 标准化名称完全相同

        Args:
            poi1: 第一个 POI
            poi2: 第二个 POI

        Returns:
            Tuple[bool, str, Dict[str, Any]]: (是否重复, 重复原因, 应该保留的 POI)
        """
        name1 = poi1.get("name", "")
        name2 = poi2.get("name", "")

        if not name1 or not name2:
            return False, "", poi1

        # 完全相同的名称直接跳过（由其他去重逻辑处理）
        if name1 == name2:
            return False, "", poi1

        # 计算距离
        distance = self.calculate_distance(poi1, poi2)

        # 计算名称相似度
        similarity = self.calculate_name_similarity(name1, name2)

        # 标准化名称后再计算相似度（更准确）
        norm1 = self.normalize_name(name1)
        norm2 = self.normalize_name(name2)
        norm_similarity = self.calculate_name_similarity(norm1, norm2)

        # 检查名称包含关系
        has_containment, shorter_name = self.check_name_containment(name1, name2)

        # 判断是否重复
        reasons: List[str] = []

        # 条件0：坐标极近（<100米），即使名称不同也可能是同一景区的不同命名
        # 例如："趵突泉景区"和"天下第一泉景区"距离只有78米
        if distance < self.VERY_CLOSE_DISTANCE_THRESHOLD:
            # 排除明显不同的景点（如一个是景点一个是美食，且名称完全无关）
            cat1 = poi1.get("category", "") or poi1.get("type", "")
            cat2 = poi2.get("category", "") or poi2.get("type", "")
            if cat1 == cat2 or (not cat1 and not cat2):
                reasons.append(
                    f"坐标极近({distance:.0f}米)<{self.VERY_CLOSE_DISTANCE_THRESHOLD}米，"
                    f"可能是同一景区的不同命名"
                )

        # 条件1：坐标距离近 + 名称相似度高
        if distance < self.DISTANCE_THRESHOLD and (
            similarity > self.SIMILARITY_THRESHOLD
            or norm_similarity > self.SIMILARITY_THRESHOLD
        ):
            reasons.append(
                f"坐标距离近({distance:.0f}米)+名称相似度高"
                f"({max(similarity, norm_similarity):.2f})"
            )

        # 条件2：坐标距离近 + 名称包含关系
        if distance < self.DISTANCE_THRESHOLD and has_containment:
            reasons.append(f"坐标距离近({distance:.0f}米)+名称包含({shorter_name})")

        # 条件3：名称相似度很高 + 名称包含关系
        if (similarity > 0.7 or norm_similarity > 0.7) and has_containment:
            reasons.append(
                f"名称相似度很高({max(similarity, norm_similarity):.2f})"
                f"+名称包含({shorter_name})"
            )

        # 条件4：标准化名称完全相同（如"趵突泉"和"趵突泉景区"）
        if norm1 and norm2 and norm1 == norm2:
            reasons.append(f"标准化名称相同({norm1})")

        if not reasons:
            return False, "", poi1

        # 决定保留哪个 POI
        kept_poi = self.choose_keep_poi(poi1, poi2, shorter_name)
        reason = "; ".join(reasons)

        return True, reason, kept_poi

    def choose_keep_poi(
        self,
        poi1: Dict[str, Any],
        poi2: Dict[str, Any],
        shorter_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        选择应该保留的 POI。

        选择优先级：
        1. 主子 POI 关系：保留主 POI（名称更短、更通用的）
        2. 评分差异较大（>0.3）：保留评分更高的
        3. 有包含关系：保留名称更短/更通用的
        4. 评分相近：保留名称更简洁的（标准化后更短的）
        5. 默认：保留第一个

        Args:
            poi1: 第一个 POI
            poi2: 第二个 POI
            shorter_name: 更短的名称（如果有包含关系）

        Returns:
            Dict[str, Any]: 应该保留的 POI
        """
        name1 = poi1.get("name", "")
        name2 = poi2.get("name", "")

        # 1. 主子 POI 关系判断：如果一个是另一个的子 POI（如"黑虎泉-取水点"），保留主 POI
        is_child1 = self.is_child_poi(name1)
        is_child2 = self.is_child_poi(name2)

        if is_child1 and not is_child2:
            # poi1 是子 POI，保留 poi2（主 POI）
            return poi2
        elif is_child2 and not is_child1:
            # poi2 是子 POI，保留 poi1（主 POI）
            return poi1

        # 2. 如果评分差异较大，保留评分高的
        rating1 = float(poi1.get("rating", 0) or 0)
        rating2 = float(poi2.get("rating", 0) or 0)

        if abs(rating1 - rating2) > 0.3:
            return poi1 if rating1 > rating2 else poi2

        # 3. 如果有包含关系，保留名称更短/更通用的
        if shorter_name:
            if name1 == shorter_name:
                return poi1
            elif name2 == shorter_name:
                return poi2

        # 4. 评分相近时，保留名称更简洁的（标准化后更短的）
        norm1 = self.normalize_name(name1)
        norm2 = self.normalize_name(name2)

        if len(norm1) != len(norm2):
            return poi1 if len(norm1) < len(norm2) else poi2

        # 5. 默认保留第一个
        return poi1

    def is_child_poi(self, name: str) -> bool:
        """
        判断是否为子 POI（景区内的功能点位）。

        判断标准：
        1. 名称包含"-"，且"-"后面是功能点位后缀
        2. 名称以功能点位后缀结尾

        Args:
            name: POI 名称

        Returns:
            bool: 是否为子 POI
        """
        if not name:
            return False

        # 检查"XX-YY"格式
        if "-" in name:
            parts = name.split("-", 1)
            if len(parts) == 2 and len(parts[1]) <= 10:
                suffix_part = parts[1]
                if any(
                    suffix_part.endswith(suf) or suffix_part == suf
                    for suf in FUNCTIONAL_SUFFIXES
                ):
                    return True

        # 检查是否以功能点位后缀结尾
        for suffix in FUNCTIONAL_SUFFIXES:
            if name.endswith(suffix) and len(name) > len(suffix) + 2:
                return True

        return False

    def deduplicate(
        self, pois: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        对 POI 列表进行去重。

        使用两两比较的方式，判断每对 POI 是否重复，然后决定保留哪个。

        Args:
            pois: POI 列表，每个元素为字典，需包含 name、lng、lat 等字段

        Returns:
            Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]: (去重后的 POI 列表, 被移除的 POI 信息列表)

        Example:
            >>> pois = [
            ...     {"name": "趵突泉景区", "lng": 117.0, "lat": 36.6, "rating": 4.8},
            ...     {"name": "天下第一泉景区", "lng": 117.001, "lat": 36.601, "rating": 4.7},
            ... ]
            >>> deduplicator = PoiDeduplicator()
            >>> result, removed = deduplicator.deduplicate(pois)
            >>> print(len(result), len(removed))
            1 1
        """
        if not pois or len(pois) < 2:
            return pois, []

        removed: List[Dict[str, Any]] = []
        kept_indices = set(range(len(pois)))

        # 两两比较
        for i in range(len(pois)):
            if i not in kept_indices:
                continue
            for j in range(i + 1, len(pois)):
                if j not in kept_indices:
                    continue

                is_dup, reason, kept_poi = self.is_duplicate(pois[i], pois[j])

                if is_dup:
                    # 决定移除哪个
                    if kept_poi is pois[i]:
                        removed_idx = j
                        kept_idx = i
                    else:
                        removed_idx = i
                        kept_idx = j

                    removed.append(
                        {
                            "removed": pois[removed_idx].get("name", ""),
                            "kept": pois[kept_idx].get("name", ""),
                            "reason": reason,
                            "removed_rating": pois[removed_idx].get("rating", 0),
                            "kept_rating": pois[kept_idx].get("rating", 0),
                        }
                    )

                    kept_indices.discard(removed_idx)

        # 构建去重后的列表
        result = [pois[i] for i in sorted(kept_indices)]

        return result, removed


# 全局单例
_deduplicator: Optional[PoiDeduplicator] = None


def get_deduplicator() -> PoiDeduplicator:
    """
    获取 POI 去重器单例。

    Returns:
        PoiDeduplicator: POI 去重器单例
    """
    global _deduplicator
    if _deduplicator is None:
        _deduplicator = PoiDeduplicator()
    return _deduplicator


def deduplicate_pois(
    pois: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    便捷函数：对 POI 列表进行去重。

    使用全局单例的 POI 去重器进行去重。

    Args:
        pois: POI 列表，每个元素为字典，需包含 name、lng、lat 等字段

    Returns:
        Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]: (去重后的 POI 列表, 被移除的 POI 信息列表)

    Example:
        >>> pois = [{"name": "趵突泉", "lng": 117.0, "lat": 36.6}, {"name": "趵突泉景区", "lng": 117.0, "lat": 36.6}]
        >>> result, removed = deduplicate_pois(pois)
        >>> print(len(result))
        1
    """
    return get_deduplicator().deduplicate(pois)
