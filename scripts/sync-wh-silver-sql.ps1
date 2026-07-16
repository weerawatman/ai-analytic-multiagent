param(
    # Root of WH_Silver SQL folder (must contain SAPHANADB/Tables and SAPHANADB/StoredProcedures)
    [string]$SourcePath = "C:\SBG_Working Folder\Special Project&Activity\SAT_Fabric_Knowledge\01_SQL\WH_Silver"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$TargetRoot = Join-Path $Root "data\local\knowledge\sql_reference"
$Schema = "SAPHANADB"

Write-Host "=== Sync WH_Silver SQL Reference ===" -ForegroundColor Cyan
Write-Host "Source: $SourcePath"
Write-Host "Target: $TargetRoot"

$sourceSchema = Join-Path $SourcePath $Schema
if (-not (Test-Path $sourceSchema)) {
    Write-Host "Schema folder not found: $sourceSchema" -ForegroundColor Red
    Write-Host "Set -SourcePath to your WH_Silver root, e.g.:"
    Write-Host '  .\scripts\sync-wh-silver-sql.ps1 -SourcePath "C:\SBG_Working Folder\Special Project&Activity\SAT_Fabric_Knowledge\01_SQL\WH_Silver"'
    exit 1
}

$folders = @(
    @{ Name = "Tables"; Kind = "table_ddl" },
    @{ Name = "StoredProcedures"; Kind = "load_sp" }
)

$copied = @()
foreach ($folder in $folders) {
    $srcDir = Join-Path $sourceSchema $folder.Name
    $dstDir = Join-Path $TargetRoot "$Schema\$($folder.Name)"
    New-Item -ItemType Directory -Force -Path $dstDir | Out-Null

    if (-not (Test-Path $srcDir)) {
        Write-Host "Skip (missing): $srcDir" -ForegroundColor Yellow
        continue
    }

    $files = Get-ChildItem -Path $srcDir -Filter "*.sql" -File
    foreach ($file in $files) {
        Copy-Item -Path $file.FullName -Destination (Join-Path $dstDir $file.Name) -Force
        $copied += [PSCustomObject]@{
            Name     = $file.Name
            Kind     = $folder.Kind
            RelPath  = "$Schema/$($folder.Name)/$($file.Name)"
            FullName = $file.BaseName
        }
        Write-Host "  Copied: $($folder.Name)/$($file.Name)"
    }
}

if ($copied.Count -eq 0) {
    Write-Host "No .sql files copied. Check SourcePath and folder contents." -ForegroundColor Red
    exit 1
}

function Convert-ToSnakeCaseId {
    param([string]$Name)
    return ($Name.ToLower() -replace '[-\s]+', '_')
}

$items = foreach ($entry in ($copied | Sort-Object RelPath)) {
    @{
        id             = Convert-ToSnakeCaseId $entry.FullName
        schema         = $Schema
        table_ref      = "$Schema.$($entry.FullName)"
        file_path      = $entry.RelPath -replace '\\', '/'
        kind           = $entry.Kind
        description_th = if ($entry.Kind -eq "table_ddl") {
            "Synced table DDL: $($entry.FullName)"
        } else {
            "Synced load SP: $($entry.FullName)"
        }
        themes         = @()
        tags           = @($entry.Kind -replace '_', '-')
    }
}

$manifest = @{
    version    = "1.0"
    warehouse  = "WH_Silver"
    updated_at = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    items      = @($items)
}

$manifestPath = Join-Path $TargetRoot "_manifest.json"
New-Item -ItemType Directory -Force -Path $TargetRoot | Out-Null
$manifest | ConvertTo-Json -Depth 6 | Set-Content -Path $manifestPath -Encoding UTF8

Write-Host ""
Write-Host "Copied $($copied.Count) file(s)." -ForegroundColor Green
Write-Host "Manifest: $manifestPath ($($items.Count) items)" -ForegroundColor Green
Write-Host "Agents can reference SQL from data/local/knowledge/sql_reference/" -ForegroundColor Green
