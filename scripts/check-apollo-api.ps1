#Requires -Version 5.1
param(
    [string] $ApiKey = $env:APOLLO_API_KEY
)

if (-not $ApiKey) {
    Write-Host "Set APOLLO_API_KEY or pass -ApiKey to smoke-test Apollo credentials." -ForegroundColor Yellow
    Write-Host "Org connectors use per-tenant keys from https://gravitre.app/connectors (Add Apollo)." -ForegroundColor Yellow
    exit 1
}

$uri = "https://api.apollo.io/api/v1/mixed_people/api_search?per_page=1"
try {
    $headers = @{
        "X-Api-Key"    = $ApiKey
        "Accept"       = "application/json"
        "Content-Type" = "application/json"
        "Cache-Control" = "no-cache"
    }
    $r = Invoke-RestMethod -Uri $uri -Method Post -Headers $headers -TimeoutSec 20
    Write-Host "Apollo API key valid (people search probe succeeded)." -ForegroundColor Green
    if ($r.pagination) {
        $r.pagination | ConvertTo-Json -Depth 3
    }
    exit 0
} catch {
    Write-Host "Apollo API check failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
