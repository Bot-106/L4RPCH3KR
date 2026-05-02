# start-backend.ps1 - run on the backend host (Windows, 100.76.124.67)
# Kills any existing instances, then (re)starts:
#   MongoDB (Docker), FastAPI, dashboard Next.js
# Usage:
#   .\scripts\start-backend.ps1
#   .\scripts\start-backend.ps1 -NoDashboard
param(
    [switch]$NoDashboard
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$REPO = Split-Path -Parent $PSScriptRoot

function Log($msg) { Write-Host "[$(Get-Date -Format 'HH:mm:ss')] $msg" }

function Kill-OnPort($port) {
    $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($conn) {
        $pid_ = $conn.OwningProcess | Select-Object -First 1
        Log "Stopping process on :$port (pid $pid_)"
        Stop-Process -Id $pid_ -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
    }
}

# --- stop existing processes ---
Log "Stopping existing processes..."
Get-Process -Name "uvicorn" -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process -Name "node"    -ErrorAction SilentlyContinue | Stop-Process -Force
Kill-OnPort 8000
Kill-OnPort 3001
Start-Sleep -Seconds 1

# --- MongoDB (Docker) ---
Log "Starting MongoDB..."
Set-Location $REPO
docker compose -f infra/docker-compose.dev.yml up -d mongo

$mongoReady = $false
for ($i = 0; $i -lt 10; $i++) {
    try {
        $containerId = docker compose -f infra/docker-compose.dev.yml ps -q mongo 2>$null
        $result = docker exec $containerId mongosh --quiet --eval "db.runCommand({ping:1})" 2>$null
        if ($result -match '"ok"') { $mongoReady = $true; break }
    } catch {}
    Start-Sleep -Seconds 1
}
if ($mongoReady) {
    Log "MongoDB ready."
} else {
    Log "WARNING: Could not confirm MongoDB is ready - continuing anyway."
}

# --- Backend (FastAPI) ---
Log "Starting FastAPI on :8000..."
Set-Location "$REPO\backend"

if (-not (Test-Path ".env")) {
    Log "ERROR: backend\.env not found. Copy .env.example and fill in secrets."
    exit 1
}

if (-not (Test-Path ".venv")) {
    Log "No .venv found - creating virtual environment..."
    python -m venv .venv
}

& ".venv\Scripts\python.exe" -c "import uvicorn, anthropic" 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Log "Installing backend dependencies..."
    & ".venv\Scripts\pip.exe" install -r requirements.txt
}

$uvicornLog = "$REPO\backend\uvicorn.log"
$uvicornProc = Start-Process -FilePath "cmd.exe" `
    -ArgumentList "/c", ".venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8000 >> `"$uvicornLog`" 2>&1" `
    -WorkingDirectory "$REPO\backend" `
    -PassThru -WindowStyle Hidden
Log "FastAPI pid=$($uvicornProc.Id) - waiting for :8000..."

$backendReady = $false
for ($i = 0; $i -lt 20; $i++) {
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:8000/healthz" -UseBasicParsing -TimeoutSec 1
        if ($resp.StatusCode -eq 200) { $backendReady = $true; break }
    } catch {}
    Start-Sleep -Milliseconds 500
}
if ($backendReady) {
    $healthz = Invoke-RestMethod -Uri "http://localhost:8000/healthz"
    Log "  healthz: ok=$($healthz.ok) mongo=$($healthz.mongo) version=$($healthz.version)"
} else {
    Log "WARNING: Backend did not respond within 10s - check uvicorn.log"
}

# --- Dashboard (Next.js) ---
if (-not $NoDashboard) {
    Log "Starting dashboard on :3001..."
    Set-Location "$REPO\dashboard"

    if (-not (Test-Path ".env.local")) {
        Log "No dashboard\.env.local found - copying from .env.example..."
        Copy-Item ".env.example" ".env.local"
    }
    if (-not (Test-Path "node_modules")) {
        Log "Installing dashboard deps..."
        npm install --silent
    }

    $dashLog = "$REPO\dashboard\next.log"
    $dashProc = Start-Process -FilePath "cmd.exe" `
        -ArgumentList "/c", "npm.cmd run dev -- --port 3001 >> `"$dashLog`" 2>&1" `
        -WorkingDirectory "$REPO\dashboard" `
        -PassThru -WindowStyle Hidden
    Log "dashboard pid=$($dashProc.Id) - log: dashboard\next.log"
}

# --- Summary ---
Log "========================================"
Log "Services started:"
Log "  FastAPI   -> http://localhost:8000  (http://100.76.124.67:8000)"
if (-not $NoDashboard) {
    Log "  dashboard -> http://localhost:3001  (http://100.76.124.67:3001)"
}
Log "  Logs:  backend\uvicorn.log  dashboard\next.log"
Log "  Stop:  Get-Process uvicorn,node | Stop-Process -Force"
Log "         docker compose -f infra\docker-compose.dev.yml down"
