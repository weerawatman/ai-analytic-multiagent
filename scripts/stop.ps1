<#
.SYNOPSIS
  หยุดบริการที่ scripts/start.ps1 เริ่มไว้ (จากไฟล์ .pid เท่านั้น)

.DESCRIPTION
  ไม่ kill process อื่นที่ใช้พอร์ต 8000/8501/11434 โดยไม่มีไฟล์ PID ของโปรเจกต์

.EXAMPLE
  .\scripts\stop.ps1
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $Root "data\local\logs"

$PidFiles = @(
    @{ File = (Join-Path $LogDir "launcher-frontend.pid"); Label = "Frontend" },
    @{ File = (Join-Path $LogDir "launcher-backend.pid"); Label = "Backend" },
    @{ File = (Join-Path $LogDir "launcher-ollama.pid"); Label = "Ollama" }
)

Write-Host ""
Write-Host "=== หยุดบริการโปรเจกต์ ===" -ForegroundColor Cyan

$stopped = 0
foreach ($entry in $PidFiles) {
    if (-not (Test-Path $entry.File)) { continue }
    $raw = (Get-Content $entry.File -Raw -ErrorAction SilentlyContinue).Trim()
    if ($raw -notmatch '^\d+$') {
        Remove-Item $entry.File -Force -ErrorAction SilentlyContinue
        continue
    }
    $procId = [int]$raw
    $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
    if ($proc) {
        Write-Host "  หยุด $($entry.Label) (PID $procId) ..." -ForegroundColor Yellow
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        $stopped++
    } else {
        Write-Host "  $($entry.Label): PID $procId ไม่พบแล้ว (ลบไฟล์ .pid)" -ForegroundColor DarkGray
    }
    Remove-Item $entry.File -Force -ErrorAction SilentlyContinue
}

if ($stopped -eq 0) {
    Write-Host "  ไม่มี process ที่บันทึกไว้ให้หยุด" -ForegroundColor DarkGray
} else {
    Write-Host "  หยุดแล้ว $stopped process" -ForegroundColor Green
}
Write-Host ""
