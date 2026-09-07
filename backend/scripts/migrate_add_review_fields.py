"""
数据库迁移脚本：添加数据审核流程字段

为 attraction_rules 和 travel_tips 表添加审核状态相关字段：
- review_status: 审核状态（pending/approved/rejected）
- reviewed_by: 审核人
- reviewed_at: 审核时间
- review_comment: 审核备注

使用方式：
    cd backend
    ./.venv/bin/python scripts/migrate_add_review_fields.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.data.database import get_conn


def column_exists(cursor, table_name: str, column_name: str) -> bool:
    """检查列是否存在"""
    cursor.execute(f"SHOW COLUMNS FROM {table_name} LIKE '{column_name}'")
    return cursor.fetchone() is not None


def add_column_if_not_exists(
    cursor,
    table_name: str,
    column_name: str,
    column_definition: str
) -> bool:
    """如果列不存在则添加"""
    if column_exists(cursor, table_name, column_name):
        print(f"  ✓ 列 {column_name} 已存在，跳过")
        return False
    else:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_definition}")
        print(f"  ✓ 添加列 {column_name}")
        return True


def add_index_if_not_exists(
    cursor,
    table_name: str,
    index_name: str,
    index_definition: str
) -> bool:
    """如果索引不存在则添加"""
    cursor.execute(f"SHOW INDEX FROM {table_name} WHERE Key_name = '{index_name}'")
    if cursor.fetchone():
        print(f"  ✓ 索引 {index_name} 已存在，跳过")
        return False
    else:
        cursor.execute(f"ALTER TABLE {table_name} ADD INDEX {index_definition}")
        print(f"  ✓ 添加索引 {index_name}")
        return True


def migrate():
    """执行迁移"""
    print("=" * 60)
    print("数据库迁移：添加数据审核流程字段")
    print("=" * 60)

    conn = get_conn()
    cursor = conn.cursor()

    try:
        # ============================================================
        # 1. attraction_rules 表
        # ============================================================
        print("\n1. 处理 attraction_rules 表...")

        add_column_if_not_exists(
            cursor, "attraction_rules", "review_status",
            "review_status VARCHAR(20) NOT NULL DEFAULT 'approved' COMMENT '审核状态：pending待审核/approved已通过/rejected已拒绝' AFTER source"
        )
        add_column_if_not_exists(
            cursor, "attraction_rules", "reviewed_by",
            "reviewed_by VARCHAR(50) NOT NULL DEFAULT '' COMMENT '审核人' AFTER review_status"
        )
        add_column_if_not_exists(
            cursor, "attraction_rules", "reviewed_at",
            "reviewed_at TIMESTAMP NULL COMMENT '审核时间' AFTER reviewed_by"
        )
        add_column_if_not_exists(
            cursor, "attraction_rules", "review_comment",
            "review_comment VARCHAR(500) NOT NULL DEFAULT '' COMMENT '审核备注' AFTER reviewed_at"
        )
        add_index_if_not_exists(
            cursor, "attraction_rules", "idx_review_status",
            "idx_review_status (review_status)"
        )

        # ============================================================
        # 2. travel_tips 表
        # ============================================================
        print("\n2. 处理 travel_tips 表...")

        add_column_if_not_exists(
            cursor, "travel_tips", "review_status",
            "review_status VARCHAR(20) NOT NULL DEFAULT 'approved' COMMENT '审核状态：pending待审核/approved已通过/rejected已拒绝' AFTER source"
        )
        add_column_if_not_exists(
            cursor, "travel_tips", "reviewed_by",
            "reviewed_by VARCHAR(50) NOT NULL DEFAULT '' COMMENT '审核人' AFTER review_status"
        )
        add_column_if_not_exists(
            cursor, "travel_tips", "reviewed_at",
            "reviewed_at TIMESTAMP NULL COMMENT '审核时间' AFTER reviewed_by"
        )
        add_column_if_not_exists(
            cursor, "travel_tips", "review_comment",
            "review_comment VARCHAR(500) NOT NULL DEFAULT '' COMMENT '审核备注' AFTER reviewed_at"
        )
        add_index_if_not_exists(
            cursor, "travel_tips", "idx_review_status",
            "idx_review_status (review_status)"
        )

        conn.commit()
        print("\n" + "=" * 60)
        print("✓ 数据库迁移完成！")
        print("=" * 60)

    except Exception as e:
        conn.rollback()
        print(f"\n✗ 迁移失败: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    migrate()
