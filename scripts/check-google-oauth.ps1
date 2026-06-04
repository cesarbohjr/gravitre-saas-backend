#Requires -Version 5.1
param(
    [string] $ApiBase = "https://gravitre-saas-backend-production.up.railway.app"
)

$ErrorActionPreference = "Stop"
$base = $ApiBase.TrimEnd("/")
$providers = @(
    "google_analytics",
    "google_calendar",
    "gmail",
    "google_drive",
    "google_docs",
    "google_sheets"
)

$allOk = $true
foreach ($slug in $providers) {
    $uri = "$base/api/connectors/oauth/$slug/status"
    try {
        $r = Invoke-RestMethod -Uri $uri -Method Get -TimeoutSec 20
        Write-Host "$slug ($uri):"
        $r | ConvertTo-Json -Depth 5
        if (-not ($r.configured -and $r.encryptionConfigured)) {
            $allOk = $false
            Write-Host "  NOT READY" -ForegroundColor Yellow
        } else {
            Write-Host "  READY - $($r.redirectUri)" -ForegroundColor Green
        }
    } catch {
        $allOk = $false
        Write-Host "$slug failed: $($_.Exception.Message)" -ForegroundColor Red
    }
    Write-Host ""
}

if ($allOk) {
    Write-Host "All Google connector OAuth endpoints are ready." -ForegroundColor Green
    exit 0
}
Write-Host "Fix: npm run google:fill-env; npm run google:railway" -ForegroundColor Yellow
exit 1
