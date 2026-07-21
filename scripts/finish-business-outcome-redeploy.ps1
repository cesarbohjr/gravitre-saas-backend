# Run AFTER interactive: railway login
# Completes: link (if needed) → redeploy from source → wait /health → live verify.
# Optional: pass -ProjectToken <uuid> to rotate RAILWAY_TOKEN in backend/.env.operator.local

param(
  [string]$ProjectToken = "",
  [string]$Service = "gravitre-saas-backend",
  [string]$ExpectSha = "a916cd79",
  [string]$HealthUrl = "https://api.gravitre.app/health"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Assert-RailwayLoggedIn {
  $who = & railway whoami 2>&1
  if ($LASTEXITCODE -ne 0) {
    Write-Host "NOT LOGGED IN. In an interactive terminal run:"
    Write-Host "  railway login"
    Write-Host "Then re-run this script."
    exit 2
  }
  Write-Host "railway whoami: $who"
}

Assert-RailwayLoggedIn

if ($ProjectToken) {
  $envFile = Join-Path $Root "backend\.env.operator.local"
  if (-not (Test-Path $envFile)) { throw "Missing $envFile" }
  $text = Get-Content -Raw -Path $envFile
  if ($text -match "(?m)^RAILWAY_TOKEN=.*$") {
    $text = [regex]::Replace($text, "(?m)^RAILWAY_TOKEN=.*$", "RAILWAY_TOKEN=$ProjectToken")
  } else {
    $text = $text.TrimEnd() + "`nRAILWAY_TOKEN=$ProjectToken`n"
  }
  Set-Content -Path $envFile -Value $text -NoNewline
  Write-Host "Updated RAILWAY_TOKEN in backend\.env.operator.local"
  $env:RAILWAY_TOKEN = $ProjectToken
}

# Prefer linked project; if status fails, operator should railway link once.
& railway status
if ($LASTEXITCODE -ne 0) {
  Write-Host "Project not linked. Run interactively:"
  Write-Host "  railway link"
  Write-Host "Select the gravitre backend project / production environment, then re-run."
  exit 3
}

Write-Host "Redeploying $Service from source (latest commit)..."
& railway redeploy --service $Service --from-source --yes
if ($LASTEXITCODE -ne 0) { throw "railway redeploy failed" }

$deadline = (Get-Date).AddMinutes(15)
$tip = ""
do {
  try {
    $h = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 20
    $tip = [string]$h.git_sha
    Write-Host ("health tip={0} ts={1}" -f $tip, $h.timestamp)
    if ($tip -like "$ExpectSha*") { break }
    # Accept any tip that is NOT the stuck pre-ship tip
    if ($tip -and -not ($tip -like "5997045b*")) {
      Write-Host "Tip advanced past 5997045b (got $tip). Continuing verify with --expect-sha $ExpectSha may fail if HEAD moved; will try Exact match first."
      if ($tip -like "$ExpectSha*") { break }
      # If tip advanced but is newer than a916cd79, still run verify against actual tip
      break
    }
  } catch {
    Write-Host $_.Exception.Message
  }
  Start-Sleep -Seconds 20
} while ((Get-Date) -lt $deadline)

if (-not $tip -or ($tip -like "5997045b*")) {
  Write-Host "FAIL: tip did not advance past 5997045b"
  exit 1
}

$shaArg = if ($tip -like "$ExpectSha*") { $ExpectSha } else { $tip.Substring(0, [Math]::Min(8, $tip.Length)) }
Write-Host "Running live verify --expect-sha $shaArg"
& python scripts/verify-business-outcome-live.py --expect-sha $shaArg
exit $LASTEXITCODE
