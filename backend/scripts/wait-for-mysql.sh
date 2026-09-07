#!/bin/bash
# ============================================================
# 等待 MySQL 就绪后启动应用
# ============================================================
# 使用方法：
#   ./wait-for-mysql.sh python run.py
#
# 环境变量：
#   DB_HOST     MySQL 主机（默认 mysql）
#   DB_PORT     MySQL 端口（默认 3306）
#   DB_USER     MySQL 用户名（默认 travel）
#   DB_PASSWORD MySQL 密码（默认 travelpassword）
#   MAX_RETRIES 最大重试次数（默认 30）
#   RETRY_DELAY 重试间隔秒数（默认 2）
# ============================================================

set -e

DB_HOST="${DB_HOST:-mysql}"
DB_PORT="${DB_PORT:-3306}"
DB_USER="${DB_USER:-travel}"
DB_PASSWORD="${DB_PASSWORD:-travelpassword}"
MAX_RETRIES="${MAX_RETRIES:-30}"
RETRY_DELAY="${RETRY_DELAY:-2}"

echo "等待 MySQL 就绪 ($DB_HOST:$DB_PORT)..."

# 方法1：使用 nc 检测端口
wait_for_port() {
    local retries=0
    while [ $retries -lt $MAX_RETRIES ]; do
        if nc -z -w 2 "$DB_HOST" "$DB_PORT" 2>/dev/null; then
            echo "MySQL 端口 $DB_PORT 已开放"
            return 0
        fi
        retries=$((retries + 1))
        echo "等待 MySQL... ($retries/$MAX_RETRIES)"
        sleep $RETRY_DELAY
    done
    return 1
}

# 方法2：使用 mysql 客户端检测连接（如果可用）
wait_for_mysql() {
    local retries=0
    while [ $retries -lt $MAX_RETRIES ]; do
        if mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASSWORD" -e "SELECT 1" >/dev/null 2>&1; then
            echo "MySQL 连接成功"
            return 0
        fi
        retries=$((retries + 1))
        echo "等待 MySQL 连接... ($retries/$MAX_RETRIES)"
        sleep $RETRY_DELAY
    done
    return 1
}

# 先等待端口开放
if wait_for_port; then
    # 再等待 MySQL 完全就绪（可能需要几秒初始化）
    echo "等待 MySQL 完全就绪..."
    sleep 5

    # 尝试使用 mysql 客户端检测（如果可用）
    if command -v mysql >/dev/null 2>&1; then
        wait_for_mysql || echo "警告：MySQL 连接检测失败，但端口已开放，继续启动..."
    else
        echo "mysql 客户端不可用，跳过连接检测"
    fi
else
    echo "错误：MySQL 在 $MAX_RETRIES 次重试后仍未就绪"
    exit 1
fi

echo "MySQL 已就绪，启动应用..."

# 初始化 RAG（如果启用）
if [ "$RAG_ENABLED" = "true" ]; then
    echo "RAG 已启用，执行初始化..."
    /app/scripts/init-rag.sh || echo "警告：RAG 初始化失败，继续启动应用..."
fi

# 执行传入的命令
exec "$@"
