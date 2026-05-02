# Tailscale networking

All devices run on a shared Tailscale mesh (tailnet). No port-forwarding or VPN configuration beyond `tailscale up` is required.

## Host / IP / port table

| Host | Tailscale IP | Services |
|------|-------------|----------|
| larpchekr-pi | `100.125.43.120` | Pi capture device (no inbound ports) |
| dev-laptop (backend host) | `100.76.124.67` | FastAPI `:8000`, web-phone Vite `:3000`, dashboard Next `:3001` |
| Attendee phone / any device | any tailnet IP | Browser only — no server |

> These IPs are stable for this tailnet. Update this table if devices re-enroll.

## Joining the tailnet

1. Install Tailscale: `curl -fsSL https://tailscale.com/install.sh | sh` (Linux/Pi) or download from tailscale.com (macOS/Windows).
2. Authenticate: `sudo tailscale up --auth-key <TAILSCALE_AUTH_KEY>` (headless/Pi) or `tailscale up` (interactive, opens browser).
3. Verify: `tailscale status` — all hosts should show `active`.

On the Pi you may also want: `sudo tailscale up --accept-routes --ssh` for headless SSH access.

## Verification commands

Run these to confirm the mesh is healthy before a demo.

### From the Pi
```bash
# Can the Pi reach the backend?
tailscale ping 100.76.124.67
curl http://100.76.124.67:8000/healthz

# WS smoke-test (requires wscat: npm install -g wscat)
wscat -c "ws://100.76.124.67:8000/ws/pi?token=REPLACE_WITH_PI_TOKEN"
# Should receive no error; send {"type":"pi_hello","id":"test","ts":"2026-01-01T00:00:00Z","data":{"device_id":"rpi-001","firmware_version":"0.1.0","battery_pct":100}}
```

### From any attendee device (browser or curl)
```bash
# Health check
curl http://100.76.124.67:8000/healthz

# Web-phone app
# Open http://100.76.124.67:3000 in a mobile browser

# WS smoke-test (from a machine with wscat)
wscat -c "ws://100.76.124.67:8000/ws/phone?token=REPLACE_WITH_USER_JWT"
```

### Backend host self-check
```bash
tailscale status          # all peers active
docker ps                 # mongo container up
curl http://localhost:8000/healthz
```

## Environment variables that must reference Tailscale IPs

| Subsystem | File | Variable | Value |
|-----------|------|----------|-------|
| web-phone | `.env` | `VITE_API_BASE` | `http://100.76.124.67:8000` |
| web-phone | `.env` | `VITE_WS_BASE` | `ws://100.76.124.67:8000` |
| dashboard | `.env.local` | `NEXT_PUBLIC_API_BASE` | `http://100.76.124.67:8000` |
| backend | `.env` | `MONGO_URL` | `mongodb://localhost:27017` (localhost OK — same host) |
| backend | `.env` | `CORS_ORIGINS` | `http://100.76.124.67:3000,http://100.76.124.67:3001` |
| pi | `.env` | `LARPCHEKR_BACKEND_WS` | `ws://100.76.124.67:8000/ws/pi` |
| pi | `.env` | `LARPCHEKR_BACKEND_REST` | `http://100.76.124.67:8000` |
