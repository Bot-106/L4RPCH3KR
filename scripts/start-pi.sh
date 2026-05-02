#!/usr/bin/env bash
# start-pi.sh — run on the Raspberry Pi (100.125.43.120)
# Kills any existing larpchekr process, rotates the log, then restarts.
# Usage:
#   ./scripts/start-pi.sh               # real hardware
#   ./scripts/start-pi.sh --fake        # fake hardware (dev/test mode)
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
FAKE=0
[[ "${1:-}" == "--fake" ]] && FAKE=1

# ── helpers ───────────────────────────────────────────────────────────────────
log() { echo "[$(date +%H:%M:%S)] $*"; }

# ── load .env if present ─────────────────────────────────────────────────────
ENV_FILE="$REPO/pi/.env"
if [[ -f "$ENV_FILE" ]]; then
  set -o allexport
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +o allexport
  log "Loaded $ENV_FILE"
else
  log "No pi/.env found — using defaults from config.py and environment."
fi

# ── token path: default to writable location if /etc/larpchekr doesn't exist ─
if [[ -z "${LARPCHEKR_PI_TOKEN_PATH:-}" ]]; then
  if [[ -w /etc/larpchekr || -w /etc ]]; then
    mkdir -p /etc/larpchekr
    LARPCHEKR_PI_TOKEN_PATH=/etc/larpchekr/pi_token
  else
    mkdir -p /tmp/larpchekr
    LARPCHEKR_PI_TOKEN_PATH=/tmp/larpchekr/pi_token
    log "WARNING: /etc/larpchekr not writable — using $LARPCHEKR_PI_TOKEN_PATH"
  fi
fi
export LARPCHEKR_PI_TOKEN_PATH

# ── stop existing process(es) ─────────────────────────────────────────────────
# pkill may return 1 if nothing was running — that's fine.
if pkill -f "larpchekr.main" 2>/dev/null; then
  log "Stopped existing larpchekr process(es)."
  sleep 2   # give ALSA/camera time to release before reopen
fi
# Hard-kill anything that survived SIGTERM
pkill -9 -f "larpchekr.main" 2>/dev/null || true

# ── mic gain: 62% (21 dB) — 100% (30 dB) causes VAD false positives ──────────
# The USB camera mic noise floor at max gain fools webrtcvad into treating all
# ambient audio as speech, so the hangover never fires and Whisper never runs.
if amixer sset 'Mic' 10 &>/dev/null; then
  log "Mic capture gain → 10/16  (62%  21 dB)"
else
  log "WARNING: could not set mic gain (amixer not available or no Mic control)"
fi

# ── log rotation ──────────────────────────────────────────────────────────────
LOG_FILE="$REPO/pi/larpchekr.log"
if [[ -s "$LOG_FILE" ]]; then
  mv "$LOG_FILE" "${LOG_FILE%.log}.$(date +%Y%m%d-%H%M%S).log"
  log "Rotated previous log."
fi

# ── venv / deps ───────────────────────────────────────────────────────────────
cd "$REPO/pi"

if [[ ! -d .venv ]]; then
  log "No .venv found — creating virtual environment..."
  python3 -m venv .venv
fi

_MISSING=0
for _pkg in dotenv websockets faster_whisper; do
  if ! .venv/bin/python -c "import $_pkg" &>/dev/null 2>&1; then
    log "Missing package: $_pkg"
    _MISSING=1
  fi
done
if [[ $_MISSING -eq 1 ]]; then
  log "Installing / updating dependencies..."
  .venv/bin/pip install --quiet -r requirements.txt
fi
unset _pkg _MISSING

# ── start ─────────────────────────────────────────────────────────────────────
if [[ $FAKE -eq 1 ]]; then
  export LARPCHEKR_FAKE_HARDWARE=1
  log "Starting larpchekr in FAKE hardware mode (no GPIO, mic, or camera)..."
else
  export LARPCHEKR_FAKE_HARDWARE=0
  log "Starting larpchekr with real hardware..."
fi

nohup .venv/bin/python -m larpchekr.main > "$LOG_FILE" 2>&1 &
PID=$!

log "larpchekr pid=$PID — log: pi/larpchekr.log"
log "Tailing log for 8s to confirm startup..."
sleep 8
tail -25 "$LOG_FILE"

# ── summary ───────────────────────────────────────────────────────────────────
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "Pi process running (pid=$PID)"
log "  Token path: $LARPCHEKR_PI_TOKEN_PATH"
log "  Backend WS: ${LARPCHEKR_BACKEND_WS:-ws://100.76.124.67:8000/ws/pi}"
log "  Log:        pi/larpchekr.log"
log "  Stop:       pkill -f 'larpchekr.main'"
log "  Simulate button press (fake mode): kill -USR1 $PID"
