#Requires -Version 5.1
<#
.SYNOPSIS
  Fast-forward v0 and Cursor branches to match main and push to origin.
#>
param(
    [switch] $DryRun
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

function Invoke-Git {
    param([string[]] $GitArgs)
    if ($DryRun) {
        Write-Host "[dry-run] git $($GitArgs -join ' ')"
        return
    }
    & git @GitArgs
    if ($LASTEXITCODE -ne 0) { throw "git failed: $($GitArgs -join ' ')" }
}

Invoke-Git @("fetch", "origin")
Invoke-Git @("checkout", "main")
Invoke-Git @("pull", "--ff-only", "origin", "main")

Invoke-Git @("checkout", "v0-sync")
Invoke-Git @("merge", "--ff-only", "main")
Invoke-Git @("push", "origin", "v0-sync:v0/cesarbohorquezjr-4251-8b623736")

Invoke-Git @("checkout", "cursor/auth-config-cli-0dd3")
Invoke-Git @("merge", "--ff-only", "main")
Invoke-Git @("push", "origin", "cursor/auth-config-cli-0dd3")

Invoke-Git @("checkout", "main")
Write-Host "Branches synced to main ($((git rev-parse --short HEAD)))" -ForegroundColor Green
