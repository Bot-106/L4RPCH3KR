#!/usr/bin/env bash
# setup-pi.sh — one-time hardware setup on the Raspberry Pi.
# Run this once after cloning / pulling major dependency changes.
# Safe to re-run.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
PI_DIR="$REPO/pi"

log() { echo "[$(date +%H:%M:%S)] $*"; }
ok()  { echo "[$(date +%H:%M:%S)] OK  $*"; }
err() { echo "[$(date +%H:%M:%S)] ERR $*" >&2; }

log "=== L4RPCH3KR Pi hardware setup ==="
log "Repo: $REPO"

# ── 1. System libraries ───────────────────────────────────────────────────────
log "Installing system libraries..."
sudo apt-get update -qq
sudo apt-get install -y --no-install-recommends \
  libportaudio2 \
  libasound2-dev \
  libzbar0 \
  libgl1 \
  v4l-utils \
  alsa-utils
ok "System libraries installed."

# ── 2. Python venv ────────────────────────────────────────────────────────────
cd "$PI_DIR"
if [[ ! -d .venv ]]; then
  log "Creating virtual environment..."
  python3 -m venv .venv
fi
ok "venv ready."

# ── 3. Pip packages ───────────────────────────────────────────────────────────
log "Installing Python dependencies (this may take a few minutes)..."
.venv/bin/pip install --upgrade pip --quiet
.venv/bin/pip install -r requirements.txt
ok "Python packages installed."

# ── 4. Verify critical imports ────────────────────────────────────────────────
log "Verifying imports..."
IMPORT_OK=1
for pkg in sounddevice webrtcvad cv2 faster_whisper pyzbar dotenv; do
  if .venv/bin/python -c "import $pkg" 2>/dev/null; then
    ok "  $pkg"
  else
    err "  $pkg — MISSING (install may have failed)"
    IMPORT_OK=0
  fi
done

if [[ $IMPORT_OK -eq 0 ]]; then
  err "Some imports failed. Check the errors above and retry."
  exit 1
fi

# ── 5. Verify camera ──────────────────────────────────────────────────────────
log "Checking camera devices..."
if ls /dev/video* 2>/dev/null | grep -qE '/dev/video[0-9]+'; then
  log "  Camera devices found:"
  v4l2-ctl --list-devices 2>/dev/null || ls /dev/video*
else
  err "  No /dev/video* devices found. Plug in a USB webcam or enable the Pi camera."
fi

# ── 6. Verify microphone ──────────────────────────────────────────────────────
log "Checking audio capture devices..."
if arecord -l 2>/dev/null | grep -q card; then
  log "  Audio capture devices found:"
  arecord -l 2>/dev/null || true
else
  err "  No capture devices found. Plug in a USB microphone."
fi

# ── 7. Update .env ────────────────────────────────────────────────────────────
ENV_FILE="$PI_DIR/.env"
if [[ ! -f "$ENV_FILE" ]]; then
  log "Creating pi/.env from example..."
  cp "$PI_DIR/.env.example" "$ENV_FILE"
fi

if grep -q "LARPCHEKR_FAKE_HARDWARE" "$ENV_FILE"; then
  sed -i 's/LARPCHEKR_FAKE_HARDWARE=.*/LARPCHEKR_FAKE_HARDWARE=0/' "$ENV_FILE"
  ok "Set LARPCHEKR_FAKE_HARDWARE=0 in pi/.env"
else
  echo "LARPCHEKR_FAKE_HARDWARE=0" >> "$ENV_FILE"
  ok "Added LARPCHEKR_FAKE_HARDWARE=0 to pi/.env"
fi

# ── 8. Token path ────────────────────────────────────────────────────────────
TOKEN_PATH=$(grep LARPCHEKR_PI_TOKEN_PATH "$ENV_FILE" 2>/dev/null | cut -d= -f2 || echo "/tmp/larpchekr/pi_token")
if [[ -f "$TOKEN_PATH" ]]; then
  ok "Pi token already exists at $TOKEN_PATH"
else
  log "No Pi token at $TOKEN_PATH — you will need to pair before first use."
  log "  Option A: run scripts/start-pi.sh and hold the Pi camera up to the phone QR code."
  log "  Option B (dev): mkdir -p \$(dirname $TOKEN_PATH) && echo 'dev-pi' > $TOKEN_PATH"
fi

log ""
log "=== Setup complete ==="
log "Start with:  cd $REPO && ./scripts/start-pi.sh"
log "Fake mode:   ./scripts/start-pi.sh --fake"
