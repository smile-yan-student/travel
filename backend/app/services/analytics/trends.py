"""
趋势统计服务

功能：
- 目的地趋势统计
- 景点趋势统计
- 行程效果分析
- 数据可视化看板数据
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import json
import logging

from app.data.database import get_conn

logger = logging.getLogger(__name__)


# ==================== 目的地趋势 ====================

def get_destination_trends(
    period_type: str = 'weekly',
    limit: int = 20,
    category: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    获取目的地趋势

    Args:
        period_type: 统计周期(daily/weekly/monthly/yearly)
        limit: 返回数量
        category: 类别筛选

    Returns:
        List: 目的地趋势列表
    """
    try:
        # 先从趋势表获取（如果有预计算数据）
        conn = get_conn()
        cursor = conn.cursor()

        # 计算统计周期
        if period_type == 'daily':
            start_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        elif period_type == 'weekly':
            start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        elif period_type == 'monthly':
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        else:  # yearly
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')

        # 从行程表实时统计
        cursor.execute('''
            SELECT 
                destination,
                COUNT(*) as plan_count,
                COUNT(DISTINCT user_id) as user_count,
                AVG(days) as avg_days
            FROM trips t
            WHERE t.destination IS NOT NULL
              AND t.created_at >= %s
            GROUP BY destination
            ORDER BY plan_count DESC
            LIMIT %s
        ''', (start_date, limit))

        trends = cursor.fetchall()

        # 获取评价数据
        cursor.execute('''
            SELECT 
                destination,
                COUNT(*) as review_count,
                AVG(overall_rating) as avg_rating
            FROM trip_reviews
            WHERE created_at >= %s
            GROUP BY destination
        ''', (start_date,))
        reviews = {row['destination']: row for row in cursor.fetchall()}

        cursor.close()
        conn.close()

        # 合并数据并计算趋势评分
        result = []
        for i, trend in enumerate(trends):
            dest = trend['destination']
            review = reviews.get(dest, {})

            # 趋势评分 = 行程数*0.4 + 用户数*0.3 + 评价数*0.2 + 评分*10*0.1
            trend_score = (
                (trend['plan_count'] or 0) * 0.4 +
                (trend['user_count'] or 0) * 0.3 +
                (review.get('review_count', 0) or 0) * 0.2 +
                float(review.get('avg_rating', 0) or 0) * 10 * 0.1
            )

            result.append({
                'rank': i + 1,
                'destination': dest,
                'plan_count': trend['plan_count'],
                'user_count': trend['user_count'],
                'avg_days': round(float(trend['avg_days'] or 0), 1),
                'review_count': review.get('review_count', 0),
                'avg_rating': round(float(review.get('avg_rating', 0) or 0), 1),
                'trend_score': round(trend_score, 2),
                'trend_label': _get_trend_label(trend_score),
            })

        return result

    except Exception as e:
        logger.error(f"获取目的地趋势失败: {e}")
        return []


def _get_trend_label(score: float) -> str:
    """根据趋势评分获取标签"""
    if score >= 50:
        return '🔥 爆款'
    elif score >= 30:
        return '📈 热门'
    elif score >= 15:
        return '👍 推荐'
    else:
        return '🌱 小众'


# ==================== 景点趋势 ====================

def get_poi_trends(
    destination: Optional[str] = None,
    category: Optional[str] = None,
    period_type: str = 'monthly',
    limit: int = 20
) -> List[Dict[str, Any]]:
    """
    获取景点趋势

    注意：当前trips表未存储详细行程点位数据，此功能暂返回空列表。
    后续可通过行程详情表或POI缓存表实现。

    Args:
        destination: 目的地筛选
        category: 类别筛选
        period_type: 统计周期
        limit: 返回数量

    Returns:
        List: 景点趋势列表
    """
    # TODO: 待行程详情表上线后实现完整的景点趋势统计
    return []


# ==================== 行程效果分析 ====================

def get_plan_effect_analysis(
    period_days: int = 30
) -> Dict[str, Any]:
    """
    获取行程效果分析

    Args:
        period_days: 统计天数

    Returns:
        Dict: 行程效果分析数据
    """
    try:
        conn = get_conn()
        cursor = conn.cursor()

        start_date = (datetime.now() - timedelta(days=period_days)).strftime('%Y-%m-%d')

        # 1. 总体统计
        cursor.execute('''
            SELECT 
                COUNT(*) as total_plans,
                COUNT(DISTINCT user_id) as total_users,
                AVG(days) as avg_days
            FROM trips 
            WHERE created_at >= %s
        ''', (start_date,))
        overall = cursor.fetchone()

        # 2. 评价统计
        cursor.execute('''
            SELECT 
                COUNT(*) as total_reviews,
                AVG(overall_rating) as avg_overall,
                AVG(route_rating) as avg_route,
                AVG(attraction_rating) as avg_attraction,
                AVG(budget_rating) as avg_budget_rating,
                SUM(would_recommend) as recommend_count
            FROM trip_reviews 
            WHERE created_at >= %s
        ''', (start_date,))
        reviews = cursor.fetchone()

        # 3. 热门目的地TOP10
        cursor.execute('''
            SELECT destination, COUNT(*) as count
            FROM trips 
            WHERE created_at >= %s AND destination IS NOT NULL
            GROUP BY destination
            ORDER BY count DESC
            LIMIT 10
        ''', (start_date,))
        top_destinations = cursor.fetchall()

        # 4. 每日趋势
        cursor.execute('''
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as plan_count,
                COUNT(DISTINCT user_id) as user_count
            FROM trips 
            WHERE created_at >= %s
            GROUP BY DATE(created_at)
            ORDER BY date
        ''', (start_date,))
        daily_trends = cursor.fetchall()

        # 5. 低评分问题分析（评分低于3分的评价）
        cursor.execute('''
            SELECT 
                content,
                overall_rating,
                route_rating,
                attraction_rating,
                budget_rating,
                tags
            FROM trip_reviews 
            WHERE overall_rating <= 3 AND created_at >= %s
            ORDER BY overall_rating ASC
            LIMIT 20
        ''', (start_date,))
        low_rating_reviews = cursor.fetchall()

        cursor.close()
        conn.close()

        # 解析标签
        for review in low_rating_reviews:
            if review.get('tags'):
                try:
                    review['tags'] = json.loads(review['tags'])
                except:
                    review['tags'] = []

        return {
            'period_days': period_days,
            'overall': {
                'total_plans': overall['total_plans'] or 0,
                'total_users': overall['total_users'] or 0,
                'avg_days': round(float(overall['avg_days'] or 0), 1),
            },
            'reviews': {
                'total_reviews': reviews['total_reviews'] or 0,
                'avg_overall': round(float(reviews['avg_overall'] or 0), 2),
                'avg_route': round(float(reviews['avg_route'] or 0), 2),
                'avg_attraction': round(float(reviews['avg_attraction'] or 0), 2),
                'avg_budget_rating': round(float(reviews['avg_budget_rating'] or 0), 2),
                'recommend_count': reviews['recommend_count'] or 0,
                'recommend_rate': round((reviews['recommend_count'] or 0) / max(reviews['total_reviews'] or 1, 1) * 100, 1),
            },
            'top_destinations': top_destinations,
            'daily_trends': daily_trends,
            'low_rating_analysis': {
                'count': len(low_rating_reviews),
                'reviews': low_rating_reviews,
                'common_issues': _extract_common_issues(low_rating_reviews),
            },
        }

    except Exception as e:
        logger.error(f"获取行程效果分析失败: {e}")
        return {}


def _extract_common_issues(reviews: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """从低评分评价中提取常见问题"""
    issue_counts = {}

    for review in reviews:
        # 分析评分维度
        if review.get('route_rating', 5) <= 2:
            issue_counts['路线不合理'] = issue_counts.get('路线不合理', 0) + 1
        if review.get('attraction_rating', 5) <= 2:
            issue_counts['景点质量差'] = issue_counts.get('景点质量差', 0) + 1
        if review.get('budget_rating', 5) <= 2:
            issue_counts['预算不准确'] = issue_counts.get('预算不准确', 0) + 1

        # 分析标签
        tags = review.get('tags', [])
        if isinstance(tags, list):
            for tag in tags:
                if tag in ['人太多', '门票贵', '交通不便', '景点重复', '时间紧张']:
                    issue_counts[tag] = issue_counts.get(tag, 0) + 1

    # 排序并返回
    result = [{'issue': k, 'count': v} for k, v in sorted(issue_counts.items(), key=lambda x: -x[1])]
    return result[:10]


# ==================== 数据看板概览 ====================

def get_dashboard_overview() -> Dict[str, Any]:
    """
    获取数据看板概览（用于管理后台首页）

    Returns:
        Dict: 看板概览数据
    """
    try:
        conn = get_conn()
        cursor = conn.cursor()

        # 用户统计
        cursor.execute('SELECT COUNT(*) as total FROM users')
        total_users = cursor.fetchone()['total']

        cursor.execute('SELECT COUNT(*) as today FROM users WHERE DATE(created_at) = CURDATE()')
        today_users = cursor.fetchone()['today']

        # 行程统计
        cursor.execute('SELECT COUNT(*) as total FROM trips')
        total_trips = cursor.fetchone()['total']

        cursor.execute('SELECT COUNT(*) as today FROM trips WHERE DATE(created_at) = CURDATE()')
        today_trips = cursor.fetchone()['today']

        # 评价统计
        cursor.execute('SELECT COUNT(*) as total, AVG(overall_rating) as avg FROM trip_reviews WHERE status = 1')
        review_stats = cursor.fetchone()

        # 行为统计
        cursor.execute('SELECT COUNT(*) as total FROM user_behavior_logs')
        total_behaviors = cursor.fetchone()['total']

        cursor.close()
        conn.close()

        return {
            'users': {
                'total': total_users,
                'today': today_users,
                'growth': _calculate_growth(total_users, today_users),
            },
            'trips': {
                'total': total_trips,
                'today': today_trips,
                'growth': _calculate_growth(total_trips, today_trips),
            },
            'reviews': {
                'total': review_stats['total'] or 0,
                'avg_rating': round(float(review_stats['avg'] or 0), 2),
            },
            'behaviors': {
                'total': total_behaviors,
            },
        }

    except Exception as e:
        logger.error(f"获取看板概览失败: {e}")
        return {}


def _calculate_growth(total: int, today: int) -> float:
    """计算增长率（简化版）"""
    if total == 0:
        return 0
    return round(today / total * 100, 2)
