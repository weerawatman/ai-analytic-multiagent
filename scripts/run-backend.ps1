# Run FastAPI backend natively on Windows
# Usage: .\scripts\run-backend.ps1

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
Write-Host "Starting FastAPI on http://127.0.0.1:8000 ..."
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
