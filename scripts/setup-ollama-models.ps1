# Pull recommended Ollama models for AI Fabric Insight Explorer
# Usage: .\scripts\setup-ollama-models.ps1 [-BaseUrl http://host:11434] [-Profile default|deep|all]

param(
    [string]$BaseUrl = $(if ($env:OLLAMA_BASE_URL) { $env:OLLAMA_BASE_URL } else { "http://127.0.0.1:11434" }),
    [ValidateSet("default", "deep", "all")]
    [string]$Profile = "default"
)

$ErrorActionPreference = "Stop"

$DefaultModels = @(
    "qwen2.5-coder:14b"      # Phase 1 primary — SQL + Thai + agents
)

$DeepModels = @(
    "qwen2.5-coder:32b"      # Quality Bar D heavy / complex SAP schema
)

$OptionalModels = @(
    "qwen2.5:14b-instruct",  # Thai business explanations
    "deepseek-coder-v2:16b"  # SQL alternative
)

$ToPull = switch ($Profile) {
    "default" { $DefaultModels }
    "deep"    { $DefaultModels + $DeepModels }
    "all"     { $DefaultModels + $DeepModels + $OptionalModels }
}

Write-Host "Ollama server: $BaseUrl" -ForegroundColor Cyan
Write-Host "Profile: $Profile" -ForegroundColor Cyan
Write-Host ""

foreach ($model in $ToPull) {
    Write-Host "Pulling $model ..." -ForegroundColor Yellow
    $env:OLLAMA_HOST = $BaseUrl
    ollama pull $model
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to pull $model (is Ollama running at $BaseUrl?)" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "Done. Set in .env:" -ForegroundColor Green
Write-Host "  OLLAMA_BASE_URL=$BaseUrl"
if ($Profile -eq "deep" -or $Profile -eq "all") {
    Write-Host "  OLLAMA_MODEL=qwen2.5-coder:32b   # for deep mode"
} else {
    Write-Host "  OLLAMA_MODEL=qwen2.5-coder:14b   # recommended default"
}
