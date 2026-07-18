<#
.SYNOPSIS
  Loop Engineering readiness runner (L0 env, L1 pytest, optional L2 live/golden)

.DESCRIPTION
  Writes raw evidence under data/local/qa/loop-engineering/runs/<run_id>/
  Does not commit, push, or kill unrelated processes.
  Fabric remains read-only (this script never issues SQL writes).

.PARAMETER Level
  0 = env smoke only
  1 = L0 + offline pytest + conformance (default)
  2 = L1 + live quality chat smoke (long-running; needs services)
  all = same as 2 for now (includes L0+L1+L2)

.PARAMETER IncludeGolden
  Also run golden eval harness (may be harness-baseline only until live answer_fn is wired)

.PARAMETER SkipLive
  When Level is 2/all, skip the quality chat live step

.PARAMETER SkipOllamaGenerate
  L0: only check /api/tags, do not call generate

.PARAMETER OutDir
  Override evidence directory (default: data/local/qa/loop-engineering/runs/<run_id>)

.EXAMPLE
  .\scripts\run-readiness-check.ps1

.EXAMPLE
  .\scripts\run-readiness-check.ps1 -Level 0

.EXAMPLE
  .\scripts\run-readiness-check.ps1 -Level all -IncludeGolden -SkipLive
#>
[CmdletBinding()]
param(
    [ValidateSet("0", "1", "2", "all")]
    [string]$Level = "1",
    [switch]$IncludeGolden,
    [switch]$SkipLive,
    [switch]$SkipOllamaGenerate,
    [string]$OutDir = ""
)

$ErrorActionPreference = "Stop"

try {
    if ($Host.Name -eq "ConsoleHost") {
        [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false
        $OutputEncoding = [Console]::OutputEncoding
    }
} catch { }

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$runId = (Get-Date -Format "yyyyMMdd-HHmmss") + "-" + ([guid]::NewGuid().ToString("N").Substring(0, 6))
if (-not $OutDir) {
    $OutDir = Join-Path $Root "data\local\qa\loop-engineering\runs\$runId"
} else {
    if (-not [System.IO.Path]::IsPathRooted($OutDir)) {
        $OutDir = Join-Path $Root $OutDir
    }
}
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $OutDir "logs") | Out-Null

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
}

$summary = [ordered]@{
    run_id        = $runId
    started_at    = (Get-Date).ToUniversalTime().ToString("o")
    level         = $Level
    repo_root     = $Root
    out_dir       = $OutDir
    scenarios     = @()
    layers        = [ordered]@{}
    honesty       = [ordered]@{
        code_complete         = $false
        test_passed_offline   = $false
        production_verified   = $false
        human_gate_pending    = $true
        commit_push_performed = $false
    }
    exit_code     = 0
}

function Add-ScenarioResult {
    param(
        [string]$Id,
        [string]$Status,
        [string]$Notes = ""
    )
    $script:summary.scenarios += [ordered]@{
        id     = $Id
        status = $Status
        notes  = $Notes
    }
}

function Write-Info([string]$Message) {
    Write-Host "[readiness] $Message"
}

function Get-DotEnvValue {
    param([string]$Key)
    $envFile = Join-Path $Root ".env"
    if (-not (Test-Path $envFile)) { return $null }
    foreach ($line in Get-Content $envFile -Encoding UTF8) {
        $trim = $line.Trim()
        if (-not $trim -or $trim.StartsWith("#")) { continue }
        if ($trim -match "^\s*$([regex]::Escape($Key))\s*=\s*(.*)$") {
            return $Matches[1].Trim().Trim('"').Trim("'")
        }
    }
    return $null
}

function Test-HttpOk {
    param([string]$Url, [int]$TimeoutSec = 5)
    try {
        $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSec
        return @{ ok = ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 300); code = [int]$resp.StatusCode; body = $resp.Content }
    } catch {
        return @{ ok = $false; code = 0; body = $_.Exception.Message }
    }
}

# ─── L0 ─────────────────────────────────────────────────────────────
function Invoke-Level0 {
    Write-Info "L0 env smoke (SCN-ENV-001 / SCN-ENV-002)"
    $l0 = [ordered]@{
        start_status = $null
        backend      = $null
        frontend     = $null
        ollama_tags  = $null
        ollama_generate = $null
    }

    $statusLog = Join-Path $OutDir "logs\start-status.txt"
    try {
        & (Join-Path $Root "scripts\start.ps1") -Status *>&1 | Tee-Object -FilePath $statusLog | Out-Null
        $l0.start_status = "ok"
        Add-ScenarioResult -Id "SCN-ENV-001" -Status "pass" -Notes "start.ps1 -Status completed"
    } catch {
        $l0.start_status = "error"
        Add-ScenarioResult -Id "SCN-ENV-001" -Status "fail" -Notes $_.Exception.Message
        $script:summary.exit_code = 1
    }

    $backend = Test-HttpOk "http://127.0.0.1:8000/health"
    $l0.backend = @{ ok = $backend.ok; code = $backend.code }
    $frontend = Test-HttpOk "http://127.0.0.1:8501/_stcore/health"
    $l0.frontend = @{ ok = $frontend.ok; code = $frontend.code }

    $ollamaBase = Get-DotEnvValue "OLLAMA_BASE_URL"
    if (-not $ollamaBase) { $ollamaBase = "http://127.0.0.1:11434" }
    $ollamaModel = Get-DotEnvValue "OLLAMA_MODEL"
    if (-not $ollamaModel) { $ollamaModel = "qwen2.5-coder:14b" }

    $tags = Test-HttpOk "$ollamaBase/api/tags" -TimeoutSec 10
    $l0.ollama_tags = @{ ok = $tags.ok; base_url_host = ([uri]$ollamaBase).Host }

    if (-not $SkipOllamaGenerate -and $tags.ok) {
        try {
            $payload = @{
                model  = $ollamaModel
                prompt = "ping"
                stream = $false
                options = @{ num_predict = 8 }
            } | ConvertTo-Json -Depth 5
            $gen = Invoke-RestMethod -Uri "$ollamaBase/api/generate" -Method Post -Body $payload -ContentType "application/json" -TimeoutSec 120
            $l0.ollama_generate = @{ ok = $true; model = $ollamaModel }
            Add-ScenarioResult -Id "SCN-ENV-002" -Status "pass" -Notes "generate smoke ok for configured model"
        } catch {
            $l0.ollama_generate = @{ ok = $false; model = $ollamaModel; error_type = $_.Exception.GetType().Name }
            Add-ScenarioResult -Id "SCN-ENV-002" -Status "fail" -Notes ("generate failed: " + $_.Exception.GetType().Name)
            $script:summary.exit_code = 1
        }
    } else {
        $l0.ollama_generate = @{ ok = $null; skipped = $true }
        if ($tags.ok) {
            Add-ScenarioResult -Id "SCN-ENV-002" -Status "skip" -Notes "generate skipped"
        } else {
            Add-ScenarioResult -Id "SCN-ENV-002" -Status "fail" -Notes "ollama tags unreachable"
            $script:summary.exit_code = 1
        }
    }

    $script:summary.layers.L0 = $l0
}

# ─── L1 ─────────────────────────────────────────────────────────────
function Invoke-Level1 {
    Write-Info "L1 offline pytest + conformance (SCN-OFF-001 / SCN-INV-001)"
    $env:PYTHONPATH = $Root
    $pytestLog = Join-Path $OutDir "logs\pytest.txt"
    $confLog = Join-Path $OutDir "logs\conformance.txt"

    $l1 = [ordered]@{
        pytest_exit       = $null
        conformance_exit  = $null
    }

    Write-Info "Running full pytest…"
    & $Python -m pytest "backend/tests" -q --tb=line 2>&1 | Tee-Object -FilePath $pytestLog | Out-Host
    $pytestCode = $LASTEXITCODE
    $l1.pytest_exit = $pytestCode
    if ($pytestCode -eq 0) {
        Add-ScenarioResult -Id "SCN-OFF-001" -Status "pass" -Notes "pytest exit 0"
    } else {
        Add-ScenarioResult -Id "SCN-OFF-001" -Status "fail" -Notes "pytest exit $pytestCode"
        $script:summary.exit_code = 1
    }

    Write-Info "Running roadmap conformance…"
    & $Python -m pytest "backend/tests/test_roadmap_conformance.py" -q --tb=line 2>&1 | Tee-Object -FilePath $confLog | Out-Host
    $confCode = $LASTEXITCODE
    $l1.conformance_exit = $confCode
    if ($confCode -eq 0) {
        Add-ScenarioResult -Id "SCN-INV-001" -Status "pass" -Notes "conformance exit 0"
    } else {
        Add-ScenarioResult -Id "SCN-INV-001" -Status "fail" -Notes "conformance exit $confCode"
        $script:summary.exit_code = 1
    }

    if ($pytestCode -eq 0 -and $confCode -eq 0) {
        $script:summary.honesty.test_passed_offline = $true
    }

    $script:summary.layers.L1 = $l1
}

# ─── L2 ─────────────────────────────────────────────────────────────
function Invoke-Level2 {
    Write-Info "L2 live / golden (opt-in)"
    $l2 = [ordered]@{
        quality_chat = $null
        golden       = $null
    }

    if (-not $SkipLive) {
        $health = Test-HttpOk "http://127.0.0.1:8000/health"
        if (-not $health.ok) {
            $l2.quality_chat = @{ status = "skip"; reason = "backend unhealthy" }
            Add-ScenarioResult -Id "SCN-CHAT-001" -Status "skip" -Notes "backend not healthy"
        } else {
            Write-Info "Running quality chat job smoke (may take a long time)…"
            $chatLog = Join-Path $OutDir "logs\quality-chat.txt"
            try {
                & $Python (Join-Path $Root "scripts\run_quality_chat_test.py") 2>&1 | Tee-Object -FilePath $chatLog | Out-Host
                $code = $LASTEXITCODE
                $l2.quality_chat = @{ status = $(if ($code -eq 0) { "pass" } else { "fail" }); exit = $code }
                Add-ScenarioResult -Id "SCN-CHAT-001" -Status $(if ($code -eq 0) { "pass" } else { "fail" }) -Notes "run_quality_chat_test exit $code"
                if ($code -ne 0) { $script:summary.exit_code = 1 }
            } catch {
                $l2.quality_chat = @{ status = "fail"; error_type = $_.Exception.GetType().Name }
                Add-ScenarioResult -Id "SCN-CHAT-001" -Status "fail" -Notes $_.Exception.GetType().Name
                $script:summary.exit_code = 1
            }
        }
    } else {
        $l2.quality_chat = @{ status = "skip"; reason = "SkipLive" }
        Add-ScenarioResult -Id "SCN-CHAT-001" -Status "skip" -Notes "SkipLive"
    }

    if ($IncludeGolden) {
        Write-Info "Running golden eval harness…"
        $gLog = Join-Path $OutDir "logs\golden.txt"
        try {
            & (Join-Path $Root "scripts\run-golden-eval.ps1") 2>&1 | Tee-Object -FilePath $gLog | Out-Host
            $code = $LASTEXITCODE
            $l2.golden = @{ status = $(if ($code -eq 0) { "pass" } else { "fail" }); exit = $code; note = "may be harness-only until live answer_fn" }
            Add-ScenarioResult -Id "SCN-GQ-001" -Status $(if ($code -eq 0) { "pass" } else { "fail" }) -Notes "golden exit $code"
            if ($code -ne 0) { $script:summary.exit_code = 1 }
        } catch {
            $l2.golden = @{ status = "fail"; error_type = $_.Exception.GetType().Name }
            Add-ScenarioResult -Id "SCN-GQ-001" -Status "fail" -Notes $_.Exception.GetType().Name
            $script:summary.exit_code = 1
        }
    } else {
        Add-ScenarioResult -Id "SCN-GQ-001" -Status "skip" -Notes "IncludeGolden not set"
        Add-ScenarioResult -Id "SCN-GQ-002" -Status "skip" -Notes "deferred live answer_fn"
    }

    Add-ScenarioResult -Id "SCN-LLM-001" -Status "skip" -Notes "agent-observed; use skill triage when UI shows all-agent fail"
    Add-ScenarioResult -Id "SCN-SRC-001" -Status "skip" -Notes "run manually or via agent when Fabric paused"
    Add-ScenarioResult -Id "SCN-GATE-001" -Status "skip" -Notes "human-gate"

    $script:summary.layers.L2 = $l2
}

# ─── Main ───────────────────────────────────────────────────────────
Write-Info "run_id=$runId"
Write-Info "out_dir=$OutDir"
Write-Info "level=$Level"

$runL0 = $true
$runL1 = $Level -in @("1", "2", "all")
$runL2 = $Level -in @("2", "all")

Invoke-Level0
if ($runL1) { Invoke-Level1 }
if ($runL2) { Invoke-Level2 }
elseif ($Level -eq "1") {
    Add-ScenarioResult -Id "SCN-CHAT-001" -Status "skip" -Notes "Level 1 only"
    Add-ScenarioResult -Id "SCN-GQ-001" -Status "skip" -Notes "Level 1 only"
    Add-ScenarioResult -Id "SCN-LLM-001" -Status "skip" -Notes "Level 1 only"
    Add-ScenarioResult -Id "SCN-SRC-001" -Status "skip" -Notes "Level 1 only"
    Add-ScenarioResult -Id "SCN-GATE-001" -Status "skip" -Notes "human-gate"
}

$summary.finished_at = (Get-Date).ToUniversalTime().ToString("o")
$summaryPath = Join-Path $OutDir "summary.json"
($summary | ConvertTo-Json -Depth 8) | Set-Content -Path $summaryPath -Encoding UTF8

Write-Info "Wrote $summaryPath"
Write-Info "honesty.test_passed_offline=$($summary.honesty.test_passed_offline)"
Write-Info "production_verified remains false (owner evidence required)"
Write-Info "commit/push not performed"

if ($summary.exit_code -ne 0) {
    Write-Host "[readiness] FAILED (exit $($summary.exit_code))" -ForegroundColor Red
    exit $summary.exit_code
}
Write-Host "[readiness] OK" -ForegroundColor Green
exit 0
