# Local dev: Stripe Connect v2 sample + thin webhook forwarder
# Usage: from repo root, after setting STRIPE_SECRET_KEY (sk_test_...) in env:
#   .\backend\scripts\run_connect_sample_local.ps1

$ErrorActionPreference = "Stop"
$stripe = "C:\Users\Cesar\AppData\Local\Microsoft\WinGet\Packages\Stripe.StripeCli_Microsoft.Winget.Source_8wekyb3d8bbwe\stripe.exe"

if (-not $env:STRIPE_SECRET_KEY) {
  Write-Error "Set STRIPE_SECRET_KEY (sk_test_...) before running."
}
if (-not $env:STRIPE_CONNECT_THIN_WEBHOOK_SECRET) {
  Write-Host "STRIPE_CONNECT_THIN_WEBHOOK_SECRET not set — stripe listen will print one; export it before testing webhooks."
}
$env:STRIPE_CONNECT_SAMPLE_BASE_URL = if ($env:STRIPE_CONNECT_SAMPLE_BASE_URL) { $env:STRIPE_CONNECT_SAMPLE_BASE_URL } else { "http://localhost:8000" }
$env:STRIPE_CONNECT_SAMPLE_PLATFORM_FEE_PERCENT = if ($env:STRIPE_CONNECT_SAMPLE_PLATFORM_FEE_PERCENT) { $env:STRIPE_CONNECT_SAMPLE_PLATFORM_FEE_PERCENT } else { "10" }

Write-Host "Starting stripe listen (thin) in background..."
Start-Process -NoNewWindow $stripe -ArgumentList @(
  "listen",
  "--thin-events", "v2.core.account.updated,v2.core.account.requirements.updated",
  "--forward-thin-to", "http://localhost:8000/api/samples/stripe-connect/webhooks/thin"
)

Write-Host "Starting uvicorn on http://localhost:8000 ..."
Set-Location "$PSScriptRoot\.."
python -m uvicorn app.main:app --reload --port 8000
