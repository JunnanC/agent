param(
    [string]$Address = '127.0.0.1',
    [int]$Port = 8080
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$npm = (Get-Command npm.cmd -ErrorAction Stop).Source

function Invoke-EdgeRequest {
    param([string]$HostName, [string]$Path, [hashtable]$Headers = @{})
    $requestHeaders = @{ Host = $HostName }
    foreach ($key in $Headers.Keys) { $requestHeaders[$key] = $Headers[$key] }
    Invoke-WebRequest -SkipHttpErrorCheck -UseBasicParsing -Uri "http://${Address}:${Port}${Path}" -Headers $requestHeaders
}

$portalHosts = @{
    'user.localhost' = 'USER'
    'teacher.localhost' = 'TEACHING'
    'admin.localhost' = 'PLATFORM'
}

foreach ($entry in $portalHosts.GetEnumerator()) {
    $homeResponse = Invoke-EdgeRequest -HostName $entry.Key -Path '/health'
    if ($homeResponse.StatusCode -ne 200) { throw "$($entry.Key) static application failed." }

    $health = Invoke-EdgeRequest -HostName $entry.Key -Path '/api/v2/health' -Headers @{
        'X-Portal' = 'FORGED'
        'X-Auth-Context' = 'FORGED'
    }
    if ($health.StatusCode -ne 200) { throw "$($entry.Key) health chain failed." }
    $payload = $health.Content | ConvertFrom-Json
    if ($payload.data.portal -ne $entry.Value) { throw "$($entry.Key) did not overwrite forged context." }
}

$machineHome = Invoke-EdgeRequest -HostName 'api.localhost' -Path '/'
if ($machineHome.StatusCode -ne 404) { throw 'Machine host unexpectedly served a web application.' }
$machineHealth = Invoke-EdgeRequest -HostName 'api.localhost' -Path '/api/v2/health'
if ($machineHealth.StatusCode -ne 404) { throw 'Machine host exposed a portal API.' }

$sse = Invoke-EdgeRequest -HostName 'user.localhost' -Path '/api/v2/events/stream'
if ($sse.StatusCode -ne 200 -or $sse.Headers['X-Accel-Buffering'] -ne 'no') {
    throw 'SSE proxy buffering contract failed.'
}

Push-Location "$root\frontend"
try {
    $env:PLAYWRIGHT_CHANNEL = $env:PLAYWRIGHT_CHANNEL ?? 'chrome'
    $env:USER_WEB_URL = "http://user.localhost:$Port"
    $env:TEACHER_WEB_URL = "http://teacher.localhost:$Port"
    $env:ADMIN_WEB_URL = "http://admin.localhost:$Port"
    & $npm run test:e2e:user
    if ($LASTEXITCODE -ne 0) { throw 'User portal E2E failed.' }
    & $npm run test:e2e:teacher
    if ($LASTEXITCODE -ne 0) { throw 'Teacher portal E2E failed.' }
    & $npm run test:e2e:admin
    if ($LASTEXITCODE -ne 0) { throw 'Admin portal E2E failed.' }
} finally { Pop-Location }

Write-Output 'P00 edge verification passed.'
