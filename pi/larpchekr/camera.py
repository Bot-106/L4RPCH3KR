"""
Camera frame snapshot.

Real mode: OpenCV USB camera, captures one JPEG every 10s, max 640×480.
Fake mode: generates a solid-colour JPEG via numpy + cv2.

Emits a `frame_snapshot` envelope every SNAPSHOT_INTERVAL_S seconds
while a session is active.
"""
from __future__ import annotations

import asyncio
import base64
import logging
import time
from collections.abc import Awaitable, Callable
from datetime import UTC

log = logging.getLogger(__name__)

SNAPSHOT_INTERVAL_S = 10
MAX_WIDTH = 640
MAX_HEIGHT = 480
JPEG_QUALITY = 75

SendEnvelopeFn = Callable[[dict], Awaitable[None]]
FrameCallback = Callable[[bytes], None]


def _make_snapshot_envelope(
    image_b64: str, width: int, height: int, session_id: str | None
) -> dict:
    import uuid
    from datetime import datetime
    return {
        "id": uuid.uuid4().hex,
        "type": "frame_snapshot",
        "ts": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "session_id": session_id,
        "data": {
            "image_b64": image_b64,
            "width": width,
            "height": height,
        },
    }


def _encode_jpeg(frame: object) -> tuple[bytes, int, int]:
    """Encode a numpy BGR frame to JPEG bytes; resize if needed."""
    import cv2  # type: ignore[import]

    h, w = frame.shape[:2]  # type: ignore[union-attr]
    if w > MAX_WIDTH or h > MAX_HEIGHT:
        scale = min(MAX_WIDTH / w, MAX_HEIGHT / h)
        new_w, new_h = int(w * scale), int(h * scale)
        frame = cv2.resize(frame, (new_w, new_h))  # type: ignore[call-overload]
        h, w = new_h, new_w
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    if not ok:
        raise RuntimeError("JPEG encode failed")
    return bytes(buf), w, h


def _make_fake_frame() -> object:
    """Generate a test frame: a gradient image with timestamp text."""
    import cv2  # type: ignore[import]
    import numpy as np  # type: ignore[import]

    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    # Blue gradient
    for col in range(320):
        frame[:, col, 0] = int(col * 255 / 320)
    frame[:, :, 1] = 80
    ts_text = f"FAKE {time.strftime('%H:%M:%S')}"
    cv2.putText(frame, ts_text, (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
    return frame


class CameraCapture:
    def __init__(self, fake: bool = False) -> None:
        self._fake = fake
        self._cap = None
        if not fake:
            try:
                import cv2  # type: ignore[import]
                self._cap = cv2.VideoCapture(0)
                if not self._cap.isOpened():
                    log.warning("camera: no camera device — falling back to fake")
                    self._cap = None
                    self._fake = True
            except Exception as exc:
                log.warning("camera: opencv init failed (%s) — falling back to fake", exc)
                self._fake = True

    async def snapshot(self) -> tuple[str, int, int]:
        """Return (image_b64, width, height)."""
        if self._fake:
            frame = _make_fake_frame()
        else:
            ok, frame = self._cap.read()  # type: ignore[union-attr]
            if not ok:
                log.warning("camera: read failed — using fake frame")
                frame = _make_fake_frame()

        jpeg_bytes, w, h = _encode_jpeg(frame)
        return base64.b64encode(jpeg_bytes).decode(), w, h

    async def run(
        self,
        send_envelope: SendEnvelopeFn,
        get_session_id: Callable[[], str | None],
        stop_event: asyncio.Event,
    ) -> None:
        log.info("camera: started (fake=%s, interval=%ds)", self._fake, SNAPSHOT_INTERVAL_S)
        while not stop_event.is_set():
            await asyncio.sleep(SNAPSHOT_INTERVAL_S)
            session_id = get_session_id()
            if session_id is None:
                continue
            try:
                image_b64, w, h = await self.snapshot()
                env = _make_snapshot_envelope(image_b64, w, h, session_id)
                await send_envelope(env)
                log.debug("camera: snapshot sent (%dx%d)", w, h)
            except Exception as exc:
                log.error("camera: snapshot error: %s", exc)

    def _capture_jpeg_sync(self) -> bytes | None:
        """Blocking capture — call via run_in_executor from async context."""
        try:
            if self._fake:
                frame = _make_fake_frame()
            else:
                ok, frame = self._cap.read()  # type: ignore[union-attr]
                if not ok:
                    frame = _make_fake_frame()
            jpeg_bytes, _, _ = _encode_jpeg(frame)
            return jpeg_bytes
        except Exception as exc:
            log.warning("camera: preview capture failed: %s", exc)
            return None

    async def preview_run(
        self,
        on_frame: FrameCallback,
        stop_event: asyncio.Event,
        fps: int = 2,
    ) -> None:
        """Capture continuously at `fps` and push JPEG bytes to on_frame."""
        interval = 1.0 / fps
        loop = asyncio.get_running_loop()
        log.info("camera: preview loop started (%d fps, fake=%s)", fps, self._fake)
        while not stop_event.is_set():
            jpeg = await loop.run_in_executor(None, self._capture_jpeg_sync)
            if jpeg:
                on_frame(jpeg)
            await asyncio.sleep(interval)

    def close(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
