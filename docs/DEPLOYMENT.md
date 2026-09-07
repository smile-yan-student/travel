# 旅行规划应用 - 部署文档

## 目录

1. [项目概述](#项目概述)
2. [系统要求](#系统要求)
3. [快速开始（Docker Compose 部署）](#快速开始docker-compose-部署)
4. [MySQL 数据库配置](#mysql-数据库配置)
5. [RAG 知识库配置（可选）](#rag-知识库配置可选)
6. [环境变量配置](#环境变量配置)
7. [Nginx 反向代理配置](#nginx-反向代理配置)
8. [HTTPS 配置（Let's Encrypt）](#https-配置lets-encrypt)
9. [数据库备份与恢复](#数据库备份与恢复)
10. [监控与日志](#监控与日志)
11. [安全加固](#安全加固)
12. [常见问题排查](#常见问题排查)
13. [升级与维护](#升级与维护)

---

## 项目概述

本项目是一个 AI 驱动的旅行规划应用，包含以下组件：

- **前端**：Vue 3 + Vite（用户端）
- **后端**：FastAPI + Python 3.11（API 服务）
- **数据库**：MySQL 8.0（数据存储）
- **AI 服务**：DeepSeek（线上模型）或 Ollama（本地模型）
- **地图服务**：腾讯地图 / 高德地图

### 架构图

```
用户浏览器
    │
    ▼
Nginx（反向代理 + HTTPS + 静态文件）
    ├── /api/ ──► 后端服务（FastAPI:8000）
    │              ├── MySQL（数据存储）
    │              ├── DeepSeek（AI 模型）
    │              └── 腾讯/高德地图（POI/路径）
    └── /     ──► 前端静态文件（Nginx:80）
```

---

## 系统要求

### 最低配置

- **CPU**：2 核
- **内存**：4 GB
- **磁盘**：20 GB（含系统和数据）
- **操作系统**：Linux（Ubuntu 20.04+ / CentOS 8+）或 macOS

### 推荐配置

- **CPU**：4 核
- **内存**：8 GB
- **磁盘**：50 GB SSD
- **操作系统**：Ubuntu 22.04 LTS

### 软件依赖

- Docker 20.10+
- Docker Compose 2.0+
- Nginx 1.18+（可选，使用 Docker 内置 Nginx 则不需要）

---

## 快速开始（Docker Compose 部署）

### 1. 克隆项目

```bash
git clone <your-repo-url> travel
cd travel
```

### 2. 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑环境变量（必须修改以下配置项）
vim .env
```

**必须修改的配置项**：

```bash
# 应用密钥（生产环境必须修改）
SECRET_KEY=<随机字符串，使用 python -c "import secrets; print(secrets.token_hex(32))" 生成>

# MySQL 密码
MYSQL_ROOT_PASSWORD=<强密码>
MYSQL_PASSWORD=<强密码>

# AI 模型 API Key
OPENAI_API_KEY=<你的 DeepSeek API Key>

# 地图服务 Key
TENCENT_MAP_KEY=<你的腾讯地图 Key>
# 或
AMAP_KEY=<你的高德地图 Key>

# CORS 允许的域名
CORS_ORIGINS=https://your-domain.com
```

### 3. 启动服务

```bash
# 构建并启动所有服务
make rebuild

# 或使用 docker-compose 命令
docker-compose up -d --build
```

### 4. 验证服务

```bash
# 查看服务状态
make ps

# 检查健康状态
make health

# 查看日志
make logs
```

### 5. 访问应用

- **前端**：http://localhost（或配置的域名）
- **后端 API 文档**：http://localhost:8000/docs
- **健康检查**：http://localhost:8000/api/health

---

## MySQL 数据库配置

### 数据库初始化

本项目采用**应用自动初始化**的方式管理数据库表结构：

- 应用启动时会自动调用 `init_db()` 函数创建所有表（使用 `CREATE TABLE IF NOT EXISTS`）
- 无需手动执行 SQL 脚本
- 表结构定义在 `backend/app/data/database.py` 中

### 数据表清单

| 表名 | 说明 |
|-----|------|
| `users` | 用户表（注册、登录、资料） |
| `trips` | 行程表（用户保存的行程） |
| `conversations` | 会话表（对话历史） |
| `admins` | 管理员表 |
| `must_visit` | 必去地标库 |
| `site_config` | 站点配置（地图Key等） |
| `generation_log` | 生成日志（规划记录） |
| `login_log` | 登录日志（安全审计） |
| `knowledge_category` | 知识分类 |
| `knowledge_doc` | 知识文档 |
| `knowledge_config` | 知识配置 |
| `poi_hierarchy` | POI层级关系（主/子景点） |

### 数据持久化

MySQL 数据通过 Docker 卷持久化到宿主机：

```bash
# 默认数据目录
./data/mysql/

# 可通过环境变量修改
MYSQL_DATA_DIR=/path/to/mysql/data
```

### 字符集配置

MySQL 默认使用 `utf8mb4` 字符集，支持完整的 Unicode（包括 emoji）：

```yaml
command: >
  --character-set-server=utf8mb4
  --collation-server=utf8mb4_unicode_ci
```

### 等待 MySQL 就绪

后端容器启动时会自动等待 MySQL 就绪：

- 使用 `wait-for-mysql.sh` 脚本检测 MySQL 端口和连接
- 默认重试 30 次，每次间隔 2 秒
- 可通过环境变量调整：`MAX_RETRIES`、`RETRY_DELAY`

---

## RAG 知识库配置（可选）

### 什么是 RAG

RAG（Retrieval-Augmented Generation，检索增强生成）是一种将知识库检索与大语言模型结合的技术：

1. **检索**：从知识库中检索与用户问题相关的内容
2. **增强**：将检索到的内容作为上下文提供给 LLM
3. **生成**：LLM 基于检索到的知识生成更准确、更有依据的回答

本项目的 RAG 功能用于提供景点的人文介绍、历史背景等知识。

### 架构

```
用户问题
    │
    ▼
文本向量化（sentence-transformers + BAAI/bge-small-zh-v1.5）
    │
    ▼
向量检索（ChromaDB，余弦相似度）
    │
    ▼
检索结果 + 用户问题 → LLM → 生成回答
```

### 启用 RAG

RAG 是**可选功能**，需要两步启用：

#### 步骤1：构建包含 RAG 依赖的镜像

```bash
# 方法1：通过环境变量
export INCLUDE_RAG=true
docker-compose build backend

# 方法2：直接构建
docker build --build-arg INCLUDE_RAG=true -t travel-backend:rag ./backend
```

**注意**：包含 RAG 依赖会增加镜像体积约 2GB（主要是 torch）。

#### 步骤2：设置环境变量启用 RAG

在 `.env` 文件中设置：

```bash
# 启用 RAG 功能
RAG_ENABLED=true

# RAG 数据目录（容器内路径）
RAG_DATA_DIR=/app/data/knowledge_base

# 向量化模型（中文优化的小模型，约100MB）
RAG_MODEL_NAME=BAAI/bge-small-zh-v1.5
```

### 依赖说明

RAG 相关依赖单独放在 `backend/requirements-rag.txt` 中：

| 依赖 | 说明 | 体积 |
|-----|------|------|
| `chromadb` | 向量数据库 | ~50MB |
| `sentence-transformers` | 文本向量化 | ~50MB |
| `torch` | 深度学习框架 | ~2GB |
| `transformers` | 模型加载 | ~100MB |
| `numpy` | 数值计算 | ~20MB |

### 模型下载

首次启用 RAG 时会自动下载向量化模型：

- **模型名称**：BAAI/bge-small-zh-v1.5
- **模型大小**：约 100MB
- **下载位置**：`~/.cache/huggingface/`
- **下载时机**：构建镜像时预下载（如果 INCLUDE_RAG=true），或首次运行时下载

如果构建时预下载失败，会在首次运行时自动下载（需要联网）。

### 数据持久化

RAG 数据通过 Docker 卷持久化到宿主机：

```bash
# 默认数据目录
./data/rag/

# 目录结构
./data/rag/
├── chroma/          # ChromaDB 向量数据库
│   └── poi_knowledge/
└── docs/            # 知识库文档（JSON格式）
    ├── 故宫.json
    ├── 西湖.json
    └── ...
```

### 初始化知识库

首次启用 RAG 后，需要导入知识库数据：

```bash
# 进入后端容器
make exec-backend

# 运行知识库初始化脚本（如果有）
python scripts/init_knowledge.py

# 或通过后台管理界面导入知识文档
```

### 验证 RAG 是否生效

```bash
# 查看后端日志中的 RAG 相关信息
make backend-logs | grep -i rag

# 测试景点知识问答
# 在前端对话中询问："故宫的历史背景是什么？"
# 如果 RAG 生效，回答会包含检索到的知识，并标注来源
```

### 关闭 RAG

如果不需要 RAG 功能，可以随时关闭：

```bash
# 在 .env 中设置
RAG_ENABLED=false

# 重启后端
docker-compose restart backend
```

关闭 RAG 后，对话功能仍然正常，只是不会检索知识库，回答会完全依赖 LLM 的内置知识。

### 性能考虑

| 方面 | 影响 | 建议 |
|-----|------|------|
| **镜像体积** | 增加约 2GB | 不需要 RAG 时不构建 RAG 镜像 |
| **内存占用** | 增加约 500MB（模型加载） | 服务器内存建议 8GB+ |
| **启动时间** | 增加约 10-30 秒（模型加载） | 首次启动较慢，后续正常 |
| **推理速度** | 增加约 100-500ms（检索+向量化） | 对用户体验影响较小 |
| **回答质量** | 显著提升（有知识依据） | 景点介绍更准确、更详细 |

---

## 环境变量配置

### 完整配置项说明

详见 [.env.example](../.env.example) 文件。

### 关键配置项

| 配置项 | 说明 | 默认值 | 是否必须 |
|-------|------|-------|---------|
| `ENV` | 运行环境（dev/staging/prod） | `prod` | 是 |
| `SECRET_KEY` | 应用密钥（JWT 签名） | 无 | **是** |
| `MYSQL_ROOT_PASSWORD` | MySQL root 密码 | 无 | **是** |
| `MYSQL_DATABASE` | 数据库名 | `travel` | 是 |
| `MYSQL_USER` | 数据库用户名 | `travel` | 是 |
| `MYSQL_PASSWORD` | 数据库密码 | 无 | **是** |
| `CORS_ORIGINS` | 允许跨域的域名 | `http://localhost` | 是 |
| `OPENAI_API_KEY` | AI 模型 API Key | 无 | **是** |
| `OPENAI_BASE_URL` | AI 模型 API 地址 | `https://api.deepseek.com/v1` | 是 |
| `AI_MODEL` | AI 模型名称 | `deepseek-chat` | 是 |
| `MAP_PROVIDER` | 地图提供商（tencent/amap） | `tencent` | 是 |
| `TENCENT_MAP_KEY` | 腾讯地图 Key | 无 | **是（腾讯地图）** |
| `AMAP_KEY` | 高德地图 Key | 无 | **是（高德地图）** |
| `EMAIL_ENABLED` | 是否启用邮箱服务 | `false` | 否 |
| `SMTP_HOST` | SMTP 服务器地址 | 无 | 否（启用邮箱时必须） |
| `SMTP_USER` | SMTP 用户名 | 无 | 否（启用邮箱时必须） |
| `SMTP_PASSWORD` | SMTP 密码/授权码 | 无 | 否（启用邮箱时必须） |

---

## Nginx 反向代理配置

### 1. 安装 Nginx

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install nginx -y

# CentOS/RHEL
sudo yum install nginx -y
```

### 2. 配置 Nginx

```bash
# 复制配置文件
sudo cp deploy/nginx/travel.conf /etc/nginx/conf.d/travel.conf

# 编辑配置文件，修改 server_name 和 SSL 证书路径
sudo vim /etc/nginx/conf.d/travel.conf
```

### 3. 测试并重载配置

```bash
# 测试配置
sudo nginx -t

# 重载配置
sudo nginx -s reload
```

### 4. 配置说明

配置文件包含以下功能：

- **HTTP → HTTPS 重定向**：所有 HTTP 请求自动跳转到 HTTPS
- **SSL 安全配置**：TLS 1.2/1.3，安全加密套件
- **安全头**：HSTS、X-Frame-Options、CSP 等
- **限流**：API 接口 10r/s，登录接口 2r/m
- **gzip 压缩**：减少传输体积
- **WebSocket 支持**：如需实时通信
- **静态资源缓存**：JS/CSS/图片长期缓存

---

## HTTPS 配置（Let's Encrypt）

### 1. 安装 Certbot

```bash
# Ubuntu/Debian
sudo apt install certbot python3-certbot-nginx -y
```

### 2. 申请证书

```bash
# 申请证书（需要域名已解析到服务器）
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

### 3. 自动续期

```bash
# 测试续期
sudo certbot renew --dry-run

# Certbot 会自动配置定时任务续期证书
# 查看定时任务
sudo systemctl list-timers | grep certbot
```

### 4. 证书路径

```
/etc/letsencrypt/live/your-domain.com/fullchain.pem
/etc/letsencrypt/live/your-domain.com/privkey.pem
```

---

## 数据库备份与恢复

### 自动备份（推荐）

创建定时任务，每天自动备份数据库：

```bash
# 编辑定时任务
crontab -e

# 添加以下内容（每天凌晨 3 点备份）
0 3 * * * cd /path/to/travel && make db-backup >> /var/log/travel-db-backup.log 2>&1
```

### 手动备份

```bash
# 备份数据库到 backups/ 目录
make db-backup
```

### 恢复数据库

```bash
# 从备份文件恢复
make db-restore FILE=backups/20240101_030000.sql
```

### 备份保留策略

建议保留最近 30 天的备份，定期清理旧备份：

```bash
# 清理 30 天前的备份
find backups/ -name "*.sql" -mtime +30 -delete
```

---

## 监控与日志

### 服务健康检查

```bash
# 检查所有服务健康状态
make health

# 检查后端健康状态
curl http://localhost:8000/api/health

# 检查后端运行状态
curl http://localhost:8000/api/status
```

### 查看日志

```bash
# 查看所有服务日志（实时）
make logs

# 查看后端日志
make backend-logs

# 查看前端日志
make frontend-logs

# 查看 MySQL 日志
make mysql-logs
```

### 日志位置

- **Docker 日志**：`docker-compose logs`
- **Nginx 日志**：`/var/log/nginx/travel_access.log`、`/var/log/nginx/travel_error.log`
- **后端日志**：Docker 卷 `backend_logs`，或容器内 `/app/logs/`

### 性能监控

```bash
# 查看容器资源使用情况
docker stats

# 查看磁盘使用情况
df -h

# 查看内存使用情况
free -h
```

---

## 安全加固

### 1. 系统安全

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 配置防火墙（只开放 80、443、22 端口）
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 22/tcp
sudo ufw enable

# 禁用 root 远程登录
sudo vim /etc/ssh/sshd_config
# 修改：PermitRootLogin no
sudo systemctl restart sshd
```

### 2. 应用安全

- ✅ **环境变量管理**：所有密钥、密码通过环境变量配置，不硬编码
- ✅ **JWT 认证**：使用 JWT Token 进行用户认证
- ✅ **密码加密**：使用 bcrypt 加密用户密码
- ✅ **SQL 注入防护**：使用参数化查询
- ✅ **速率限制**：API 接口限流，登录接口更严格
- ✅ **CORS 配置**：只允许指定域名访问
- ✅ **安全头**：HSTS、X-Frame-Options、CSP 等
- ✅ **输入验证**：所有用户输入进行验证和清洗

### 3. 数据库安全

```bash
# 修改 MySQL root 密码（已在 docker-compose 中配置）
# 创建独立的应用用户（已在 docker-compose 中配置）
# 定期备份数据库（见上文）
# 禁止 MySQL 远程访问（docker-compose 中只映射到 127.0.0.1）
```

### 4. 定期安全检查

```bash
# 检查系统漏洞
sudo apt install unattended-upgrades -y
sudo dpkg-reconfigure -plow unattended-upgrades

# 检查 Docker 镜像漏洞
docker scan travel-backend

# 检查 Python 依赖漏洞
cd backend && pip-audit
```

---

## 常见问题排查

### 1. 服务启动失败

```bash
# 查看服务状态
make ps

# 查看日志
make logs

# 查看特定服务日志
make backend-logs
make mysql-logs

# 重启服务
make restart
```

### 2. 数据库连接失败

```bash
# 检查 MySQL 容器状态
docker-compose ps mysql

# 查看 MySQL 日志
make mysql-logs

# 进入 MySQL 容器测试连接
make exec-mysql

# 检查数据库配置
grep DB_ .env
```

### 3. AI 模型调用失败

```bash
# 检查 API Key 配置
grep OPENAI_ .env

# 测试 API 连通性
curl https://api.deepseek.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"

# 查看后端日志中的 AI 调用错误
make backend-logs | grep -i ai
```

### 4. 地图服务不可用

```bash
# 检查地图 Key 配置
grep MAP_ .env
grep TENCENT_ .env
grep AMAP_ .env

# 测试地图 API
curl "https://apis.map.qq.com/ws/geocoder/v1/?address=北京&key=$TENCENT_MAP_KEY"

# 查看后端日志中的地图调用错误
make backend-logs | grep -i map
```

### 5. 前端页面空白

```bash
# 检查前端容器状态
docker-compose ps frontend

# 查看前端日志
make frontend-logs

# 检查前端构建是否成功
docker-compose logs frontend | grep -i error

# 清除浏览器缓存，强制刷新（Ctrl+Shift+R）
```

### 6. 端口被占用

```bash
# 查看端口占用情况
lsof -i :80
lsof -i :8000
lsof -i :3306

# 修改 docker-compose.yml 中的端口映射
# 例如：FRONTEND_PORT=8080
```

---

## 升级与维护

### 1. 升级应用

```bash
# 拉取最新代码
git pull

# 重新构建并启动
make rebuild

# 查看日志确认启动成功
make logs
```

### 2. 数据库迁移

如果数据库结构有变更，需要运行迁移脚本：

```bash
# 进入后端容器
make exec-backend

# 运行迁移（根据实际项目配置）
python -m alembic upgrade head
```

### 3. 清理旧镜像

```bash
# 清理未使用的 Docker 镜像
docker image prune -a

# 清理未使用的 Docker 卷（谨慎！）
docker volume prune
```

### 4. 日志轮转

配置日志轮转，避免日志文件过大：

```bash
# 创建日志轮转配置
sudo vim /etc/logrotate.d/travel

# 添加以下内容
/var/log/nginx/travel_*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0640 www-data adm
    sharedscripts
    postrotate
        nginx -s reload > /dev/null 2>&1 || true
    endscript
}
```

---

## 联系与支持

如有问题，请提交 Issue 或联系开发团队。

---

**文档版本**：v1.0  
**最后更新**：2026-08-31
