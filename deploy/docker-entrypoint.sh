#!/bin/sh
set -e

# Load Docker secrets into environment variables
# Each secret file in /run/secrets/ maps to an env var
for secret_file in /run/secrets/*; do
  [ -f "$secret_file" ] || continue
  secret_name=$(basename "$secret_file")
  # Convert secret name to uppercase env var name
  env_name=$(echo "$secret_name" | tr "[:lower:]" "[:upper:]")
  # Export the secret value as an environment variable
  export "$env_name"="$(cat "$secret_file")"
done

# Map secret names to the env var names the app expects
export DJANGO_SECRET_KEY="${DJANGO_SECRET_KEY:-}"
export MYSQL_PASSWORD="${MYSQL_PASSWORD:-}"
export REDIS_CACHE_URL="${REDIS_CACHE_URL_V2:-${REDIS_CACHE_URL:-}}"
export CELERY_BROKER_URL="${CELERY_BROKER_URL_V2:-${CELERY_BROKER_URL:-}}"
export MINIO_ACCESS_KEY="${MINIO_ACCESS_KEY:-}"
export MINIO_SECRET_KEY="${MINIO_SECRET_KEY:-}"

# Execute the original command
exec "$@"
