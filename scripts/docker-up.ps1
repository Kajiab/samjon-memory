# samjon-memory - build and start the local deployment in detached mode.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\scripts\docker-up.ps1
#
# Creates the host data directories (idempotent; never overwrites files) and
# then runs docker compose up. All paths are resolved from the repository root
# ($PSScriptRoot\..), independent of the caller's working directory.
$ErrorActionPreference = 'Stop'

# Repository root = parent of the scripts/ directory.
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker is not installed or not on PATH. Install Docker first."
    exit 1
}

# 1) Ensure the host bind-mount directories exist. No existing file/data is
#    touched; New-Item with -Force is a no-op when the directory already exists.
$dirs = @(
    'data',
    'data\media',
    'data\media\originals',
    'data\media\thumbnails',
    'data\media\archived',
    'data\backups',
    'category-covers'
)
foreach ($d in $dirs) {
    $p = Join-Path $repo $d
    if (-not (Test-Path -LiteralPath $p)) {
        New-Item -ItemType Directory -Path $p -Force | Out-Null
    }
}
Write-Host ("Host data directories ready under: " + $repo)

# 2) Warn when secrets are not configured (container still boots, Portal locked).
if (-not (Test-Path -LiteralPath (Join-Path $repo '.env'))) {
    Write-Warning ".env not found. The container will start with empty secrets."
    Write-Warning "Copy .env.docker.example to .env and re-run docker-up before production use."
}

# 3) Build and start from the repository root (where compose.yaml lives).
Push-Location $repo
Write-Host "Building and starting Samjon Memory (docker compose up -d --build)..." -ForegroundColor Cyan
docker compose up -d --build
$code = $LASTEXITCODE
Pop-Location

if ($code -ne 0) {
    Write-Error "docker compose up failed (exit $code)."
    exit $code
}
Write-Host "Samjon Memory started. Portal: http://localhost:8100/portal/" -ForegroundColor Green
Write-Host "Logs: powershell -ExecutionPolicy Bypass -File .\scripts\docker-logs.ps1"
exit 0