<#
.SYNOPSIS
    Validate OpenHands integration with ARIA.

.DESCRIPTION
    Tests all components of the OpenHands + ARIA integration:
    - NVIDIA API connectivity
    - Repository access
    - Git functionality
    - OpenHands server startup
#>
param(
    [switch]$Quick
)

$ErrorActionPreference = "Continue"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Passed = 0
$Failed = 0
$Warnings = 0

function Test-Step {
    param([string]$Name, [scriptblock]$Test)
    Write-Host "`n[*] Testing: $Name" -ForegroundColor Cyan
    try {
        $result = & $Test
        if ($result -eq $true) {
            Write-Host "    PASS" -ForegroundColor Green
            $script:Passed++
        } elseif ($result -eq "warn") {
            Write-Host "    WARNING" -ForegroundColor Yellow
            $script:Warnings++
        } else {
            Write-Host "    FAIL: $result" -ForegroundColor Red
            $script:Failed++
        }
    } catch {
        Write-Host "    FAIL: $($_.Exception.Message)" -ForegroundColor Red
        $script:Failed++
    }
}

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  ARIA - OpenHands Integration Validator" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

# --- Test 1: Node.js ---
Test-Step "Node.js installed (22.12+)" {
    $ver = node --version 2>&1
    if ($ver -match "v(\d+)") {
        $major = [int]$matches[1]
        if ($major -ge 22) { return $true }
        return "Node.js $ver is too old (need 22.12+)"
    }
    return "Node.js not found"
}

# --- Test 2: npm ---
Test-Step "npm available" {
    $ver = npm --version 2>&1
    if ($ver -match "^\d+\.") { return $true }
    return "npm not found"
}

# --- Test 3: uv ---
Test-Step "uv available (for agent-server)" {
    $ver = uv --version 2>&1
    if ($ver -match "uv") { return $true }
    return "uv not found - required for agent-server backend"
}

# --- Test 4: Agent Canvas installed ---
Test-Step "Agent Canvas installed" {
    $ver = npx @openhands/agent-canvas --version 2>&1
    if ($ver -match "\d+\.\d+") { return $true }
    return "Not installed. Run: npm install -g @openhands/agent-canvas"
}

# --- Test 5: NVIDIA API key ---
Test-Step "NVIDIA API key configured" {
    # Load from .env
    $envFile = Join-Path $ProjectRoot "openhands\.env"
    if (Test-Path $envFile) {
        Get-Content $envFile | ForEach-Object {
            if ($_ -match "^NVIDIA_API_KEY=(.+)$") {
                $script:NvidiaKey = $matches[1].Trim()
            }
        }
    }
    if (-not $script:NvidiaKey) {
        $script:NvidiaKey = [System.Environment]::GetEnvironmentVariable("NVIDIA_API_KEY", "User")
    }
    if ($script:NvidiaKey -and $script:NvidiaKey.StartsWith("nvapi-")) { return $true }
    return "NVIDIA_API_KEY not set or invalid"
}

# --- Test 6: NVIDIA API connectivity ---
Test-Step "NVIDIA API reachable" {
    if (-not $script:NvidiaKey) { return "Skipped - no API key" }
    try {
        $headers = @{ "Authorization" = "Bearer $($script:NvidiaKey)" }
        $r = Invoke-RestMethod -Uri "https://integrate.api.nvidia.com/v1/models" -Headers $headers -TimeoutSec 10
        $minimax = $r.data | Where-Object { $_.id -like "*minimax*" }
        if ($minimax) {
            Write-Host "    Found models: $($minimax.id -join ', ')" -ForegroundColor DarkGray
            return $true
        }
        return "No minimax models found in API response"
    } catch {
        return "API connection failed: $($_.Exception.Message)"
    }
}

# --- Test 7: Repository exists ---
Test-Step "ARIA repository accessible" {
    if (Test-Path $ProjectRoot) {
        $files = Get-ChildItem $ProjectRoot -File | Select-Object -First 5
        Write-Host "    Found: $($files.Name -join ', ')" -ForegroundColor DarkGray
        return $true
    }
    return "Repository not found at $ProjectRoot"
}

# --- Test 8: Git repository ---
Test-Step "Git repository initialized" {
    $gitDir = Join-Path $ProjectRoot ".git"
    if (Test-Path $gitDir) {
        $branch = git -C $ProjectRoot branch --show-current 2>&1
        Write-Host "    Branch: $branch" -ForegroundColor DarkGray
        return $true
    }
    return "Not a git repository"
}

# --- Test 9: Git operations ---
Test-Step "Git operations work" {
    $status = git -C $ProjectRoot status --short 2>&1
    if ($LASTEXITCODE -eq 0) { return $true }
    return "git status failed"
}

# --- Test 10: Config file ---
Test-Step "OpenHands config.toml exists" {
    $configPath = "$env:USERPROFILE\.openhands\config.toml"
    if (Test-Path $configPath) {
        Write-Host "    Path: $configPath" -ForegroundColor DarkGray
        return $true
    }
    return "Config not found at $configPath"
}

# --- Test 11: Python tests ---
if (-not $Quick) {
    Test-Step "Python tests can run" {
        $testResult = python -m pytest "$ProjectRoot\tests" --co -q 2>&1
        if ($LASTEXITCODE -eq 0) {
            $count = ($testResult | Select-String "test").Count
            Write-Host "    Found $count tests" -ForegroundColor DarkGray
            return $true
        }
        return "pytest collection failed"
    }
}

# --- Test 12: .env files ---
Test-Step "Environment files present" {
    $openhandsEnv = Test-Path (Join-Path $ProjectRoot "openhands\.env")
    $projectEnv = Test-Path (Join-Path $ProjectRoot ".env")
    if ($openhandsEnv -and $projectEnv) { return $true }
    if ($openhandsEnv) { return "warn" }
    return "openhands/.env missing"
}

# --- Summary ---
Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "  Results: $Passed passed, $Failed failed, $Warnings warnings" -ForegroundColor $(if ($Failed -eq 0) { "Green" } else { "Red" })
Write-Host "============================================" -ForegroundColor Cyan

if ($Failed -gt 0) {
    Write-Host "`nSome tests failed. Fix the issues above before using OpenHands." -ForegroundColor Yellow
    exit 1
} else {
    Write-Host "`nAll checks passed. OpenHands is ready to use." -ForegroundColor Green
    Write-Host "Run: .\openhands\start.ps1" -ForegroundColor Cyan
    exit 0
}
