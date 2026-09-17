#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

ensure_env() {
  local source_file="$1"
  local target_file="$2"
  if [[ ! -f "$target_file" ]]; then
    cp "$source_file" "$target_file"
  fi
}

ensure_env "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
ensure_env "$ROOT_DIR/backend/.env.example" "$ROOT_DIR/backend/.env"
ensure_env "$ROOT_DIR/frontend/.env.example" "$ROOT_DIR/frontend/.env"

set -a
# shellcheck disable=SC1091
source "$ROOT_DIR/.env"
# shellcheck disable=SC1091
source "$ROOT_DIR/backend/.env"
set +a

cd "$ROOT_DIR"
docker compose --env-file "$ROOT_DIR/.env" --env-file "$ROOT_DIR/backend/.env" up -d --build

until curl -fsS "http://localhost:${API_PORT:-8000}/admin/health" >/dev/null; do
  sleep 2
done

echo "Local environment is ready: http://localhost:${API_PORT:-8000}/admin/health"
