# samjon-memory - local developer test runner.
# Runs media tests, OpenAPI drift, then the complete test suite.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\scripts\test-local.ps1
#
# Preconditions:
#   - .venv\Scripts\python.exe exists (repository virtual environment)
$ErrorActionPreference = 'Stop'

$repo = (Get-Location).Path
$venvPython = Join-Path $repo '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Error ".venv\Scripts\python.exe not found. Expected: $venvPython"
    Write-Error "Create the virtual environment first (e.g. python -m venv .venv)."
    exit 1
}

Write-Host ""
Write-Host "=== 1/3 Media tests ==="
& $venvPython -m pytest tests/test_media.py -v

Write-Host ""
Write-Host "=== 2/3 OpenAPI drift ==="
& $venvPython -m pytest tests/test_openapi_drift.py -v

Write-Host ""
Write-Host "=== 3/3 Complete test suite ==="
& $venvPython -m pytest tests/ -v