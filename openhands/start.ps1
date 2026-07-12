<#
.SYNOPSIS
    Start OpenHands Agent Canvas for the ARIA project.

.DESCRIPTION
    Launches OpenHands with NVIDIA API integration, pointed at the ARIA repository.
    The CTO remains responsible for planning; OpenHands is the execution engine.

.EXAMPLE
    .\start.ps1
    .\start.ps1 -Port 3000
    .\start.ps1 -BackendOnly
#>
param(
    [int]$Port = 8000,
    [switch]$BackendOnly,
    [switch]$FrontendOnly,
    [switch]$Public
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  ARIA - OpenHands Agent Canvas" -ForegroundColor Cyan
Write-Host "  Execution Engine for CTO Architecture" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Load environment variables from openhands/.env
$EnvFile = Join-Path $ScriptDir ".env"
if (Test-Path $EnvFile) {
    Write-Host "[*] Loading environment from $EnvFile" -ForegroundColor Gray
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match "^([^#][^=]+)=(.+)$") {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim()
            [System.Environment]::SetEnvironmentVariable($key, $value, "Process")
            Write-Host "    Set $key" -ForegroundColor DarkGray
        }
    }
} else {
    Write-Host "[!] Warning: .env file not found at $EnvFile" -ForegroundColor Yellow
}

# Also load from project root .env if it exists
$ProjectEnv = Join-Path $ProjectRoot ".env"
if (Test-Path $ProjectEnv) {
    Write-Host "[*] Loading additional env from $ProjectEnv" -ForegroundColor Gray
    Get-Content $ProjectEnv | ForEach-Object {
        if ($_ -match "^([^#][^=]+)=(.+)$") {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim()
            if (-not [System.Environment]::GetEnvironmentVariable($key, "Process")) {
                [System.Environment]::SetEnvironmentVariable($key, $value, "Process")
                Write-Host "    Set $key" -ForegroundColor DarkGray
            }
        }
    }
}

# Verify NVIDIA API key
$NvidiaKey = [System.Environment]::GetEnvironmentVariable("NVIDIA_API_KEY", "Process")
if (-not $NvidiaKey) {
    Write-Host "[!] ERROR: NVIDIA_API_KEY not set. Check your .env file." -ForegroundColor Red
    exit 1
}
Write-Host "[OK] NVIDIA API key loaded" -ForegroundColor Green

# Verify Node.js
$NodeVersion = node --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[!] ERROR: Node.js not found. Install Node.js 22.12+ first." -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Node.js $NodeVersion" -ForegroundColor Green

# Verify agent-canvas is installed
$AgentCanvas = npx @openhands/agent-canvas --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[!] ERROR: @openhands/agent-canvas not installed." -ForegroundColor Red
    Write-Host "    Run: npm install -g @openhands/agent-canvas" -ForegroundColor Yellow
    exit 1
}
Write-Host "[OK] Agent Canvas installed" -ForegroundColor Green

# Configure Git author for OpenHands commits
git config --global user.name "ARIA-CTO" 2>$null
git config --global user.email "aria-cto@aria-project.local" 2>$null

Write-Host ""
Write-Host "Configuration:" -ForegroundColor Cyan
Write-Host "  LLM:       openai/minimaxai/minimax-m2.7 (NVIDIA API)" -ForegroundColor White
Write-Host "  Workspace: $ProjectRoot" -ForegroundColor White
Write-Host "  Port:      $Port" -ForegroundColor White
Write-Host "  Mode:      $(if ($BackendOnly) {'Backend Only'} elseif ($FrontendOnly) {'Frontend Only'} else {'Full Stack'})" -ForegroundColor White
Write-Host ""

# Build arguments
$Args = @("--port", $Port.ToString())
if ($BackendOnly) { $Args += "--backend-only" }
if ($FrontendOnly) { $Args += "--frontend-only" }
if ($Public) { $Args += "--public" }

Write-Host "Starting OpenHands Agent Canvas..." -ForegroundColor Green
Write-Host "UI will be available at: http://localhost:$Port" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop" -ForegroundColor Gray
Write-Host ""

# Launch agent-canvas
try {
    & npx @openhands/agent-canvas @Args
} catch {
    Write-Host "[!] Error starting Agent Canvas: $_" -ForegroundColor Red
    exit 1
}
