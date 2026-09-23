# samjon-memory - local developer runner.
# Starts the Samjon Memory Core service against the local repository .env.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\scripts\run-local.ps1
#
# Preconditions:
#   - .venv\Scripts\python.exe exists (repository virtual environment)
#   - .env exists next to this repo
$ErrorActionPreference = 'Stop'

$repo = (Get-Location).Path
$venvPython = Join-Path $repo '.venv\Scripts\python.exe'
$envFile = Join-Path $repo '.env'

# 1) Verify the repository virtual environment interpreter exists.
if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Error ".venv\Scripts\python.exe not found. Expected: $venvPython"
    Write-Error "Create the virtual environment first (e.g. python -m venv .venv)."
    exit 1
}

# 2) Verify the local .env exists. Never auto-create or overwrite it.
if (-not (Test-Path -LiteralPath $envFile)) {
    Write-Error ".env not found. Expected: $envFile"
    Write-Error "Copy .env.example to .env and set real values before running locally."
    exit 1
}

# Helper: read a simple KEY=VALUE setting from the local .env (values only, never printed).
function Get-EnvValue {
    param([string]$Key)
    foreach ($line in Get-Content -LiteralPath $envFile) {
        if ($line -match "^\uFEFF?\s*$([regex]::Escape($Key))\s*=(.*)$") {
            $val = ($Matches[1].Trim()).Trim('"').Trim("'")
            # Strip an inline trailing comment (space + # ...)
            $idx = $val.IndexOf('#')
            if ($idx -gt 0) { $val = $val.Substring(0, $idx).TrimEnd() }
            return $val
        }
    }
    return $null
}

$coreDb = Get-EnvValue 'SAMJON_CORE_DATABASE_PATH'
$resolverDb = Get-EnvValue 'SAMJON_RESOLVER_DATABASE_PATH'
$mediaRoot = Get-EnvValue 'SAMJON_MEDIA_ROOT'
$portalUser = Get-EnvValue 'SAMJON_PORTAL_USERNAME'
$portalPass = Get-EnvValue 'SAMJON_PORTAL_PASSWORD'

# 7) Stop with a clear error if required configuration is missing.
$missing = @()
if (-not $coreDb) { $missing += 'SAMJON_CORE_DATABASE_PATH' }
if (-not $resolverDb) { $missing += 'SAMJON_RESOLVER_DATABASE_PATH' }
if (-not $mediaRoot) { $missing += 'SAMJON_MEDIA_ROOT' }
if (-not $portalUser) { $missing += 'SAMJON_PORTAL_USERNAME' }
if (-not $portalPass) { $missing += 'SAMJON_PORTAL_PASSWORD' }

if ($missing.Count -gt 0) {
    Write-Error ("Missing required configuration in .env: " + ($missing -join ', '))
    Write-Error "Add the missing settings to .env (see .env.example) and re-run."
    exit 1
}

# 3) Create required runtime directories (idempotent).
foreach ($d in @('data', 'data\media\originals', 'data\media\thumbnails', 'data\media\archived')) {
    $p = Join-Path $repo $d
    if (-not (Test-Path -LiteralPath $p)) {
        New-Item -ItemType Directory -Path $p -Force | Out-Null
    }
}

# Print the selected runtime configuration (paths only, never credentials).
Write-Host ""
Write-Host "Samjon Memory - local run"
Write-Host "  Core DB     : $coreDb"
Write-Host "  Resolver DB : $resolverDb"
Write-Host "  Media root  : $mediaRoot"
Write-Host ""

# 4/5) Start Uvicorn with the local .env, loopback host, and port 8100.
& $venvPython -m uvicorn samjon_memory.core.main:app --env-file $envFile --host 127.0.0.1 --port 8100