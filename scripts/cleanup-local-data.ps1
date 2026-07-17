<#
.SYNOPSIS
  Clear Phase D/E scratch data, old logs, and terminal chat jobs.
  Never touch knowledge, team_memory, or models/approved.

.DESCRIPTION
  Removes contents of data/local/local_data/ and aged files under data/local/logs/,
  then purges terminal jobs older than -JobDays from the local SQLite job store.

  ALWAYS preserved:
    - data/local/team_memory/
    - data/local/knowledge/
    - data/local/models/approved/

.PARAMETER Days
  Delete log files older than this many days (default 14).

.PARAMETER JobDays
  Delete terminal jobs (done/failed/cancelled) older than this many days (default 14).

.PARAMETER WhatIf
  Show actions without deleting.

.EXAMPLE
  .\scripts\cleanup-local-data.ps1

.EXAMPLE
  # Windows Task Scheduler (daily 03:00):
  #   Program: powershell.exe
  #   Arguments: -NoProfile -ExecutionPolicy Bypass -File "C:\Projects\ai-analytic-multiagent\scripts\cleanup-local-data.ps1"
  #   Start in: C:\Projects\ai-analytic-multiagent
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [int]$Days = 14,
    [int]$JobDays = 14
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $Root "backend"))) {
    $Root = (Get-Location).Path
}

$Local = Join-Path $Root "data\local"
$LocalData = Join-Path $Local "local_data"
$Logs = Join-Path $Local "logs"

Write-Host "cleanup-local-data - root=$Root days=$Days jobDays=$JobDays"

# --- local_data scratch (Phase E parquet / job models) ---
if (Test-Path $LocalData) {
    Get-ChildItem -Path $LocalData -Force -ErrorAction SilentlyContinue | ForEach-Object {
        if ($PSCmdlet.ShouldProcess($_.FullName, "Remove")) {
            Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
            Write-Host "  removed $($_.FullName)"
        }
    }
} else {
    New-Item -ItemType Directory -Path $LocalData -Force | Out-Null
    Write-Host "  created $LocalData"
}

# --- aged logs (keep directory; never touch preserved trees) ---
if (Test-Path $Logs) {
    $cutoff = (Get-Date).AddDays(-[Math]::Abs($Days))
    Get-ChildItem -Path $Logs -File -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt $cutoff } |
        ForEach-Object {
            if ($PSCmdlet.ShouldProcess($_.FullName, "Remove old log")) {
                Remove-Item -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue
                Write-Host "  removed log $($_.Name)"
            }
        }
}

# --- terminal jobs via Python helper (same DB as backend) ---
$venvPy = Join-Path $Root ".venv\Scripts\python.exe"
$py = if (Test-Path $venvPy) { $venvPy } else { "python" }
$helper = Join-Path $Root "scripts\cleanup_local_data.py"
$env:PYTHONPATH = $Root
if ($PSCmdlet.ShouldProcess("job_store", "Purge terminal jobs older than $JobDays days")) {
    & $py $helper --job-days $JobDays
}

Write-Host "Preserved (never deleted by this script):"
Write-Host "  - data/local/team_memory/"
Write-Host "  - data/local/knowledge/"
Write-Host "  - data/local/models/approved/"
Write-Host "Done."
