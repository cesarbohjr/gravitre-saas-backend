#Requires -Version 5.1
param(
    [string] $ApiBase = "https://api.gravitre.app"
)

$base = "$($ApiBase.TrimEnd('/'))/api/connectors/oauth"

$tier1 = @(
    "hubspot", "salesforce", "quickbooks", "netsuite", "workday", "marketo",
    "jira", "confluence", "pagerduty", "notion", "slack"
)
$google = @(
    "google_analytics", "google_calendar", "gmail", "google_drive", "google_docs", "google_sheets"
)
$generic = @(
    "mailchimp", "constant_contact", "xero", "airtable", "asana", "clickup",
    "freshdesk", "intercom", "monday", "microsoft365", "github", "zendesk",
    "zapier", "hootsuite", "gusto", "canva", "figma"
)

function Test-Provider([string]$Provider) {
    $uri = "$base/$Provider/status"
    try {
        $r = Invoke-RestMethod -Uri $uri -Method Get -TimeoutSec 20
        $ready = [bool]($r.configured -and $r.encryptionConfigured)
        return [PSCustomObject]@{
            Provider    = $Provider
            Ready       = $ready
            Configured  = [bool]$r.configured
            Encryption  = [bool]$r.encryptionConfigured
            RedirectUri = $r.redirectUri
            Error       = $null
        }
    } catch {
        $msg = $_.Exception.Message
        if ($_.ErrorDetails.Message) { $msg = $_.ErrorDetails.Message }
        return [PSCustomObject]@{
            Provider    = $Provider
            Ready       = $false
            Configured  = $false
            Encryption  = $false
            RedirectUri = $null
            Error       = $msg
        }
    }
}

Write-Host ""
Write-Host "Gravitre OAuth status - $ApiBase" -ForegroundColor Cyan
Write-Host ""

$all = @()
foreach ($group in @(
    @{ Name = "Tier1"; Items = $tier1 },
    @{ Name = "Google"; Items = $google },
    @{ Name = "Generic"; Items = $generic }
)) {
    Write-Host "=== $($group.Name) ===" -ForegroundColor Cyan
    foreach ($p in $group.Items) {
        $result = Test-Provider $p
        $all += $result
        $color = if ($result.Ready) { "Green" } elseif ($result.Error) { "Red" } else { "Yellow" }
        $status = if ($result.Ready) { "READY" } elseif ($result.Error) { "ERROR" } else { "NOT CONFIGURED" }
        Write-Host ("  {0,-22} {1}" -f $p, $status) -ForegroundColor $color
        if ($result.RedirectUri) { Write-Host "    redirect: $($result.RedirectUri)" }
        if ($result.Error) { Write-Host "    error: $($result.Error)" -ForegroundColor DarkGray }
    }
    Write-Host ""
}

$ready = @($all | Where-Object { $_.Ready })
$gaps = @($all | Where-Object { -not $_.Ready -and -not $_.Error })
$errors = @($all | Where-Object { $_.Error })

Write-Host "Summary: $($ready.Count) ready / $($all.Count) checked" -ForegroundColor Cyan
if ($gaps.Count) {
    Write-Host "Not configured (add env vars then npm run hubspot:railway):" -ForegroundColor Yellow
    $gaps | ForEach-Object { Write-Host "  - $($_.Provider)" }
}
if ($errors.Count) {
    Write-Host "Errors (deploy latest backend for generic OAuth):" -ForegroundColor Red
    $errors | ForEach-Object { Write-Host "  - $($_.Provider)" }
}

if ($ready.Count -ge 10) {
    Write-Host ""
    Write-Host "Phase 1 core is operational. Connect at https://gravitre.app/connectors" -ForegroundColor Green
}

if ($ready.Count -lt 1) { exit 1 }
exit 0
