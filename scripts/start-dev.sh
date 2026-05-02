#!/usr/bin/env bash
# start-dev.sh — run on your local macOS dev machine
# Starts everything pointing to localhost (no Tailscale required).
# Usage:
#   ./scripts/start-dev.sh               # full stack
#   ./scripts/start-dev.sh --backend     # backend + mongo only
#   ./scripts/start-dev.sh --frontend    # web-phone + dashboard only (backend must already be running)
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
MODE="full"
[[ "${1:-}" == "--backend"  ]] && MODE="backend"
[[ "${1:-}" == "--frontend" ]] && MODE="frontend"

# ── helpers ───────────────────────────────────────────────────────────────────
log()  { echo "[$(date +%H:%M:%S)] $*"; }
kill_on_port() {
  local port=$1
  local pid; pid=$(lsof -ti :"$port" 2>/dev/null || true)
  [[ -n "$pid" ]] && { log "Stopping process on :$port (pid $pid)"; kill "$pid" 2>/dev/null || true; sleep 1; }
}

# ── stop existing processes ───────────────────────────────────────────────────
log "Stopping existing processes..."
pkill -f "uvicorn app.main:app" 2>/dev/null || true
pkill -f "vite"                 2>/dev/null || true
pkill -f "next"                 2>/dev/null || true
kill_on_port 8000
kill_on_port 3000
kill_on_port 3001
sleep 1

# ── MongoDB ───────────────────────────────────────────────────────────────────
if [[ "$MODE" != "frontend" ]]; then
  log "Starting MongoDB..."
  if command -v docker &>/dev/null; then
    cd "$REPO"
    docker compose -f infra/docker-compose.dev.yml up -d mongo
  elif command -v brew &>/dev/null && brew list mongodb-community &>/dev/null 2>&1; then
    brew services start mongodb-community
  elif command -v mongod &>/dev/null; then
    mkdir -p /tmp/mongodata
    mongod --dbpath /tmp/mongodata --fork --logpath /tmp/mongod.log --quiet
  else
    log "ERROR: No MongoDB found. Install Docker Desktop or: brew install mongodb-community"
    exit 1
  fi
  # Wait for Mongo to be ready
  for i in {1..10}; do
    mongosh --quiet --eval "db.runCommand({ping:1})" larpchekr &>/dev/null 2>&1 && break || true
    sleep 1
  done
  log "MongoDB ready."
fi

# ── Backend ───────────────────────────────────────────────────────────────────
if [[ "$MODE" != "frontend" ]]; then
  log "Starting FastAPI on :8000 (localhost)..."
  cd "$REPO/backend"

  # Create a local dev .env if none exists, overriding Tailscale IPs → localhost
  if [[ ! -f .env ]]; then
    log "No backend/.env found — creating a localhost dev copy from .env.example..."
    sed \
      -e 's|MONGO_URL=.*|MONGO_URL=mongodb://localhost:27017|' \
      -e 's|CORS_ORIGINS=.*|CORS_ORIGINS=http://localhost:3000,http://localhost:3001|' \
      -e 's|FIXTURE_MODE=.*|FIXTURE_MODE=true|' \
      .env.example > .env
    log "  backend/.env created with FIXTURE_MODE=true. Fill in JWT_SECRET + OPENAI_API_KEY."
  fi

  [[ ! -d .venv ]] && { log "ERROR: backend/.venv not found. Run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"; exit 1; }

  nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload \
    >> "$REPO/backend/uvicorn.log" 2>&1 &
  UVICORN_PID=$!
  log "FastAPI pid=$UVICORN_PID — waiting for :8000..."
  for i in {1..20}; do
    curl -sf http://localhost:8000/healthz &>/dev/null && break || true
    sleep 0.5
  done
  HEALTHZ=$(curl -s http://localhost:8000/healthz)
  log "  healthz: $HEALTHZ"

  # Seed DB (idempotent — safe to run every time)
  log "Seeding database (idempotent)..."
  .venv/bin/python -m app.scripts.init_db  2>&1 | tail -2
  .venv/bin/python -m app.scripts.seed_event 2>&1 | tail -4
fi

# ── Frontend (web-phone + dashboard) ─────────────────────────────────────────
if [[ "$MODE" != "backend" ]]; then
  log "Starting web-phone on :3000..."
  cd "$REPO/web-phone"
  if [[ ! -f .env ]]; then
    log "No web-phone/.env found — creating localhost dev copy..."
    sed \
      -e 's|VITE_API_BASE=.*|VITE_API_BASE=http://localhost:8000|' \
      -e 's|VITE_WS_BASE=.*|VITE_WS_BASE=ws://localhost:8000|' \
      .env.example > .env
  fi
  [[ ! -d node_modules ]] && { log "Installing web-phone deps..."; npm install --silent; }
  nohup npm run dev -- --host 127.0.0.1 --port 3000 \
    >> "$REPO/web-phone/vite.log" 2>&1 &
  log "web-phone pid=$! — log: web-phone/vite.log"

  log "Starting dashboard on :3001..."
  cd "$REPO/dashboard"
  if [[ ! -f .env.local ]]; then
    log "No dashboard/.env.local found — creating localhost dev copy..."
    sed \
      -e 's|NEXT_PUBLIC_API_BASE=.*|NEXT_PUBLIC_API_BASE=http://localhost:8000|' \
      -e 's|DASHBOARD_BASE_URL=.*|DASHBOARD_BASE_URL=http://localhost:3001|' \
      .env.example > .env.local
  fi
  [[ ! -d node_modules ]] && { log "Installing dashboard deps..."; npm install --silent; }
  nohup npm run dev -- --port 3001 \
    >> "$REPO/dashboard/next.log" 2>&1 &
  log "dashboard pid=$! — log: dashboard/next.log"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "Dev stack running:"
[[ "$MODE" != "frontend" ]] && log "  FastAPI   → http://localhost:8000/healthz"
[[ "$MODE" != "backend"  ]] && log "  web-phone → http://localhost:3000"
[[ "$MODE" != "backend"  ]] && log "  dashboard → http://localhost:3001"
log "  Logs:  backend/uvicorn.log  web-phone/vite.log  dashboard/next.log"
log "  Stop:  pkill -f 'uvicorn|vite|next'"
log ""
log "Pi (fake hardware, pointing to localhost):"
log "  LARPCHEKR_FAKE_HARDWARE=1 LARPCHEKR_PI_TOKEN_PATH=/tmp/larpchekr/pi_token \\"
log "    LARPCHEKR_BACKEND_WS=ws://localhost:8000/ws/pi \\"
log "    LARPCHEKR_BACKEND_REST=http://localhost:8000 \\"
log "    pi/.venv/bin/python -m larpchekr.main"
