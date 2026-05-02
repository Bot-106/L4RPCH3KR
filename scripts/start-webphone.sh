#!/usr/bin/env bash
# start-webphone.sh - run on the MacBook
# Starts the web-phone Vite dev server pointing at the backend on 100.76.124.67
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"

log() { echo "[$(date +%H:%M:%S)] $*"; }

# Stop any existing Vite process on :3000
EXISTING=$(lsof -ti :3000 2>/dev/null || true)
if [[ -n "$EXISTING" ]]; then
    log "Stopping existing process on :3000 (pid $EXISTING)"
    kill "$EXISTING" 2>/dev/null || true
    sleep 1
fi

cd "$REPO/web-phone"

# Create .env if missing, pointing at the backend host over Tailscale
if [[ ! -f .env ]]; then
    log "No web-phone/.env found - creating one..."
    cat > .env <<'EOF'
VITE_API_BASE=http://100.76.124.67:8000
VITE_WS_BASE=ws://100.76.124.67:8000
EOF
    log "Created web-phone/.env - edit if your backend Tailscale IP differs."
fi

# Install deps if needed
if [[ ! -d node_modules ]]; then
    log "Installing dependencies..."
    npm install
fi

log "Starting web-phone at http://localhost:3000 -> backend at 100.76.124.67:8000"
npm run dev -- --host 127.0.0.1 --port 3000
