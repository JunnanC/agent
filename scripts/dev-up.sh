#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HEALTH_TIMEOUT_SECONDS=180

random_hex() {
  od -An -N16 -tx1 /dev/urandom | tr -d ' \n'
}

replace_placeholder() {
  local file="$1"
  local key="$2"
  local value="$3"
  if grep -q "^${key}=change-me$" "$file"; then
    sed -i "s|^${key}=change-me$|${key}=${value}|" "$file"
  fi
}

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

replace_placeholder "$ROOT_DIR/.env" COMPOSE_PROJECT_NAME agent-local
replace_placeholder "$ROOT_DIR/backend/.env" DJANGO_SECRET_KEY "$(random_hex)"
replace_placeholder "$ROOT_DIR/backend/.env" DJANGO_ALLOWED_HOSTS "localhost,127.0.0.1"
replace_placeholder "$ROOT_DIR/backend/.env" MYSQL_NAME agent
replace_placeholder "$ROOT_DIR/backend/.env" MYSQL_USER agent
replace_placeholder "$ROOT_DIR/backend/.env" MYSQL_PASSWORD "$(random_hex)"
replace_placeholder "$ROOT_DIR/backend/.env" MYSQL_ROOT_PASSWORD "$(random_hex)"
replace_placeholder "$ROOT_DIR/backend/.env" MINIO_ACCESS_KEY "$(random_hex)"
replace_placeholder "$ROOT_DIR/backend/.env" MINIO_SECRET_KEY "$(random_hex)"
replace_placeholder "$ROOT_DIR/backend/.env" MINIO_GENERAL_BUCKET agent-general
replace_placeholder "$ROOT_DIR/backend/.env" MINIO_ARCHIVE_BUCKET agent-archive
replace_placeholder "$ROOT_DIR/backend/.env" MINIO_SNAPSHOT_BUCKET agent-snapshot
replace_placeholder "$ROOT_DIR/backend/.env" MINIO_EXPORT_BUCKET agent-export

set -a
# shellcheck disable=SC1091
source "$ROOT_DIR/.env"
# shellcheck disable=SC1091
source "$ROOT_DIR/backend/.env"
set +a

cd "$ROOT_DIR"
docker compose --env-file "$ROOT_DIR/.env" --env-file "$ROOT_DIR/backend/.env" up -d --build

deadline=$((SECONDS + HEALTH_TIMEOUT_SECONDS))
until curl --fail --silent --max-time 2 "http://localhost:${API_PORT:-8000}/admin/health" >/dev/null; do
  if (( SECONDS >= deadline )); then
    echo "Backend health check timed out after ${HEALTH_TIMEOUT_SECONDS}s" >&2
    exit 1
  fi
  sleep 2
done

echo "Local environment is ready: http://localhost:${API_PORT:-8000}/admin/health"
