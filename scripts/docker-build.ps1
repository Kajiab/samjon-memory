# samjon-memory - build the local deployment image.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\scripts\docker-build.ps1
#
# Requires: Docker with the Compose plugin. Does not start any container.
$ErrorActionPreference = 'Stop'

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker is not installed or not on PATH. Install Docker first."
    exit 1
}

Write-Host "Building Samjon Memory image (samjon-memory:local)..." -ForegroundColor Cyan
docker compose build
if ($LASTEXITCODE -ne 0) {
    Write-Error "Image build failed (docker compose build exited with $LASTEXITCODE)."
    exit $LASTEXITCODE
}
Write-Host "Image build complete: samjon-memory:local" -ForegroundColor Green
exit 0