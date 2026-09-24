# samjon-memory - build and start the local deployment in detached mode.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\scripts\docker-up.ps1
#
# Prerequisite: copy .env.docker.example -> .env and set real secrets.
$ErrorActionPreference = 'Stop'

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker is not installed or not on PATH. Install Docker first."
    exit 1
}

if (-not (Test-Path -LiteralPath (Join-Path (Get-Location) '.env'))) {
    Write-Warning ".env not found. The container will start with empty secrets."
    Write-Warning "Copy .env.docker.example to .env and re-run docker-up before production use."
}

Write-Host "Building and starting Samjon Memory (docker compose up -d --build)..." -ForegroundColor Cyan
docker compose up -d --build
if ($LASTEXITCODE -ne 0) {
    Write-Error "docker compose up failed (exit $LASTEXITCODE)."
    exit $LASTEXITCODE
}
Write-Host "Samjon Memory started. Portal: http://localhost:8100/portal/" -ForegroundColor Green
Write-Host "Logs: powershell -ExecutionPolicy Bypass -File .\scripts\docker-logs.ps1"
exit 0