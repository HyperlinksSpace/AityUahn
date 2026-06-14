# Verify local AityUahn forge and optional cloud SaaS.
param(
    [string]$ForgeUrl = "http://127.0.0.1:8765",
    [string]$SaasUrl = ""
)

$ErrorActionPreference = "Stop"
$fail = 0

Write-Host "=== AityUahn setup verification ==="
Write-Host "Forge URL: $ForgeUrl"

try {
    $ver = & aityuahn version 2>$null
    Write-Host "CLI: $ver"
} catch {
    Write-Host "CLI: not in PATH (activate venv or reinstall)"
    $fail++
}

$forgeHealth = "$ForgeUrl/api/health"
try {
    $body = Invoke-RestMethod -Uri $forgeHealth -Headers @{ Accept = "application/json" }
    Write-Host "Forge health: OK"
    $body | ConvertTo-Json -Compress
    if ($body.role -ne "forge") {
        Write-Host "ERROR: expected role=forge at $ForgeUrl"
        $fail++
    }
} catch {
    Write-Host "ERROR: forge not reachable at $forgeHealth"
    Write-Host "       Start: aityuahn serve --demo"
    $fail++
}

if ($SaasUrl) {
    $SaasUrl = $SaasUrl.TrimEnd("/")
    $saasHealth = "$SaasUrl/api/health"
    Write-Host ""
    Write-Host "SaaS URL: $SaasUrl"
    try {
        $body = Invoke-RestMethod -Uri $saasHealth -Headers @{ Accept = "application/json" }
        $body | ConvertTo-Json -Compress
        if ($body.ok -eq $false) {
            Write-Host "ERROR: SaaS health ok=false — check Vercel env"
            $fail++
        }
    } catch {
        Write-Host "ERROR: SaaS not reachable at $saasHealth"
        $fail++
    }
}

Write-Host ""
if ($fail -eq 0) {
    Write-Host "All checks passed."
    exit 0
}
Write-Host "$fail check(s) failed."
exit 1
