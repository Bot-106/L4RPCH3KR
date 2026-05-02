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

# Preview stream — lower res/quality for low latency
PREVIEW_WIDTH = 320
PREVIEW_HEIGHT = 240
PREVIEW_JPEG_QUALITY = 45

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


def _open_first_camera(cv2: object) -> object | None:
    """Probe low-index /dev/videoN nodes and return the first that can capture.

    Pi 5 ISP nodes live at video20+; USB/UVC cameras are typically below 10.
    """
    import glob

    candidates = sorted(
        (p for p in glob.glob("/dev/video*")
         if p[len("/dev/video"):].isdigit() and int(p[len("/dev/video"):]) < 20),
        key=lambda p: int(p[len("/dev/video"):]),
    )
    for path in candidates:
        cap = cv2.VideoCapture(path)  # type: ignore[union-attr]
        if cap.isOpened():
            ok, _ = cap.read()
            if ok:
                log.debug("camera: found capture device at %s", path)
                return cap
        cap.release()
    return None


class CameraCapture:
    def __init__(self, fake: bool = False) -> None:
        self._fake = fake
        self._cap = None
        if not fake:
            try:
                import glob
                import cv2  # type: ignore[import]
                self._cap = _open_first_camera(cv2)
                if self._cap is None or not self._cap.isOpened():
                    log.warning("camera: no capture device found — falling back to fake")
                    if self._cap:
                        self._cap.release()
                    self._cap = None
                    self._fake = True
                else:
                    # Lower capture resolution to reduce USB bandwidth and encode time
                    self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, PREVIEW_WIDTH)
                    self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, PREVIEW_HEIGHT)
                    # Minimal internal buffer so reads return the freshest frame
                    self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
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
            log.warning("camera: snapshot capture failed: %s", exc)
            return None

    def _capture_frame_sync(
        self,
        overlay_lines: list[tuple[str, tuple[int, int, int]]] | None = None,
    ) -> tuple[object | None, bytes | None]:
        """Capture one raw frame and encode a preview JPEG.

        overlay_lines: list of (text, bgr_color) to draw bottom-up on the frame.
        Returns (raw_frame, jpeg_bytes); either can be None on failure.
        """
        try:
            import cv2  # type: ignore[import]

            if self._fake:
                frame = _make_fake_frame()
            else:
                ok, frame = self._cap.read()  # type: ignore[union-attr]
                if not ok:
                    frame = _make_fake_frame()

            if overlay_lines:
                h = frame.shape[0]  # type: ignore[union-attr]
                for idx, (text, color) in enumerate(reversed(overlay_lines)):
                    y = h - 10 - idx * 18
                    cv2.putText(
                        frame, text, (6, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, color, 1,
                    )

            ok, buf = cv2.imencode(
                ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, PREVIEW_JPEG_QUALITY]
            )
            return frame, (bytes(buf) if ok else None)
        except Exception as exc:
            log.warning("camera: capture failed: %s", exc)
            return None, None

    async def preview_run(
        self,
        on_frame: FrameCallback,
        stop_event: asyncio.Event,
        fps: int = 5,
        get_overlay: "Callable[[], list[tuple[str, tuple[int, int, int]]]] | None" = None,
        face_queue: "asyncio.Queue | None" = None,
    ) -> None:
        """Capture at `fps`, push JPEG to on_frame and raw frame to face_queue."""
        interval = 1.0 / fps
        loop = asyncio.get_running_loop()
        log.info("camera: preview loop started (%d fps, fake=%s)", fps, self._fake)
        while not stop_event.is_set():
            lines = get_overlay() if get_overlay else None
            raw, jpeg = await loop.run_in_executor(
                None, self._capture_frame_sync, lines
            )
            if jpeg:
                on_frame(jpeg)
            if face_queue is not None and raw is not None:
                # Non-blocking put — drop stale frames rather than block the capture loop
                try:
                    face_queue.put_nowait(raw)
                except asyncio.QueueFull:
                    pass
            await asyncio.sleep(interval)

    def close(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass


class FaceDetector:
    """Debounced face-presence detector that drives session start/stop.

    Runs at the same cadence as preview_run (~5 fps). When a face is present
    for `start_frames` consecutive frames, calls `on_start`. When absent for
    `end_frames` consecutive frames (during an active session), calls `on_end`.
    """

    def __init__(self, fake: bool = False, start_frames: int = 3, end_frames: int = 15) -> None:
        self._fake = fake
        self._start_frames = start_frames
        self._end_frames = end_frames
        self._classifier = None
        if not fake:
            try:
                import cv2  # type: ignore[import]
                cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
                self._classifier = cv2.CascadeClassifier(cascade_path)
                if self._classifier.empty():
                    log.warning("face: haar cascade failed to load — detection disabled")
                    self._classifier = None
            except Exception as exc:
                log.warning("face: cv2 init failed (%s) — detection disabled", exc)

    def _detect_sync(self, frame: object) -> bool:
        """Return True if ≥1 face detected in the frame (blocking, call in executor)."""
        if self._classifier is None:
            return False
        try:
            import cv2  # type: ignore[import]
            import numpy as np  # type: ignore[import]
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)  # type: ignore[arg-type]
            faces = self._classifier.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
            )
            return len(faces) > 0
        except Exception:
            return False

    async def run(
        self,
        frame_queue: "asyncio.Queue",
        on_start: Callable[[], Awaitable[None]],
        on_end: Callable[[], Awaitable[None]],
        stop_event: asyncio.Event,
        on_face_update: "Callable[[bool], None] | None" = None,
    ) -> None:
        """Consume raw frames from frame_queue, debounce, fire on_start/on_end.

        on_face_update(detected) is called synchronously on every frame with
        the raw detection result (before debounce), so the preview overlay
        updates immediately.
        """
        loop = asyncio.get_running_loop()
        log.info("face: detector started (fake=%s, start=%d end=%d frames)", self._fake, self._start_frames, self._end_frames)

        if self._fake:
            await asyncio.sleep(2.0)
            log.info("face: FAKE mode — triggering session start")
            if on_face_update:
                on_face_update(True)
            await on_start()
            await stop_event.wait()
            return

        present_count = 0
        absent_count = 0
        session_active = False

        while not stop_event.is_set():
            try:
                frame = await asyncio.wait_for(frame_queue.get(), timeout=0.5)
            except (asyncio.TimeoutError, TimeoutError):
                continue

            face_found = await loop.run_in_executor(None, self._detect_sync, frame)

            if on_face_update:
                on_face_update(face_found)

            if face_found:
                present_count += 1
                absent_count = 0
                if not session_active and present_count >= self._start_frames:
                    session_active = True
                    present_count = 0
                    log.info("face: present %d frames — starting session", self._start_frames)
                    await on_start()
            else:
                absent_count += 1
                present_count = 0
                if session_active and absent_count >= self._end_frames:
                    session_active = False
                    absent_count = 0
                    log.info("face: absent %d frames — ending session", self._end_frames)
                    await on_end()
