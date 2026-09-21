$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = if (Test-Path "$root\.venv\Scripts\python.exe") { "$root\.venv\Scripts\python.exe" } else { 'python' }
$npm = (Get-Command npm.cmd -ErrorAction Stop).Source

Push-Location "$root\backend\education_experiment_platform"
try {
    $env:DJANGO_SETTINGS_MODULE = 'education_experiment_platform.settings.test'
    & $python manage.py check
    if ($LASTEXITCODE -ne 0) { throw 'Django check failed.' }
    & $python -m pytest
    if ($LASTEXITCODE -ne 0) { throw 'Backend tests failed.' }
} finally { Pop-Location }

Push-Location "$root\backend"
try {
    & $python -m ruff check education_experiment_platform
    if ($LASTEXITCODE -ne 0) { throw 'Backend lint failed.' }
    & $python -m mypy education_experiment_platform
    if ($LASTEXITCODE -ne 0) { throw 'Backend typecheck failed.' }
} finally { Pop-Location }

Push-Location "$root\frontend"
try {
    & $npm run typecheck
    if ($LASTEXITCODE -ne 0) { throw 'Frontend typecheck failed.' }
    & $npm run lint
    if ($LASTEXITCODE -ne 0) { throw 'Frontend lint failed.' }
    & $npm run test
    if ($LASTEXITCODE -ne 0) { throw 'Frontend component tests failed.' }
    & $npm run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
} finally { Pop-Location }

docker compose -f "$root\docker-compose.dev.yml" config --quiet
if ($LASTEXITCODE -ne 0) { throw 'Compose validation failed.' }
Write-Output 'P00 static verification passed.'
