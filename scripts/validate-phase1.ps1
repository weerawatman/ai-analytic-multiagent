$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = $Root

Write-Host "=== Phase 1 Validation ===" -ForegroundColor Cyan

Write-Host "`n[1/2] Running tests..." -ForegroundColor Yellow
python -m pytest "$Root\backend\tests\" -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`n[2/2] Running DoD checks..." -ForegroundColor Yellow
python -c @"
import asyncio
import json
from backend.app.services.phase1_validator import run_phase1_validation

report = asyncio.run(run_phase1_validation())
print(json.dumps(report['summary'], indent=2, ensure_ascii=False))
print()
for c in report['checks']:
    mark = 'PASS' if c['passed'] else 'FAIL'
    print(f\"  [{mark}] {c['id']}: {c['title']}\")
    if not c['passed'] and c.get('manual_note'):
        print(f\"         -> {c['manual_note']}\")
exit(0 if report['summary']['ready_for_signoff'] else 1)
"@

if ($LASTEXITCODE -ne 0) {
    Write-Host "`nSome checks failed — complete manual steps in knowledge/07-testing/sign-off.md" -ForegroundColor Yellow
    exit 1
}

Write-Host "`nAll Phase 1 checks passed." -ForegroundColor Green
