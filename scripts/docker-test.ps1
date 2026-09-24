# samjon-memory - build, start, and smoke-test the local deployment.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\scripts\docker-test.ps1
#
# Steps: docker compose up -d --build, then poll the container /health endpoint
# and the Portal homepage (requires Portal credentials from .env when set).
$ErrorActionPreference = 'Stop'

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker is not installed or not on PATH. Install Docker first."
    exit 1
}

if (-not (Test-Path -LiteralPath (Join-Path (Get-Location) '.env'))) {
    Write-Warning ".env not found. Set SAMJON_PORTAL_USERNAME/PASSWORD in .env for the Portal check."
}

Write-Host "Building and starting Samjon Memory (docker compose up -d --build)..." -ForegroundColor Cyan
docker compose up -d --build
if ($LASTEXITCODE -ne 0) {
    Write-Error "docker compose up failed (exit $LASTEXITCODE)."
    exit $LASTEXITCODE
}

$port = if ($env:SAMJON_CORE_PORT) { $env:SAMJON_CORE_PORT } else { '8100' }
$base = "http://127.0.0.1:$port"

# Poll /health until healthy or timeout (~90s).
Write-Host "Waiting for $base/health ..."
$deadline = (Get-Date).AddSeconds(90)
$ok = $false
while ((Get-Date) -lt $deadline) {
    try {
        $r = Invoke-RestMethod -Uri "$base/health" -TimeoutSec 3
        if ($r.status -eq 'ok') { $ok = $true; break }
    } catch {
        Start-Sleep -Seconds 3
    }
}
if (-not $ok) {
    Write-Error "Samjon Memory did not become healthy within 90s. Inspect logs with docker-logs.ps1."
    docker compose logs --tail=80 samjon-memory
    exit 1
}
Write-Host "Health OK: $($r.status) (core_schema=$($r.core_schema_version))" -ForegroundColor Green

# Optional HTML probe: Portal returns the Jinja-rendered UI when credentials are set.
$user = if ($env:SAMJON_PORTAL_USERNAME) { $env:SAMJON_PORTAL_USERNAME } else { '' }
$pass = if ($env:SAMJON_PORTAL_PASSWORD) { $env:SAMJON_PORTAL_PASSWORD } else { '' }
if ($user) {
    $pair = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("${user}:${pass}"))
    try {
        $html = Invoke-WebRequest -Uri "$base/portal/" -Headers @{ Authorization = "Basic $pair" } -TimeoutSec 10
        if ($html.StatusCode -eq 200 -and $html.Content -match 'class="navbar"') {
            Write-Host "Portal renders OK (Jinja template, single navbar)." -ForegroundColor Green
        } else {
            Write-Warning "Portal returned a non-200 or unexpected body."
        }
    } catch {
        Write-Warning ("Portal probe failed: " + $_.Exception.Message)
    }
} else {
    Write-Warning "SAMJON_PORTAL_USERNAME not set; skipping Portal HTML probe."
}

Write-Host "Smoke test complete." -ForegroundColor Green
exit 0