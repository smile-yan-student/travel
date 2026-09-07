"""
数据库连接池 + 表结构定义 + 初始化模块。

从 user_repository.py 抽出，统一管理数据库连接和表结构。
使用 pymysql 连接池（DBUtils.PooledDB），避免频繁创建连接。

表结构升级要点：
- 经纬度 DOUBLE → DECIMAL(10,6)（精度更高）
- 所有表增加 created_at / updated_at TIMESTAMP
- 增加索引（查询高频字段）
- 字符集统一 utf8mb4_unicode_ci
- 外键关联 ON DELETE CASCADE

功能特性：
- 连接池管理（懒加载单例）
- 事务管理（自动 commit/rollback）
- 只读连接管理
- 表结构定义（22张表）
- 数据库初始化（幂等）
- 查询和更新函数

使用方式：
    from app.data.database import get_conn, transaction, read_connection, init_db, execute_query, execute_update

    # 获取连接
    conn = get_conn()

    # 事务管理
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO ...")

    # 只读查询
    with read_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT ...")
            return cur.fetchall()

    # 初始化数据库
    init_db()

    # 执行查询
    results = execute_query("SELECT * FROM users WHERE id=%s", (1,), fetch="all")

    # 执行更新
    affected = execute_update("UPDATE users SET username=%s WHERE id=%s", ("new_name", 1))
"""
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union

import pymysql
from pymysql.cursors import DictCursor

from app.config import settings

# 连接池（懒加载）
_pool: Optional[Any] = None


def get_pool() -> Optional[Any]:
    """
    获取数据库连接池（单例）。

    连接池参数可通过环境变量配置：
    - DB_POOL_MAX_CONNECTIONS: 最大连接数（默认10）
    - DB_POOL_MIN_CACHED: 初始空闲连接数（默认2）
    - DB_POOL_MAX_CACHED: 最大空闲连接数（默认5）
    - DB_POOL_BLOCKING: 连接耗尽时是否阻塞等待（默认true）
    - DB_CONNECT_TIMEOUT: 连接超时秒数（默认5）
    - DB_READ_TIMEOUT: 读超时秒数（默认30）
    - DB_WRITE_TIMEOUT: 写超时秒数（默认30）

    Returns:
        Optional[Any]: 数据库连接池对象，DBUtils 未安装时返回 None
    """
    global _pool
    if _pool is None:
        try:
            from dbutils.pooled_db import PooledDB

            _pool = PooledDB(
                creator=pymysql,
                maxconnections=settings.db_pool_max_connections,
                mincached=settings.db_pool_min_cached,
                maxcached=settings.db_pool_max_cached,
                maxshared=settings.db_pool_max_shared,
                blocking=settings.db_pool_blocking,
                maxusage=settings.db_pool_max_usage,
                host=settings.db_host,
                port=settings.db_port,
                user=settings.db_user,
                password=settings.db_password,
                database=settings.db_name,
                charset="utf8mb4",
                cursorclass=DictCursor,
                autocommit=False,
                connect_timeout=settings.db_connect_timeout,
                read_timeout=settings.db_read_timeout,
                write_timeout=settings.db_write_timeout,
            )
        except ImportError:
            # DBUtils 未安装时回落直连
            _pool = None
    return _pool


def get_conn() -> Any:
    """
    获取数据库连接（优先从连接池，回落直连）。

    Returns:
        Any: 数据库连接对象
    """
    pool = get_pool()
    if pool:
        return pool.connection()
    return pymysql.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=False,
    )


# ---------------- 事务管理 ----------------


@contextmanager
def transaction() -> Iterator[Any]:
    """
    事务上下文管理器，自动处理commit和rollback。

    使用方式：
        with transaction() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO ...")
                cur.execute("UPDATE ...")

    特点：
    - 自动commit（无异常时）
    - 自动rollback（有异常时）
    - 自动关闭连接
    - 支持多条SQL语句在同一个事务中执行

    Yields:
        Any: 数据库连接对象
    """
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def read_connection() -> Iterator[Any]:
    """
    只读连接上下文管理器，自动关闭连接（不涉及事务）。

    使用方式：
        with read_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT ...")
                return cur.fetchall()

    特点：
    - 自动关闭连接
    - 不涉及事务（只读操作）
    - 适用于SELECT查询

    Yields:
        Any: 数据库连接对象
    """
    conn = get_conn()
    try:
        yield conn
    finally:
        conn.close()


# ---------------- 表结构定义 ----------------

TABLES_SQL: List[str] = [
    # users 表（升级：增加 updated_at / last_login_at / status）
    """
    CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(20) NOT NULL,
        password_hash VARCHAR(100) NOT NULL,
        enabled TINYINT(1) NOT NULL DEFAULT 1,
        status ENUM('active', 'disabled') NOT NULL DEFAULT 'active',
        last_login_at TIMESTAMP NULL DEFAULT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uk_username (username),
        KEY idx_enabled (enabled),
        KEY idx_created_at (created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    # trips 表（升级：经纬度 DECIMAL、增加 updated_at、索引）
    """
    CREATE TABLE IF NOT EXISTS trips (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        destination VARCHAR(50) NOT NULL,
        days INT NOT NULL DEFAULT 1,
        style VARCHAR(50) NOT NULL DEFAULT '',
        lng DECIMAL(10,6) NOT NULL DEFAULT 0,
        lat DECIMAL(10,6) NOT NULL DEFAULT 0,
        distance_km DECIMAL(10,2) NOT NULL DEFAULT 0,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        KEY idx_trips_user (user_id),
        KEY idx_trips_created (created_at),
        KEY idx_trips_destination (destination),
        CONSTRAINT fk_trips_user FOREIGN KEY (user_id)
            REFERENCES users(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    # conversations 表（升级：增加 summary / message_count / deleted_at、索引）
    """
    CREATE TABLE IF NOT EXISTS conversations (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        title VARCHAR(60) NOT NULL DEFAULT '未命名对话',
        summary VARCHAR(200) NOT NULL DEFAULT '',
        message_count INT NOT NULL DEFAULT 0,
        messages JSON NOT NULL,
        deleted_at TIMESTAMP NULL DEFAULT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        KEY idx_convo_user (user_id),
        KEY idx_convo_updated (updated_at),
        KEY idx_convo_created (created_at),
        CONSTRAINT fk_convo_user FOREIGN KEY (user_id)
            REFERENCES users(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    # admins 表（升级：增加 updated_at / last_login_at）
    """
    CREATE TABLE IF NOT EXISTS admins (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(32) NOT NULL,
        password_hash VARCHAR(100) NOT NULL,
        role VARCHAR(16) NOT NULL DEFAULT 'ops',
        enabled TINYINT(1) NOT NULL DEFAULT 1,
        last_login_at TIMESTAMP NULL DEFAULT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uk_admin_username (username)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    # must_visit 表（升级：rating DECIMAL、增加 adcode / lng / lat、索引）
    """
    CREATE TABLE IF NOT EXISTS must_visit (
        id INT AUTO_INCREMENT PRIMARY KEY,
        city VARCHAR(50) NOT NULL,
        name VARCHAR(100) NOT NULL,
        kw VARCHAR(100) NOT NULL DEFAULT '',
        category VARCHAR(20) NOT NULL DEFAULT '景点',
        rating DECIMAL(3,1) NOT NULL DEFAULT 4.5,
        priority INT NOT NULL DEFAULT 50,
        adcode VARCHAR(12) NOT NULL DEFAULT '',
        lng DECIMAL(10,6) NULL DEFAULT NULL,
        lat DECIMAL(10,6) NULL DEFAULT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        KEY idx_mv_city (city),
        KEY idx_mv_category (category),
        KEY idx_mv_priority (priority)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    # site_config 表（升级：v → TEXT、增加 description）
    """
    CREATE TABLE IF NOT EXISTS site_config (
        k VARCHAR(64) PRIMARY KEY,
        v TEXT NOT NULL,
        description VARCHAR(200) NOT NULL DEFAULT '',
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    # generation_log 表（升级：detail → TEXT、增加 user_id / params）
    """
    CREATE TABLE IF NOT EXISTS generation_log (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NULL DEFAULT NULL,
        kind VARCHAR(20) NOT NULL,
        model VARCHAR(50) NOT NULL DEFAULT '',
        status VARCHAR(16) NOT NULL DEFAULT 'ok',
        ms INT NOT NULL DEFAULT 0,
        detail TEXT NOT NULL,
        params JSON NULL DEFAULT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        KEY idx_gen_kind (kind),
        KEY idx_gen_status (status),
        KEY idx_gen_created (created_at),
        KEY idx_gen_user (user_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    # 登录审计日志表（新增）
    """
    CREATE TABLE IF NOT EXISTS login_log (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NULL DEFAULT NULL,
        username VARCHAR(32) NOT NULL,
        client_ip VARCHAR(45) NOT NULL DEFAULT '',
        status ENUM('success', 'failed', 'locked') NOT NULL,
        failure_reason VARCHAR(100) NOT NULL DEFAULT '',
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        KEY idx_login_username (username),
        KEY idx_login_ip (client_ip),
        KEY idx_login_created (created_at),
        KEY idx_login_status (status)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    # 知识库分类表（新增）
    """
    CREATE TABLE IF NOT EXISTS knowledge_category (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(64) NOT NULL COMMENT '分类名称：景点人文、历史名人、美食文化、旅行贴士',
        code VARCHAR(32) NOT NULL COMMENT '分类编码：scenic、celebrity、food、travel_tip',
        description VARCHAR(200) NOT NULL DEFAULT '',
        sort_order INT NOT NULL DEFAULT 0,
        is_active TINYINT(1) NOT NULL DEFAULT 1,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uk_code (code)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    # 知识文档表（新增）
    """
    CREATE TABLE IF NOT EXISTS knowledge_doc (
        id INT AUTO_INCREMENT PRIMARY KEY,
        category_id INT NOT NULL,
        title VARCHAR(200) NOT NULL COMMENT '文档标题',
        content TEXT NOT NULL COMMENT '文档内容（富文本/Markdown）',
        summary VARCHAR(500) NOT NULL DEFAULT '' COMMENT '内容摘要',
        tags VARCHAR(500) NOT NULL DEFAULT '' COMMENT '标签，逗号分隔',
        related_poi VARCHAR(200) NOT NULL DEFAULT '' COMMENT '关联POI名称，逗号分隔',
        related_city VARCHAR(100) NOT NULL DEFAULT '' COMMENT '关联城市',
        status ENUM('draft', 'published', 'offline') NOT NULL DEFAULT 'draft' COMMENT '状态：草稿、已发布、已下架',
        is_pinned TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否置顶（人工干预）',
        is_blocked TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否屏蔽（人工干预）',
        weight INT NOT NULL DEFAULT 0 COMMENT '权重（人工干预，越大越优先）',
        source VARCHAR(100) NOT NULL DEFAULT 'manual' COMMENT '来源：manual、import、ai_generated',
        author VARCHAR(64) NOT NULL DEFAULT '',
        view_count INT NOT NULL DEFAULT 0,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        KEY idx_doc_category (category_id),
        KEY idx_doc_status (status),
        KEY idx_doc_poi (related_poi),
        KEY idx_doc_city (related_city),
        KEY idx_doc_pinned (is_pinned),
        KEY idx_doc_created (created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    # 知识库配置表（新增）
    """
    CREATE TABLE IF NOT EXISTS knowledge_config (
        id INT AUTO_INCREMENT PRIMARY KEY,
        config_key VARCHAR(64) NOT NULL,
        config_value TEXT NOT NULL,
        description VARCHAR(200) NOT NULL DEFAULT '',
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uk_config_key (config_key)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    # 景区开放时间表（新增）
    """
    CREATE TABLE IF NOT EXISTS poi_open_hours (
        id INT AUTO_INCREMENT PRIMARY KEY,
        poi_name VARCHAR(200) NOT NULL COMMENT '景点名称',
        poi_city VARCHAR(100) NOT NULL DEFAULT '' COMMENT '所在城市',
        day_of_week TINYINT NOT NULL COMMENT '星期几：1-7（1=周一，7=周日），0=每天',
        open_time TIME NOT NULL COMMENT '开放时间',
        close_time TIME NOT NULL COMMENT '关闭时间',
        is_closed TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否闭馆',
        special_date DATE NULL COMMENT '特殊日期（节假日等）',
        note VARCHAR(500) NOT NULL DEFAULT '' COMMENT '备注',
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        KEY idx_poi_name (poi_name),
        KEY idx_poi_city (poi_city),
        KEY idx_day_of_week (day_of_week)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    # POI主表（主景点/大型景区）
    """
    CREATE TABLE IF NOT EXISTS poi_main (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(200) NOT NULL COMMENT '景点名称',
        alias TEXT COMMENT '别名（JSON数组）',
        city VARCHAR(100) NOT NULL DEFAULT '' COMMENT '所在城市',
        district VARCHAR(100) NOT NULL DEFAULT '' COMMENT '所在区县',
        category VARCHAR(50) NOT NULL DEFAULT '景点' COMMENT '分类：景点/美食/购物等',
        level VARCHAR(20) NOT NULL DEFAULT '' COMMENT '景区级别：5A/4A/无',
        description TEXT COMMENT '景点详细描述',
        recommended_duration INT NOT NULL DEFAULT 180 COMMENT '建议游玩时长（分钟）',
        best_time VARCHAR(500) NOT NULL DEFAULT '' COMMENT '最佳游玩时间',
        avoid_tips TEXT COMMENT '避坑提示（JSON数组）',
        lng DECIMAL(10,6) NULL COMMENT '经度',
        lat DECIMAL(10,6) NULL COMMENT '纬度',
        is_active TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用',
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uk_name_city (name, city),
        KEY idx_city (city),
        KEY idx_level (level),
        KEY idx_is_active (is_active)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    # POI内部子景点表（景区内部游览动线）
    """
    CREATE TABLE IF NOT EXISTS poi_inner (
        id INT AUTO_INCREMENT PRIMARY KEY,
        poi_main_id INT NOT NULL COMMENT '主景点ID',
        name VARCHAR(200) NOT NULL COMMENT '子景点名称',
        description TEXT COMMENT '子景点描述',
        duration_min INT NOT NULL DEFAULT 30 COMMENT '建议停留时间（分钟）',
        sort_order INT NOT NULL DEFAULT 0 COMMENT '游览顺序',
        highlight VARCHAR(500) NOT NULL DEFAULT '' COMMENT '拍照提示/亮点',
        must_see TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否必看',
        is_active TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用',
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        KEY idx_poi_main_id (poi_main_id),
        KEY idx_sort_order (sort_order)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    # POI周边附属景点表
    """
    CREATE TABLE IF NOT EXISTS poi_nearby (
        id INT AUTO_INCREMENT PRIMARY KEY,
        poi_main_id INT NOT NULL COMMENT '主景点ID',
        name VARCHAR(200) NOT NULL COMMENT '周边点位名称',
        category VARCHAR(50) NOT NULL DEFAULT '美食街' COMMENT '分类：美食街/老街/夜市/市井/购物街',
        description TEXT COMMENT '描述',
        distance_m INT NOT NULL DEFAULT 500 COMMENT '距主景区距离（米）',
        recommended_slot VARCHAR(20) NOT NULL DEFAULT '晚上' COMMENT '推荐时段：上午/中午/下午/晚上',
        duration_min INT NOT NULL DEFAULT 60 COMMENT '建议停留时间（分钟）',
        is_active TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用',
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        KEY idx_poi_main_id (poi_main_id),
        KEY idx_category (category)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    # 历史名人表
    """
    CREATE TABLE IF NOT EXISTS historical_figure (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100) NOT NULL COMMENT '人物名称',
        aliases TEXT COMMENT '别名（JSON数组）',
        category VARCHAR(50) NOT NULL DEFAULT '历史名人' COMMENT '分类：历史名人/革命先辈/文人墨客',
        brief_intro TEXT COMMENT '人物简介',
        travel_theme VARCHAR(200) NOT NULL DEFAULT '' COMMENT '相关的旅行主题',
        is_active TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用',
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uk_name (name),
        KEY idx_category (category)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    # 历史名人相关地点表
    """
    CREATE TABLE IF NOT EXISTS historical_figure_place (
        id INT AUTO_INCREMENT PRIMARY KEY,
        figure_id INT NOT NULL COMMENT '历史名人ID',
        place_name VARCHAR(100) NOT NULL COMMENT '地名',
        relation VARCHAR(100) NOT NULL DEFAULT '' COMMENT '关系描述（出生地、主要活动地、纪念地）',
        attractions TEXT COMMENT '相关景点（JSON数组）',
        travel_recommendation TEXT COMMENT '出行推荐介绍',
        sort_order INT NOT NULL DEFAULT 0 COMMENT '排序',
        is_active TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用',
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        KEY idx_figure_id (figure_id),
        KEY idx_place_name (place_name)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    # POI检索缓存表（按行政区域缓存，减少第三方API调用）
    """
    CREATE TABLE IF NOT EXISTS poi_cache (
        id INT AUTO_INCREMENT PRIMARY KEY,
        province VARCHAR(50) NOT NULL DEFAULT '' COMMENT '省份',
        city VARCHAR(50) NOT NULL DEFAULT '' COMMENT '城市',
        district VARCHAR(50) NOT NULL DEFAULT '' COMMENT '区县',
        adcode VARCHAR(20) NOT NULL DEFAULT '' COMMENT '行政区划代码',
        category VARCHAR(50) NOT NULL DEFAULT '景点' COMMENT '分类：景点/美食/购物/夜生活',
        poi_name VARCHAR(200) NOT NULL COMMENT 'POI名称',
        poi_id VARCHAR(100) NOT NULL DEFAULT '' COMMENT '第三方POI ID',
        address VARCHAR(500) NOT NULL DEFAULT '' COMMENT '地址',
        lng DECIMAL(10,6) NULL COMMENT '经度',
        lat DECIMAL(10,6) NULL COMMENT '纬度',
        rating DECIMAL(3,1) NULL COMMENT '评分',
        tel VARCHAR(50) NOT NULL DEFAULT '' COMMENT '电话',
        business_area VARCHAR(100) NOT NULL DEFAULT '' COMMENT '商圈',
        source VARCHAR(20) NOT NULL DEFAULT 'amap' COMMENT '数据来源：amap/tencent',
        raw_data JSON NULL COMMENT '原始数据（JSON）',
        cached_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '缓存时间',
        expire_at TIMESTAMP NULL COMMENT '过期时间',
        is_active TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否有效',
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uk_region_poi (adcode, category, poi_name, source),
        KEY idx_region (province, city, district),
        KEY idx_adcode (adcode),
        KEY idx_category (category),
        KEY idx_cached_at (cached_at),
        KEY idx_expire_at (expire_at),
        KEY idx_is_active (is_active)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    # major_attractions 表（主要景点库）
    """
    CREATE TABLE IF NOT EXISTS major_attractions (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(200) NOT NULL COMMENT '景点名称',
        aliases JSON NULL COMMENT '别名列表（JSON数组）',
        city VARCHAR(50) NOT NULL COMMENT '城市',
        district VARCHAR(50) NOT NULL DEFAULT '' COMMENT '区县',
        province VARCHAR(50) NOT NULL DEFAULT '' COMMENT '省份',
        level VARCHAR(20) NOT NULL DEFAULT '' COMMENT '景区等级：5A/4A/3A',
        category VARCHAR(20) NOT NULL DEFAULT '景点' COMMENT '分类：景点/美食/购物/夜生活',
        description TEXT NULL COMMENT '景点描述',
        recommended_duration INT NOT NULL DEFAULT 120 COMMENT '推荐游览时长（分钟）',
        lng DECIMAL(10,6) NULL COMMENT '经度',
        lat DECIMAL(10,6) NULL COMMENT '纬度',
        must_visit TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否必去',
        hot TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否热门',
        tags JSON NULL COMMENT '标签（JSON数组）',
        inner_route JSON NULL COMMENT '内部路线（JSON数组）',
        nearby_attractions JSON NULL COMMENT '附近景点（JSON数组）',
        best_time VARCHAR(200) NOT NULL DEFAULT '' COMMENT '最佳游览时间',
        avoid_tips JSON NULL COMMENT '避坑提示（JSON数组）',
        source VARCHAR(20) NOT NULL DEFAULT 'static' COMMENT '数据来源：static/ai_generated/manual',
        priority INT NOT NULL DEFAULT 50 COMMENT '优先级（0-100，越高越优先）',
        is_active TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否有效',
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uk_city_name (city, name),
        KEY idx_city (city),
        KEY idx_province (province),
        KEY idx_category (category),
        KEY idx_level (level),
        KEY idx_must_visit (must_visit),
        KEY idx_hot (hot),
        KEY idx_priority (priority),
        KEY idx_is_active (is_active)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ============================================================
    # 搜索结果缓存表 - 存储公开网页搜索结果，避免重复搜索
    # ============================================================
    """
    CREATE TABLE IF NOT EXISTS search_cache (
        id INT AUTO_INCREMENT PRIMARY KEY,
        keyword VARCHAR(500) NOT NULL COMMENT '搜索关键词',
        keyword_hash VARCHAR(32) NOT NULL COMMENT '关键词MD5哈希（用于快速查询）',
        category VARCHAR(20) NOT NULL DEFAULT 'general' COMMENT '搜索类别：guide/attraction/tips/food/hotel/official/general',
        results JSON NOT NULL COMMENT '搜索结果（JSON数组）',
        expire_at DOUBLE NOT NULL COMMENT '过期时间戳',
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uk_hash_category (keyword_hash, category),
        KEY idx_keyword (keyword(100)),
        KEY idx_category (category),
        KEY idx_expire_at (expire_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ============================================================
    # 景点预约规则表 - 存储景点的预约规则、开放时间、票价等信息
    # ============================================================
    """
    CREATE TABLE IF NOT EXISTS attraction_rules (
        id INT AUTO_INCREMENT PRIMARY KEY,
        attraction_name VARCHAR(100) NOT NULL COMMENT '景点名称',
        destination VARCHAR(50) NOT NULL DEFAULT '' COMMENT '所属目的地（城市）',
        reservation_channel VARCHAR(200) NOT NULL DEFAULT '' COMMENT '预约渠道（公众号/小程序/APP/官网）',
        reservation_url VARCHAR(500) NOT NULL DEFAULT '' COMMENT '预约链接',
        ticket_release_time VARCHAR(200) NOT NULL DEFAULT '' COMMENT '放票时间（如：提前7天20:00）',
        opening_hours VARCHAR(500) NOT NULL DEFAULT '' COMMENT '开放时间（如：08:30-17:00，16:00停止入场）',
        closing_days VARCHAR(200) NOT NULL DEFAULT '' COMMENT '闭馆日（如：每周一）',
        ticket_price VARCHAR(500) NOT NULL DEFAULT '' COMMENT '票价信息（如：旺季60元，淡季40元，学生半价）',
        visitor_route VARCHAR(500) NOT NULL DEFAULT '' COMMENT '游览路线（如：午门进，神武门出）',
        daily_limit VARCHAR(200) NOT NULL DEFAULT '' COMMENT '每日限流（如：每日最大接待8万人）',
        tips TEXT NULL COMMENT '其他提示',
        source VARCHAR(20) NOT NULL DEFAULT 'manual' COMMENT '数据来源：official/manual/search/ai_generated',
        review_status VARCHAR(20) NOT NULL DEFAULT 'approved' COMMENT '审核状态：pending待审核/approved已通过/rejected已拒绝',
        reviewed_by VARCHAR(50) NOT NULL DEFAULT '' COMMENT '审核人',
        reviewed_at TIMESTAMP NULL COMMENT '审核时间',
        review_comment VARCHAR(500) NOT NULL DEFAULT '' COMMENT '审核备注',
        is_active TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用',
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uk_attraction_name (attraction_name),
        KEY idx_destination (destination),
        KEY idx_is_active (is_active),
        KEY idx_source (source),
        KEY idx_review_status (review_status)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ============================================================
    # 旅游避坑提示表 - 存储目的地的旅游避坑提示、防骗建议等
    # ============================================================
    """
    CREATE TABLE IF NOT EXISTS travel_tips (
        id INT AUTO_INCREMENT PRIMARY KEY,
        destination VARCHAR(50) NOT NULL COMMENT '目的地（城市）',
        tip TEXT NOT NULL COMMENT '提示内容',
        category VARCHAR(20) NOT NULL DEFAULT 'general' COMMENT '类别：general/reservation/anti_fraud/traffic/food/accommodation/weather/safety',
        severity VARCHAR(10) NOT NULL DEFAULT 'info' COMMENT '严重程度：info/warning/danger',
        source VARCHAR(20) NOT NULL DEFAULT 'manual' COMMENT '数据来源：search/manual/official/ai_generated',
        review_status VARCHAR(20) NOT NULL DEFAULT 'approved' COMMENT '审核状态：pending待审核/approved已通过/rejected已拒绝',
        reviewed_by VARCHAR(50) NOT NULL DEFAULT '' COMMENT '审核人',
        reviewed_at TIMESTAMP NULL COMMENT '审核时间',
        review_comment VARCHAR(500) NOT NULL DEFAULT '' COMMENT '审核备注',
        is_active TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用',
        sort_order INT NOT NULL DEFAULT 0 COMMENT '排序权重（越大越靠前）',
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        KEY idx_destination (destination),
        KEY idx_category (category),
        KEY idx_severity (severity),
        KEY idx_is_active (is_active),
        KEY idx_sort_order (sort_order),
        KEY idx_review_status (review_status)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
]


def init_db() -> None:
    """
    初始化数据库：创建所有表（幂等）。

    遍历 TABLES_SQL 列表，执行所有 CREATE TABLE IF NOT EXISTS 语句。
    如果表已存在，则跳过（不会修改表结构）。

    Raises:
        Exception: 数据库操作失败时抛出
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for sql in TABLES_SQL:
                cur.execute(sql)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def execute_query(
    sql: str,
    params: Tuple[Any, ...] = (),
    fetch: str = "all",
) -> Optional[Union[List[Dict[str, Any]], Dict[str, Any]]]:
    """
    执行查询语句（SELECT），自动管理连接。

    Args:
        sql: SQL 语句（使用 %s 占位符）
        params: 查询参数元组
        fetch:  fetch 模式："all" 返回所有行，"one" 返回单行，None 不返回结果

    Returns:
        Optional[Union[List[Dict[str, Any]], Dict[str, Any]]]:
            - fetch="all": 返回所有行的列表
            - fetch="one": 返回单行字典
            - fetch=None: 返回 None（用于 INSERT/UPDATE/DELETE）

    Raises:
        Exception: 数据库操作失败时抛出
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            if fetch == "all":
                return cur.fetchall()
            elif fetch == "one":
                return cur.fetchone()
            conn.commit()
            return None
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def execute_update(sql: str, params: Tuple[Any, ...] = ()) -> int:
    """
    执行更新语句（INSERT/UPDATE/DELETE），返回受影响行数。

    Args:
        sql: SQL 语句（使用 %s 占位符）
        params: 更新参数元组

    Returns:
        int: 受影响行数（INSERT 语句返回自增 ID）

    Raises:
        Exception: 数据库操作失败时抛出
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            affected = cur.rowcount
            last_id = cur.lastrowid
        conn.commit()
        return last_id if sql.strip().upper().startswith("INSERT") else affected
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
