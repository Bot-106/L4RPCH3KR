"""
QR-code pairing flow.

Real mode:
  1. Open camera, scan QR code (pyzbar).
  2. POST the token to `{backend_rest}/pi/claim`.
  3. Persist the returned `pi_token` to pi_token_path.

Fake mode:
  - Skip QR scan; use LARPCHEKR_DEV_PAIR_TOKEN env var or a fixed test value.
  - Still writes to pi_token_path so the main process can read it.

Call `PairingManager.pair()` once during initial setup (before main loop).
After pairing succeeds, restart the main loop to pick up the new token.
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

import httpx

log = logging.getLogger(__name__)

PAIR_TIMEOUT = 120  # seconds to wait for a QR code before giving up
QR_POLL_INTERVAL = 0.1  # seconds between camera polls


class PairingManager:
    def __init__(
        self,
        backend_rest: str,
        pi_token_path: Path,
        device_id: str,
        fake: bool = False,
    ) -> None:
        self._rest = backend_rest.rstrip("/")
        self._token_path = pi_token_path
        self._device_id = device_id
        self._fake = fake

    def is_paired(self) -> bool:
        return self._token_path.exists() and self._token_path.stat().st_size > 0

    async def pair(self) -> str:
        """Run the pairing flow; returns the pi_token string."""
        if self._fake:
            return self._fake_pair()
        return await self._real_pair()

    def _fake_pair(self) -> str:
        token = os.environ.get("LARPCHEKR_DEV_PAIR_TOKEN", "dev-pair-token-0000")
        log.info("pairing: FAKE mode — using token %s", token)
        self._save_token(token)
        return token

    async def _real_pair(self) -> str:
        token = self._scan_qr()
        pi_token = await self._claim(token)
        self._save_token(pi_token)
        return pi_token

    def _scan_qr(self) -> str:
        try:
            import cv2  # type: ignore[import]
            from pyzbar import pyzbar  # type: ignore[import]
        except ImportError as exc:
            raise RuntimeError(f"QR dependencies missing: {exc}") from exc

        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            raise RuntimeError("Cannot open camera for QR scan")

        log.info("pairing: hold the partner phone QR up to the camera …")
        deadline = time.monotonic() + PAIR_TIMEOUT
        try:
            while time.monotonic() < deadline:
                ok, frame = cap.read()
                if not ok:
                    continue
                codes = pyzbar.decode(frame)
                for code in codes:
                    data = code.data.decode("utf-8", errors="replace")
                    log.info("pairing: QR scanned: %s", data)
                    # The QR payload is expected to be the raw pairing token
                    # (or a JSON blob with a "token" key)
                    try:
                        payload = json.loads(data)
                        return payload["token"]
                    except (json.JSONDecodeError, KeyError):
                        return data.strip()
                time.sleep(QR_POLL_INTERVAL)
        finally:
            cap.release()

        raise TimeoutError("QR scan timed out after %ds" % PAIR_TIMEOUT)

    async def _claim(self, token: str) -> str:
        """POST /pi/claim; returns the pi_token from the response."""
        url = f"{self._rest}/pi/claim"
        payload = {"token": token, "device_id": self._device_id}
        log.info("pairing: POSTing to %s", url)
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            body = resp.json()
            pi_token = body.get("pi_token") or body.get("token")
            if not pi_token:
                raise ValueError(f"Unexpected /pi/claim response: {body}")
            return pi_token

    def _save_token(self, token: str) -> None:
        self._token_path.parent.mkdir(parents=True, exist_ok=True)
        self._token_path.write_text(token)
        # Restrict to root-readable only on real Pi
        try:
            import stat
            self._token_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
        except Exception:
            pass
        log.info("pairing: token saved to %s", self._token_path)
