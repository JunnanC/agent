# Membership module

`apps.membership` owns the single-team membership lifecycle for `team_settings` and `team_memberships`. Both models map the frozen V4.0 schema with `managed = False`; do not generate migrations in this phase.

## State machine

| Transition | Trigger |
| --- | --- |
| `None/REJECTED/EXITED/REMOVED -> PENDING` | user application |
| `None -> ACTIVE` | direct add by `ORG_ADMIN` |
| `PENDING -> ACTIVE` | application approval |
| `PENDING -> REJECTED` | application rejection |
| `ACTIVE -> EXITED` | user exit |
| `ACTIVE -> REMOVED` | `ORG_ADMIN` removal |

The table is centralized in `constants.py` and services call `transition_membership`; illegal transitions return `STATE_CONFLICT`.

## API

All routes are under `/api/v1`:

- `GET /me/team-membership`
- `POST /me/team-membership/applications`
- `POST /me/team-membership/exit`
- `GET /teaching/team-members`
- `GET /teaching/team-membership-applications`
- `POST /teaching/team-membership-applications/{id}/review`
- `POST /teaching/team-members`
- `POST /teaching/team-members/{id}/remove`

Write operations use `apps.common.idempotency.idempotent`, write audit records, and publish Outbox events in the same database transaction as the business fact.

## Domain services

- `is_active_member(user_id)`
- `get_active_membership_id(user_id)`
- `assert_member_active(user_id)`
- `has_blocking_items(user_id, operation)`
- `get_team_settings()`

`TeamMembership.last_block_check_json` is only a point-in-time block-check snapshot. Runtime authorization always rechecks the current `ACTIVE` status.

## Identity integration

`IDENTITY_MEMBERSHIP_PROVIDER` points to `apps.membership.identity_provider.MembershipIdentityProvider`. The provider returns `membership_id` and `status` (or `None`) for identity responses. Session revocation is requested only through an Outbox event and never touches M4-B storage.

## Extensibility

| Setting | Purpose | Default |
| --- | --- | --- |
| `MEMBERSHIP_BLOCKING_PROVIDER` | Read-only assignment/instance block-check provider | empty |
| `MEMBERSHIP_TASK_STATS_PROVIDER` | Read-only teaching-list task stats provider | empty |
| `MEMBERSHIP_AUTHORIZED_SCOPE_PROVIDER` | `ORG_SUB_ADMIN` authorized member scope | empty |

Empty providers are conservative: no blocking items are returned, task counts are zero, and the sub-admin member scope is empty.

## Conflict decisions

- **C8**: `ORG_SUB_ADMIN` is read-only and sees only its authorized member subset.
- **C9**: persisted join sources use `APPLY/DIRECT/IMPORT`.
- **C11**: identifiers use the database BIGINT primary keys.
- **C12**: membership change blocks use `MEMBERSHIP_CHANGE_BLOCKED`.
- **C13**: last-admin protection uses `LAST_TEAM_ADMIN_PROTECTED`.

## Tests

```powershell
Set-Location agent\backend
.venv\Scripts\python.exe -m pytest apps\membership -q
.venv\Scripts\python.exe -m pytest apps\identity -q
.venv\Scripts\python.exe -m ruff format --check apps\membership
.venv\Scripts\python.exe -m ruff check apps\membership
```
