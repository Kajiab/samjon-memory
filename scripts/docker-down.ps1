# samjon-memory - stop and remove the local deployment containers + network.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\scripts\docker-down.ps1
#
# Note: persistent data lives in the `samjon_memory_data` volume and is NOT
# removed by `down`. Use `docker compose down -v` only if you intend to delete
# all data (irreversible).
$ErrorActionPreference = 'Stop'

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker is not installed or not on PATH. Install Docker first."
    exit 1
}

Write-Host "Stopping Samjon Memory (docker compose down)..."
docker compose down
if ($LASTEXITCODE -ne 0) {
    Write-Error "docker compose down failed (exit $LASTEXITCODE)."
    exit $LASTEXITCODE
}
Write-Host "Samjon Memory stopped. Persistent data volume retained." -ForegroundColor Green
exit 0