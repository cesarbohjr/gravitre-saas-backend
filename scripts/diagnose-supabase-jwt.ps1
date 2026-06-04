#Requires -Version 5.1
<#
.SYNOPSIS
  Determine whether your Supabase access tokens use HS256 (legacy secret) or ES256 (JWKS).

  Usage:
    .\scripts\diagnose-supabase-jwt.ps1
    .\scripts\diagnose-supabase-jwt.ps1 -AccessToken "eyJhbG..."

  Get AccessToken after login:
    Browser DevTools → Application → Cookies → gravitre.app → find sb-* auth token,
    or Network → any request → Authorization: Bearer <token>
    (Supabase session access_token from getSession is the one Railway validates.)
#>
param(
    [string] $ProjectRef = "smyeexlrqdpymwjmgzqu",
    [string] $AccessToken
)

$ErrorActionPreference = "Stop"
$JwksUrl = "https://$ProjectRef.supabase.co/auth/v1/.well-known/jwks.json"

Write-Host ""
Write-Host "Supabase JWT signing diagnostic" -ForegroundColor Cyan
Write-Host "Project: $ProjectRef"
Write-Host ""

Write-Host "1) Public JWKS (what Supabase publishes for verification)" -ForegroundColor Yellow
Write-Host "   $JwksUrl"
try {
    $jwks = Invoke-RestMethod -Uri $JwksUrl
} catch {
    Write-Host "   Could not fetch JWKS: $_" -ForegroundColor Red
    exit 1
}

if (-not $jwks.keys -or $jwks.keys.Count -eq 0) {
    Write-Host "   No asymmetric keys in JWKS." -ForegroundColor Gray
    Write-Host "   => Project likely still uses Legacy JWT Secret (HS256) only." -ForegroundColor Green
    Write-Host "   => Use: Dashboard -> Settings -> JWT Keys -> Legacy JWT Secret" -ForegroundColor Green
    Write-Host "      Set SUPABASE_JWT_SECRET on Railway + Vercel (npm run auth:sync-jwt)." -ForegroundColor Green
} else {
    Write-Host "   Found $($jwks.keys.Count) public key(s):" -ForegroundColor Green
    foreach ($k in $jwks.keys) {
        Write-Host "     - alg=$($k.alg) kid=$($k.kid) kty=$($k.kty)" -ForegroundColor Gray
    }
    Write-Host ""
    Write-Host "   => Your project uses JWT Signing Keys (asymmetric)." -ForegroundColor Yellow
    Write-Host '   => The JSON you pasted is a PUBLIC verify key (ES256 JWKS), not SUPABASE_JWT_SECRET.' -ForegroundColor Yellow
}

Write-Host ""
Write-Host "2) Your access token (optional)" -ForegroundColor Yellow

function Decode-JwtHeader($token) {
    $parts = $token.Trim().Split(".")
    if ($parts.Count -lt 2) { throw "Not a JWT" }
    $b64 = $parts[0].Replace("-", "+").Replace("_", "/")
    switch ($b64.Length % 4) { 2 { $b64 += "==" }; 3 { $b64 += "=" } }
    $json = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($b64))
    return $json | ConvertFrom-Json
}

if (-not $AccessToken) {
    Write-Host "   No -AccessToken passed. After Google login, run:" -ForegroundColor Gray
    Write-Host '   .\scripts\diagnose-supabase-jwt.ps1 -AccessToken "PASTE_SESSION_ACCESS_TOKEN"' -ForegroundColor Gray
    Write-Host ""
    Write-Host "3) What to put in SUPABASE_JWT_SECRET (Railway / Vercel)" -ForegroundColor Yellow
    if ($jwks.keys -and $jwks.keys.Count -gt 0) {
        Write-Host "   For ES256 tokens: HS256 secret validation will FAIL on the backend." -ForegroundColor Red
        Write-Host "   Do NOT use: sb_secret_* / sb_publishable_* / JWKS public JSON." -ForegroundColor Red
        Write-Host ""
        Write-Host '   Option A - quick fix only if tokens are still HS256:' -ForegroundColor Cyan
        Write-Host "     Dashboard -> JWT Keys -> Legacy JWT Secret (long shared string)" -ForegroundColor Cyan
        Write-Host "     Only works when token header alg is HS256 (see step 2)." -ForegroundColor Cyan
        Write-Host ""
        Write-Host '   Option B - correct for ES256 signing keys:' -ForegroundColor Cyan
        Write-Host "     Update backend to verify via JWKS URL (no shared secret copy)." -ForegroundColor Cyan
        Write-Host "     PyJWT: PyJWKClient + algorithms ES256" -ForegroundColor Cyan
    } else {
        Write-Host "   Copy Legacy JWT Secret from JWT Keys into SUPABASE_JWT_SECRET." -ForegroundColor Green
    }
    exit 0
}

try {
    $hdr = Decode-JwtHeader $AccessToken
} catch {
    Write-Host "   Invalid token: $_" -ForegroundColor Red
    exit 1
}

Write-Host "   Token header:" -ForegroundColor Green
Write-Host "     alg  = $($hdr.alg)"
Write-Host "     kid  = $($hdr.kid)"
Write-Host "     typ  = $($hdr.typ)"

Write-Host ""
Write-Host "3) Recommendation for THIS token" -ForegroundColor Yellow

switch ($hdr.alg) {
    "HS256" {
        Write-Host "   Token is HS256 (legacy symmetric signing)." -ForegroundColor Green
        Write-Host "   => Copy Legacy JWT Secret from:" -ForegroundColor Green
        Write-Host "      https://supabase.com/dashboard/project/$ProjectRef/settings/jwt" -ForegroundColor Green
        Write-Host "   => Set SUPABASE_JWT_SECRET on Railway and run: npm run auth:sync-jwt" -ForegroundColor Green
    }
    "ES256" {
        Write-Host "   Token is ES256 (asymmetric signing keys)." -ForegroundColor Yellow
        Write-Host "   => SUPABASE_JWT_SECRET (HS256) will NOT validate this token." -ForegroundColor Red
        Write-Host "   => Backend must verify using JWKS:" -ForegroundColor Cyan
        Write-Host "      $JwksUrl" -ForegroundColor Cyan
        if ($hdr.kid) {
            $match = $jwks.keys | Where-Object { $_.kid -eq $hdr.kid }
            if ($match) {
                Write-Host "   => kid $($hdr.kid) matches a key in JWKS (good)." -ForegroundColor Green
            } else {
                Write-Host "   => kid $($hdr.kid) not in JWKS - key rotation or stale token." -ForegroundColor Red
            }
        }
    }
    "RS256" {
        Write-Host '   Token is RS256 - verify via JWKS (same as ES256 path).' -ForegroundColor Yellow
    }
    default {
        Write-Host "   Unknown alg $($hdr.alg) - check Supabase JWT Keys dashboard." -ForegroundColor Red
    }
}

Write-Host ""
