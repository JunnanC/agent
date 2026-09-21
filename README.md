# Education Agent Platform

Greenfield implementation of the teaching cloud experiment platform. The current deliverable is P00: engineering, entry-point, contract, and infrastructure foundations only.

## Local prerequisites

- Docker Desktop 28+ with Compose v2
- Node.js 24+ for host-side frontend commands
- Python 3.14 for host-side backend commands

## Start

```powershell
Copy-Item .env.example .env
docker compose -f docker-compose.dev.yml up --build
```

The edge entry point listens on port `8080`. Use the hostnames below so portal cookies and trusted host mapping remain isolated:

- `http://user.localhost:8080`
- `http://teacher.localhost:8080`
- `http://admin.localhost:8080`
- `http://api.localhost:8080` (machine API only; no web application)

Run `./scripts/verify-p00.ps1` for the P00 checks. Architecture and stage requirements live under `documents/`.

