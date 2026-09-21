#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
docker compose --env-file "$ROOT_DIR/.env" --env-file "$ROOT_DIR/backend/.env" down
