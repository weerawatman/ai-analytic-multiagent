# Seed Metric Registry (Phase G2)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$env:PYTHONPATH = $Root
& "$Root\.venv\Scripts\python.exe" "$Root\scripts\seed_metric_registry.py" @args
