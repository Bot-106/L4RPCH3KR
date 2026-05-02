#!/usr/bin/env bash
# start-backend.sh — run on the backend host (100.76.124.67)
# Kills any existing instances, then (re)starts:
#   MongoDB (Docker), FastAPI, web-phone Vite, dashboard Next.js
# Usage: ./scripts/start-backend.sh [--no-frontend]
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
NO_FRONTEND=0
[[ "${1:-}" == "--no-frontend" ]] && NO_FRONTEND=1

# ── helpers ───────────────────────────────────────────────────────────────────
log()  { echo "[$(date +%H:%M:%S)] $*"; }
kill_on_port() {
  local port=$1
  local pid; pid=$(lsof -ti :"$port" 2>/dev/null || true)
  [[ -n "$pid" ]] && { log "Stopping process on :$port (pid $pid)"; kill "$pid" 2>/dev/null || true; sleep 1; }
}

# ── tear down existing processes ──────────────────────────────────────────────
log "Stopping existing processes..."
pkill -f "uvicorn app.main:app" 2>/dev/null || true
pkill -f "vite"                 2>/dev/null || true
pkill -f "next"                 2>/dev/null || true
kill_on_port 8000
kill_on_port 3000
kill_on_port 3001
sleep 1

# ── MongoDB ───────────────────────────────────────────────────────────────────
log "Starting MongoDB..."
cd "$REPO"
docker compose -f infra/docker-compose.dev.yml up -d mongo
# Give Mongo a moment to be ready
for i in {1..10}; do
  mongosh --quiet --eval "db.runCommand({ping:1})" larpchekr &>/dev/null && break
  sleep 1
done
log "MongoDB ready."

# ── Backend (FastAPI) ─────────────────────────────────────────────────────────
log "Starting FastAPI on :8000..."
cd "$REPO/backend"
[[ ! -f .env ]] && { log "ERROR: backend/.env not found. Copy .env.example and fill in secrets."; exit 1; }
nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 \
  >> "$REPO/backend/uvicorn.log" 2>&1 &
UVICORN_PID=$!
log "FastAPI pid=$UVICORN_PID — tailing uvicorn.log for 5s..."
# Wait for it to be ready
for i in {1..10}; do
  curl -sf http://localhost:8000/healthz &>/dev/null && break
  sleep 0.5
done
curl -s http://localhost:8000/healthz | python3 -c "import sys,json; d=json.load(sys.stdin); print('  healthz:', d)"

# ── Frontend processes (skippable) ────────────────────────────────────────────
if [[ $NO_FRONTEND -eq 0 ]]; then
  log "Starting web-phone on :3000..."
  cd "$REPO/web-phone"
  [[ ! -f .env ]] && cp .env.example .env
  nohup npm run dev -- --host 0.0.0.0 --port 3000 \
    >> "$REPO/web-phone/vite.log" 2>&1 &
  log "web-phone pid=$! — log: web-phone/vite.log"

  log "Starting dashboard on :3001..."
  cd "$REPO/dashboard"
  [[ ! -f .env.local ]] && cp .env.example .env.local
  nohup npm run dev -- --port 3001 \
    >> "$REPO/dashboard/next.log" 2>&1 &
  log "dashboard pid=$! — log: dashboard/next.log"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "Services started:"
log "  FastAPI   → http://localhost:8000  (http://100.76.124.67:8000)"
[[ $NO_FRONTEND -eq 0 ]] && log "  web-phone → http://localhost:3000  (http://100.76.124.67:3000)"
[[ $NO_FRONTEND -eq 0 ]] && log "  dashboard → http://localhost:3001  (http://100.76.124.67:3001)"
log "  Logs:  backend/uvicorn.log  web-phone/vite.log  dashboard/next.log"
log "  Stop:  pkill -f 'uvicorn|vite|next'; docker compose -f infra/docker-compose.dev.yml down"
