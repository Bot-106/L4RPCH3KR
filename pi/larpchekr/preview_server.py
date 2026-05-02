"""
MJPEG preview server.

Serves a live camera feed over HTTP so you can watch it in a browser over Tailscale.

  http://100.125.43.120:8080        -> HTML page with embedded stream
  http://100.125.43.120:8080/stream -> raw MJPEG stream (for VLC, curl, etc.)

Frames are pushed in by CameraCapture via update_frame(). The server uses one
asyncio.Queue per connected client so slow clients drop frames without blocking
the capture loop.
"""
from __future__ import annotations

import asyncio
import logging
from asyncio import StreamReader, StreamWriter
from collections.abc import Callable

log = logging.getLogger(__name__)

_BOUNDARY = b"frame"

_INDEX_HTML = b"""\
<!doctype html>
<html>
<head>
  <title>L4RPCH3KR Pi Camera</title>
  <style>
    * { box-sizing: border-box; }
    body {
      background: #111; color: #ddd; font-family: monospace;
      display: flex; flex-direction: column; align-items: center;
      justify-content: center; min-height: 100vh; margin: 0; gap: 1rem;
    }
    h1   { font-size: .9rem; letter-spacing: .15em; text-transform: uppercase; color: #888; }
    img  { max-width: min(640px, 100vw); border: 1px solid #333; display: block; }
    p    { font-size: .75rem; color: #555; }
  </style>
</head>
<body>
  <h1>L4RPCH3KR &mdash; Pi Camera Preview</h1>
  <img src="/stream" alt="camera feed">
  <p>Live MJPEG &bull; <a href="/stream" style="color:#555">/stream</a></p>
</body>
</html>
"""


class PreviewServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 8080) -> None:
        self._host = host
        self._port = port
        self._latest_jpeg: bytes | None = None
        self._queues: list[asyncio.Queue[bytes | None]] = []

    def update_frame(self, jpeg_bytes: bytes) -> None:
        """Called by the camera capture loop with a fresh JPEG frame."""
        self._latest_jpeg = jpeg_bytes
        for q in list(self._queues):
            try:
                q.put_nowait(jpeg_bytes)
            except asyncio.QueueFull:
                pass  # slow client — skip frame rather than block

    async def _handle(self, reader: StreamReader, writer: StreamWriter) -> None:
        try:
            request_line = await asyncio.wait_for(reader.readline(), timeout=5)
            if not request_line:
                return
            parts = request_line.decode(errors="replace").split()
            path = parts[1] if len(parts) >= 2 else "/"
            # drain request headers
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
        if self._latest_jpeg:
            await _write_frame(writer, self._latest_jpeg)

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
        log.info(
            "preview: http://%s:%d  (MJPEG stream at /stream)",
            self._host,
            self._port,
        )
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
