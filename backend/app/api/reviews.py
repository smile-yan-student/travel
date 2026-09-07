"""
用户评价体系 API

功能：
- 行程评价（提交、列表、统计）
- 景点评价（提交、列表、统计）
- 用户反馈（提交、列表）
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import json

from app.data.database import get_conn
from app.security.auth import require_user
from app.utils.responses import ok, fail

router = APIRouter(prefix="/api/reviews", tags=["评价体系"])


# ==================== 请求模型 ====================

class TripReviewCreate(BaseModel):
    """行程评价创建请求"""
    trip_id: str = Field(..., description="行程ID")
    destination: Optional[str] = Field("", description="目的地")
    overall_rating: int = Field(5, ge=1, le=5, description="整体评分(1-5)")
    route_rating: Optional[int] = Field(5, ge=1, le=5, description="路线合理性评分")
    attraction_rating: Optional[int] = Field(5, ge=1, le=5, description="景点质量评分")
    budget_rating: Optional[int] = Field(5, ge=1, le=5, description="预算合理性评分")
    recommend_index: Optional[int] = Field(3, ge=1, le=5, description="推荐指数")
    content: Optional[str] = Field("", description="评价内容")
    tags: Optional[List[str]] = Field(default_factory=list, description="评价标签")
    would_recommend: Optional[int] = Field(1, ge=0, le=1, description="是否推荐")


class PoiReviewCreate(BaseModel):
    """景点评价创建请求"""
    poi_id: str = Field(..., description="POI ID")
    poi_name: str = Field(..., description="POI名称")
    trip_id: Optional[str] = Field("", description="关联行程ID")
    rating: int = Field(5, ge=1, le=5, description="评分(1-5)")
    content: Optional[str] = Field("", description="评价内容")
    tags: Optional[List[str]] = Field(default_factory=list, description="评价标签")
    duration_min: Optional[int] = Field(None, description="实际游玩时长(分钟)")
    cost: Optional[float] = Field(None, description="实际花费")


class FeedbackCreate(BaseModel):
    """用户反馈创建请求"""
    type: str = Field("general", description="反馈类型(bug/feature/experience/general)")
    title: Optional[str] = Field("", description="反馈标题")
    content: str = Field(..., description="反馈内容")
    contact: Optional[str] = Field("", description="联系方式")


# ==================== 行程评价 ====================

@router.post("/trip")
async def create_trip_review(
    req: TripReviewCreate,
    user: dict = Depends(require_user)
):
    """提交行程评价"""
    try:
        conn = get_conn()
        cursor = conn.cursor()

        # 检查是否已评价
        cursor.execute(
            "SELECT id FROM trip_reviews WHERE trip_id = %s AND user_id = %s AND status = 1",
            (req.trip_id, user['id'])
        )
        existing = cursor.fetchone()
        if existing:
            cursor.close()
            conn.close()
            return fail("您已评价过该行程", code=400)

        # 插入评价
        cursor.execute('''
            INSERT INTO trip_reviews 
            (trip_id, user_id, destination, overall_rating, route_rating, 
             attraction_rating, budget_rating, recommend_index, content, tags, would_recommend)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            req.trip_id, user['id'], req.destination,
            req.overall_rating, req.route_rating, req.attraction_rating,
            req.budget_rating, req.recommend_index, req.content,
            json.dumps(req.tags, ensure_ascii=False) if req.tags else None,
            req.would_recommend
        ))
        review_id = cursor.lastrowid
        conn.commit()
        cursor.close()
        conn.close()

        return ok({"id": review_id, "message": "评价提交成功"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"提交评价失败: {str(e)}")


@router.get("/trip/{trip_id}")
async def get_trip_reviews(
    trip_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50)
):
    """获取行程评价列表"""
    try:
        conn = get_conn()
        cursor = conn.cursor()

        offset = (page - 1) * page_size

        # 获取评价列表
        cursor.execute('''
            SELECT r.*, u.username 
            FROM trip_reviews r 
            LEFT JOIN users u ON r.user_id = u.id 
            WHERE r.trip_id = %s AND r.status = 1 
            ORDER BY r.created_at DESC 
            LIMIT %s OFFSET %s
        ''', (trip_id, page_size, offset))
        reviews = cursor.fetchall()

        # 获取总数
        cursor.execute(
            "SELECT COUNT(*) as total FROM trip_reviews WHERE trip_id = %s AND status = 1",
            (trip_id,)
        )
        total = cursor.fetchone()['total']

        # 获取统计信息
        cursor.execute('''
            SELECT 
                COUNT(*) as count,
                AVG(overall_rating) as avg_overall,
                AVG(route_rating) as avg_route,
                AVG(attraction_rating) as avg_attraction,
                AVG(budget_rating) as avg_budget,
                AVG(recommend_index) as avg_recommend,
                SUM(would_recommend) as recommend_count
            FROM trip_reviews 
            WHERE trip_id = %s AND status = 1
        ''', (trip_id,))
        stats = cursor.fetchone()

        cursor.close()
        conn.close()

        # 解析tags
        for r in reviews:
            if r.get('tags'):
                try:
                    r['tags'] = json.loads(r['tags'])
                except:
                    r['tags'] = []

        return ok({
            "list": reviews,
            "total": total,
            "page": page,
            "page_size": page_size,
            "stats": {
                "count": stats['count'] or 0,
                "avg_overall": round(float(stats['avg_overall'] or 0), 1),
                "avg_route": round(float(stats['avg_route'] or 0), 1),
                "avg_attraction": round(float(stats['avg_attraction'] or 0), 1),
                "avg_budget": round(float(stats['avg_budget'] or 0), 1),
                "avg_recommend": round(float(stats['avg_recommend'] or 0), 1),
                "recommend_rate": round((stats['recommend_count'] or 0) / (stats['count'] or 1) * 100, 1),
            }
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取评价失败: {str(e)}")


@router.get("/trip/user/my")
async def get_my_trip_reviews(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    user: dict = Depends(require_user)
):
    """获取我的行程评价列表"""
    try:
        conn = get_conn()
        cursor = conn.cursor()

        offset = (page - 1) * page_size

        cursor.execute('''
            SELECT * FROM trip_reviews 
            WHERE user_id = %s AND status = 1 
            ORDER BY created_at DESC 
            LIMIT %s OFFSET %s
        ''', (user['id'], page_size, offset))
        reviews = cursor.fetchall()

        cursor.execute(
            "SELECT COUNT(*) as total FROM trip_reviews WHERE user_id = %s AND status = 1",
            (user['id'],)
        )
        total = cursor.fetchone()['total']

        cursor.close()
        conn.close()

        for r in reviews:
            if r.get('tags'):
                try:
                    r['tags'] = json.loads(r['tags'])
                except:
                    r['tags'] = []

        return ok({
            "list": reviews,
            "total": total,
            "page": page,
            "page_size": page_size
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取评价失败: {str(e)}")


# ==================== 景点评价 ====================

@router.post("/poi")
async def create_poi_review(
    req: PoiReviewCreate,
    user: dict = Depends(require_user)
):
    """提交景点评价"""
    try:
        conn = get_conn()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO poi_reviews 
            (poi_id, poi_name, trip_id, user_id, rating, content, tags, duration_min, cost)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            req.poi_id, req.poi_name, req.trip_id, user['id'],
            req.rating, req.content,
            json.dumps(req.tags, ensure_ascii=False) if req.tags else None,
            req.duration_min, req.cost
        ))
        review_id = cursor.lastrowid
        conn.commit()
        cursor.close()
        conn.close()

        return ok({"id": review_id, "message": "评价提交成功"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"提交评价失败: {str(e)}")


@router.get("/poi/{poi_id}")
async def get_poi_reviews(
    poi_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50)
):
    """获取景点评价列表"""
    try:
        conn = get_conn()
        cursor = conn.cursor()

        offset = (page - 1) * page_size

        cursor.execute('''
            SELECT r.*, u.username 
            FROM poi_reviews r 
            LEFT JOIN users u ON r.user_id = u.id 
            WHERE r.poi_id = %s AND r.status = 1 
            ORDER BY r.created_at DESC 
            LIMIT %s OFFSET %s
        ''', (poi_id, page_size, offset))
        reviews = cursor.fetchall()

        cursor.execute(
            "SELECT COUNT(*) as total FROM poi_reviews WHERE poi_id = %s AND status = 1",
            (poi_id,)
        )
        total = cursor.fetchone()['total']

        cursor.execute('''
            SELECT COUNT(*) as count, AVG(rating) as avg_rating 
            FROM poi_reviews WHERE poi_id = %s AND status = 1
        ''', (poi_id,))
        stats = cursor.fetchone()

        cursor.close()
        conn.close()

        for r in reviews:
            if r.get('tags'):
                try:
                    r['tags'] = json.loads(r['tags'])
                except:
                    r['tags'] = []

        return ok({
            "list": reviews,
            "total": total,
            "page": page,
            "page_size": page_size,
            "stats": {
                "count": stats['count'] or 0,
                "avg_rating": round(float(stats['avg_rating'] or 0), 1),
            }
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取评价失败: {str(e)}")


# ==================== 用户反馈 ====================

@router.post("/feedback")
async def create_feedback(
    req: FeedbackCreate,
    user: dict = Depends(require_user)
):
    """提交用户反馈"""
    try:
        conn = get_conn()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO user_feedback (user_id, type, title, content, contact)
            VALUES (%s, %s, %s, %s, %s)
        ''', (user['id'], req.type, req.title, req.content, req.contact))
        feedback_id = cursor.lastrowid
        conn.commit()
        cursor.close()
        conn.close()

        return ok({"id": feedback_id, "message": "反馈提交成功，感谢您的建议"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"提交反馈失败: {str(e)}")


@router.get("/feedback/my")
async def get_my_feedback(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    user: dict = Depends(require_user)
):
    """获取我的反馈列表"""
    try:
        conn = get_conn()
        cursor = conn.cursor()

        offset = (page - 1) * page_size

        cursor.execute('''
            SELECT * FROM user_feedback 
            WHERE user_id = %s 
            ORDER BY created_at DESC 
            LIMIT %s OFFSET %s
        ''', (user['id'], page_size, offset))
        feedbacks = cursor.fetchall()

        cursor.execute(
            "SELECT COUNT(*) as total FROM user_feedback WHERE user_id = %s",
            (user['id'],)
        )
        total = cursor.fetchone()['total']

        cursor.close()
        conn.close()

        return ok({
            "list": feedbacks,
            "total": total,
            "page": page,
            "page_size": page_size
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取反馈失败: {str(e)}")
