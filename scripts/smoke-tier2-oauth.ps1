#Requires -Version 5.1
param(
    [string] $ApiBase = "https://api.gravitre.app",
    [string] $AppBase = "https://gravitre.app"
)

$vendors = @("quickbooks", "netsuite")

function Test-CallbackRoute {
    param([string] $Url)
    $raw = curl.exe -s -o NUL -w "%{http_code}" $Url 2>$null
    if ($raw -match '^\d{3}$') {
        $code = [int]$raw
        return $code -in 200, 302, 400, 401, 422
    }
    return $false
}

Write-Host ""
Write-Host "Tier 2 OAuth smoke" -ForegroundColor Cyan
Write-Host ""

$results = @()
foreach ($v in $vendors) {
    $statusOk = $false
    $redirectOk = $false
    $callbackOk = $false
    $redirectUri = $null
    $notes = @()

    try {
        $s = Invoke-RestMethod -Uri "$ApiBase/api/connectors/oauth/$v/status" -Method Get -TimeoutSec 25
        $statusOk = [bool]($s.configured -and $s.encryptionConfigured)
        $redirectUri = $s.redirectUri
        if ($redirectUri -match "^https://gravitre\.app") { $redirectOk = $true }
        else { $notes += "redirect=$redirectUri" }
    } catch {
        $notes += "status=$($_.Exception.Message)"
    }

    $callbackUrl = "$AppBase/api/connectors/oauth/$v/callback"
    $callbackOk = Test-CallbackRoute -Url $callbackUrl
    if (-not $callbackOk) { $notes += "callback failed" }

    $pass = $statusOk -and $redirectOk -and $callbackOk
    $results += [PSCustomObject]@{
        vendor      = $v
        pass        = $pass
        statusOk    = $statusOk
        redirectOk  = $redirectOk
        callbackOk  = $callbackOk
        redirectUri = $redirectUri
        notes       = ($notes -join "; ")
    }

    if ($pass) {
        Write-Host ("  {0,-20} PASS" -f $v) -ForegroundColor Green
    } else {
        Write-Host ("  {0,-20} FAIL" -f $v) -ForegroundColor Red
    }
    if ($notes) { Write-Host "    $($notes -join '; ')" -ForegroundColor DarkGray }
}

$passed = @($results | Where-Object { $_.pass }).Count
Write-Host ""
Write-Host "Summary: $passed/$($results.Count) passed" -ForegroundColor Cyan

$outPath = Join-Path (Split-Path -Parent $PSScriptRoot) "docs\delivery\tier2-oauth-smoke-latest.json"
$payload = @{
    generatedAt = (Get-Date).ToUniversalTime().ToString("o")
    issue       = "STA-277"
    apiBase     = $ApiBase
    appBase     = $AppBase
    summary     = @{ passed = $passed; total = $results.Count }
    vendors     = $results
} | ConvertTo-Json -Depth 6
Set-Content -Path $outPath -Value $payload -Encoding UTF8
Write-Host "Report: $outPath"

if ($passed -lt $results.Count) { exit 1 }
exit 0
