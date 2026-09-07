"""
地图服务 - 天气模块。

从 amap.py 抽出的天气功能：
- weather：天气查询（缓存2小时，高德优先→腾讯兜底）
- weather_tips：天气出行提示

功能特性：
- 天气查询（实时天气、温度、风力）
- 天气出行提示（根据天气类型给出建议）
- TTL缓存（2小时，保证时效性）
- 高德/腾讯双Provider兼容（高德优先→腾讯兜底）

使用方式：
    from app.services.map.weather import weather, weather_tips

    # 查询天气
    result = await weather("杭州")
    print(result["weather"])  # 晴
    print(result["temperature"])  # 25℃
    print(result["tips"])  # 晴天紫外线较强，注意防晒补水。

    # 获取天气提示
    tips = weather_tips("晴")
    print(tips)  # 晴天紫外线较强，注意防晒补水。
"""
from typing import Any, Dict

from ...infrastructure.cache import TTL_WEATHER, cache, get_ttl
from .client import AMAP_BASE, TENCENT_BASE, amap_get, provider, tencent_get
from .geocode import geocode


async def weather(city: str, adcode: str = "") -> Dict[str, Any]:
    """
    天气查询 -> {weather, temperature, wind, tips}；失败返回通用提示。

    天气是快变量，缓存仅 2 小时，保证时效性。高德优先 → 腾讯兜底。

    Args:
        city: 城市名称
        adcode: 城市行政编码（可选，优先使用）

    Returns:
        Dict[str, Any]: 天气信息（city, weather, temperature, wind, tips）

    Example:
        >>> result = await weather("杭州")
        >>> print(result["weather"])
        晴
        >>> print(result["temperature"])
        25℃
    """
    prov = provider()
    cache_key = f"weather:{prov}:{city}:{adcode}"
    hit = cache.get("weather", cache_key, get_ttl("weather", TTL_WEATHER))
    if hit is not None:
        return hit
    if prov == "amap":
        data = await amap_get(
            f"{AMAP_BASE}/weather/weatherInfo", {"city": adcode or city}
        )
        if data and data.get("lives"):
            lv = data["lives"][0]
            result = {
                "city": lv.get("city", city),
                "weather": lv.get("weather", ""),
                "temperature": f"{lv.get('temperature', '')}℃",
                "wind": f"{lv.get('winddirection', '')}风{lv.get('windpower', '')}级",
                "tips": weather_tips(lv.get("weather", "")),
            }
            cache.set("weather", cache_key, result)
            return result
    if prov == "tencent":
        geo = await geocode(city)
        if geo and geo.get("lng"):
            data = await tencent_get(
                f"{TENCENT_BASE}/weather/v1/",
                {"location": f"{geo['lat']},{geo['lng']}"},
            )
            rt = {}
            if data:
                rt = (data.get("result") or {}).get("realtime") or {}
            if rt:
                w = rt.get("weather", "")
                result = {
                    "city": rt.get("province") or city,
                    "weather": w,
                    "temperature": f"{rt.get('temperature', '')}℃",
                    "wind": f"{rt.get('wind_direction', '')}风{rt.get('wind_power', '')}级",
                    "tips": weather_tips(w),
                }
                cache.set("weather", cache_key, result)
                return result
    return {
        "city": city,
        "weather": "",
        "temperature": "",
        "wind": "",
        "tips": "未获取到实时天气，出行前建议关注当地天气预报。",
    }


def weather_tips(w: str) -> str:
    """
    根据天气类型给出出行提示。

    Args:
        w: 天气类型（晴/雨/雪/云/阴等）

    Returns:
        str: 出行提示

    Example:
        >>> tips = weather_tips("晴")
        >>> print(tips)
        晴天紫外线较强，注意防晒补水。
    """
    if "雨" in w:
        return "有降水，记得带伞，景点地面湿滑注意安全。"
    if "雪" in w:
        return "有降雪，注意保暖和防滑。"
    if "晴" in w:
        return "晴天紫外线较强，注意防晒补水。"
    if "云" in w or "阴" in w:
        return "多云天气，体感舒适，适合户外游玩。"
    return "出行前关注实时天气，合理安排行程。"
