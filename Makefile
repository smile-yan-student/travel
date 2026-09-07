# ============================================================
# Makefile - 旅行规划应用
# ============================================================
# 使用方法：make <target>
# 示例：make up / make down / make logs / make build
# ============================================================

# 默认目标
.DEFAULT_GOAL := help

# Docker Compose 命令
DC = docker-compose
DC_RUN = $(DC) run --rm

# ============================================================
# 帮助信息
# ============================================================
.PHONY: help
help: ## 显示帮助信息
	@echo "旅行规划应用 - Makefile 命令"
	@echo ""
	@echo "常用命令："
	@echo "  make up              启动所有服务（后台运行）"
	@echo "  make down            停止所有服务"
	@echo "  make restart         重启所有服务"
	@echo "  make build           构建所有Docker镜像"
	@echo "  make rebuild         重新构建并启动所有服务"
	@echo "  make logs            查看所有服务日志（实时）"
	@echo "  make ps              查看服务状态"
	@echo ""
	@echo "服务日志："
	@echo "  make backend-logs    查看后端日志"
	@echo "  make frontend-logs   查看前端日志"
	@echo "  make mysql-logs      查看MySQL日志"
	@echo ""
	@echo "进入容器："
	@echo "  make exec-backend    进入后端容器"
	@echo "  make exec-mysql      进入MySQL容器"
	@echo ""
	@echo "数据库："
	@echo "  make db-backup       备份数据库"
	@echo "  make db-restore      恢复数据库（需指定FILE=xxx.sql）"
	@echo ""
	@echo "其他："
	@echo "  make clean           停止并删除所有容器和数据卷（危险！）"
	@echo "  make health          检查服务健康状态"
	@echo "  make config          检查docker-compose配置"

# ============================================================
# 服务管理
# ============================================================
.PHONY: up
up: ## 启动所有服务（后台运行）
	$(DC) up -d

.PHONY: down
down: ## 停止所有服务
	$(DC) down

.PHONY: restart
restart: ## 重启所有服务
	$(DC) restart

.PHONY: build
build: ## 构建所有Docker镜像
	$(DC) build

.PHONY: rebuild
rebuild: ## 重新构建并启动所有服务
	$(DC) up -d --build

.PHONY: ps
ps: ## 查看服务状态
	$(DC) ps

.PHONY: config
config: ## 检查docker-compose配置
	$(DC) config

# ============================================================
# 日志
# ============================================================
.PHONY: logs
logs: ## 查看所有服务日志（实时）
	$(DC) logs -f --tail=100

.PHONY: backend-logs
backend-logs: ## 查看后端日志
	$(DC) logs -f --tail=100 backend

.PHONY: frontend-logs
frontend-logs: ## 查看前端日志
	$(DC) logs -f --tail=100 frontend

.PHONY: mysql-logs
mysql-logs: ## 查看MySQL日志
	$(DC) logs -f --tail=100 mysql

# ============================================================
# 进入容器
# ============================================================
.PHONY: exec-backend
exec-backend: ## 进入后端容器
	$(DC) exec backend /bin/bash

.PHONY: exec-mysql
exec-mysql: ## 进入MySQL容器
	$(DC) exec mysql mysql -u$(MYSQL_USER:-travel) -p$(MYSQL_PASSWORD:-travelpassword) $(MYSQL_DATABASE:-travel)

# ============================================================
# 数据库
# ============================================================
.PHONY: db-backup
db-backup: ## 备份数据库
	@echo "备份数据库到 backups/$(shell date +%Y%m%d_%H%M%S).sql"
	@mkdir -p backups
	$(DC) exec -T mysql mysqldump -u$(MYSQL_USER:-travel) -p$(MYSQL_PASSWORD:-travelpassword) $(MYSQL_DATABASE:-travel) > backups/$(shell date +%Y%m%d_%H%M%S).sql
	@echo "备份完成"

.PHONY: db-restore
db-restore: ## 恢复数据库（需指定FILE=xxx.sql）
	@if [ -z "$(FILE)" ]; then echo "错误：请指定备份文件，例如 make db-restore FILE=backups/xxx.sql"; exit 1; fi
	@echo "从 $(FILE) 恢复数据库..."
	$(DC) exec -T mysql mysql -u$(MYSQL_USER:-travel) -p$(MYSQL_PASSWORD:-travelpassword) $(MYSQL_DATABASE:-travel) < $(FILE)
	@echo "恢复完成"

# ============================================================
# 健康检查
# ============================================================
.PHONY: health
health: ## 检查服务健康状态
	@echo "检查服务健康状态..."
	@echo ""
	@echo "MySQL:"
	@curl -s -o /dev/null -w "  状态: %{http_code}\n" http://localhost:$(MYSQL_PORT:-3306) 2>/dev/null || echo "  状态: 运行中（MySQL不支持HTTP检查）"
	@echo ""
	@echo "后端:"
	@curl -s -o /dev/null -w "  状态: %{http_code}\n" http://localhost:$(BACKEND_PORT:-8000)/api/health 2>/dev/null || echo "  状态: 未启动"
	@echo ""
	@echo "前端:"
	@curl -s -o /dev/null -w "  状态: %{http_code}\n" http://localhost:$(FRONTEND_PORT:-80)/ 2>/dev/null || echo "  状态: 未启动"
	@echo ""
	@echo "Docker 容器状态:"
	$(DC) ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

# ============================================================
# 清理
# ============================================================
.PHONY: clean
clean: ## 停止并删除所有容器和数据卷（危险！）
	@echo "警告：此操作将删除所有容器和数据卷！"
	@read -p "确认继续？(yes/no): " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		$(DC) down -v; \
		echo "清理完成"; \
	else \
		echo "已取消"; \
	fi
