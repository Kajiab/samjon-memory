# samjon-memory - stream the running container logs.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\scripts\docker-logs.ps1 [-Follow]
param(
    [switch]$Follow
)

$ErrorActionPreference = 'Stop'

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker is not installed or not on PATH. Install Docker first."
    exit 1
}

Write-Host "Streaming Samjon Memory logs..." -ForegroundColor Cyan
if ($Follow) {
    docker compose logs -f --tail=200 samjon-memory
} else {
    docker compose logs --tail=200 samjon-memory
}
exit $LASTEXITCODE