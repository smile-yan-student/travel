"""
用户画像服务

功能：
- 基于用户历史行程、评价、行为数据计算用户画像
- 用户行为记录
- 画像更新和查询
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import json
import logging

from app.data.database import get_conn

logger = logging.getLogger(__name__)


# ==================== 用户行为记录 ====================

def log_behavior(
    user_id: Optional[int],
    session_id: Optional[str],
    behavior_type: str,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    target_name: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    duration: Optional[int] = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> int:
    """
    记录用户行为

    Args:
        user_id: 用户ID（未登录可为空）
        session_id: 会话ID
        behavior_type: 行为类型(search/view/plan/review/share/click)
        target_type: 目标类型(destination/poi/trip)
        target_id: 目标ID
        target_name: 目标名称
        metadata: 行为元数据
        duration: 停留时长(秒)
        ip: IP地址
        user_agent: User Agent

    Returns:
        int: 行为记录ID
    """
    try:
        conn = get_conn()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO user_behavior_logs 
            (user_id, session_id, behavior_type, target_type, target_id, target_name, 
             metadata, duration, ip, user_agent)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            user_id, session_id, behavior_type, target_type, target_id, target_name,
            json.dumps(metadata, ensure_ascii=False) if metadata else None,
            duration, ip, user_agent
        ))
        log_id = cursor.lastrowid
        conn.commit()
        cursor.close()
        conn.close()

        # 异步触发画像更新（这里简化为直接调用）
        if user_id:
            try:
                update_user_profile(user_id)
            except Exception as e:
                logger.warning(f"更新用户画像失败: {e}")

        return log_id
    except Exception as e:
        logger.error(f"记录用户行为失败: {e}")
        return 0


# ==================== 用户画像计算 ====================

def calculate_user_profile(user_id: int) -> Dict[str, Any]:
    """
    基于用户历史数据计算用户画像

    Args:
        user_id: 用户ID

    Returns:
        Dict: 用户画像数据
    """
    profile = {
        'user_id': user_id,
        'travel_frequency': 'medium',
        'avg_budget_level': 'medium',
        'preferred_styles': [],
        'preferred_categories': [],
        'preferred_destinations': [],
        'travel_companion': 'solo',
        'total_trips': 0,
        'total_reviews': 0,
        'avg_rating': 0.0,
        'favorite_regions': [],
        'travel_seasons': [],
        'tags': [],
    }

    try:
        conn = get_conn()
        cursor = conn.cursor()

        # 1. 统计用户行程数据
        cursor.execute('''
            SELECT 
                COUNT(*) as total_trips,
                AVG(days) as avg_days,
                GROUP_CONCAT(DISTINCT destination) as destinations,
                GROUP_CONCAT(DISTINCT style) as styles
            FROM trips 
            WHERE user_id = %s 
        ''', (user_id,))
        trip_stats = cursor.fetchone()

        if trip_stats and trip_stats['total_trips'] > 0:
            profile['total_trips'] = trip_stats['total_trips']

            # 出行频率
            total_trips = trip_stats['total_trips']
            if total_trips <= 2:
                profile['travel_frequency'] = 'rare'
            elif total_trips <= 6:
                profile['travel_frequency'] = 'medium'
            else:
                profile['travel_frequency'] = 'frequent'

            # 预算水平（当前trips表无预算字段，暂设为medium）
            profile['avg_budget_level'] = 'medium'

            # 偏好风格
            if trip_stats['styles']:
                styles = [s.strip() for s in trip_stats['styles'].split(',') if s.strip()]
                profile['preferred_styles'] = list(set(styles))[:5]

            # 偏好目的地
            if trip_stats['destinations']:
                dests = [d.strip() for d in trip_stats['destinations'].split(',') if d.strip()]
                profile['preferred_destinations'] = list(set(dests))[:10]

            # 出行伙伴（当前trips表无此字段，暂设为默认值）
            profile['travel_companion'] = 'solo'

        # 2. 统计用户评价数据
        cursor.execute('''
            SELECT 
                COUNT(*) as total_reviews,
                AVG(overall_rating) as avg_rating,
                AVG(attraction_rating) as avg_attraction_rating,
                AVG(route_rating) as avg_route_rating
            FROM trip_reviews 
            WHERE user_id = %s 
        ''', (user_id,))
        review_stats = cursor.fetchone()

        if review_stats and review_stats['total_reviews'] > 0:
            profile['total_reviews'] = review_stats['total_reviews']
            profile['avg_rating'] = round(float(review_stats['avg_rating'] or 0), 2)

        # 3. 统计用户行为数据（最近90天）
        ninety_days_ago = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
        cursor.execute('''
            SELECT 
                behavior_type,
                target_type,
                target_name,
                COUNT(*) as cnt
            FROM user_behavior_logs 
            WHERE user_id = %s AND created_at >= %s
            GROUP BY behavior_type, target_type, target_name
            ORDER BY cnt DESC
            LIMIT 50
        ''', (user_id, ninety_days_ago))
        behaviors = cursor.fetchall()

        # 分析偏好类别
        category_counts = {}
        region_counts = {}
        for b in behaviors:
            if b['target_type'] == 'poi' and b['target_name']:
                category_counts[b['target_name']] = category_counts.get(b['target_name'], 0) + b['cnt']
            elif b['target_type'] == 'destination' and b['target_name']:
                region_counts[b['target_name']] = region_counts.get(b['target_name'], 0) + b['cnt']

        # 偏好类别（Top 5）
        profile['preferred_categories'] = sorted(category_counts.items(), key=lambda x: -x[1])[:5]
        profile['preferred_categories'] = [c[0] for c in profile['preferred_categories']]

        # 喜欢的地区（Top 5）
        profile['favorite_regions'] = sorted(region_counts.items(), key=lambda x: -x[1])[:5]
        profile['favorite_regions'] = [r[0] for r in profile['favorite_regions']]

        # 4. 生成用户标签
        tags = []
        if profile['travel_frequency'] == 'frequent':
            tags.append('旅行达人')
        elif profile['travel_frequency'] == 'rare':
            tags.append('偶尔出行')

        if profile['avg_budget_level'] == 'luxury':
            tags.append('品质出行')
        elif profile['avg_budget_level'] == 'economy':
            tags.append('经济实惠')

        if profile['travel_companion'] == 'family':
            tags.append('亲子出行')
        elif profile['travel_companion'] == 'couple':
            tags.append('情侣出行')
        elif profile['travel_companion'] == 'solo':
            tags.append('独自旅行')

        if '人文' in profile['preferred_styles'] or '历史文化' in profile['preferred_styles']:
            tags.append('文化爱好者')
        if '美食' in profile['preferred_styles']:
            tags.append('美食探索者')
        if '自然' in profile['preferred_styles']:
            tags.append('自然风光')
        if '摄影' in profile['preferred_styles']:
            tags.append('摄影爱好者')

        profile['tags'] = tags[:8]

        cursor.close()
        conn.close()

    except Exception as e:
        logger.error(f"计算用户画像失败: {e}")

    return profile


def update_user_profile(user_id: int) -> Optional[Dict[str, Any]]:
    """
    更新用户画像（计算后保存到数据库）

    Args:
        user_id: 用户ID

    Returns:
        Dict: 更新后的用户画像
    """
    try:
        profile = calculate_user_profile(user_id)

        conn = get_conn()
        cursor = conn.cursor()

        # 检查是否已存在画像
        cursor.execute('SELECT id FROM user_profiles WHERE user_id = %s', (user_id,))
        existing = cursor.fetchone()

        if existing:
            # 更新画像
            cursor.execute('''
                UPDATE user_profiles SET
                    travel_frequency = %s,
                    avg_budget_level = %s,
                    preferred_styles = %s,
                    preferred_categories = %s,
                    preferred_destinations = %s,
                    travel_companion = %s,
                    total_trips = %s,
                    total_reviews = %s,
                    avg_rating = %s,
                    favorite_regions = %s,
                    travel_seasons = %s,
                    tags = %s,
                    profile_version = profile_version + 1,
                    last_updated = NOW()
                WHERE user_id = %s
            ''', (
                profile['travel_frequency'],
                profile['avg_budget_level'],
                json.dumps(profile['preferred_styles'], ensure_ascii=False),
                json.dumps(profile['preferred_categories'], ensure_ascii=False),
                json.dumps(profile['preferred_destinations'], ensure_ascii=False),
                profile['travel_companion'],
                profile['total_trips'],
                profile['total_reviews'],
                profile['avg_rating'],
                json.dumps(profile['favorite_regions'], ensure_ascii=False),
                json.dumps(profile['travel_seasons'], ensure_ascii=False),
                json.dumps(profile['tags'], ensure_ascii=False),
                user_id
            ))
        else:
            # 创建画像
            cursor.execute('''
                INSERT INTO user_profiles 
                (user_id, travel_frequency, avg_budget_level, preferred_styles, 
                 preferred_categories, preferred_destinations, travel_companion, 
                 total_trips, total_reviews, avg_rating, favorite_regions, 
                 travel_seasons, tags, profile_version)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1)
            ''', (
                user_id,
                profile['travel_frequency'],
                profile['avg_budget_level'],
                json.dumps(profile['preferred_styles'], ensure_ascii=False),
                json.dumps(profile['preferred_categories'], ensure_ascii=False),
                json.dumps(profile['preferred_destinations'], ensure_ascii=False),
                profile['travel_companion'],
                profile['total_trips'],
                profile['total_reviews'],
                profile['avg_rating'],
                json.dumps(profile['favorite_regions'], ensure_ascii=False),
                json.dumps(profile['travel_seasons'], ensure_ascii=False),
                json.dumps(profile['tags'], ensure_ascii=False),
            ))

        conn.commit()
        cursor.close()
        conn.close()

        return profile
    except Exception as e:
        logger.error(f"更新用户画像失败: {e}")
        return None


def get_user_profile(user_id: int) -> Optional[Dict[str, Any]]:
    """
    获取用户画像（如果不存在则计算并保存）

    Args:
        user_id: 用户ID

    Returns:
        Dict: 用户画像数据
    """
    try:
        conn = get_conn()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM user_profiles WHERE user_id = %s', (user_id,))
        profile = cursor.fetchone()

        cursor.close()
        conn.close()

        if profile:
            # 解析JSON字段
            for key in ['preferred_styles', 'preferred_categories', 'preferred_destinations',
                        'favorite_regions', 'travel_seasons', 'tags']:
                if profile.get(key):
                    try:
                        profile[key] = json.loads(profile[key])
                    except:
                        profile[key] = []
            return profile
        else:
            # 画像不存在，计算并保存
            return update_user_profile(user_id)
    except Exception as e:
        logger.error(f"获取用户画像失败: {e}")
        return None
