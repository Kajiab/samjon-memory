# samjon-memory - stop and remove the local deployment containers + network.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\scripts\docker-down.ps1
#
# This command never removes volumes or data. Persistent data lives on the host
# under ./data via a bind mount and is always retained on `down`. Deleting all
# data is a manual, explicit action and is never triggered by this script.
$ErrorActionPreference = 'Stop'

$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker is not installed or not on PATH. Install Docker first."
    exit 1
}

Write-Host "Stopping Samjon Memory (docker compose down)..."
Push-Location $repo
docker compose down
$code = $LASTEXITCODE
Pop-Location

if ($code -ne 0) {
    Write-Error "docker compose down failed (exit $code)."
    exit $code
}
Write-Host "Samjon Memory stopped. Host data under ./data is retained." -ForegroundColor Green
exit 0