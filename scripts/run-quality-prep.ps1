$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = $Root
$Base = "http://127.0.0.1:8000"

Write-Host "=== Quality Test Prep ===" -ForegroundColor Cyan

function Get-Json($Url, $TimeoutSec = 30) {
    return Invoke-RestMethod -Uri $Url -TimeoutSec $TimeoutSec
}

Write-Host "1. Backend health..."
$h = Get-Json "$Base/health" 5
Write-Host "   status: $($h.status)"

Write-Host "2. Fabric health..."
try {
    $f = Get-Json "$Base/api/v1/fabric/health" 120
    Write-Host "   fabric: $($f.status) connected=$($f.connected)"
} catch {
    Write-Host "   fabric check failed: $_" -ForegroundColor Yellow
}

Write-Host "3. Ollama health..."
try {
    $o = Get-Json "$Base/api/v1/ollama/health" 30
    Write-Host "   ollama: $($o.status)"
} catch {
    Write-Host "   ollama check failed: $_" -ForegroundColor Yellow
}

Write-Host "4. Run discovery for theme sales..."
$disc = Invoke-RestMethod -Uri "$Base/api/v1/discovery/sales/run" -Method POST -TimeoutSec 300
Write-Host "   tables: $($disc.tables_profiled) columns: $($disc.columns_found)"

Write-Host "5. Verify VBRK columns..."
$discovery = Get-Json "$Base/api/v1/discovery/sales"
$vbrk = $discovery.tables | Where-Object { $_.table -like "*VBRK*" }
if ($vbrk) {
    $colNames = $vbrk.columns | ForEach-Object { $_.COLUMN_NAME }
    $required = @("Billing_Date", "Net_Value_In_Document_Currency")
    foreach ($c in $required) {
        if ($colNames -contains $c) {
            Write-Host "   OK: $c" -ForegroundColor Green
        } else {
            Write-Host "   MISSING: $c" -ForegroundColor Red
        }
    }
}

Write-Host "Done." -ForegroundColor Green
