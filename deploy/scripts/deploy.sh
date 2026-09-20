#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────
# EduTech 生产环境部署脚本
# 用法: ./deploy/scripts/deploy.sh [--build] [--no-pull]
# ──────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
STACK_NAME="${STACK_NAME:-edutech}"
COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.prod.yml"

BUILD=false
NO_PULL=false
for arg in "$@"; do
    case "$arg" in
        --build)   BUILD=true ;;
        --no-pull) NO_PULL=true ;;
    esac
done

echo "=== EduTech 部署 ==="
echo "  项目目录: ${PROJECT_ROOT}"
echo "  Stack:    ${STACK_NAME}"
echo "  构建镜像: ${BUILD}"
echo ""

# ── 前置检查 ──────────────────────────────────────────────
if [ ! -f "${PROJECT_ROOT}/backend/.env.prod" ]; then
    echo "ERROR: backend/.env.prod 不存在"
    echo "  请先复制 .env.prod.example 并填写真实值:"
    echo "  cp backend/.env.prod.example backend/.env.prod"
    exit 1
fi

# ── 检查 Swarm ────────────────────────────────────────────
if ! docker info --format '{{.Swarm.LocalNodeState}}' | grep -q active; then
    echo "ERROR: Docker Swarm 未初始化"
    echo "  请先运行: bash deploy/scripts/init-swarm.sh"
    exit 1
fi

# ── 构建镜像 ──────────────────────────────────────────────
if [ "${BUILD}" = true ]; then
    echo "[1/4] 构建后端镜像 ..."
    docker build \
        -f "${PROJECT_ROOT}/backend/Dockerfile.prod" \
        -t edutech/backend:latest \
        -t "edutech/backend:$(date +%Y%m%d)-$(git -C "${PROJECT_ROOT}" rev-parse --short HEAD)" \
        "${PROJECT_ROOT}/backend/"
    echo "  镜像构建完成"
else
    echo "[1/4] 跳过构建（使用 --build 触发构建）"
fi

# ── 拉取镜像 ──────────────────────────────────────────────
if [ "${NO_PULL}" = false ]; then
    echo "[2/4] 拉取最新镜像 ..."
    docker pull edutech/backend:latest 2>/dev/null || echo "  使用本地镜像"
    docker pull nginx:1.27-alpine 2>/dev/null || true
    docker pull minio/minio:latest 2>/dev/null || true
else
    echo "[2/4] 跳过拉取"
fi

# ── 收集静态文件 ──────────────────────────────────────────
echo "[3/4] 收集 Django 静态文件 ..."
docker run --rm \
    --env-file "${PROJECT_ROOT}/backend/.env.prod" \
    -e DJANGO_SETTINGS_MODULE=config.settings.prod \
    -v "${PROJECT_ROOT}/backend/staticfiles:/app/staticfiles" \
    edutech/backend:latest \
    python manage.py collectstatic --noinput 2>/dev/null \
    || echo "  静态文件收集跳过（可能需要数据库连接）"

# ── 部署 Stack ────────────────────────────────────────────
echo "[4/4] 部署 Swarm Stack '${STACK_NAME}' ..."
docker stack deploy \
    -c "${COMPOSE_FILE}" \
    "${STACK_NAME}" \
    --prune

echo ""
echo "=== 部署完成 ==="
echo ""
echo "查看状态:"
echo "  docker stack services ${STACK_NAME}"
echo "  docker stack ps ${STACK_NAME}"
echo ""
echo "查看日志:"
echo "  docker service logs ${STACK_NAME}_api -f"
echo "  docker service logs ${STACK_NAME}_nginx -f"
