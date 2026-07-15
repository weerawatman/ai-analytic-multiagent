# Run Streamlit frontend natively on Windows
# Usage: .\scripts\run-frontend.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
}

& .\.venv\Scripts\Activate.ps1
pip install -q -r frontend\requirements.txt

$env:BACKEND_URL = if ($env:BACKEND_URL) { $env:BACKEND_URL } else { "http://127.0.0.1:8000" }
Write-Host "Starting Streamlit on http://127.0.0.1:8501 (backend: $env:BACKEND_URL) ..."
streamlit run frontend/app.py --server.port 8501 --server.address 127.0.0.1
