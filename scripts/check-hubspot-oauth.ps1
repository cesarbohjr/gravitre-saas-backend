#Requires -Version 5.1
param(
    [string] $ApiBase = "https://api.gravitre.app"
)

$uri = "$($ApiBase.TrimEnd('/'))/api/connectors/oauth/hubspot/status"
try {
    $r = Invoke-RestMethod -Uri $uri -Method Get -TimeoutSec 20
    Write-Host "HubSpot OAuth status ($uri):"
    $r | ConvertTo-Json -Depth 5
    if ($r.configured -and $r.encryptionConfigured) {
        Write-Host "READY for Connect HubSpot in UI" -ForegroundColor Green
        exit 0
    }
    Write-Host "NOT READY - set missing Railway env vars (see apply-railway-hubspot-env.ps1)" -ForegroundColor Yellow
    exit 1
} catch {
    Write-Host "Request failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
