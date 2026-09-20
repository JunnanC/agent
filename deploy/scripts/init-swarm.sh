#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────
# 初始化 Docker Swarm 集群
# 在服务器上首次部署前运行一次即可
# ──────────────────────────────────────────────────────────
set -euo pipefail

echo "=== EduTech Swarm 初始化 ==="

# 1. 初始化 Swarm（如果尚未初始化）
if ! docker info --format '{{.Swarm.LocalNodeState}}' | grep -q active; then
    echo "[1/4] 初始化 Swarm ..."
    ADVERTISE_ADDR="${ADVERTISE_ADDR:-$(hostname -I | awk '{print $1}')}"
    docker swarm init --advertise-addr "${ADVERTISE_ADDR}:2377"
    echo "  Swarm 已初始化，advertise=${ADVERTISE_ADDR}:2377"
else
    echo "[1/4] Swarm 已在运行，跳过初始化"
fi

# 2. 创建基础设施网络（用于连接已有 MySQL/Redis 容器）
echo "[2/4] 创建 infra 网络 edutech-infra ..."
docker network create --driver bridge --attachable edutech-infra 2>/dev/null \
    || echo "  网络 edutech-infra 已存在，跳过"

# 3. 将已有 MySQL/Redis 容器接入 infra 网络
echo "[3/4] 将已有容器接入 edutech-infra ..."
for container in mysql8 redis_sfex-redis_SFex-1; do
    if docker inspect "$container" &>/dev/null; then
        docker network connect edutech-infra "$container" 2>/dev/null \
            || echo "  $container 已在 edutech-infra 中"
        echo "  $container → edutech-infra ✓"
    else
        echo "  WARNING: 容器 $container 不存在，跳过"
    fi
done

# 4. 验证
echo "[4/4] 验证 ..."
echo "  Swarm nodes: $(docker node ls --format '{{.Hostname}}' | wc -l)"
echo "  Networks:"
docker network ls --format '    {{.Name}} ({{.Driver}})' | grep -E '(edutech|infra)' || true
echo ""
echo "=== 初始化完成 ==="
echo ""
echo "后续步骤:"
echo "  1. 复制 backend/.env.prod.example → backend/.env.prod 并填写真实值"
echo "  2. 运行 deploy/scripts/deploy.sh 部署服务"
