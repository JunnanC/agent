#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────
# 依赖锁校验：检查 uv.lock 与 pyproject.toml 是否一致
# CI 和本地开发均可使用
# ──────────────────────────────────────────────────────────
set -euo pipefail

BACKEND_DIR="${1:-backend}"

cd "${BACKEND_DIR}"

if [ ! -f pyproject.toml ]; then
    echo "ERROR: ${BACKEND_DIR}/pyproject.toml 不存在"
    exit 1
fi

if [ ! -f uv.lock ]; then
    echo "FAIL: uv.lock 不存在"
    echo "  请先运行: cd ${BACKEND_DIR} && uv lock"
    exit 1
fi

# 记录 lock 文件的原始 hash
LOCK_HASH_BEFORE=$(sha256sum uv.lock | awk '{print $1}')

# 尝试重新锁定（dry-run 模式）
if command -v uv &>/dev/null; then
    uv lock --check 2>/dev/null
    LOCK_HASH_AFTER=$(sha256sum uv.lock | awk '{print $1}')

    if [ "${LOCK_HASH_BEFORE}" != "${LOCK_HASH_AFTER}" ]; then
        echo "FAIL: uv.lock 已变更，请先运行 uv lock 更新锁文件"
        exit 1
    fi
    echo "OK: uv.lock 与 pyproject.toml 一致"
else
    echo "WARN: uv 未安装，仅检查 uv.lock 是否存在"
    echo "  安装 uv: pip install uv"
fi
