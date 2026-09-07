#!/usr/bin/env python3
"""
数据库迁移脚本：为已存在的表添加新字段（表结构升级）。

升级内容：
- users: 增加 status / last_login_at / updated_at
- trips: 经纬度 DOUBLE → DECIMAL(10,6)、增加 updated_at
- conversations: 增加 summary / message_count / deleted_at / updated_at
- admins: 增加 last_login_at / updated_at
- must_visit: rating DOUBLE → DECIMAL(3,1)、增加 adcode / lng / lat / updated_at
- site_config: v VARCHAR(500) → TEXT、增加 description
- generation_log: detail VARCHAR(500) → TEXT、增加 user_id / params
- 新增 login_log 表

幂等执行：字段已存在时跳过（通过 information_schema 检查）。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.data.database import get_conn, settings
from app.security.db_security import safe_limit


def column_exists(cur, table: str, column: str) -> bool:
    """检查字段是否已存在。"""
    cur.execute(
        "SELECT COUNT(*) AS c FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME=%s",
        (settings.db_name, table, column),
    )
    return cur.fetchone()["c"] > 0


def add_column(cur, table: str, column: str, definition: str) -> None:
    """添加字段（幂等）。"""
    if column_exists(cur, table, column):
        print(f"  跳过 {table}.{column}（已存在）")
        return
    cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    print(f"  添加 {table}.{column} {definition}")


def modify_column(cur, table: str, column: str, definition: str) -> None:
    """修改字段类型。"""
    cur.execute(f"ALTER TABLE {table} MODIFY COLUMN {column} {definition}")
    print(f"  修改 {table}.{column} → {definition}")


def add_index(cur, table: str, index_name: str, columns: str) -> None:
    """添加索引（幂等）。"""
    cur.execute(
        "SELECT COUNT(*) AS c FROM information_schema.STATISTICS "
        "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND INDEX_NAME=%s",
        (settings.db_name, table, index_name),
    )
    if cur.fetchone()["c"] > 0:
        print(f"  跳过索引 {table}.{index_name}（已存在）")
        return
    cur.execute(f"ALTER TABLE {table} ADD INDEX {index_name} ({columns})")
    print(f"  添加索引 {table}.{index_name} ({columns})")


def main():
    print("=== 数据库迁移：表结构升级 ===\n")

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # users 表
            print("【users】")
            add_column(cur, "users", "status", "ENUM('active','disabled') NOT NULL DEFAULT 'active' AFTER enabled")
            add_column(cur, "users", "last_login_at", "TIMESTAMP NULL DEFAULT NULL AFTER status")
            add_column(cur, "users", "updated_at", "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP AFTER created_at")
            add_index(cur, "users", "idx_enabled", "enabled")
            add_index(cur, "users", "idx_created_at", "created_at")

            # trips 表
            print("\n【trips】")
            modify_column(cur, "trips", "lng", "DECIMAL(10,6) NOT NULL DEFAULT 0")
            modify_column(cur, "trips", "lat", "DECIMAL(10,6) NOT NULL DEFAULT 0")
            modify_column(cur, "trips", "distance_km", "DECIMAL(10,2) NOT NULL DEFAULT 0")
            add_column(cur, "trips", "updated_at", "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP AFTER created_at")
            add_index(cur, "trips", "idx_trips_created", "created_at")
            add_index(cur, "trips", "idx_trips_destination", "destination")

            # conversations 表
            print("\n【conversations】")
            add_column(cur, "conversations", "summary", "VARCHAR(200) NOT NULL DEFAULT '' AFTER title")
            add_column(cur, "conversations", "message_count", "INT NOT NULL DEFAULT 0 AFTER summary")
            add_column(cur, "conversations", "deleted_at", "TIMESTAMP NULL DEFAULT NULL AFTER messages")
            add_column(cur, "conversations", "updated_at", "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP AFTER created_at")
            add_index(cur, "conversations", "idx_convo_updated", "updated_at")
            add_index(cur, "conversations", "idx_convo_created", "created_at")

            # admins 表
            print("\n【admins】")
            add_column(cur, "admins", "last_login_at", "TIMESTAMP NULL DEFAULT NULL AFTER enabled")
            add_column(cur, "admins", "updated_at", "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP AFTER created_at")

            # must_visit 表
            print("\n【must_visit】")
            modify_column(cur, "must_visit", "rating", "DECIMAL(3,1) NOT NULL DEFAULT 4.5")
            add_column(cur, "must_visit", "adcode", "VARCHAR(12) NOT NULL DEFAULT '' AFTER priority")
            add_column(cur, "must_visit", "lng", "DECIMAL(10,6) NULL DEFAULT NULL AFTER adcode")
            add_column(cur, "must_visit", "lat", "DECIMAL(10,6) NULL DEFAULT NULL AFTER lng")
            add_column(cur, "must_visit", "updated_at", "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP AFTER created_at")
            add_index(cur, "must_visit", "idx_mv_category", "category")
            add_index(cur, "must_visit", "idx_mv_priority", "priority")

            # site_config 表
            print("\n【site_config】")
            modify_column(cur, "site_config", "v", "TEXT NOT NULL")
            add_column(cur, "site_config", "description", "VARCHAR(200) NOT NULL DEFAULT '' AFTER v")

            # generation_log 表
            print("\n【generation_log】")
            modify_column(cur, "generation_log", "detail", "TEXT NOT NULL")
            add_column(cur, "generation_log", "user_id", "INT NULL DEFAULT NULL AFTER id")
            add_column(cur, "generation_log", "params", "JSON NULL DEFAULT NULL AFTER detail")
            add_index(cur, "generation_log", "idx_gen_user", "user_id")

            # login_log 表（新增）
            print("\n【login_log】（新增）")
            cur.execute("""
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
            """)
            print("  创建 login_log 表")

        conn.commit()
        print("\n=== 迁移完成 ===")
    except Exception as e:
        conn.rollback()
        print(f"\n迁移失败: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
