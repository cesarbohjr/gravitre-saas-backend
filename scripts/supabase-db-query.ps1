#Requires -Version 5.1
<#
.SYNOPSIS
  Run supabase db query against the linked project with reliable auth.

.DESCRIPTION
  Fixes intermittent cli_login_postgres pooler auth failures by:
  - loading SUPABASE_ACCESS_TOKEN / SUPABASE_DB_PASSWORD from backend env files
  - optionally repairing the link with --skip-pooler (direct Postgres, no stale pooler cache)

.PARAMETER Sql
  Inline SQL to execute.

.PARAMETER File
  Path to a .sql file to execute.

.PARAMETER OutputFormat
  table | json | csv (passed to supabase -o)

.PARAMETER RepairLink
  Delete stale pooler cache and re-link before querying. Use -SkipPooler only on IPv6-capable networks.

.PARAMETER SkipPooler
  Pass --skip-pooler to supabase link (direct Postgres). Fails on IPv4-only networks.

.EXAMPLE
  .\scripts\supabase-db-query.ps1 -Sql "SELECT COUNT(*) FROM public.workflows"
  .\scripts\supabase-db-query.ps1 -File supabase\scripts\legacy\verify_backfill.sql -OutputFormat json
  .\scripts\supabase-db-query.ps1 -RepairLink -Sql "SELECT 1"
#>
param(
    [string] $Sql,
    [string] $File,
    [ValidateSet("table", "json", "csv")]
    [string] $OutputFormat = "table",
    [switch] $RepairLink,
    [switch] $SkipPooler,
    [string] $ProjectRef = "smyeexlrqdpymwjmgzqu"
)

$ErrorActionPreference = "Stop"
if (-not $Sql -and -not $File) {
    Write-Error "Provide -Sql or -File"
}
if ($Sql -and $File) {
    Write-Error "Use only one of -Sql or -File"
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$envFiles = @(
    (Join-Path $repoRoot "backend\.env.operator.local"),
    (Join-Path $repoRoot "backend\.env")
)

function Import-DotEnvValue {
    param([string] $Path, [string] $Key)
    if (-not (Test-Path $Path)) { return $null }
    foreach ($line in Get-Content $Path) {
        if ($line -match "^\s*$Key=(.*)$") {
            $value = $Matches[1].Trim()
            if ($value.StartsWith('"') -and $value.EndsWith('"')) {
                $value = $value.Substring(1, $value.Length - 2)
            }
            return $value
        }
    }
    return $null
}

foreach ($path in $envFiles) {
    if (-not $env:SUPABASE_ACCESS_TOKEN) {
        $token = Import-DotEnvValue -Path $path -Key "SUPABASE_ACCESS_TOKEN"
        if ($token) { $env:SUPABASE_ACCESS_TOKEN = $token }
    }
    if (-not $env:SUPABASE_DB_PASSWORD) {
        $dbPassword = Import-DotEnvValue -Path $path -Key "SUPABASE_DB_PASSWORD"
        if ($dbPassword) { $env:SUPABASE_DB_PASSWORD = $dbPassword }
    }
}

Push-Location $repoRoot
try {
    if ($RepairLink) {
        $tempDir = Join-Path $repoRoot "supabase\.temp"
        $poolerFile = Join-Path $tempDir "pooler-url"
        if (Test-Path $poolerFile) {
            Write-Host "Removing stale pooler cache: $poolerFile"
            Remove-Item $poolerFile -Force
        }
        Write-Host "Re-linking project $ProjectRef ..."
        $linkArgs = @("link", "--project-ref", $ProjectRef, "--yes")
        if ($SkipPooler) { $linkArgs += "--skip-pooler" }
        supabase @linkArgs
        if ($LASTEXITCODE -ne 0) {
            Write-Error "supabase link --skip-pooler failed (exit $LASTEXITCODE). Set SUPABASE_DB_PASSWORD in backend/.env.operator.local if prompted."
        }
    }

    $args = @("db", "query", "--linked", "-o", $OutputFormat)
    if ($File) {
        if (-not (Test-Path $File)) {
            Write-Error "SQL file not found: $File"
        }
        $args += @("-f", $File)
    } else {
        $args += $Sql
    }

    & supabase @args
    if ($LASTEXITCODE -ne 0) {
        Write-Error "supabase db query failed (exit $LASTEXITCODE). Try: .\scripts\supabase-db-query.ps1 -RepairLink -Sql `"SELECT 1`""
    }
}
finally {
    Pop-Location
}
