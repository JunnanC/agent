# Backend Local Environment

## Design decisions

- The backend image uses Python 3.12. Source compatibility targets Python 3.11+.
- Formatting uses `ruff format`; static checks use `ruff check`. Do not use black.
- Repository text files use LF line endings; `.gitattributes` enforces this.
- MySQL stores business facts only.
- Redis logical database 0 stores cache, locks, rate limiting, short-term session state, and idempotency records.
- Redis logical database 1 stores the Celery broker and result backend.
- Object content is stored only in MinIO. Buckets are private and file access uses time-limited presigned URLs.
- Django does not own the database schema and must not generate migrations in this phase.
- The image build defaults to the Tsinghua Debian mirror because the official Debian mirror is unstable in the local network. Override `DEBIAN_MIRROR_URL` at build time if another mirror is required.

## Startup

```bash
cp .env.example .env
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
scripts/dev-up.sh
```

Health check: `http://localhost:8000/admin/health`

Stop the environment without deleting volumes:

```bash
scripts/dev-down.sh
```

## Environment variables

| Variable | Purpose | Required | Default | Affected functionality |
|---|---|---:|---:|---|
| `COMPOSE_PROJECT_NAME` | Compose project namespace | Yes | None | All containers |
| `API_PORT` | Host API port | Yes | None | API access |
| `MINIO_API_PORT` | Host MinIO API port | Yes | None | Object API access |
| `MINIO_CONSOLE_PORT` | Host MinIO console port | Yes | None | Object console access |
| `TZ` | Container timezone | Yes | `UTC` | All containers |
| `DJANGO_SECRET_KEY` | Django secret key | Yes | None | Django runtime |
| `DJANGO_DEBUG` | Django debug mode | No | `false` | Django runtime |
| `MYSQL_HOST` | MySQL hostname | Yes | None | Database access |
| `MYSQL_PORT` | MySQL port | Yes | None | Database access |
| `MYSQL_NAME` | MySQL database | Yes | None | Database access |
| `MYSQL_USER` | MySQL user | Yes | None | Database access |
| `MYSQL_PASSWORD` | MySQL password | Yes | None | Database access |
| `MYSQL_ROOT_PASSWORD` | MySQL root password | Yes | None | MySQL container initialization |
| `REDIS_CACHE_URL` | Redis URL for cache and short-term state | Yes | None | Cache, locks, rate limiting, idempotency |
| `CELERY_BROKER_URL` | Redis URL for Celery | Yes | None | Worker and beat |
| `MINIO_ENDPOINT` | MinIO endpoint | Yes | None | Object storage |
| `MINIO_ACCESS_KEY` | MinIO access key | Yes | None | Object storage and initialization |
| `MINIO_SECRET_KEY` | MinIO secret key | Yes | None | Object storage and initialization |
| `MINIO_SECURE` | Use HTTPS for MinIO | No | `false` | Object storage |
| `MINIO_GENERAL_BUCKET` | General files bucket | Yes | None | File storage |
| `MINIO_ARCHIVE_BUCKET` | Results and archive bucket | Yes | None | Results and archive storage |
| `MINIO_SNAPSHOT_BUCKET` | Runtime snapshot bucket | Yes | None | Runtime snapshots |
| `MINIO_EXPORT_BUCKET` | Audit export bucket | Yes | None | Audit exports |

Any newly added environment variable must be added to this table and the matching `.env.example`.

## Known legacy security findings

- The historical Django `SECRET_KEY` is treated as compromised. It has been rotated, and current settings require `DJANGO_SECRET_KEY` from the environment.
- The legacy `db.sqlite3` is removed from Git tracking; the file remains ignored and must not be used in production.
- History is intentionally not rewritten. Shared branches stay stable, and local clones may retain historical content.
