"""
在线数据管理API路由模块（后台管理）。

提供预约规则和避坑提示的CRUD操作，以及统计、批量导入等接口。

功能特性：
- 预约规则管理（CRUD、统计、按目的地查询）
- 避坑提示管理（CRUD、统计、按目的地查询、批量创建）
- 管理员鉴权（所有管理接口需要管理员登录）

使用方式：
    from app.api.admin_online_data import router

    # 在FastAPI应用中注册路由
    app.include_router(router)

    # 预约规则接口
    # GET /api/admin/online-data/reservation-rules/stats 获取统计
    # GET /api/admin/online-data/reservation-rules 获取列表
    # GET /api/admin/online-data/reservation-rules/{id} 获取详情
    # POST /api/admin/online-data/reservation-rules 创建
    # PUT /api/admin/online-data/reservation-rules/{id} 更新
    # DELETE /api/admin/online-data/reservation-rules/{id} 删除

    # 避坑提示接口
    # GET /api/admin/online-data/travel-tips/stats 获取统计
    # GET /api/admin/online-data/travel-tips 获取列表
    # GET /api/admin/online-data/travel-tips/{id} 获取详情
    # POST /api/admin/online-data/travel-tips 创建
    # POST /api/admin/online-data/travel-tips/batch 批量创建
    # PUT /api/admin/online-data/travel-tips/{id} 更新
    # DELETE /api/admin/online-data/travel-tips/{id} 删除
"""
from typing import Any, Dict, List, Optional
import csv
import io

from fastapi import APIRouter, Depends, Header, HTTPException, Query, UploadFile, File
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ..services.online_data import (
    get_attraction_rules,
    get_travel_tips,
    AttractionRule,
    TravelTip,
)

router = APIRouter(prefix="/api/admin/online-data", tags=["admin-online-data"])


# ========== 管理员鉴权 ==========

def _admin_from_header(authorization: str = Header(default="")) -> dict:
    """从请求头解析管理员信息。"""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    token = authorization[7:]
    # 简单的token验证（实际项目中应该使用JWT）
    # 这里假设token格式为 "admin:username:role"
    parts = token.split(":")
    if len(parts) < 3 or parts[0] != "admin":
        raise HTTPException(status_code=401, detail="无效的管理员凭证")
    return {"username": parts[1], "role": parts[2]}


# ========== 请求模型 ==========

class ReservationRuleCreateRequest(BaseModel):
    """预约规则创建请求。"""
    attraction_name: str = Field(..., description="景点名称")
    destination: Optional[str] = Field("", description="所属目的地（城市/省份）")
    reservation_channel: Optional[str] = Field("", description="预约渠道（公众号/小程序/APP/官网）")
    ticket_release_time: Optional[str] = Field("", description="放票时间（如：提前7天20:00）")
    opening_hours: Optional[str] = Field("", description="开放时间")
    closing_days: Optional[str] = Field("", description="闭馆日")
    ticket_price: Optional[str] = Field("", description="票价信息")
    visitor_route: Optional[str] = Field("", description="游览路线（如：午门进，神武门出）")
    daily_limit: Optional[str] = Field("", description="每日限流")
    tips: Optional[str] = Field("", description="温馨提示")
    reservation_url: Optional[str] = Field("", description="预约链接")
    priority: Optional[int] = Field(50, description="优先级（0-100）")
    source: Optional[str] = Field("manual", description="数据来源")


class ReservationRuleUpdateRequest(BaseModel):
    """预约规则更新请求。"""
    attraction_name: Optional[str] = None
    destination: Optional[str] = None
    reservation_channel: Optional[str] = None
    ticket_release_time: Optional[str] = None
    opening_hours: Optional[str] = None
    closing_days: Optional[str] = None
    ticket_price: Optional[str] = None
    visitor_route: Optional[str] = None
    daily_limit: Optional[str] = None
    tips: Optional[str] = None
    reservation_url: Optional[str] = None
    priority: Optional[int] = None
    source: Optional[str] = None


class TravelTipCreateRequest(BaseModel):
    """避坑提示创建请求。"""
    destination: str = Field(..., description="所属目的地（城市/省份）")
    tip: str = Field(..., description="提示内容")
    category: Optional[str] = Field("general", description="类别：general/anti_fraud/reservation/traffic/food/accommodation/weather/safety")
    severity: Optional[str] = Field("info", description="严重程度：info/warning/danger")
    sort_weight: Optional[int] = Field(50, description="排序权重（0-100）")
    source: Optional[str] = Field("manual", description="数据来源")
    frequency: Optional[int] = Field(0, description="验证人数")


class TravelTipUpdateRequest(BaseModel):
    """避坑提示更新请求。"""
    destination: Optional[str] = None
    tip: Optional[str] = None
    category: Optional[str] = None
    severity: Optional[str] = None
    sort_weight: Optional[int] = None
    source: Optional[str] = None
    frequency: Optional[int] = None


class TravelTipBatchCreateRequest(BaseModel):
    """避坑提示批量创建请求。"""
    tips: List[TravelTipCreateRequest] = Field(..., description="提示列表")


# ========== 预约规则接口 ==========

@router.get("/reservation-rules/stats")
async def get_reservation_rules_stats(
    _: dict = Depends(_admin_from_header)
):
    """获取预约规则统计信息。"""
    try:
        rules_service = get_attraction_rules()
        stats = await rules_service.get_stats()
        return {"success": True, "data": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计失败: {str(e)}")


@router.get("/reservation-rules")
async def list_reservation_rules(
    destination: str = Query("", description="目的地筛选"),
    keyword: str = Query("", description="关键词搜索"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页数量"),
    _: dict = Depends(_admin_from_header)
):
    """获取预约规则列表。"""
    try:
        rules_service = get_attraction_rules()

        # 如果指定了目的地，按目的地查询
        if destination:
            rules = await rules_service.get_by_destination(destination)
        else:
            # 否则获取所有（简单实现，实际项目应该有分页查询）
            rules = await rules_service.get_by_destination("")

        # 关键词搜索
        if keyword:
            rules = [
                r for r in rules
                if keyword.lower() in r.attraction_name.lower()
                or keyword.lower() in (r.destination or "").lower()
            ]

        # 分页
        total = len(rules)
        start = (page - 1) * size
        end = start + size
        page_rules = rules[start:end]

        return {
            "success": True,
            "data": {
                "list": [r.to_dict() for r in page_rules],
                "total": total,
                "page": page,
                "size": size,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取列表失败: {str(e)}")


@router.get("/reservation-rules/{rule_id}")
async def get_reservation_rule(
    rule_id: int,
    _: dict = Depends(_admin_from_header)
):
    """获取预约规则详情。"""
    try:
        rules_service = get_attraction_rules()
        rule = await rules_service.get_by_id(rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail="预约规则不存在")
        return {"success": True, "data": rule.to_dict()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取详情失败: {str(e)}")


@router.post("/reservation-rules")
async def create_reservation_rule(
    body: ReservationRuleCreateRequest,
    _: dict = Depends(_admin_from_header)
):
    """创建预约规则。"""
    try:
        rules_service = get_attraction_rules()

        # 检查是否已存在同名景点
        existing = await rules_service.get_by_name(body.attraction_name)
        if existing:
            raise HTTPException(status_code=400, detail=f"景点「{body.attraction_name}」的预约规则已存在")

        # 创建规则对象
        rule = AttractionRule(
            attraction_name=body.attraction_name,
            destination=body.destination or "",
            reservation_channel=body.reservation_channel or "",
            ticket_release_time=body.ticket_release_time or "",
            opening_hours=body.opening_hours or "",
            closing_days=body.closing_days or "",
            ticket_price=body.ticket_price or "",
            visitor_route=body.visitor_route or "",
            daily_limit=body.daily_limit or "",
            tips=body.tips or "",
            reservation_url=body.reservation_url or "",
            priority=body.priority or 50,
            source=body.source or "manual",
        )

        rule_id = await rules_service.create(rule)
        if not rule_id:
            raise HTTPException(status_code=500, detail="创建失败")

        return {"success": True, "data": {"id": rule_id}, "message": "创建成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建失败: {str(e)}")


@router.put("/reservation-rules/{rule_id}")
async def update_reservation_rule(
    rule_id: int,
    body: ReservationRuleUpdateRequest,
    _: dict = Depends(_admin_from_header)
):
    """更新预约规则。"""
    try:
        rules_service = get_attraction_rules()

        # 检查是否存在
        existing = await rules_service.get_by_id(rule_id)
        if not existing:
            raise HTTPException(status_code=404, detail="预约规则不存在")

        # 更新字段
        update_data = body.dict(exclude_unset=True)
        for key, value in update_data.items():
            if hasattr(existing, key):
                setattr(existing, key, value)

        success = await rules_service.update(existing)
        if not success:
            raise HTTPException(status_code=500, detail="更新失败")

        return {"success": True, "message": "更新成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")


@router.delete("/reservation-rules/{rule_id}")
async def delete_reservation_rule(
    rule_id: int,
    _: dict = Depends(_admin_from_header)
):
    """删除预约规则。"""
    try:
        rules_service = get_attraction_rules()
        success = await rules_service.delete(rule_id)
        if not success:
            raise HTTPException(status_code=404, detail="预约规则不存在或删除失败")
        return {"success": True, "message": "删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


# ========== 避坑提示接口 ==========

@router.get("/travel-tips/stats")
async def get_travel_tips_stats(
    _: dict = Depends(_admin_from_header)
):
    """获取避坑提示统计信息。"""
    try:
        tips_service = get_travel_tips()
        stats = await tips_service.get_stats()
        return {"success": True, "data": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计失败: {str(e)}")


@router.get("/travel-tips")
async def list_travel_tips(
    destination: str = Query("", description="目的地筛选"),
    category: str = Query("", description="类别筛选"),
    severity: str = Query("", description="严重程度筛选"),
    keyword: str = Query("", description="关键词搜索"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页数量"),
    _: dict = Depends(_admin_from_header)
):
    """获取避坑提示列表。"""
    try:
        tips_service = get_travel_tips()

        # 如果指定了目的地，按目的地查询
        if destination:
            tips = await tips_service.get_by_destination(destination)
        else:
            # 否则获取所有（简单实现）
            tips = await tips_service.get_by_destination("")

        # 类别筛选
        if category:
            tips = [t for t in tips if t.category == category]

        # 严重程度筛选
        if severity:
            tips = [t for t in tips if t.severity == severity]

        # 关键词搜索
        if keyword:
            tips = [
                t for t in tips
                if keyword.lower() in t.tip.lower()
                or keyword.lower() in (t.destination or "").lower()
            ]

        # 分页
        total = len(tips)
        start = (page - 1) * size
        end = start + size
        page_tips = tips[start:end]

        return {
            "success": True,
            "data": {
                "list": [t.to_dict() for t in page_tips],
                "total": total,
                "page": page,
                "size": size,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取列表失败: {str(e)}")


@router.get("/travel-tips/{tip_id}")
async def get_travel_tip(
    tip_id: int,
    _: dict = Depends(_admin_from_header)
):
    """获取避坑提示详情。"""
    try:
        tips_service = get_travel_tips()
        tip = await tips_service.get_by_id(tip_id)
        if not tip:
            raise HTTPException(status_code=404, detail="避坑提示不存在")
        return {"success": True, "data": tip.to_dict()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取详情失败: {str(e)}")


@router.post("/travel-tips")
async def create_travel_tip(
    body: TravelTipCreateRequest,
    _: dict = Depends(_admin_from_header)
):
    """创建避坑提示。"""
    try:
        tips_service = get_travel_tips()

        # 创建提示对象
        tip = TravelTip(
            destination=body.destination,
            tip=body.tip,
            category=body.category or "general",
            severity=body.severity or "info",
            sort_weight=body.sort_weight or 50,
            source=body.source or "manual",
            frequency=body.frequency or 0,
        )

        tip_id = await tips_service.create(tip)
        if not tip_id:
            raise HTTPException(status_code=500, detail="创建失败")

        return {"success": True, "data": {"id": tip_id}, "message": "创建成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建失败: {str(e)}")


@router.post("/travel-tips/batch")
async def batch_create_travel_tips(
    body: TravelTipBatchCreateRequest,
    _: dict = Depends(_admin_from_header)
):
    """批量创建避坑提示。"""
    try:
        tips_service = get_travel_tips()

        # 创建提示对象列表
        tips = [
            TravelTip(
                destination=t.destination,
                tip=t.tip,
                category=t.category or "general",
                severity=t.severity or "info",
                sort_weight=t.sort_weight or 50,
                source=t.source or "manual",
                frequency=t.frequency or 0,
            )
            for t in body.tips
        ]

        count = await tips_service.batch_create(tips)
        return {"success": True, "data": {"count": count}, "message": f"成功创建{count}条提示"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量创建失败: {str(e)}")


@router.put("/travel-tips/{tip_id}")
async def update_travel_tip(
    tip_id: int,
    body: TravelTipUpdateRequest,
    _: dict = Depends(_admin_from_header)
):
    """更新避坑提示。"""
    try:
        tips_service = get_travel_tips()

        # 检查是否存在
        existing = await tips_service.get_by_id(tip_id)
        if not existing:
            raise HTTPException(status_code=404, detail="避坑提示不存在")

        # 更新字段
        update_data = body.dict(exclude_unset=True)
        for key, value in update_data.items():
            if hasattr(existing, key):
                setattr(existing, key, value)

        success = await tips_service.update(existing)
        if not success:
            raise HTTPException(status_code=500, detail="更新失败")

        return {"success": True, "message": "更新成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")


@router.delete("/travel-tips/{tip_id}")
async def delete_travel_tip(
    tip_id: int,
    _: dict = Depends(_admin_from_header)
):
    """删除避坑提示。"""
    try:
        tips_service = get_travel_tips()
        success = await tips_service.delete(tip_id)
        if not success:
            raise HTTPException(status_code=404, detail="避坑提示不存在或删除失败")
        return {"success": True, "message": "删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


# ========== 数据导入导出接口 ==========

# 预约规则CSV字段
RESERVATION_RULE_FIELDS = [
    "attraction_name", "destination", "reservation_channel",
    "ticket_release_time", "opening_hours", "closing_days",
    "ticket_price", "visitor_route", "daily_limit",
    "tips", "reservation_url", "source"
]

# 避坑提示CSV字段
TRAVEL_TIP_FIELDS = [
    "destination", "tip", "category", "severity",
    "sort_order", "source"
]


@router.get("/reservation-rules/export")
async def export_reservation_rules(
    destination: str = Query("", description="目的地筛选"),
    _: dict = Depends(_admin_from_header)
):
    """导出预约规则为CSV文件。"""
    try:
        rules_service = get_attraction_rules()

        if destination:
            rules = await rules_service.get_by_destination(destination)
        else:
            rules = await rules_service.get_by_destination("")

        # 生成CSV
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=RESERVATION_RULE_FIELDS)
        writer.writeheader()

        for rule in rules:
            row = {field: getattr(rule, field, "") for field in RESERVATION_RULE_FIELDS}
            writer.writerow(row)

        csv_content = output.getvalue()
        filename = f"reservation_rules_{destination or 'all'}.csv"

        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")


@router.post("/reservation-rules/import")
async def import_reservation_rules(
    file: UploadFile = File(..., description="CSV文件"),
    _: dict = Depends(_admin_from_header)
):
    """从CSV文件导入预约规则。"""
    try:
        rules_service = get_attraction_rules()

        # 读取CSV内容
        content = await file.read()
        csv_content = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(csv_content))

        success_count = 0
        skip_count = 0
        error_count = 0
        errors = []

        for row_num, row in enumerate(reader, start=2):
            try:
                attraction_name = row.get("attraction_name", "").strip()
                if not attraction_name:
                    skip_count += 1
                    continue

                # 检查是否已存在
                existing = await rules_service.get_by_name(attraction_name)
                if existing:
                    skip_count += 1
                    continue

                # 创建规则
                rule_data = {}
                for field in RESERVATION_RULE_FIELDS:
                    value = row.get(field, "").strip()
                    rule_data[field] = value

                rule = AttractionRule(**rule_data)
                rule_id = await rules_service.create(rule)
                if rule_id:
                    success_count += 1
                else:
                    error_count += 1
                    errors.append(f"第{row_num}行：创建失败")
            except Exception as e:
                error_count += 1
                errors.append(f"第{row_num}行：{str(e)}")

        return {
            "success": True,
            "data": {
                "success_count": success_count,
                "skip_count": skip_count,
                "error_count": error_count,
                "errors": errors[:10]  # 只返回前10个错误
            },
            "message": f"导入完成：成功{success_count}条，跳过{skip_count}条，失败{error_count}条"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")


@router.get("/travel-tips/export")
async def export_travel_tips(
    destination: str = Query("", description="目的地筛选"),
    category: str = Query("", description="类别筛选"),
    _: dict = Depends(_admin_from_header)
):
    """导出避坑提示为CSV文件。"""
    try:
        tips_service = get_travel_tips()

        if destination:
            tips = await tips_service.get_by_destination(destination)
        else:
            tips = await tips_service.get_by_destination("")

        # 类别筛选
        if category:
            tips = [t for t in tips if t.category == category]

        # 生成CSV
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=TRAVEL_TIP_FIELDS)
        writer.writeheader()

        for tip in tips:
            row = {field: getattr(tip, field, "") for field in TRAVEL_TIP_FIELDS}
            writer.writerow(row)

        csv_content = output.getvalue()
        filename = f"travel_tips_{destination or 'all'}.csv"

        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")


@router.post("/travel-tips/import")
async def import_travel_tips(
    file: UploadFile = File(..., description="CSV文件"),
    _: dict = Depends(_admin_from_header)
):
    """从CSV文件导入避坑提示。"""
    try:
        tips_service = get_travel_tips()

        # 读取CSV内容
        content = await file.read()
        csv_content = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(csv_content))

        success_count = 0
        skip_count = 0
        error_count = 0
        errors = []

        for row_num, row in enumerate(reader, start=2):
            try:
                destination = row.get("destination", "").strip()
                tip_text = row.get("tip", "").strip()
                if not destination or not tip_text:
                    skip_count += 1
                    continue

                # 检查是否已存在（按目的地+提示内容）
                existing_tips = await tips_service.get_by_destination(destination)
                exists = any(t.tip == tip_text for t in existing_tips)
                if exists:
                    skip_count += 1
                    continue

                # 创建提示
                tip_data = {}
                for field in TRAVEL_TIP_FIELDS:
                    value = row.get(field, "").strip()
                    if field == "sort_order" and value:
                        try:
                            value = int(value)
                        except:
                            value = 50
                    tip_data[field] = value

                tip = TravelTip(**tip_data)
                tip_id = await tips_service.create(tip)
                if tip_id:
                    success_count += 1
                else:
                    error_count += 1
                    errors.append(f"第{row_num}行：创建失败")
            except Exception as e:
                error_count += 1
                errors.append(f"第{row_num}行：{str(e)}")

        return {
            "success": True,
            "data": {
                "success_count": success_count,
                "skip_count": skip_count,
                "error_count": error_count,
                "errors": errors[:10]
            },
            "message": f"导入完成：成功{success_count}条，跳过{skip_count}条，失败{error_count}条"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")


# ========== 数据审核接口 ==========

class ReviewRequest(BaseModel):
    """审核请求"""
    status: str = Field(..., description="审核状态：approved/rejected")
    comment: str = Field("", description="审核备注")


@router.get("/reservation-rules/pending")
async def get_pending_reservation_rules(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: dict = Depends(_admin_from_header)
):
    """获取待审核的预约规则列表。"""
    try:
        rules_service = get_attraction_rules()
        all_rules = await rules_service.get_by_destination("")

        # 筛选待审核的规则
        pending_rules = [r for r in all_rules if getattr(r, 'review_status', 'approved') == 'pending']

        # 分页
        start = (page - 1) * page_size
        end = start + page_size
        page_rules = pending_rules[start:end]

        return {
            "success": True,
            "data": {
                "items": [r.__dict__ if hasattr(r, '__dict__') else r for r in page_rules],
                "total": len(pending_rules),
                "page": page,
                "page_size": page_size,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取待审核列表失败: {str(e)}")


@router.post("/reservation-rules/{rule_id}/review")
async def review_reservation_rule(
    rule_id: int,
    request: ReviewRequest,
    admin: dict = Depends(_admin_from_header)
):
    """审核预约规则（通过/拒绝）。"""
    try:
        if request.status not in ["approved", "rejected"]:
            raise HTTPException(status_code=400, detail="审核状态必须是 approved 或 rejected")

        rules_service = get_attraction_rules()
        rule = await rules_service.get_by_id(rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail="预约规则不存在")

        # 更新审核状态
        from datetime import datetime
        rule.review_status = request.status
        rule.reviewed_by = admin.get("username", "admin")
        rule.reviewed_at = datetime.now()
        rule.review_comment = request.comment

        # 如果审核拒绝，则禁用该规则
        if request.status == "rejected":
            rule.is_active = 0

        success = await rules_service.update(rule)
        if not success:
            raise HTTPException(status_code=500, detail="审核失败")

        return {
            "success": True,
            "message": f"审核{'通过' if request.status == 'approved' else '拒绝'}成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"审核失败: {str(e)}")


@router.get("/travel-tips/pending")
async def get_pending_travel_tips(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: dict = Depends(_admin_from_header)
):
    """获取待审核的避坑提示列表。"""
    try:
        tips_service = get_travel_tips()
        all_tips = await tips_service.get_by_destination("")

        # 筛选待审核的提示
        pending_tips = [t for t in all_tips if getattr(t, 'review_status', 'approved') == 'pending']

        # 分页
        start = (page - 1) * page_size
        end = start + page_size
        page_tips = pending_tips[start:end]

        return {
            "success": True,
            "data": {
                "items": [t.__dict__ if hasattr(t, '__dict__') else t for t in page_tips],
                "total": len(pending_tips),
                "page": page,
                "page_size": page_size,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取待审核列表失败: {str(e)}")


@router.post("/travel-tips/{tip_id}/review")
async def review_travel_tip(
    tip_id: int,
    request: ReviewRequest,
    admin: dict = Depends(_admin_from_header)
):
    """审核避坑提示（通过/拒绝）。"""
    try:
        if request.status not in ["approved", "rejected"]:
            raise HTTPException(status_code=400, detail="审核状态必须是 approved 或 rejected")

        tips_service = get_travel_tips()
        tip = await tips_service.get_by_id(tip_id)
        if not tip:
            raise HTTPException(status_code=404, detail="避坑提示不存在")

        # 更新审核状态
        from datetime import datetime
        tip.review_status = request.status
        tip.reviewed_by = admin.get("username", "admin")
        tip.reviewed_at = datetime.now()
        tip.review_comment = request.comment

        # 如果审核拒绝，则禁用该提示
        if request.status == "rejected":
            tip.is_active = 0

        success = await tips_service.update(tip)
        if not success:
            raise HTTPException(status_code=500, detail="审核失败")

        return {
            "success": True,
            "message": f"审核{'通过' if request.status == 'approved' else '拒绝'}成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"审核失败: {str(e)}")
