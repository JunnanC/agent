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

## common module

`apps/common` is the cross-cutting foundation for later modules. It contains no business semantics and must not import business apps. `OutboxEvent` and `AuditLog` map the frozen V4.0 tables with `managed = False`; do not generate migrations for them.

### Responses and errors

Use `apps.common.responses.success`, `paginated`, and `accepted` for success envelopes. Success `code` is integer `0`; every response contains `request_id`.

Raise `apps.common.errors.ApiError` with an `ErrorCode` constant. Error responses expose the numeric `code`, HTTP status, message, details, and `request_id`; symbol names remain internal only. Unknown exceptions are converted to `50001` without a stack trace or HTML error page.

### Request context, logging, and pagination

`RequestTraceMiddleware` is configured in `config/settings/base.py`. It generates or passes through `X-Request-ID` and `X-Trace-ID`, exposes them through `apps.common.context`, writes response headers, and clears the context after the request.

Use `apps.common.logging.json_log` for structured JSON logs. Sensitive keys such as `password`, `token`, `cookie`, `authorization`, and API keys are masked recursively.

Use `parse_page_params` and `paginate_queryset` for validated pagination. The page size is capped and sort fields must be explicitly whitelisted.

### Idempotency

Wrap a write view with `@idempotent("scope")`. The request must send a UUID in `Idempotency-Key`. Redis stores the request digest and response for the configured TTL. The same key and digest replay the first response; the same key with a different digest returns numeric code `40902`.

### Transactional Outbox

Inside a database transaction, construct `OutboxMessage` and call `publish_outbox`. If the transaction rolls back, the event is not persisted. A worker calls `dispatch_due_outbox` to publish due events to the transport, retry failures, and mark repeatedly failing events as `DEAD`.

### Audit APIs and export

`record_audit(AuditRecord)` writes a masked, append-only audit entry. System administrators can query:

- `GET /admin/audit-logs`
- `POST /admin/audit-logs/export`
- `GET /admin/audit-logs/export/{operation_id}`

Export requires at least one filter, rejects more than `COMMON_AUDIT_EXPORT_MAX_RECORDS`, returns a 202 envelope with `operation_id` and `trace_id`, generates CSV or JSON, uploads to the MinIO export bucket, and stores state in Redis for 24 hours. `ip_address` and `user_agent` are masked by default.

### Provider and common settings

Business modules provide actors and permission decisions without creating a reverse dependency:

| Setting | Purpose | Default |
|---|---|---:|
| `COMMON_PRINCIPAL_PERMISSION_PROVIDER` | Dotted path to a principal permission provider | Empty |
| `COMMON_AUDITABLE_ACTOR_PROVIDER` | Dotted path to an auditable actor provider | Empty |
| `COMMON_IDEMPOTENCY_TTL_SECONDS` | Redis idempotency TTL | 86400 |
| `COMMON_OUTBOX_BATCH_SIZE` | Default Outbox dispatch batch size | 100 |
| `COMMON_AUDIT_EXPORT_MAX_RECORDS` | Maximum audit export records | 100000 |
| `COMMON_AUDIT_EXPORT_TTL_SECONDS` | Audit export state and download lifetime | 86400 |

Provider classes implement the protocols in `apps.common.providers`. An unconfigured or invalid provider returns the unified internal-error envelope.

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
| `DJANGO_ALLOWED_HOSTS` | Comma-separated allowed hosts for production | Yes in prod | None | Production host validation |
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
