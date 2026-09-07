# ============================================================
# 后端 Dockerfile - FastAPI + Python 3.11
# ============================================================
# 多阶段构建：减少最终镜像体积
#
# 构建参数：
#   INCLUDE_RAG=true  包含 RAG 依赖（chromadb + sentence-transformers + torch）
#   INCLUDE_RAG=false 不包含 RAG 依赖（默认，镜像较小）
#
# 示例：
#   docker build --build-arg INCLUDE_RAG=true -t travel-backend:rag .
#   docker build -t travel-backend:latest .
# ============================================================

# ---- 阶段1：构建依赖 ----
FROM python:3.11-slim AS builder

ARG INCLUDE_RAG=false

WORKDIR /app

# 安装系统依赖（编译Python包可能需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    default-libmysqlclient-dev \
    pkg-config \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .
COPY requirements-rag.txt .

# 安装基础依赖
RUN pip install --no-cache-dir --user -r requirements.txt

# 条件安装 RAG 依赖
RUN if [ "$INCLUDE_RAG" = "true" ]; then \
        echo "安装 RAG 依赖（chromadb + sentence-transformers + torch）..." && \
        pip install --no-cache-dir --user -r requirements-rag.txt; \
    else \
        echo "跳过 RAG 依赖安装（使用 --build-arg INCLUDE_RAG=true 启用）"; \
    fi

# 预下载 sentence-transformers 模型（如果包含 RAG）
RUN if [ "$INCLUDE_RAG" = "true" ]; then \
        echo "预下载 sentence-transformers 模型 BAAI/bge-small-zh-v1.5..." && \
        python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-zh-v1.5')" || \
        echo "模型预下载失败，将在首次运行时下载"; \
    fi

# ---- 阶段2：运行时 ----
FROM python:3.11-slim

ARG INCLUDE_RAG=false
ENV INCLUDE_RAG=${INCLUDE_RAG}

WORKDIR /app

# 安装运行时系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-libmysqlclient-dev \
    curl \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# 从构建阶段复制已安装的Python包
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# 复制应用代码
COPY . .

# 创建数据目录（RAG 知识库、日志等）
RUN mkdir -p /app/data/knowledge_base/chroma \
    mkdir -p /app/logs \
    mkdir -p /app/scripts

# 复制启动脚本
COPY scripts/wait-for-mysql.sh /app/scripts/wait-for-mysql.sh
COPY scripts/init-rag.sh /app/scripts/init-rag.sh
RUN chmod +x /app/scripts/*.sh

# 创建非root用户（安全最佳实践）
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# 环境变量（可通过docker-compose或.env覆盖）
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENV=prod \
    RAG_ENABLED=false \
    LOG_DIR=/app/logs

# 数据卷（持久化）
VOLUME ["/app/data", "/app/logs"]

# 启动命令：等待MySQL就绪 → 初始化RAG（可选）→ 启动应用
CMD ["/app/scripts/wait-for-mysql.sh", "python", "run.py"]
