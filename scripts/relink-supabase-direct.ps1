#Requires -Version 5.1
<#
.SYNOPSIS
  Repair Supabase CLI database auth by clearing stale pooler cache and re-linking.

.EXAMPLE
  .\scripts\relink-supabase-direct.ps1
#>
param(
    [string] $ProjectRef = "smyeexlrqdpymwjmgzqu"
)

& (Join-Path $PSScriptRoot "supabase-db-query.ps1") -RepairLink -Sql "SELECT 1 AS ok" -OutputFormat json -ProjectRef $ProjectRef
