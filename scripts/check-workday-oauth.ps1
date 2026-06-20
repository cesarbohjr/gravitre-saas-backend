#Requires -Version 5.1
param(
    [string] $ApiBase = "https://api.gravitre.app"
)

$uri = "$($ApiBase.TrimEnd('/'))/api/connectors/oauth/workday/status"
try {
    $r = Invoke-RestMethod -Uri $uri -Method Get -TimeoutSec 20
    Write-Host "Workday OAuth status ($uri):"
    $r | ConvertTo-Json -Depth 5
    if ($r.configured -and $r.encryptionConfigured) {
        Write-Host "READY - Connect Workday at https://gravitre.app/connectors" -ForegroundColor Green
        exit 0
    }
    Write-Host "NOT READY - set WORKDAY_CLIENT_ID/SECRET on Railway" -ForegroundColor Yellow
    exit 1
} catch {
    Write-Host "Request failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
