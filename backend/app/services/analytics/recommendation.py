"""
个性化推荐服务

功能：
- 基于用户画像推荐目的地
- 基于用户画像推荐景点
- 基于用户画像推荐行程
- 热门推荐（基于全局数据）
- 协同过滤推荐（基于相似用户）
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import json
import logging

from app.data.database import get_conn
from app.services.analytics.user_profile import get_user_profile

logger = logging.getLogger(__name__)


# ==================== 目的地推荐 ====================

def recommend_destinations(
    user_id: Optional[int] = None,
    limit: int = 10,
    algorithm: str = 'hybrid'
) -> List[Dict[str, Any]]:
    """
    推荐目的地

    Args:
        user_id: 用户ID（为空则返回热门推荐）
        limit: 返回数量
        algorithm: 推荐算法(popular/content/collaborative/hybrid)

    Returns:
        List: 推荐的目的地列表
    """
    recommendations = []

    try:
        if algorithm == 'popular' or user_id is None:
            recommendations = _get_popular_destinations(limit)
        elif algorithm == 'content':
            recommendations = _get_content_based_destinations(user_id, limit)
        elif algorithm == 'collaborative':
            recommendations = _get_collaborative_destinations(user_id, limit)
        else:  # hybrid
            popular = _get_popular_destinations(limit)
            content = _get_content_based_destinations(user_id, limit)
            # 合并推荐结果，去重
            seen = set()
            for item in content + popular:
                if item['destination'] not in seen:
                    seen.add(item['destination'])
                    recommendations.append(item)
                    if len(recommendations) >= limit:
                        break

        # 记录推荐日志
        if user_id:
            _log_recommendation(user_id, 'destination', recommendations, algorithm)

    except Exception as e:
        logger.error(f"推荐目的地失败: {e}")

    return recommendations[:limit]


def _get_popular_destinations(limit: int = 10) -> List[Dict[str, Any]]:
    """获取热门目的地（基于全局行程和搜索数据）"""
    try:
        conn = get_conn()
        cursor = conn.cursor()

        # 从行程表统计热门目的地
        cursor.execute('''
            SELECT 
                destination,
                COUNT(*) as plan_count,
                COUNT(DISTINCT user_id) as user_count,
                AVG(days) as avg_days
            FROM trips 
            WHERE destination IS NOT NULL
            GROUP BY destination
            ORDER BY plan_count DESC
            LIMIT %s
        ''', (limit * 2,))
        trips = cursor.fetchall()

        # 从行为日志统计搜索热度
        thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        cursor.execute('''
            SELECT 
                target_name as destination,
                COUNT(*) as search_count
            FROM user_behavior_logs 
            WHERE behavior_type = 'search' 
              AND target_type = 'destination'
              AND target_name IS NOT NULL
              AND created_at >= %s
            GROUP BY target_name
            ORDER BY search_count DESC
            LIMIT %s
        ''', (thirty_days_ago, limit * 2))
        searches = cursor.fetchall()

        cursor.close()
        conn.close()

        # 合并统计结果
        dest_map = {}
        for t in trips:
            dest = t['destination']
            if dest not in dest_map:
                dest_map[dest] = {
                    'destination': dest,
                    'plan_count': 0,
                    'search_count': 0,
                    'user_count': 0,
                    'avg_days': 0,
                }
            dest_map[dest]['plan_count'] = t['plan_count']
            dest_map[dest]['user_count'] = t['user_count']
            dest_map[dest]['avg_days'] = round(float(t['avg_days'] or 0), 1)

        for s in searches:
            dest = s['destination']
            if dest not in dest_map:
                dest_map[dest] = {
                    'destination': dest,
                    'plan_count': 0,
                    'search_count': 0,
                    'user_count': 0,
                    'avg_days': 0,
                }
            dest_map[dest]['search_count'] = s['search_count']

        # 计算热度评分（搜索权重0.4，行程权重0.6）
        for dest in dest_map.values():
            dest['hot_score'] = dest['search_count'] * 0.4 + dest['plan_count'] * 0.6
            dest['recommend_reason'] = f"近期有{dest['search_count']}次搜索，{dest['plan_count']}份行程"

        # 按热度排序
        result = sorted(dest_map.values(), key=lambda x: -x['hot_score'])[:limit]
        return result

    except Exception as e:
        logger.error(f"获取热门目的地失败: {e}")
        return []


def _get_content_based_destinations(user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """基于内容的推荐（根据用户画像推荐相似目的地）"""
    try:
        profile = get_user_profile(user_id)
        if not profile:
            return _get_popular_destinations(limit)

        # 获取用户喜欢的地区
        favorite_regions = profile.get('favorite_regions', [])
        preferred_destinations = profile.get('preferred_destinations', [])

        # 查找相似目的地（同省份、同类风格）
        conn = get_conn()
        cursor = conn.cursor()

        # 获取用户已去过的目的地
        visited = set(preferred_destinations)

        # 从热门目的地中排除已去过的
        popular = _get_popular_destinations(limit * 3)
        recommendations = []
        for dest in popular:
            if dest['destination'] not in visited:
                # 根据用户偏好调整评分
                score = dest['hot_score']
                # 预算偏好暂时无法从行程数据获取，暂不调整

                dest['recommend_score'] = round(score, 2)
                dest['recommend_reason'] = f"与您的出行偏好匹配（{profile.get('avg_budget_level', '中等')}预算）"
                recommendations.append(dest)

        cursor.close()
        conn.close()

        return sorted(recommendations, key=lambda x: -x.get('recommend_score', 0))[:limit]

    except Exception as e:
        logger.error(f"内容推荐失败: {e}")
        return _get_popular_destinations(limit)


def _get_collaborative_destinations(user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """协同过滤推荐（基于相似用户的行为）"""
    try:
        conn = get_conn()
        cursor = conn.cursor()

        # 获取当前用户去过的目的地
        cursor.execute('''
            SELECT DISTINCT destination FROM trips 
            WHERE user_id = %s  AND destination IS NOT NULL
        ''', (user_id,))
        user_dests = set(row['destination'] for row in cursor.fetchall())

        if not user_dests:
            cursor.close()
            conn.close()
            return _get_popular_destinations(limit)

        # 找出去过相同目的地的其他用户
        placeholders = ','.join(['%s'] * len(user_dests))
        cursor.execute(f'''
            SELECT DISTINCT user_id FROM trips 
            WHERE destination IN ({placeholders}) 
              AND user_id != %s 
              
            LIMIT 50
        ''', (*user_dests, user_id))
        similar_users = [row['user_id'] for row in cursor.fetchall()]

        if not similar_users:
            cursor.close()
            conn.close()
            return _get_popular_destinations(limit)

        # 找出这些相似用户去过但当前用户没去过的目的地
        placeholders = ','.join(['%s'] * len(similar_users))
        cursor.execute(f'''
            SELECT 
                destination,
                COUNT(*) as plan_count,
                COUNT(DISTINCT user_id) as similar_user_count
            FROM trips 
            WHERE user_id IN ({placeholders}) 
              
              AND destination IS NOT NULL
            GROUP BY destination
            ORDER BY plan_count DESC
            LIMIT %s
        ''', (*similar_users, limit * 2))
        recommendations = cursor.fetchall()

        cursor.close()
        conn.close()

        # 过滤掉当前用户已去过的目的地
        result = []
        for rec in recommendations:
            if rec['destination'] not in user_dests:
                rec['recommend_score'] = rec['plan_count'] * 0.5 + rec['similar_user_count'] * 0.5
                rec['recommend_reason'] = f"有{rec['similar_user_count']}位与您偏好相似的用户去过"
                result.append(rec)

        return result[:limit]

    except Exception as e:
        logger.error(f"协同过滤推荐失败: {e}")
        return _get_popular_destinations(limit)


# ==================== 景点推荐 ====================

def recommend_pois(
    user_id: Optional[int] = None,
    destination: Optional[str] = None,
    limit: int = 10,
    algorithm: str = 'hybrid'
) -> List[Dict[str, Any]]:
    """
    推荐景点

    注意：当前trips表未存储详细行程点位数据，此功能暂返回空列表。
    后续可通过行程详情表或POI缓存表实现。

    Args:
        user_id: 用户ID
        destination: 目的地（为空则全局推荐）
        limit: 返回数量
        algorithm: 推荐算法

    Returns:
        List: 推荐的景点列表
    """
    # TODO: 待行程详情表上线后实现完整的景点推荐
    return []


# ==================== 推荐日志 ====================

def _log_recommendation(
    user_id: int,
    rec_type: str,
    rec_items: List[Dict[str, Any]],
    algorithm: str
) -> None:
    """记录推荐日志"""
    try:
        conn = get_conn()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO recommendation_logs 
            (user_id, rec_type, rec_items, algorithm, score)
            VALUES (%s, %s, %s, %s, %s)
        ''', (
            user_id, rec_type,
            json.dumps(rec_items[:10], ensure_ascii=False),
            algorithm,
            rec_items[0].get('recommend_score', 0) if rec_items else 0
        ))

        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        logger.warning(f"记录推荐日志失败: {e}")
