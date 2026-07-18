<#
.SYNOPSIS
  เริ่ม AI Fabric Insight Explorer ด้วยคำสั่งเดียว (FastAPI + Streamlit + ตรวจ Ollama)

.DESCRIPTION
  ตรวจ prerequisites, ใช้บริการที่ยัง healthy อยู่, เริ่มเฉพาะสิ่งที่ยังไม่รัน
  บันทึก PID และ launcher logs ใต้ data/local/logs/ (gitignored)
  หยุดเฉพาะ process ที่สคริปต์นี้เป็นคนเริ่ม (ผ่านไฟล์ .pid) - ไม่ kill process อื่น

.PARAMETER SkipOllama
  ข้ามการตรวจและเริ่ม Ollama

.PARAMETER NoBrowser
  ไม่เปิดเบราว์เซอร์ไปที่ Streamlit

.PARAMETER Restart
  หยุดบริการของโปรเจกต์ (จากไฟล์ .pid) แล้วเริ่มใหม่

.PARAMETER Status
  แสดงสถานะเท่านั้น ไม่เริ่มบริการ

.PARAMETER Dev
  เปิด hot-reload ที่ backend (save ไฟล์ backend จะฆ่างานที่กำลังรัน)

.EXAMPLE
  .\scripts\start.ps1

.EXAMPLE
  .\scripts\start.ps1 -Status

.EXAMPLE
  .\scripts\start.ps1 -Restart -NoBrowser
#>
[CmdletBinding()]
param(
    [switch]$SkipOllama,
    [switch]$NoBrowser,
    [switch]$Restart,
    [switch]$Status,
    [switch]$Dev
)

$ErrorActionPreference = "Stop"

try {
    if ($Host.Name -eq "ConsoleHost") {
        [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false
        $OutputEncoding = [Console]::OutputEncoding
    }
} catch {
    # optional: console encoding for Thai output
}

$BackendHost = "127.0.0.1"
$BackendPort = 8000
$FrontendPort = 8501
$BackendUrl = "http://${BackendHost}:${BackendPort}"
$FrontendUrl = "http://127.0.0.1:${FrontendPort}"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$LogDir = Join-Path $Root "data\local\logs"
$BackendPidFile = Join-Path $LogDir "launcher-backend.pid"
$FrontendPidFile = Join-Path $LogDir "launcher-frontend.pid"
$OllamaPidFile = Join-Path $LogDir "launcher-ollama.pid"

function Write-StatusLine {
    param(
        [string]$Label,
        [string]$State,
        [string]$Detail = ""
    )
    $color = switch ($State) {
        "พร้อม" { "Green" }
        "ข้าม" { "DarkGray" }
        "เตือน" { "Yellow" }
        default { "Red" }
    }
    $suffix = if ($Detail) { " - $Detail" } else { "" }
    Write-Host ("  {0,-12} [{1}]{2}" -f $Label, $State, $suffix) -ForegroundColor $color
}

function Read-EnvFileValue {
    param(
        [Parameter(Mandatory = $true)][string]$Key,
        [string]$Default = $null
    )
    $envPath = Join-Path $Root ".env"
    if (-not (Test-Path $envPath)) { return $Default }
    foreach ($line in Get-Content $envPath -Encoding UTF8) {
        if ($line -match "^\s*#") { continue }
        if ($line -match "^\s*$([regex]::Escape($Key))\s*=\s*(.*)$") {
            $val = $matches[1].Trim()
            if ($val.StartsWith('"') -and $val.EndsWith('"')) { $val = $val.Substring(1, $val.Length - 2) }
            if ($val.StartsWith("'") -and $val.EndsWith("'")) { $val = $val.Substring(1, $val.Length - 2) }
            return $val
        }
    }
    return $Default
}

function Test-TcpPortOpen {
    param(
        [string]$HostName = "127.0.0.1",
        [int]$Port
    )
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $connect = $client.BeginConnect($HostName, $Port, $null, $null)
        $ok = $connect.AsyncWaitHandle.WaitOne(1000, $false)
        if ($ok -and $client.Connected) {
            $client.Close()
            return $true
        }
        $client.Close()
    } catch {
        # port closed or unreachable
    }
    return $false
}

function Invoke-HealthJson {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [int]$TimeoutSec = 3
    )
    try {
        return Invoke-RestMethod -Uri $Url -Method Get -TimeoutSec $TimeoutSec
    } catch {
        return $null
    }
}

function Test-BackendHealthy {
    if (-not (Test-TcpPortOpen -Port $BackendPort)) { return $false }
    $body = Invoke-HealthJson -Url "$BackendUrl/health"
    return ($null -ne $body -and $body.service -eq "ai-analytics-multiagent")
}

function Test-FrontendHealthy {
    if (-not (Test-TcpPortOpen -Port $FrontendPort)) { return $false }
    try {
        $resp = Invoke-WebRequest -Uri "$FrontendUrl/_stcore/health" -UseBasicParsing -TimeoutSec 3
        return ($resp.StatusCode -eq 200)
    } catch {
        return $false
    }
}

function Test-OllamaHealthy {
    param([Parameter(Mandatory = $true)][string]$BaseUrl)
    $tagsUrl = ($BaseUrl.TrimEnd("/")) + "/api/tags"
    $body = Invoke-HealthJson -Url $tagsUrl
    return ($null -ne $body -and $null -ne $body.models)
}

function Test-OllamaIsLocal {
    param([Parameter(Mandatory = $true)][string]$BaseUrl)
    try {
        $uri = [Uri]$BaseUrl
        return ($uri.Host -in @("127.0.0.1", "localhost", "::1"))
    } catch {
        return $false
    }
}

function Get-RecordedPid {
    param([string]$PidFile)
    if (-not (Test-Path $PidFile)) { return $null }
    $raw = (Get-Content $PidFile -Raw -ErrorAction SilentlyContinue).Trim()
    if ($raw -match '^\d+$') { return [int]$raw }
    return $null
}

function Wait-UntilHealthy {
    param(
        [scriptblock]$TestFn,
        [string]$Label,
        [int]$TimeoutSec = 45
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        if (& $TestFn) { return $true }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Ensure-Prerequisites {
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        Write-Host "ERROR: ไม่พบ Python ใน PATH - ติดตั้ง Python 3.11+ ก่อน" -ForegroundColor Red
        exit 1
    }

    $pyVersion = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
    if ($pyVersion) {
        $parts = $pyVersion.Split(".")
        $major = [int]$parts[0]
        $minor = [int]$parts[1]
        if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 11)) {
            Write-Host "WARN: Python $pyVersion - แนะนำ 3.11+ อาจยังรันได้" -ForegroundColor Yellow
        }
    }

    if (-not (Test-Path (Join-Path $Root ".env"))) {
        Write-Host "WARN: ยังไม่มีไฟล์ .env - คัดลอกจาก .env.example แล้วใส่ค่า FABRIC_* / OLLAMA_*" -ForegroundColor Yellow
    }

    if (-not (Test-Path (Join-Path $Root ".venv"))) {
        Write-Host "  สร้าง virtual environment (.venv) ..." -ForegroundColor Cyan
        python -m venv (Join-Path $Root ".venv")
    }

    $python = Join-Path $Root ".venv\Scripts\python.exe"
    if (-not (Test-Path $python)) {
        Write-Host "ERROR: ไม่พบ $python" -ForegroundColor Red
        exit 1
    }

    Write-Host "  ติดตั้ง/อัปเดต dependencies ..." -ForegroundColor DarkGray
    & $python -m pip install -q -r (Join-Path $Root "backend\requirements.txt")
    & $python -m pip install -q -r (Join-Path $Root "frontend\requirements.txt")

    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
}

function Start-DetachedProcess {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$ArgumentList,
        [Parameter(Mandatory = $true)][string]$StdoutLog,
        [Parameter(Mandatory = $true)][string]$StderrLog,
        [Parameter(Mandatory = $true)][string]$PidFile
    )

    # Child inherits environment variables from this session (PS 5.1 compatible).
    $proc = Start-Process -FilePath $FilePath -ArgumentList $ArgumentList `
        -WorkingDirectory $Root -WindowStyle Hidden `
        -RedirectStandardOutput $StdoutLog -RedirectStandardError $StderrLog -PassThru

    $proc.Id | Set-Content -Path $PidFile -Encoding ASCII
    return $proc.Id
}

function Start-BackendIfNeeded {
    if (Test-BackendHealthy) {
        Write-StatusLine -Label "Backend" -State "พร้อม" -Detail "ใช้ instance ที่รันอยู่แล้ว $BackendUrl"
        return
    }

    if (Test-TcpPortOpen -Port $BackendPort) {
        Write-Host "ERROR: พอร์ต $BackendPort ถูกใช้โดยโปรแกรมอื่น - ไม่หยุด process ที่ไม่ใช่ของโปรเจกต์" -ForegroundColor Red
        Write-Host "    ตรวจสอบด้วย: netstat -ano | findstr :$BackendPort" -ForegroundColor DarkGray
        exit 1
    }

    $python = Join-Path $Root ".venv\Scripts\python.exe"
    $uvicornArgs = @("-m", "uvicorn", "backend.app.main:app", "--host", $BackendHost, "--port", "$BackendPort")
    if ($Dev) {
        $uvicornArgs += @("--reload", "--reload-dir", "backend")
        Write-Host "  WARN: Dev mode: hot-reload เปิด - save ไฟล์ backend จะฆ่างานที่กำลังรัน" -ForegroundColor Yellow
    }

    $env:PYTHONPATH = $Root
    $outLog = Join-Path $LogDir "launcher-backend.out.log"
    $errLog = Join-Path $LogDir "launcher-backend.err.log"

    Write-Host "  เริ่ม Backend ..." -ForegroundColor Cyan
    $null = Start-DetachedProcess -FilePath $python -ArgumentList $uvicornArgs `
        -StdoutLog $outLog -StderrLog $errLog -PidFile $BackendPidFile

    if (-not (Wait-UntilHealthy -TestFn { Test-BackendHealthy } -Label "Backend")) {
        Write-Host "ERROR: Backend ไม่ตอบสนองที่ ${BackendUrl}/health - ดู $errLog" -ForegroundColor Red
        exit 1
    }
    Write-StatusLine -Label "Backend" -State "พร้อม" -Detail $BackendUrl
}

function Start-FrontendIfNeeded {
    if (Test-FrontendHealthy) {
        Write-StatusLine -Label "Frontend" -State "พร้อม" -Detail "ใช้ instance ที่รันอยู่แล้ว $FrontendUrl"
        return
    }

    if (Test-TcpPortOpen -Port $FrontendPort) {
        Write-Host "ERROR: พอร์ต $FrontendPort ถูกใช้โดยโปรแกรมอื่น - ไม่หยุด process ที่ไม่ใช่ของโปรเจกต์" -ForegroundColor Red
        exit 1
    }

    $backendFromEnv = Read-EnvFileValue -Key "BACKEND_URL" -Default "http://127.0.0.1:8000"
    $chatTimeout = Read-EnvFileValue -Key "FRONTEND_HTTP_TIMEOUT" -Default $null
    if (-not $chatTimeout) {
        $chatTimeout = Read-EnvFileValue -Key "CHAT_HTTP_TIMEOUT" -Default "3600"
    }
    $onboardingTimeout = Read-EnvFileValue -Key "ONBOARDING_HTTP_TIMEOUT" -Default "3600"

    $streamlit = Join-Path $Root ".venv\Scripts\streamlit.exe"
    $streamlitArgs = @(
        "run", "frontend/app.py",
        "--server.port", "$FrontendPort",
        "--server.address", "127.0.0.1",
        "--server.headless", "true"
    )

    $env:BACKEND_URL = $backendFromEnv
    $env:CHAT_HTTP_TIMEOUT = $chatTimeout
    $env:ONBOARDING_HTTP_TIMEOUT = $onboardingTimeout

    $outLog = Join-Path $LogDir "launcher-frontend.out.log"
    $errLog = Join-Path $LogDir "launcher-frontend.err.log"

    Write-Host "  เริ่ม Frontend ..." -ForegroundColor Cyan
    $null = Start-DetachedProcess -FilePath $streamlit -ArgumentList $streamlitArgs `
        -StdoutLog $outLog -StderrLog $errLog -PidFile $FrontendPidFile

    if (-not (Wait-UntilHealthy -TestFn { Test-FrontendHealthy } -Label "Frontend")) {
        Write-Host "ERROR: Frontend ไม่ตอบสนองที่ $FrontendUrl - ดู $errLog" -ForegroundColor Red
        exit 1
    }
    Write-StatusLine -Label "Frontend" -State "พร้อม" -Detail $FrontendUrl
}

function Ensure-Ollama {
    $baseUrl = Read-EnvFileValue -Key "OLLAMA_BASE_URL" -Default "http://127.0.0.1:11434"
    $model = Read-EnvFileValue -Key "OLLAMA_MODEL" -Default "qwen2.5-coder:14b"

    if (Test-OllamaHealthy -BaseUrl $baseUrl) {
        Write-StatusLine -Label "Ollama" -State "พร้อม" -Detail "$baseUrl | model ใน .env: $model"
        return
    }

    if (-not (Test-OllamaIsLocal -BaseUrl $baseUrl)) {
        Write-StatusLine -Label "Ollama" -State "เตือน" -Detail "ไม่ตอบที่ $baseUrl - ตรวจ LAN/host หรือใช้ -SkipOllama"
        return
    }

    if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
        Write-StatusLine -Label "Ollama" -State "เตือน" -Detail "ไม่พบคำสั่ง ollama ใน PATH - ติดตั้ง Ollama หรือชี้ OLLAMA_BASE_URL ไป LAN"
        return
    }

    Write-Host "  เริ่ม ollama serve (local) ..." -ForegroundColor Cyan
    $outLog = Join-Path $LogDir "launcher-ollama.out.log"
    $errLog = Join-Path $LogDir "launcher-ollama.err.log"
    $null = Start-DetachedProcess -FilePath "ollama" -ArgumentList @("serve") `
        -StdoutLog $outLog -StderrLog $errLog -PidFile $OllamaPidFile

    if (-not (Wait-UntilHealthy -TestFn { Test-OllamaHealthy -BaseUrl $baseUrl } -Label "Ollama" -TimeoutSec 30)) {
        Write-StatusLine -Label "Ollama" -State "เตือน" -Detail "serve แล้วแต่ยังไม่ตอบ - ดู $errLog"
        return
    }
    Write-StatusLine -Label "Ollama" -State "พร้อม" -Detail $baseUrl
}

function Show-StatusSummary {
    param([switch]$Detailed)

    $baseUrl = Read-EnvFileValue -Key "OLLAMA_BASE_URL" -Default "http://127.0.0.1:11434"
    Write-Host ""
    Write-Host "=== สถานะ AI Fabric Insight Explorer ===" -ForegroundColor Cyan

    if (Test-BackendHealthy) {
        Write-StatusLine -Label "Backend" -State "พร้อม" -Detail $BackendUrl
    } elseif (Test-TcpPortOpen -Port $BackendPort) {
        Write-StatusLine -Label "Backend" -State "ไม่พร้อม" -Detail "พอร์ต $BackendPort ถูกใช้แต่ไม่ใช่ API ของโปรเจกต์"
    } else {
        Write-StatusLine -Label "Backend" -State "ไม่พร้อม" -Detail "ยังไม่รัน"
    }

    if (Test-FrontendHealthy) {
        Write-StatusLine -Label "Frontend" -State "พร้อม" -Detail $FrontendUrl
    } elseif (Test-TcpPortOpen -Port $FrontendPort) {
        Write-StatusLine -Label "Frontend" -State "ไม่พร้อม" -Detail "พอร์ต $FrontendPort ถูกใช้แต่ไม่ใช่ Streamlit ของโปรเจกต์"
    } else {
        Write-StatusLine -Label "Frontend" -State "ไม่พร้อม" -Detail "ยังไม่รัน"
    }

    if ($SkipOllama) {
        Write-StatusLine -Label "Ollama" -State "ข้าม" -Detail "-SkipOllama"
    } elseif (Test-OllamaHealthy -BaseUrl $baseUrl) {
        Write-StatusLine -Label "Ollama" -State "พร้อม" -Detail $baseUrl
    } else {
        Write-StatusLine -Label "Ollama" -State "ไม่พร้อม" -Detail $baseUrl
    }

    if ($Detailed) {
        Write-Host ""
        Write-Host "  PID ที่สคริปต์เริ่ม:" -ForegroundColor DarkGray
        foreach ($pair in @(
                @{ File = $BackendPidFile; Name = "backend" },
                @{ File = $FrontendPidFile; Name = "frontend" },
                @{ File = $OllamaPidFile; Name = "ollama" }
            )) {
            $id = Get-RecordedPid -PidFile $pair.File
            $line = if ($id) { "$($pair.Name): $id" } else { "$($pair.Name): -" }
            Write-Host "    $line" -ForegroundColor DarkGray
        }
        Write-Host ""
        Write-Host "  Logs: $LogDir" -ForegroundColor DarkGray
        Write-Host "    backend app log: backend.log" -ForegroundColor DarkGray
        Write-Host "    launcher stdout: launcher-*.out.log" -ForegroundColor DarkGray
    }

    Write-Host ""
    Write-Host "  UI:       $FrontendUrl" -ForegroundColor Green
    Write-Host "  API docs: ${BackendUrl}/docs" -ForegroundColor Green
    Write-Host "  หยุด:     .\scripts\stop.ps1" -ForegroundColor DarkGray
    Write-Host ""
}

# --- main ---

if ($Status) {
    Show-StatusSummary -Detailed
    exit 0
}

Write-Host ""
Write-Host "=== เริ่ม AI Fabric Insight Explorer ===" -ForegroundColor Cyan
Write-Host ""

if ($Restart) {
    Write-Host "  Restart: หยุดบริการที่สคริปต์เริ่มไว้ ..." -ForegroundColor Yellow
    & (Join-Path $PSScriptRoot "stop.ps1")
    Start-Sleep -Seconds 1
}

Ensure-Prerequisites

Start-BackendIfNeeded
Start-FrontendIfNeeded

if (-not $SkipOllama) {
    Ensure-Ollama
} else {
    Write-StatusLine -Label "Ollama" -State "ข้าม" -Detail "-SkipOllama"
}

Show-StatusSummary -Detailed

if (-not $NoBrowser) {
    Write-Host "  เปิดเบราว์เซอร์ ..." -ForegroundColor DarkGray
    Start-Process $FrontendUrl | Out-Null
}

Write-Host "OK: พร้อมใช้งาน - บริการรันเบื้องหลัง ปิด PowerShell นี้ได้" -ForegroundColor Green
Write-Host ""
