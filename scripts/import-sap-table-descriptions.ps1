param(
    [string]$CsvPath = "$env:USERPROFILE\Downloads\SAP_Table_Description.csv",
    [string]$Language = "E"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = $Root

Write-Host "=== Import SAP Table Descriptions ===" -ForegroundColor Cyan
Write-Host "Source: $CsvPath"

if (-not (Test-Path $CsvPath)) {
    Write-Host "File not found: $CsvPath" -ForegroundColor Red
    Write-Host "Usage: .\scripts\import-sap-table-descriptions.ps1 -CsvPath 'C:\path\SAP_Table_Description.csv'"
    exit 1
}

python -c @"
from backend.app.services.sap_table_store import import_from_csv, get_stats
import json

result = import_from_csv(r'$CsvPath', language='$Language', replace=True)
stats = get_stats()
print(json.dumps({'import': result, 'stats': stats}, indent=2, ensure_ascii=False))
"@

if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`nImport complete. Agents will use SAP descriptions for theme tables." -ForegroundColor Green
