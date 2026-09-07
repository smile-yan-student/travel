#!/bin/bash
# ============================================================
# RAG 初始化脚本
# ============================================================
# 功能：
#   1. 检查 RAG 依赖是否安装
#   2. 下载 sentence-transformers 模型（如果未下载）
#   3. 初始化 ChromaDB 向量数据库
#   4. 导入知识库数据（如果有）
#
# 使用方法：
#   ./init-rag.sh
#
# 环境变量：
#   RAG_ENABLED     是否启用 RAG（默认 false）
#   RAG_DATA_DIR    RAG 数据目录（默认 /app/data/knowledge_base）
#   RAG_MODEL_NAME  模型名称（默认 BAAI/bge-small-zh-v1.5）
# ============================================================

set -e

RAG_ENABLED="${RAG_ENABLED:-false}"
RAG_DATA_DIR="${RAG_DATA_DIR:-/app/data/knowledge_base}"
RAG_MODEL_NAME="${RAG_MODEL_NAME:-BAAI/bge-small-zh-v1.5}"

# 检查是否启用 RAG
if [ "$RAG_ENABLED" != "true" ]; then
    echo "RAG 未启用（RAG_ENABLED=$RAG_ENABLED），跳过初始化"
    exit 0
fi

echo "=========================================="
echo "RAG 初始化"
echo "=========================================="
echo "数据目录: $RAG_DATA_DIR"
echo "模型名称: $RAG_MODEL_NAME"
echo ""

# 1. 检查 RAG 依赖
echo "[1/4] 检查 RAG 依赖..."
if ! python -c "import chromadb" 2>/dev/null; then
    echo "错误：chromadb 未安装，请使用 --build-arg INCLUDE_RAG=true 构建镜像"
    exit 1
fi

if ! python -c "import sentence_transformers" 2>/dev/null; then
    echo "错误：sentence-transformers 未安装，请使用 --build-arg INCLUDE_RAG=true 构建镜像"
    exit 1
fi
echo "✓ RAG 依赖已安装"

# 2. 创建数据目录
echo "[2/4] 创建数据目录..."
mkdir -p "$RAG_DATA_DIR/chroma"
mkdir -p "$RAG_DATA_DIR/docs"
echo "✓ 数据目录已创建"

# 3. 下载模型（如果未下载）
echo "[3/4] 检查/下载 sentence-transformers 模型..."
python -c "
from sentence_transformers import SentenceTransformer
import os

model_name = '$RAG_MODEL_NAME'
cache_dir = os.path.expanduser('~/.cache/huggingface')
model_path = os.path.join(cache_dir, 'hub', 'models--' + model_name.replace('/', '--'))

if os.path.exists(model_path):
    print(f'✓ 模型已存在: {model_name}')
else:
    print(f'下载模型: {model_name}...')
    model = SentenceTransformer(model_name)
    print(f'✓ 模型下载完成')
" || {
    echo "警告：模型下载失败，将在首次使用时下载"
}

# 4. 初始化向量数据库
echo "[4/4] 初始化 ChromaDB 向量数据库..."
python -c "
import chromadb
from chromadb.config import Settings
import os

data_dir = '$RAG_DATA_DIR/chroma'
os.makedirs(data_dir, exist_ok=True)

client = chromadb.PersistentClient(path=data_dir)

# 获取或创建集合
collection = client.get_or_create_collection(
    name='poi_knowledge',
    metadata={'hnsw:space': 'cosine'}
)

count = collection.count()
print(f'✓ ChromaDB 初始化完成，当前文档数: {count}')
" || {
    echo "警告：ChromaDB 初始化失败"
}

echo ""
echo "=========================================="
echo "RAG 初始化完成"
echo "=========================================="
