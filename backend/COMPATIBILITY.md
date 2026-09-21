# Backend compatibility baseline

This file freezes the P00 implementation baseline. Dependency upgrades require a compatibility review and a regenerated lock file.

| Component | Baseline |
|---|---|
| Python | 3.14.x |
| Django | 6.1.1 |
| Django REST Framework | 3.18.1 |
| drf-spectacular | 0.30.0 |
| Celery | 5.6.3 |
| django-celery-beat | 2.9.0 target; blocked from the executable lock (requires Django `<6.1`) |
| MySQL | 8.4 LTS |
| Redis | 7 |
| MongoDB | 8.0 replica set |
| MinIO | RELEASE.2025-09-07T16-13-09Z |
| ClamAV | 1.4 |
| OpenAPI | 3.0.3, revision `v2-p00` |

The supported production path is ASGI behind Nginx and Kong. SQLite is permitted only by the isolated unit-test settings; local, integration, and production settings use MySQL.

## Compatibility exceptions

As of 2026-09-20, the published metadata for `django-celery-beat==2.9.0` requires `Django>=2.2,<6.1`, which conflicts with the frozen Django 6.1.1 baseline. P00 uses Celery workers but does not run Beat, so Beat is intentionally excluded from the executable dependency lock. It must not be enabled until an upstream release supports Django 6.1 or the architecture baseline is revised through review.
