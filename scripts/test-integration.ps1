# Gravitre Integration Test (PowerShell)
# Usage: .\scripts\test-integration.ps1
#        $env:BACKEND_URL = "https://your-backend.up.railway.app"; .\scripts\test-integration.ps1

$ErrorActionPreference = "Stop"
$BackendUrl = if ($env:BACKEND_URL) { $env:BACKEND_URL.TrimEnd("/") } else { "http://localhost:8000" }

Write-Host "Testing backend at $BackendUrl"
Write-Host ""

# 1. Health check
Write-Host "-> Health check..."
try {
    $health = Invoke-RestMethod -Uri "$BackendUrl/health" -Method Get
    if ($health.status -eq "ok") {
        Write-Host "OK Backend healthy"
        $health | ConvertTo-Json -Compress | Write-Host
    } else {
        Write-Host "FAIL Unexpected health payload"
        exit 1
    }
} catch {
    Write-Host "FAIL Backend unreachable: $($_.Exception.Message)"
    exit 1
}

# 2. Auth check (expect 401)
Write-Host ""
Write-Host "-> Auth check..."
try {
    Invoke-WebRequest -Uri "$BackendUrl/api/assistant/chat" -Method POST `
        -ContentType "application/json" `
        -Body '{"messages":[],"org_id":"test"}' | Out-Null
    Write-Host "WARN Expected 401, got 2xx"
} catch {
    $code = [int]$_.Exception.Response.StatusCode
    if ($code -eq 401) {
        Write-Host "OK Auth gate working (got 401)"
    } else {
        Write-Host "WARN Expected 401, got $code"
    }
}

# 3. Killswitch check
Write-Host ""
Write-Host "-> Checking killswitch status..."
if ($null -eq $health.ai_disabled) {
    Write-Host "  (health endpoint does not report AI status - ok)"
} elseif ($health.ai_disabled) {
    Write-Host "WARN AI killswitch is ON"
} else {
    Write-Host "OK AI enabled"
}

Write-Host ""
Write-Host "Integration test complete."
Write-Host "To test with auth, POST to $BackendUrl/api/assistant/chat with Authorization: Bearer <jwt>"
