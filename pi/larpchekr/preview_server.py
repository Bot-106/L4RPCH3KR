"""
MJPEG preview server — diagnostic display.

Serves a live camera feed + state overlay over HTTP (viewable over Tailscale).

  http://100.125.43.120:8080        -> HTML page with embedded stream
  http://100.125.43.120:8080/stream -> raw MJPEG (VLC, curl, etc.)

Frames are pushed by CameraCapture.preview_run() via update_frame().
State text is set via set_state() — shown as an overlay on every frame,
and as a generated status JPEG when no camera frame has arrived yet.
"""
from __future__ import annotations

import asyncio
import logging
import time
from asyncio import StreamReader, StreamWriter
from collections.abc import Callable

log = logging.getLogger(__name__)

_INDEX_HTML = b"""\
<!doctype html>
<html>
<head>
  <title>L4RPCH3KR Pi Diagnostic</title>
  <style>
    * { box-sizing: border-box; }
    body {
      background: #0d0d0d; color: #ccc; font-family: monospace;
      display: flex; flex-direction: column; align-items: center;
      justify-content: center; min-height: 100vh; margin: 0; gap: .75rem;
    }
    h1  { font-size: .8rem; letter-spacing: .2em; text-transform: uppercase; color: #555; margin: 0; }
    img { max-width: min(640px, 100vw); border: 1px solid #222; display: block; }
    p   { font-size: .7rem; color: #444; margin: 0; }
  </style>
</head>
<body>
  <h1>L4RPCH3KR &mdash; Pi Diagnostic</h1>
  <img src="/stream" alt="diagnostic feed">
  <p>Live MJPEG &bull; <a href="/stream" style="color:#444">/stream</a></p>
</body>
</html>
"""


def _make_status_jpeg(state: str, detail: str, elapsed: float | None = None) -> bytes | None:
    """Generate a plain status frame using cv2/numpy when no camera frame is available."""
    try:
        import cv2
        import numpy as np

        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        # dim background grid for depth
        for y in range(0, 240, 20):
            cv2.line(frame, (0, y), (320, y), (20, 20, 20), 1)
        for x in range(0, 320, 20):
            cv2.line(frame, (x, 0), (x, 240), (20, 20, 20), 1)

        color = (0, 220, 80)
        cv2.putText(frame, state, (10, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)
        if detail:
            # word-wrap naively at 36 chars
            words, line, lines = detail.split(), "", []
            for w in words:
                if len(line) + len(w) + 1 > 36:
                    lines.append(line)
                    line = w
                else:
                    line = (line + " " + w).strip()
            if line:
                lines.append(line)
            for i, l in enumerate(lines[:3]):
                cv2.putText(frame, l, (10, 138 + i * 18), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (160, 160, 160), 1)
        if elapsed is not None:
            cv2.putText(frame, f"{elapsed:.0f}s", (270, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (80, 80, 80), 1)

        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        return bytes(buf)
    except Exception as exc:
        log.debug("preview: status JPEG generation failed: %s", exc)
        return None


def add_overlay(frame: object, state: str, detail: str = "") -> object:
    """
    Overlay state text onto a cv2 BGR frame in-place.
    Call from camera/pairing code before encoding to JPEG.
    """
    try:
        import cv2

        h, w = frame.shape[:2]  # type: ignore[union-attr]
        # semi-transparent dark band at top
        band = frame.copy()  # type: ignore[union-attr]
        cv2.rectangle(band, (0, 0), (w, 52), (0, 0, 0), -1)
        import cv2 as _cv2
        _cv2.addWeighted(band, 0.65, frame, 0.35, 0, frame)  # type: ignore[call-overload]

        color = (0, 220, 80)
        cv2.putText(frame, state, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        if detail:
            cv2.putText(frame, detail[:55], (8, 44), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (180, 180, 180), 1)
    except Exception:
        pass
    return frame


class PreviewServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 8080) -> None:
        self._host = host
        self._port = port
        self._latest_jpeg: bytes | None = None
        self._queues: list[asyncio.Queue[bytes | None]] = []
        self._state = "starting"
        self._detail = ""
        self._state_since = time.monotonic()

    def set_state(self, state: str, detail: str = "") -> None:
        """Update the diagnostic state label shown on every frame."""
        if state != self._state or detail != self._detail:
            log.info("preview: state -> %s  %s", state, detail)
        self._state = state
        self._detail = detail
        self._state_since = time.monotonic()
        # push a status frame immediately so watchers see the change right away
        jpeg = _make_status_jpeg(state, detail, elapsed=0.0)
        if jpeg:
            self._broadcast_sync(jpeg)

    def update_frame(self, jpeg_bytes: bytes) -> None:
        """Called by the camera capture loop with a fresh JPEG frame."""
        self._latest_jpeg = jpeg_bytes
        self._broadcast_sync(jpeg_bytes)

    def _broadcast_sync(self, jpeg_bytes: bytes) -> None:
        for q in list(self._queues):
            try:
                q.put_nowait(jpeg_bytes)
            except asyncio.QueueFull:
                pass

    async def _status_tick(self, stop_event: asyncio.Event) -> None:
        """
        Periodically push a generated status JPEG when no camera frames arrive.
        This keeps the browser stream alive during pairing / boot.
        """
        while not stop_event.is_set():
            await asyncio.sleep(0.5)
            if self._queues and self._latest_jpeg is None:
                elapsed = time.monotonic() - self._state_since
                jpeg = _make_status_jpeg(self._state, self._detail, elapsed)
                if jpeg:
                    self._broadcast_sync(jpeg)

    async def _handle(self, reader: StreamReader, writer: StreamWriter) -> None:
        try:
            request_line = await asyncio.wait_for(reader.readline(), timeout=5)
            if not request_line:
                return
            parts = request_line.decode(errors="replace").split()
            path = parts[1] if len(parts) >= 2 else "/"
            while True:
                line = await asyncio.wait_for(reader.readline(), timeout=3)
                if line in (b"\r\n", b"\n", b""):
                    break

            if "/stream" in path:
                await self._handle_stream(writer)
            else:
                writer.write(
                    b"HTTP/1.1 200 OK\r\n"
                    b"Content-Type: text/html; charset=utf-8\r\n"
                    b"Content-Length: " + str(len(_INDEX_HTML)).encode() + b"\r\n"
                    b"\r\n" + _INDEX_HTML
                )
                await writer.drain()
        except Exception:
            pass
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _handle_stream(self, writer: StreamWriter) -> None:
        writer.write(
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: multipart/x-mixed-replace; boundary=frame\r\n"
            b"Cache-Control: no-cache\r\n"
            b"Connection: keep-alive\r\n"
            b"\r\n"
        )
        await writer.drain()

        q: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=2)
        self._queues.append(q)

        # send latest frame immediately so the browser isn't blank on load
        seed = self._latest_jpeg or _make_status_jpeg(self._state, self._detail, 0.0)
        if seed:
            await _write_frame(writer, seed)

        try:
            while True:
                jpeg = await asyncio.wait_for(q.get(), timeout=30)
                if jpeg is None:
                    break
                await _write_frame(writer, jpeg)
        except (asyncio.TimeoutError, ConnectionResetError, BrokenPipeError, OSError):
            pass
        finally:
            if q in self._queues:
                self._queues.remove(q)

    async def run(self, stop_event: asyncio.Event) -> None:
        server = await asyncio.start_server(self._handle, self._host, self._port)
        log.info("preview: http://%s:%d  (MJPEG at /stream)", self._host, self._port)
        asyncio.create_task(self._status_tick(stop_event), name="preview_status_tick")
        async with server:
            await stop_event.wait()
        for q in list(self._queues):
            try:
                q.put_nowait(None)
            except asyncio.QueueFull:
                pass
        log.info("preview: stopped")


async def _write_frame(writer: StreamWriter, jpeg: bytes) -> None:
    writer.write(
        b"--frame\r\n"
        b"Content-Type: image/jpeg\r\n"
        b"Content-Length: " + str(len(jpeg)).encode() + b"\r\n"
        b"\r\n" + jpeg + b"\r\n"
    )
    await writer.drain()


FrameCallback = Callable[[bytes], None]
