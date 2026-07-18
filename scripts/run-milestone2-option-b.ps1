# Milestone 2 Option B — local pre/post RM latency A/B (requires backend\.env.operator.local)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$AbJson = "docs/delivery/milestone2-latency-ab-latest.json"
$PreJson = "docs/delivery/milestone2-latency-pre-rm-probe.json"
$AuditJson = "docs/delivery/milestone2-performance-audit-latest.json"
$EnvFile = Join-Path $Root "backend\.env.operator.local"
if (-not (Test-Path $EnvFile)) {
    Write-Host "Missing $EnvFile — need RAILWAY_TOKEN + Supabase smoke vars" -ForegroundColor Red
    exit 2
}
Get-Content $EnvFile | ForEach-Object {
    if ($_ -match '^\s*([^#=]+)=(.*)$') {
        $name = $matches[1].Trim()
        $val = $matches[2].Trim().Trim('"')
        if ($name -and $val) { Set-Item -Path "env:$name" -Value $val }
    }
}
Write-Host "=== Milestone 2 Option B: full latency A/B ==="
python scripts/smoke-milestone2-latency-ab.py --full-ab --json $AbJson
python scripts/smoke-milestone2-performance-audit.py --latency-baseline $PreJson --json $AuditJson
Write-Host "=== Done — see $AbJson and $AuditJson ==="
