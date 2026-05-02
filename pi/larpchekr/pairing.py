from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable
from pathlib import Path

import httpx

log = logging.getLogger(__name__)

PAIR_TIMEOUT = 120
QR_POLL_INTERVAL = 0.1
FIRMWARE_VERSION = "0.1.0"


def _draw_overlay(
    frame: object,
    state: str,
    detail: str,
    elapsed: float | None = None,
    color: tuple[int, int, int] = (0, 220, 80),
) -> None:
    import cv2  # type: ignore[import]

    cv2.putText(frame, state, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
    cv2.putText(frame, detail, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
    if elapsed is not None:
        cv2.putText(
            frame,
            f"{elapsed:.0f}s",
            (10, frame.shape[0] - 10),  # type: ignore[union-attr]
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            color,
            1,
        )


def _encode_frame(frame: object) -> bytes | None:
    import cv2  # type: ignore[import]

    ok, buf = cv2.imencode(".jpg", frame)
    if not ok:
        return None
    return bytes(buf)


class PairingManager:
    def __init__(
        self,
        backend_rest: str,
        pi_token_path: Path,
        device_id: str,
        fake: bool = False,
    ) -> None:
        self._backend_rest = backend_rest
        self._pi_token_path = pi_token_path
        self._device_id = device_id
        self._fake = fake

    def is_paired(self) -> bool:
        return self._pi_token_path.exists()

    def pair(
        self,
        on_frame: Callable[[bytes], None] | None = None,
        on_state: Callable[[str, str], None] | None = None,
    ) -> str:
        if self._fake:
            return self._fake_pair(on_state)
        return self._real_pair(on_frame, on_state)

    def _fake_pair(self, on_state: Callable[[str, str], None] | None = None) -> str:
        token = os.environ.get("LARPCHEKR_DEV_PAIR_TOKEN", "dev-pi")
        log.info("pairing: fake mode — using token %r", token)
        if on_state:
            on_state("paired", f"token={token}")
        self._save_token(token)
        return token

    def _real_pair(
        self,
        on_frame: Callable[[bytes], None] | None = None,
        on_state: Callable[[str, str], None] | None = None,
    ) -> str:
        pair_token = self._scan_qr(on_frame, on_state)
        pi_token = self._claim(pair_token)
        self._save_token(pi_token)
        return pi_token

    def _scan_qr(
        self,
        on_frame: Callable[[bytes], None] | None = None,
        on_state: Callable[[str, str], None] | None = None,
    ) -> str:
        import cv2  # type: ignore[import]
        from pyzbar import pyzbar  # type: ignore[import]

        cap = cv2.VideoCapture(0)
        start = time.monotonic()
        deadline = start + PAIR_TIMEOUT
        try:
            while True:
                now = time.monotonic()
                if now >= deadline:
                    raise TimeoutError(f"QR scan timed out after {PAIR_TIMEOUT}s")
                elapsed = now - start
                remaining = deadline - now

                ok, frame = cap.read()
                if not ok:
                    time.sleep(QR_POLL_INTERVAL)
                    continue

                codes = pyzbar.decode(frame)
                for code in codes:
                    data = code.data.decode("utf-8", errors="replace").strip()
                    if data:
                        log.info("pairing: QR scanned — token=%r", data)
                        if on_state:
                            on_state("claimed", "QR detected")
                        return data

                remaining_str = f"{remaining:.0f}s remaining"
                _draw_overlay(frame, "Waiting for QR", remaining_str, elapsed)
                if on_frame:
                    jpeg = _encode_frame(frame)
                    if jpeg:
                        on_frame(jpeg)
                if on_state:
                    on_state("scanning", remaining_str)

                time.sleep(QR_POLL_INTERVAL)
        finally:
            cap.release()

    def _claim(self, pair_token: str) -> str:
        log.info("pairing: claiming with backend %s", self._backend_rest)
        resp = httpx.post(
            f"{self._backend_rest}/pi/claim",
            json={
                "pair_token": pair_token,
                "device_id": self._device_id,
                "firmware_version": FIRMWARE_VERSION,
            },
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()
        pi_token = data["pi_token"]
        log.info("pairing: claimed — user_id=%s", data.get("user_id"))
        return pi_token

    def _save_token(self, token: str) -> None:
        self._pi_token_path.parent.mkdir(parents=True, exist_ok=True)
        self._pi_token_path.write_text(token)
        log.info("pairing: token saved to %s", self._pi_token_path)
