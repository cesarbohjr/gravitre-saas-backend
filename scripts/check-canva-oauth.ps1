#Requires -Version 5.1
param(
    [string] $ApiBase = "https://api.gravitre.app"
)

$uri = "$($ApiBase.TrimEnd('/'))/api/connectors/oauth/canva/status"
try {
    $r = Invoke-RestMethod -Uri $uri -Method Get -TimeoutSec 20
    Write-Host "Canva OAuth status ($uri):"
    $r | ConvertTo-Json -Depth 5
    if ($r.configured -and $r.encryptionConfigured) {
        Write-Host "READY - Register redirect: $($r.redirectUri)" -ForegroundColor Green
        exit 0
    }
    Write-Host "NOT READY - set CANVA_CLIENT_ID/SECRET on Railway" -ForegroundColor Yellow
    exit 1
} catch {
    Write-Host "Request failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
