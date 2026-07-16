# Run FastAPI backend natively on Windows
# Usage: .\scripts\run-backend.ps1          (production-like: no hot-reload — jobs survive file saves)
#        .\scripts\run-backend.ps1 -Dev     (development: hot-reload on backend/ changes)
param([switch]$Dev)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
}

& .\.venv\Scripts\Activate.ps1
pip install -q -r backend\requirements.txt

$env:PYTHONPATH = $Root
$reloadArgs = @()
if ($Dev) {
    $reloadArgs = @("--reload", "--reload-dir", "backend")
    Write-Host "WARNING: -Dev hot-reload is ON — saving any file under backend\ kills in-flight jobs (they will show as failed)." -ForegroundColor Yellow
}
Write-Host "Starting FastAPI on http://127.0.0.1:8000 ..."
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 @reloadArgs
