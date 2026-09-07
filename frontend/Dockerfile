# ============================================================
# 前端 Dockerfile - Vue 3 + Vite + Nginx
# ============================================================
# 多阶段构建：Node.js构建 + Nginx提供静态文件

# ---- 阶段1：构建前端 ----
FROM node:20-alpine AS builder

WORKDIR /app

# 复制package.json并安装依赖（利用Docker缓存）
COPY package*.json ./
RUN npm ci --only=production || npm install

# 复制源代码并构建
COPY . .
RUN npm run build

# ---- 阶段2：Nginx提供静态文件 ----
FROM nginx:alpine

# 复制构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制Nginx配置（支持SPA路由）
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 暴露端口
EXPOSE 80

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost/ || exit 1

# 启动Nginx
CMD ["nginx", "-g", "daemon off;"]
