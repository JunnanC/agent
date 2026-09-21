[CmdletBinding(SupportsShouldProcess, ConfirmImpact = 'High')]
param()

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$compose = "$root\docker-compose.dev.yml"

if ($PSCmdlet.ShouldProcess('edu-platform-p00 Docker Compose volumes', 'Remove and recreate empty P00 data services')) {
    docker compose -f $compose down --volumes --remove-orphans
    if ($LASTEXITCODE -ne 0) { throw 'Failed to remove the local P00 environment.' }
    docker compose -f $compose up --build --detach
    if ($LASTEXITCODE -ne 0) { throw 'Failed to recreate the local P00 environment.' }
}

