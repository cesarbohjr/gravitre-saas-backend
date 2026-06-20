#Requires -Version 5.1
param(
    [string] $ApiBase = "https://api.gravitre.app"
)

$uri = "$($ApiBase.TrimEnd('/'))/api/connectors/oauth/microsoft365/status"
try {
    $r = Invoke-RestMethod -Uri $uri -Method Get -TimeoutSec 20
    Write-Host "Microsoft 365 OAuth status ($uri):"
    $r | ConvertTo-Json -Depth 5
    if ($r.configured -and $r.encryptionConfigured) {
        Write-Host "READY - Connect Microsoft 365 at https://gravitre.app/connectors" -ForegroundColor Green
        exit 0
    }
    Write-Host "NOT READY - set MICROSOFT365_CLIENT_ID/SECRET on Railway" -ForegroundColor Yellow
    exit 1
} catch {
    Write-Host "Request failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
