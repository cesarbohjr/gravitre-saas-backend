#Requires -Version 5.1
<#
.SYNOPSIS
  Enable internet research on Railway + Vercel (production flags + provider keys from operator env).

  Sets:
    Railway  INTERNET_RESEARCH_ENABLED=true (+ GEMINI_API_KEY / TAVILY_API_KEY when present locally)
    Vercel   NEXT_PUBLIC_INTERNET_RESEARCH_ENABLED=true (Production)
#>
param(
    [string] $EnvFile = $(Join-Path (Split-Path -Parent $PSScriptRoot) "backend\.env.operator.local"),
    [string] $RailwayService = "gravitre-saas-backend",
    [string] $VercelCwd = $(Join-Path (Split-Path -Parent $PSScriptRoot) "apps\web")
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $EnvFile)) {
    Write-Host "Missing $EnvFile" -ForegroundColor Red
    exit 1
}

$parsed = @{}
foreach ($enc in @("utf-8", "utf-8-sig", "cp1252", "latin-1")) {
    try {
        Get-Content $EnvFile -Encoding $enc | ForEach-Object {
            $line = $_.Trim()
            if (-not $line -or $line.StartsWith("#")) { return }
            $idx = $line.IndexOf("=")
            if ($idx -lt 1) { return }
            $key = $line.Substring(0, $idx).Trim()
            $val = $line.Substring($idx + 1).Trim().Trim('"')
            if ($val) { $parsed[$key] = $val }
        }
        break
    } catch {
        continue
    }
}

if ($parsed.ContainsKey("RAILWAY_TOKEN")) {
    $env:RAILWAY_TOKEN = $parsed["RAILWAY_TOKEN"]
}
if (-not $env:RAILWAY_TOKEN) {
    Write-Host "RAILWAY_TOKEN missing in $EnvFile" -ForegroundColor Red
    exit 1
}

if (-not (Get-Command railway -ErrorAction SilentlyContinue)) {
    Write-Host "Install Railway CLI: npm i -g @railway/cli" -ForegroundColor Red
    exit 1
}

Write-Host "Setting Railway internet research flags on $RailwayService..."
railway variables set "INTERNET_RESEARCH_ENABLED=true" --service $RailwayService
foreach ($key in @("GEMINI_API_KEY", "GOOGLE_API_KEY", "TAVILY_API_KEY", "WEB_RESEARCH_PROVIDER", "WEB_RESEARCH_FALLBACK_TAVILY")) {
    if ($parsed.ContainsKey($key)) {
        Write-Host "Setting $key on Railway..."
        railway variables set "${key}=$($parsed[$key])" --service $RailwayService
    }
}

Write-Host "Triggering Railway redeploy..."
railway redeploy --service $RailwayService -y 2>&1 | Out-Host

if (Get-Command vercel -ErrorAction SilentlyContinue) {
    Push-Location $VercelCwd
    try {
        Write-Host "Setting Vercel NEXT_PUBLIC_INTERNET_RESEARCH_ENABLED=true (production)..."
        echo "true" | vercel env add NEXT_PUBLIC_INTERNET_RESEARCH_ENABLED production --force 2>&1 | Out-Host
        Write-Host "Deploying web to production..."
        vercel deploy --prod --yes --archive=tgz 2>&1 | Out-Host
    } finally {
        Pop-Location
    }
} else {
    Write-Host "Vercel CLI not found — set NEXT_PUBLIC_INTERNET_RESEARCH_ENABLED=true manually." -ForegroundColor Yellow
}

Write-Host "Done. Verify: Invoke-RestMethod https://api.gravitre.app/health | internet_research_enabled" -ForegroundColor Green
