$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = $Root

Write-Host "=== Seed Sales Glossary + Targets ===" -ForegroundColor Cyan
python "$PSScriptRoot\seed_sales_glossary.py"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Glossary + targets seeded for sales theme." -ForegroundColor Green
