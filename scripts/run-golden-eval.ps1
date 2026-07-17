# Golden-question eval (Phase G3)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$env:PYTHONPATH = $Root
& "$Root\.venv\Scripts\python.exe" "$Root\scripts\run_golden_eval.py" @args
