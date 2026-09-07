"""
接口数据模型模块（Pydantic）。

定义所有 API 接口的请求和响应数据模型，使用 Pydantic 进行数据验证和序列化。

功能特性：
- 请求模型（行程规划、路径规划、探索、对话）
- 响应模型（POI、探索结果、行程规划、每日计划）
- 字段验证（范围、默认值、描述）
- 嵌套模型（POI、PlanItem、DayPlan）

使用方式：
    from app.data.models.models import (
        PlanRequest, PlanResponse, POI, DayPlan, PlanItem,
        ChatPlanRequest, ChatPlanResponse, ExploreRequest, ExploreResponse
    )

    # 创建行程规划请求
    request = PlanRequest(destination="杭州", days=3, travelers=2)

    # 创建行程规划响应
    response = PlanResponse(
        destination="杭州",
        days=3,
        day_plans=[...],
        all_pois=[...]
    )
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ---------- 请求模型 ----------


class PlanRequest(BaseModel):
    """
    行程规划请求模型。

    包含行程规划所需的所有参数，包括目的地、时间、人数、预算、风格等。

    Example:
        >>> request = PlanRequest(
        ...     destination="杭州",
        ...     days=3,
        ...     travelers=2,
        ...     group_type="情侣",
        ...     budget_level="适中",
        ...     style="美食+人文"
        ... )
    """

    destination: str = Field(
        ...,
        description="目的地（必须有）：全国/省/市/区县/具体地点，如：杭州",
    )
    days: int = Field(
        3,
        ge=1,
        le=15,
        description="出行时间跨度（天），默认 2~3 天；大跨度（月/年）收束后用于每省精华天数",
    )
    span_unit: str = Field(
        "day",
        description="原始时间跨度单位：day/week/month/year，默认 day",
    )
    span_value: int = Field(
        3,
        description="原始时间跨度数量（如 span_unit=month, span_value=2 表示2个月）",
    )
    origin: str = Field("", description="出发点（非必须），如：北京")
    travelers: int = Field(
        1, ge=1, le=99, description="出行人数（非必须），默认 1 人"
    )
    return_point: str = Field("", description="返回点（非必须），如：上海")
    return_station: str = Field(
        "",
        description="返程车站（非必须），如：济南站、济南西站、济南遥墙机场",
    )
    return_station_type: str = Field(
        "",
        description="返程车站类型：train（火车站）/airport（机场）/bus（汽车站），默认自动识别",
    )
    return_departure_time: str = Field(
        "",
        description="返程出发时间（非必须），如：18:00，用于最后一天行程时间安排",
    )
    group_type: str = Field("单人", description="单人/情侣/亲子/家庭/朋友/老人")
    budget_level: str = Field("适中", description="经济/适中/舒适/奢华")
    style: str = Field(
        "美食+人文", description="旅行风格：美食/人文/网红/小众/亲子/自然"
    )
    pace: str = Field("适中", description="节奏：轻松/适中/暴走")
    traffic_mode: str = Field(
        "公共交通", description="出行方式：自驾/公共交通/骑行/步行/混合，默认公共交通"
    )
    daily_start_time: str = Field("09:00", description="每日出发时间")
    daily_end_time: str = Field("21:00", description="每日结束时间")
    must_include_poi: List[str] = Field(
        default_factory=list, description="必去点位名称"
    )
    exclude_poi: List[str] = Field(default_factory=list, description="排除点位名称")
    interests: List[str] = Field(
        default_factory=list, description="兴趣标签，如 [博物馆, 夜景, 购物]"
    )
    plan_strategy: str = Field(
        "traditional",
        description="规划策略：traditional（传统按天分配）/ spatial_temporal（先空间整体规划再时间拆分），默认 traditional",
    )


class RouteRequest(BaseModel):
    """
    路径规划请求模型。

    Example:
        >>> request = RouteRequest(
        ...     origin=[120.15, 30.28],
        ...     destination=[120.17, 30.30],
        ...     traffic_mode="混合"
        ... )
    """

    origin: List[float] = Field(..., description="起点 [lng, lat]")
    destination: List[float] = Field(..., description="终点 [lng, lat]")
    traffic_mode: str = Field("混合", description="自驾/公共交通/混合")


class ExploreRequest(BaseModel):
    """
    探索功能请求模型。

    用于地图选点后，以该位置为中心点检索周围可去的景点。

    Example:
        >>> request = ExploreRequest(
        ...     lng=120.15,
        ...     lat=30.28,
        ...     radius=10000,
        ...     categories=["景点"]
        ... )
    """

    lng: float = Field(..., description="中心点经度")
    lat: float = Field(..., description="中心点纬度")
    radius: int = Field(
        10_000, ge=1000, le=50_000, description="检索半径（米）"
    )
    categories: List[str] = Field(
        default_factory=lambda: ["景点"],
        description="类别：景点/美食/购物/夜生活",
    )


class ChatMessage(BaseModel):
    """
    对话消息模型。

    Example:
        >>> message = ChatMessage(role="user", content="我想去杭州玩3天")
    """

    role: str = Field("user", description="user / assistant")
    content: str = Field("", description="消息文本")


class ChatPlanRequest(BaseModel):
    """
    对话式规划请求模型。

    包含对话历史，用于多轮对话式行程规划。

    Example:
        >>> request = ChatPlanRequest(
        ...     messages=[
        ...         ChatMessage(role="user", content="我想去杭州玩"),
        ...         ChatMessage(role="assistant", content="好的，请问您想玩几天？"),
        ...         ChatMessage(role="user", content="3天")
        ...     ]
        ... )
    """

    messages: List[ChatMessage] = Field(
        default_factory=list, description="对话历史（含多轮）"
    )


class ChatPlanResponse(BaseModel):
    """
    对话式规划响应模型。

    包含助手回复、解析出的规划参数、以及生成的行程规划。

    Example:
        >>> response = ChatPlanResponse(
        ...     ready=True,
        ...     reply="好的，已为您规划杭州3天行程",
        ...     params={"destination": "杭州", "days": 3},
        ...     plan=PlanResponse(...)
        ... )
    """

    ready: bool = Field(False, description="是否已具备生成条件（能定位目的地）")
    reply: str = Field("", description="助手回复文本")
    params: Dict[str, Any] = Field(default_factory=dict, description="解析出的规划参数")
    plan: Optional["PlanResponse"] = None
    usage_info: Optional[Dict[str, Any]] = Field(None, description="调用次数使用情况")


# ---------- 响应模型 ----------


class POI(BaseModel):
    """
    兴趣点（Point of Interest）模型。

    包含景点、美食、购物、夜生活等地点的详细信息。

    Example:
        >>> poi = POI(
        ...     id="1",
        ...     name="西湖",
        ...     lng=120.15,
        ...     lat=30.28,
        ...     category="景点",
        ...     rating=4.8
        ... )
    """

    id: str
    name: str
    lng: float
    lat: float
    address: str = ""
    category: str = "景点"  # 景点 / 美食 / 购物 / 夜生活 / 酒店
    price: float = 0.0  # 人均 / 门票参考价
    rating: float = 0.0
    district: str = ""  # 所属区县（高德 adname），用于跨天区域去重
    source: str = "amap"  # amap=真实高德 / tencent=真实腾讯
    # 三层POI扩展字段（精细点位体系）
    inner_route: List[Dict[str, Any]] = Field(
        default_factory=list, description="景区内部游览动线"
    )
    nearby_attractions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="周边附属点位（美食街/老街/市井等）",
    )
    poi_level: str = ""  # 景区级别（5A/4A/无）
    recommended_duration: int = 0  # 建议游玩时长（分钟）
    best_time: str = ""  # 最佳游玩时间
    avoid_tips: List[str] = Field(default_factory=list, description="避坑提示")
    has_hierarchy: bool = False  # 是否有三层POI数据
    open_hours: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="开放时间列表 [{day_of_week, open_time, close_time, is_closed, note}]",
    )
    description: str = ""  # 景点描述/简介
    must_visit: bool = False  # 是否是必去景点（地标/必打卡）
    hot: bool = False  # 是否是热门景点

    @field_validator('open_hours', 'inner_route', 'nearby_attractions', 'avoid_tips', mode='before')
    @classmethod
    def parse_json_list_fields(cls, v):
        """把字符串格式的JSON列表转换成列表，处理数据库中存储的字符串格式。"""
        if v is None:
            return []
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            # 如果是开放时间字符串，转换成列表格式
            if v.strip() and not v.strip().startswith('['):
                return [{"note": v.strip()}]
            # 尝试解析JSON
            try:
                import json
                parsed = json.loads(v)
                return parsed if isinstance(parsed, list) else []
            except (json.JSONDecodeError, ValueError):
                return [{"note": v.strip()}] if v.strip() else []
        return []


class ExploreItem(POI):
    """
    探索功能的兴趣点模型（继承自 POI）。

    增加了距中心点距离字段，用于放射状可视化。

    Example:
        >>> item = ExploreItem(
        ...     id="1",
        ...     name="西湖",
        ...     lng=120.15,
        ...     lat=30.28,
        ...     distance_m=500
        ... )
    """

    distance_m: int = 0  # 距中心点距离（米），用于放射状可视化


class ExploreResponse(BaseModel):
    """
    探索功能响应模型。

    包含中心点、检索半径、POI 列表等信息。

    Example:
        >>> response = ExploreResponse(
        ...     center={"lng": 120.15, "lat": 30.28},
        ...     radius=10000,
        ...     count=10,
        ...     pois=[...]
        ... )
    """

    center: Dict[str, float] = Field(
        default_factory=lambda: {"lng": 120.15, "lat": 30.28}
    )
    radius: int = 10_000
    count: int = 0
    pois: List[ExploreItem] = Field(default_factory=list)
    source: str = "amap"  # amap=真实高德 / tencent=真实腾讯


class PlanItem(BaseModel):
    """
    行程规划项模型。

    表示一天中的某个行程安排，包括时间段、POI、时长、交通等信息。

    Example:
        >>> item = PlanItem(
        ...     slot="上午",
        ...     start_time="09:00",
        ...     poi=POI(...),
        ...     duration_min=120,
        ...     transport="步行"
        ... )
    """

    slot: str = "上午"  # 上午 / 中午 / 下午 / 晚上
    start_time: str = ""
    poi: POI
    duration_min: int = 120
    transport: str = ""  # 步行 / 驾车 / 公交地铁
    transit_min: int = 0  # 上一站到本站的路上耗时（分钟）
    distance_m: int = 0  # 上一站到本站距离（米）
    note: str = ""


class DayPlan(BaseModel):
    """
    每日行程计划模型。

    表示一天的完整行程安排，包括主题、日期、行程项、预算、住宿等。

    Example:
        >>> day_plan = DayPlan(
        ...     day=1,
        ...     theme="西湖之韵",
        ...     items=[...],
        ...     budget=500.0
        ... )
    """

    day: int
    theme: str = ""
    date_label: str = ""
    items: List[PlanItem] = Field(default_factory=list)
    budget: float = 0.0
    tip: str = ""
    inspiration: str = ""  # 每日寄语（旅程叙事：给这一天的出发力量）
    hotel: Optional[POI] = None  # 当晚住宿点（已废弃，保留向后兼容）
    hotel_area: Optional[Dict[str, Any]] = None  # 当晚住宿区域建议 {area_name, reason, center_lng, center_lat}


class PlanResponse(BaseModel):
    """
    行程规划响应模型。

    包含完整的行程规划结果，包括目的地、天数、每日计划、POI 列表、预算等。

    Example:
        >>> response = PlanResponse(
        ...     destination="杭州",
        ...     days=3,
        ...     day_plans=[...],
        ...     all_pois=[...],
        ...     total_budget=1500.0
        ... )
    """

    request_id: str = ""
    destination: str
    city_center: Dict[str, float] = Field(
        default_factory=lambda: {"lng": 116.407, "lat": 39.904}
    )
    days: int
    origin: str = ""
    travelers: int = 1
    return_point: str = ""
    group_type: str
    budget_level: str
    style: str
    pace: str
    traffic_mode: str = "公共交通"
    daily_start_time: str = "09:00"
    ai_model: str = ""  # 实际使用到的 AI 模型名
    source: str = "rule"  # ai=大模型生成 / rule=内置引擎
    weather: Dict[str, Any] = Field(default_factory=dict)
    departure_message: str = ""  # 出发宣言（旅程叙事：激发行走天下的勇气）
    day_plans: List[DayPlan] = Field(default_factory=list)
    all_pois: List[POI] = Field(default_factory=list)
    total_budget: float = 0.0
    budget_breakdown: Dict[str, Any] = Field(default_factory=dict)
    generated_at: str = ""
    span_summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="大时间跨度（月/年）的月度分配摘要，如 [{month:1, province:'海南省', reason:'冬季温暖避寒'}]",
    )
    # 质量评估相关字段
    quality_score: Optional[float] = Field(
        default=None, description="规划质量评估综合得分（0-100）"
    )
    quality_issues: List[str] = Field(
        default_factory=list, description="规划质量评估发现的问题列表"
    )
    quality_suggestions: List[str] = Field(
        default_factory=list, description="规划质量优化建议列表"
    )
    # 在线数据增强相关字段
    reservation_alerts: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="景点预约提醒列表（预约渠道、放票时间、开放时间、闭馆日、票价等）"
    )
    travel_tips: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="旅游避坑提示列表（防骗、交通、美食、住宿等提示）"
    )
    online_data_meta: Dict[str, Any] = Field(
        default_factory=dict,
        description="在线数据元信息（是否加载、置信度、数据来源统计等）"
    )
