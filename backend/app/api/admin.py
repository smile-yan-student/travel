# -*- coding: utf-8 -*-
"""
管理后台路由模块。

提供管理后台相关的接口：/api/admin/*。

模块划分（对应规划文档 M1-M9）：
  M1 登录与权限（/login /me /admins）  M2 仪表盘（/dashboard）
  M3 用户管理（/users）                M4 行程与足迹（/trips）
  M5 对话运营（/conversations）         M6 内容与景点（/must-visit /cities）
  M7 AI 模型（/ai）                    M8 高德与缓存（/amap /cache）
  M9 系统配置（/config）

功能特性：
- 管理员登录与权限管理（JWT token、角色权限）
- 仪表盘（用户统计、行程统计、对话统计、AI调用统计）
- 用户管理（用户列表、用户详情、禁用/启用用户）
- 行程与足迹管理（行程列表、行程详情、删除行程）
- 对话运营（对话列表、对话详情、删除对话）
- 内容与景点管理（必去地标、城市配置、POI层级）
- AI模型管理（模型列表、模型配置、模型性能统计）
- 高德与缓存管理（API Key管理、缓存统计、缓存清理）
- 系统配置（品牌文案、TTL配置、其他系统配置）
- 管理员鉴权（所有管理后台接口需要管理员登录）

使用方式：
    from app.api.admin import router

    # 在FastAPI应用中注册路由
    app.include_router(router)

    # POST /api/admin/login 管理员登录
    # GET /api/admin/me 获取当前管理员信息
    # GET /api/admin/dashboard 获取仪表盘数据
    # GET /api/admin/users 获取用户列表
    # GET /api/admin/trips 获取行程列表
    # GET /api/admin/conversations 获取对话列表
    # GET /api/admin/must-visit 获取必去地标列表
    # GET /api/admin/ai 获取AI模型配置
    # GET /api/admin/amap 获取高德配置
    # GET /api/admin/config 获取系统配置
"""
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from ..ai import ai as ai_mod
from ..config import settings
from ..core import geo_local
from ..data.repositories import admin_repository
from ..infrastructure import logger as log_mod
from ..infrastructure.cache import cache
from ..services import map as amap

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ---------------- 鉴权依赖 ----------------

def _admin_from_header(authorization: str = Header(default="")) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "未登录")
    admin = admin_repository.admin_by_token(authorization[7:])
    if not admin:
        raise HTTPException(401, "登录已失效，请重新登录")
    return admin


def _super_required(admin: dict = Depends(_admin_from_header)) -> dict:
    if admin["role"] != "super":
        raise HTTPException(403, "需要超级管理员权限")
    return admin


# ---------------- M1 登录与权限 ----------------

class LoginBody(BaseModel):
    username: str
    password: str


class AdminCreateBody(BaseModel):
    username: str
    password: str
    role: str = "ops"


class StatusBody(BaseModel):
    enabled: bool


class ResetPwBody(BaseModel):
    password: str


@router.post("/login")
def admin_login(body: LoginBody):
    res = admin_repository.admin_login(body.username, body.password)
    if not res:
        raise HTTPException(401, "用户名或密码错误，或账号已停用")
    return res


@router.get("/me")
def admin_me(admin: dict = Depends(_admin_from_header)):
    return {"admin": admin}


@router.get("/admins")
def list_admins(_: dict = Depends(_super_required)):
    return {"items": admin_repository.list_admins()}


@router.post("/admins")
def create_admin(body: AdminCreateBody, _: dict = Depends(_super_required)):
    if body.role not in ("super", "ops"):
        raise HTTPException(400, "角色只能是 super 或 ops")
    admin, err = admin_repository.create_admin(body.username, body.password, body.role)
    if err:
        raise HTTPException(400, err)
    return {"admin": admin}


@router.put("/admins/{aid}/status")
def set_admin_status(aid: int, body: StatusBody, _: dict = Depends(_super_required)):
    if not admin_repository.set_admin_enabled(aid, body.enabled):
        raise HTTPException(404, "管理员不存在")
    return {"ok": True, "enabled": body.enabled}


@router.post("/admins/{aid}/reset-password")
def reset_admin_password(aid: int, body: ResetPwBody, _: dict = Depends(_super_required)):
    if not admin_repository.reset_admin_password(aid, body.password):
        raise HTTPException(400, "密码至少 8 位或管理员不存在")
    return {"ok": True}


# ---------------- M2 仪表盘 ----------------

@router.get("/dashboard")
async def dashboard(_: dict = Depends(_admin_from_header)):
    from ..data.repositories import user_repository
    now = time.time()
    ns_counts = cache.counts()
    try:
        stats = _db_dashboard()
    except Exception:
        stats = {}
    return {
        "stats": stats,
        "amap_ready": settings.amap_ready,
        "amap_mode": "real" if settings.amap_ready else "unavailable",
        "ai_available": ai_mod.ai_available(),
        "ai_model": ai_mod.resolve_model() if ai_mod.ai_available() else "",
        "cache": {"total": cache.size(), "by_type": ns_counts},
        "ts": now,
    }


def _db_dashboard() -> dict:
    import pymysql
    from ..config import settings as cfg
    conn = pymysql.connect(
        host=cfg.db_host, port=cfg.db_port, user=cfg.db_user,
        password=cfg.db_password, database=cfg.db_name, charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor, autocommit=True,
    )
    try:
        with conn.cursor() as cur:
            out = {}
            cur.execute("SELECT COUNT(*) AS c FROM users")
            out["users_total"] = cur.fetchone()["c"]
            cur.execute(
                "SELECT COUNT(*) AS c FROM users WHERE created_at >= (NOW() - INTERVAL 7 DAY)"
            )
            out["users_new_7d"] = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) AS c FROM trips")
            out["trips_total"] = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(DISTINCT destination) AS c FROM trips")
            out["cities_total"] = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) AS c FROM conversations")
            out["conv_total"] = cur.fetchone()["c"]
            cur.execute("SELECT COALESCE(SUM(JSON_LENGTH(messages)),0) AS c FROM conversations")
            out["conv_msgs_total"] = cur.fetchone()["c"]
            return out
    finally:
        conn.close()


# ---------------- M3 用户管理 ----------------

@router.get("/users")
def list_users(page: int = 1, size: int = 20, keyword: str = "",
               _: dict = Depends(_admin_from_header)):
    size = min(max(size, 1), 100)
    return admin_repository.list_users(keyword, page, size)


@router.get("/users/{uid}")
def get_user_detail(uid: int, _: dict = Depends(_admin_from_header)):
    detail = admin_repository.user_detail(uid)
    if not detail:
        raise HTTPException(404, "用户不存在")
    return detail


@router.put("/users/{uid}/status")
def set_user_status(uid: int, body: StatusBody, _: dict = Depends(_admin_from_header)):
    if not admin_repository.set_user_enabled(uid, body.enabled):
        raise HTTPException(404, "用户不存在")
    return {"ok": True, "enabled": body.enabled}


# ---------------- M4 行程与足迹 ----------------

@router.get("/trips")
def list_trips(destination: str = "", page: int = 1, size: int = 20,
               _: dict = Depends(_admin_from_header)):
    size = min(max(size, 1), 100)
    return admin_repository.list_trips(destination, page, size)


@router.get("/trips/stats")
def trips_stats(_: dict = Depends(_admin_from_header)):
    return admin_repository.trips_stats()


# ---------------- M5 对话运营 ----------------

@router.get("/conversations")
def list_convos(keyword: str = "", page: int = 1, size: int = 20,
                _: dict = Depends(_admin_from_header)):
    size = min(max(size, 1), 100)
    return admin_repository.list_convos(keyword, page, size)


@router.get("/conversations/stats")
def convo_stats(_: dict = Depends(_admin_from_header)):
    return admin_repository.convo_stats()


@router.get("/conversations/{cid}")
def get_convo_detail(cid: int, _: dict = Depends(_admin_from_header)):
    detail = admin_repository.convo_detail(cid)
    if not detail:
        raise HTTPException(404, "会话不存在")
    return detail


# ---------------- M6 内容与景点管理 ----------------

class MustVisitBody(BaseModel):
    city: str
    name: str
    kw: str = ""
    category: str = "景点"
    rating: float = 4.5
    priority: int = 50


class MustVisitPatch(BaseModel):
    city: Optional[str] = None
    name: Optional[str] = None
    kw: Optional[str] = None
    category: Optional[str] = None
    rating: Optional[float] = None
    priority: Optional[int] = None


@router.get("/must-visit")
def list_must_visit(city: str = "", _: dict = Depends(_admin_from_header)):
    items = admin_repository.get_must_visit(city) or []
    return {"items": items, "total": len(items)}


@router.post("/must-visit")
def add_must_visit(body: MustVisitBody, _: dict = Depends(_admin_from_header)):
    item, err = admin_repository.add_must_visit(
        body.city, body.name, body.category, body.rating, body.kw, body.priority
    )
    if err:
        raise HTTPException(400, err)
    return {"item": item}


@router.put("/must-visit/{mid}")
def update_must_visit(mid: int, body: MustVisitPatch, _: dict = Depends(_admin_from_header)):
    fields = {k: v for k, v in body.dict().items() if v is not None}
    if not admin_repository.update_must_visit(mid, fields):
        raise HTTPException(404, "条目不存在")
    return {"ok": True}


@router.delete("/must-visit/{mid}")
def delete_must_visit(mid: int, _: dict = Depends(_admin_from_header)):
    if not admin_repository.delete_must_visit(mid):
        raise HTTPException(404, "条目不存在")
    return {"ok": True}


@router.get("/cities")
def list_cities(_: dict = Depends(_admin_from_header)):
    items = [{"city": c, "lng": v[0], "lat": v[1]} for c, v in amap.CITY_CENTERS.items()]
    return {"items": items, "total": len(items)}


# ---------------- M7 AI 模型管理 ----------------

@router.get("/ai")
def ai_status(_: dict = Depends(_admin_from_header)):
    available = ai_mod.ai_available()
    return {
        "ai_available": available,
        "current_model": ai_mod.resolve_model() if available else "",
        "model_config": settings.ollama_model,
        "base_url": settings.ollama_base_url,
    }


@router.get("/ai/logs")
def ai_logs(limit: int = 50, _: dict = Depends(_admin_from_header)):
    return {"items": admin_repository.list_gen_logs(limit)}


# ---------------- M8 高德与缓存管理 ----------------

class AmapKeyBody(BaseModel):
    amap_key: str = ""


def _amap_status_payload() -> dict:
    from . import config as config_mod
    key = settings.amap_key
    src = config_mod.amap_key_source()
    masked = (key[:6] + "****" + key[-4:]) if len(key) > 10 else ("已配置" if key else "")
    return {
        "amap_ready": settings.amap_ready,
        "mode": "real" if settings.amap_ready else "unavailable",
        "key_configured": bool(key),
        "key_source": src,          # site=后台配置 / env=环境变量 / none=未配置
        "key_masked": masked,
    }


def _tencent_status_payload() -> dict:
    from . import config as config_mod
    key = settings.tencent_key
    src = config_mod.tencent_key_source()
    masked = (key[:6] + "****" + key[-4:]) if len(key) > 10 else ("已配置" if key else "")
    return {
        "tencent_ready": settings.tencent_ready,
        "tencent_mode": "real" if settings.tencent_ready else "unavailable",
        "tencent_key_configured": bool(key),
        "tencent_key_source": src,      # site=后台配置 / env=环境变量 / none=未配置
        "tencent_key_masked": masked,
    }


@router.get("/amap")
def amap_status(_: dict = Depends(_admin_from_header)):
    """高德与腾讯双 Provider 状态（兼容旧字段，新增 tencent_* / provider）。"""
    from ..services import map as amap_mod
    payload = _amap_status_payload()
    payload.update(_tencent_status_payload())
    payload["provider"] = amap_mod.provider()  # amap / tencent / none
    return payload


class AmapKeyBody(BaseModel):
    amap_key: str = ""


class TencentKeyBody(BaseModel):
    tencent_key: str = ""


@router.post("/amap/key")
async def set_amap_key(body: AmapKeyBody, _: dict = Depends(_super_required)):
    """保存/更新高德 Web 服务 Key（仅超级管理员）：持久化到 site_config，
    运行时立即覆盖生效，重新探测有效性并清空旧缓存（旧 Key 缓存不可信）。"""
    from . import cache as cache_mod
    from . import config as config_mod
    from ..config import set_amap_effective as set_eff

    new_key = (body.amap_key or "").strip()
    admin_repository.set_config({"amap_key": new_key})
    config_mod.set_amap_key(new_key)
    cache_mod.cache.clear()          # 换 Key 后清空旧 POI/geo 缓存
    ok = await amap.probe_amap()
    set_eff(ok)
    return {"ok": True, "probed": ok, ** _amap_status_payload()}


@router.post("/tencent/key")
async def set_tencent_key(body: TencentKeyBody, _: dict = Depends(_super_required)):
    """保存/更新腾讯地图 Key（仅超级管理员）：持久化到 site_config，
    运行时立即覆盖生效，重新探测有效性并清空旧缓存。"""
    from . import cache as cache_mod
    from . import config as config_mod
    from ..config import set_tencent_effective as set_eff

    new_key = (body.tencent_key or "").strip()
    admin_repository.set_config({"tencent_key": new_key})
    config_mod.set_tencent_key(new_key)
    cache_mod.cache.clear()
    ok = await amap.probe_tencent()
    set_eff(ok)
    return {"ok": True, "probed": ok, ** _tencent_status_payload()}


@router.get("/cache")
def cache_status(_: dict = Depends(_admin_from_header)):
    return {
        "total": cache.size(),
        "by_type": cache.counts(),
        "ttl": {
            "geo": getattr(__import__("app.cache", fromlist=["TTL_GEO"]), "TTL_GEO", 0),
            "poi": getattr(__import__("app.cache", fromlist=["TTL_POI"]), "TTL_POI", 0),
            "route": getattr(__import__("app.cache", fromlist=["TTL_ROUTE"]), "TTL_ROUTE", 0),
            "weather": getattr(__import__("app.cache", fromlist=["TTL_WEATHER"]), "TTL_WEATHER", 0),
        },
    }


@router.post("/cache/clear")
def cache_clear(_: dict = Depends(_admin_from_header)):
    cache.clear()
    return {"ok": True, "total": 0}


# ---------------- M8.5 本地行政区域数据 ----------------

@router.get("/geo/stats")
def geo_stats(_: dict = Depends(_admin_from_header)):
    """查看本地行政区域数据统计（版本/条数/adcode 覆盖率）"""
    return geo_local.stats()


@router.post("/geo/refresh")
async def geo_refresh(_: dict = Depends(_admin_from_header)):
    """触发全量更新：从高德 district_query 拉取全国省/市/区县，补充 adcode 和完整层级。

    注意：需要 AMAP_KEY 可用；全量拉取约 3000+ 条，耗时 5-15 秒。
    """
    if not settings.amap_key:
        raise HTTPException(400, "未配置 AMAP_KEY，无法从高德拉取全量数据")
    try:
        from scripts.update_admin_divisions import fetch_all_divisions
        result = await fetch_all_divisions()
        by_name = result["by_name"]
        by_adcode = result["by_adcode"]
        # 写入文件
        import json
        from datetime import date
        from pathlib import Path
        data_path = Path(__file__).resolve().parent / "data" / "admin_divisions.json"
        # 备份
        if data_path.exists():
            backup = data_path.with_suffix(f".json.bak.{date.today().isoformat()}")
            data_path.rename(backup)
        stats = {
            "province": sum(1 for e in by_name.values() if e["level"] == "province"),
            "city": sum(1 for e in by_name.values() if e["level"] == "city"),
            "district": sum(1 for e in by_name.values() if e["level"] == "district"),
            "with_adcode": sum(1 for e in by_name.values() if e["adcode"]),
        }
        output = {
            "version": f"amap-{date.today().isoformat()}",
            "updated_at": date.today().isoformat(),
            "source": "高德 district_query 全量拉取（后台触发）",
            "by_name": by_name,
            "by_adcode": by_adcode,
            "stats": stats,
        }
        data_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        geo_local._reload()
        return {"ok": True, "stats": geo_local.stats()}
    except Exception as e:
        raise HTTPException(500, f"全量更新失败: {e}")


# ---------------- M9 系统配置 ----------------

class ConfigBody(BaseModel):
    brand_slogan: Optional[str] = None
    brand_hero: Optional[str] = None
    brand_footer: Optional[str] = None
    ttl_geo_days: Optional[str] = None
    ttl_poi_days: Optional[str] = None
    ttl_route_min: Optional[str] = None
    ttl_weather_h: Optional[str] = None


@router.get("/config")
def get_config(_: dict = Depends(_admin_from_header)):
    return admin_repository.get_config(include_secret=True)


@router.put("/config")
def put_config(body: ConfigBody, _: dict = Depends(_admin_from_header)):
    pairs = {k: v for k, v in body.dict().items() if v is not None}
    if not pairs:
        raise HTTPException(400, "无配置项")
    admin_repository.set_config(pairs)
    # TTL 配置立即同步到缓存模块（对新缓存生效）
    _apply_ttl(pairs)
    return {"ok": True, "config": admin_repository.get_config()}


@router.get("/logs")
def admin_logs(level: str = "", keyword: str = "", limit: int = 200,
                _: dict = Depends(_admin_from_header)):
    """M10 日志监控：查询最近的结构化日志（支持按级别/关键词过滤）。

    读取今天和昨天的 JSON 日志文件，返回最新的 limit 条。
    level: DEBUG/INFO/WARNING/ERROR（空=全部）
    keyword: 在消息和字段值中模糊搜索
    """
    entries = log_mod.read_recent_logs(level=level, keyword=keyword, limit=limit)
    # 统计各级别数量
    level_counts = {}
    for e in entries:
        lv = e.get("level", "UNKNOWN")
        level_counts[lv] = level_counts.get(lv, 0) + 1
    return {
        "total": len(entries),
        "level_counts": level_counts,
        "logs": entries,
    }


def _apply_ttl(pairs: dict) -> None:
    from . import cache as cache_mod
    mapping = {
        "ttl_geo_days": ("geo", 24 * 3600),
        "ttl_poi_days": ("poi", 24 * 3600),
        "ttl_route_min": ("route", 60),
        "ttl_weather_h": ("weather", 3600),
    }
    for k, (ns, factor) in mapping.items():
        if k in pairs:
            try:
                cache_mod.set_ttl(ns, float(pairs[k]) * factor)
            except (TypeError, ValueError):
                pass


# ---------------- M8 POI数据测试 ----------------

@router.get("/poi-test")
async def poi_test(
    city: str,
    types: str = "110200",
    pages: int = 3,
    _: dict = Depends(_admin_from_header),
):
    """M8 POI数据测试：测试高德POI检索能力，查看数据覆盖情况。

    Args:
        city: 城市名称（如：休宁、杭州、北京）
        types: POI类型代码（默认110200=风景名胜）
        pages: 检索页数（每页20条，默认3页）

    Returns:
        统计信息和POI数据列表
    """
    import aiohttp
    from ..config import settings

    if not city.strip():
        raise HTTPException(400, "城市名称不能为空")

    pages = max(1, min(pages, 10))

    amap_key = settings.amap_key
    if not amap_key:
        raise HTTPException(500, "高德Web服务Key未配置")

    base_url = "https://restapi.amap.com/v3/place/text"
    all_pois = []
    seen_ids = set()
    total_count = 0
    pages_fetched = 0

    try:
        async with aiohttp.ClientSession() as session:
            for page in range(1, pages + 1):
                params = {
                    "key": amap_key,
                    "city": city,
                    "types": types,
                    "offset": 20,
                    "page": page,
                    "extensions": "all",
                }

                try:
                    async with session.get(base_url, params=params, timeout=10) as resp:
                        data = await resp.json()
                        pois = data.get("pois", [])
                        count_str = data.get("count", "0")
                        try:
                            total_count = int(count_str)
                        except (ValueError, TypeError):
                            total_count = 0

                        pages_fetched += 1

                        if not pois:
                            break

                        for p in pois:
                            poi_id = p.get("id", "")
                            if poi_id and poi_id not in seen_ids:
                                seen_ids.add(poi_id)
                                all_pois.append(p)

                        if len(pois) < 20:
                            break
                except Exception as e:
                    print(f"[poi-test] 第{page}页错误: {e}")
                    break
    except Exception as e:
        raise HTTPException(500, f"高德API调用失败: {str(e)}")

    fetched_count = len(all_pois)
    unique_count = len(seen_ids)
    coverage = round((fetched_count / total_count) * 100) if total_count > 0 else 0

    return {
        "success": True,
        "data": {
            "city": city,
            "types": types,
            "totalCount": total_count,
            "fetchedCount": fetched_count,
            "pagesFetched": pages_fetched,
            "uniqueCount": unique_count,
            "coverage": coverage,
            "pois": all_pois,
        },
    }
