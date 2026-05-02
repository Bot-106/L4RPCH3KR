from __future__ import annotations

import asyncio
import json
import logging
import time
from asyncio import StreamReader, StreamWriter
from collections.abc import Callable

log = logging.getLogger(__name__)

_BOUNDARY = b"boundary"

_INDEX_HTML = b"""<!doctype html>
<html>
<head>
  <title>L4RPCH3KR Pi Diagnostic</title>
  <meta charset="utf-8">
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{background:#0d0d0d;color:#eee;font-family:'Courier New',monospace;display:flex;flex-direction:column;min-height:100vh}
    #hdr{padding:10px 14px;background:#111;border-bottom:1px solid #1e1e1e;display:flex;align-items:center;gap:10px}
    #hdr h1{font-size:12px;letter-spacing:3px;color:#555;text-transform:uppercase}
    #stream-wrap{flex:1;display:flex;align-items:center;justify-content:center;padding:12px;background:#0a0a0a}
    #stream{max-width:100%;max-height:70vh;border:1px solid #1e1e1e;display:block}
    #bar{padding:10px 14px;background:#111;border-top:1px solid #1e1e1e;display:flex;align-items:center;gap:10px}
    #dot{width:10px;height:10px;border-radius:50%;background:#333;flex-shrink:0;transition:background .4s}
    #phase{font-size:12px;font-weight:bold;letter-spacing:2px;text-transform:uppercase;transition:color .4s}
    #sep{color:#333;font-size:12px}
    #detail{font-size:11px;color:#555;flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    #ts{font-size:10px;color:#333;margin-left:auto}
  </style>
</head>
<body>
  <div id="hdr"><h1>L4RPCH3KR &mdash; PI DIAGNOSTIC</h1></div>
  <div id="stream-wrap">
    <img id="stream" src="/stream" alt="live feed">
  </div>
  <div id="bar">
    <div id="dot"></div>
    <span id="phase">--</span>
    <span id="sep">/</span>
    <span id="detail"></span>
    <span id="ts"></span>
  </div>
  <script>
    const COLORS={armed:'#00cc55',recording:'#00ff77',pairing:'#3399ff',scanning:'#3399ff',
      claimed:'#66bbff',connecting:'#555',starting:'#333',degraded:'#ffaa00',offline:'#ff4444'};
    async function poll(){
      try{
        const r=await fetch('/status');
        const d=await r.json();
        const c=COLORS[d.state]||'#888';
        document.getElementById('dot').style.background=c;
        const ph=document.getElementById('phase');
        ph.textContent=d.state; ph.style.color=c;
        document.getElementById('detail').textContent=d.detail||'';
        document.getElementById('ts').textContent=new Date().toLocaleTimeString();
      }catch(e){}
    }
    poll(); setInterval(poll,2000);
  </script>
</body>
</html>
"""

FrameCallback = Callable[[bytes], None]


def _make_status_jpeg(
    state: str, detail: str, elapsed: float | None = None
) -> bytes | None:
    try:
        import cv2  # type: ignore[import]
        import numpy as np  # type: ignore[import]

        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        for col in range(320):
            frame[:, col, 0] = int(col * 40 / 320)
        for row in range(0, 240, 20):
            cv2.line(frame, (0, row), (320, row), (30, 30, 30), 1)

        STATE_COLORS = {
            "armed": (0, 204, 85), "recording": (0, 255, 119),
            "pairing": (51, 153, 255), "scanning": (51, 153, 255),
            "claimed": (102, 187, 255), "degraded": (0, 170, 255),
            "offline": (68, 68, 255),
        }
        color = STATE_COLORS.get(state, (100, 100, 100))

        cv2.putText(frame, state.upper(), (10, 44), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)
        cv2.putText(frame, detail, (10, 72), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (160, 160, 160), 1)
        if elapsed is not None:
            cv2.putText(
                frame, f"{elapsed:.0f}s", (10, 232),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, (80, 80, 80), 1,
            )

        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
        if not ok:
            return None
        return bytes(buf)
    except Exception:
        return None


def add_overlay(frame: object, state: str = "", detail: str = "") -> object:
    try:
        import cv2  # type: ignore[import]

        if state:
            cv2.putText(frame, state, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 220, 80), 1)
        if detail:
            cv2.putText(frame, detail, (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (180, 180, 180), 1)
    except Exception:
        pass
    return frame


async def _write_frame(writer: StreamWriter, jpeg: bytes) -> None:
    header = (
        b"--" + _BOUNDARY + b"\r\n"
        b"Content-Type: image/jpeg\r\n"
        b"Content-Length: " + str(len(jpeg)).encode() + b"\r\n"
        b"\r\n"
    )
    writer.write(header + jpeg + b"\r\n")
    await writer.drain()


class PreviewServer:
    def __init__(self, host: str = "", port: int = 8080) -> None:
        self._host = host
        self._port = port
        self._current_frame: bytes | None = None
        self._state = "starting"
        self._detail = ""
        self._started_at = time.monotonic()
        self._queues: list[asyncio.Queue[bytes]] = []
        self._face_detected: bool = False
        self._last_transcript: str = ""

    def set_face_detected(self, detected: bool) -> None:
        self._face_detected = detected

    def set_last_transcript(self, text: str) -> None:
        # Trim to fit within the 320px frame at small font
        self._last_transcript = text[-72:] if len(text) > 72 else text

    def get_camera_overlay(self) -> "list[tuple[str, tuple[int, int, int]]]":
        """Return overlay lines for the camera preview, bottom-up."""
        lines = []
        if self._last_transcript:
            lines.append((self._last_transcript, (200, 200, 200)))
        face_label = "FACE: YES" if self._face_detected else "FACE: NO"
        face_color = (50, 220, 50) if self._face_detected else (50, 50, 220)
        lines.append((face_label, face_color))
        return lines

    def set_state(self, state: str, detail: str = "") -> None:
        """Must be called from the event loop thread."""
        self._state = state
        self._detail = detail
        log.info("preview: phase → %s  %s", state, detail)
        if self._current_frame is None:
            jpeg = _make_status_jpeg(state, detail)
            if jpeg:
                self._broadcast_sync(jpeg)

    def update_frame(self, jpeg_bytes: bytes) -> None:
        """Must be called from the event loop thread."""
        self._current_frame = jpeg_bytes
        self._broadcast_sync(jpeg_bytes)

    def _broadcast_sync(self, jpeg_bytes: bytes) -> None:
        for q in self._queues:
            # Drop the oldest stale frame before adding new one (lowest latency)
            if q.full():
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                q.put_nowait(jpeg_bytes)
            except asyncio.QueueFull:
                pass

    async def _status_tick(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            await asyncio.sleep(1.0)
            if self._current_frame is None:
                elapsed = time.monotonic() - self._started_at
                jpeg = _make_status_jpeg(self._state, self._detail, elapsed)
                if jpeg:
                    self._broadcast_sync(jpeg)

    async def _handle(self, reader: StreamReader, writer: StreamWriter) -> None:
        try:
            request_line = await asyncio.wait_for(reader.readline(), timeout=5.0)
        except (asyncio.TimeoutError, ConnectionError):
            writer.close()
            return

        parts = request_line.decode("utf-8", errors="replace").split()
        path = parts[1] if len(parts) >= 2 else "/"

        while True:
            line = await reader.readline()
            if line in (b"\r\n", b"\n", b""):
                break

        if path == "/stream":
            await self._handle_stream(writer)
        elif path == "/status":
            body = json.dumps({"state": self._state, "detail": self._detail}).encode()
            writer.write(
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: application/json\r\n"
                b"Content-Length: " + str(len(body)).encode() + b"\r\n"
                b"Access-Control-Allow-Origin: *\r\n"
                b"Connection: close\r\n\r\n" + body
            )
            await writer.drain()
            writer.close()
        else:
            writer.write(
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: text/html\r\n"
                b"Content-Length: " + str(len(_INDEX_HTML)).encode() + b"\r\n"
                b"Connection: close\r\n\r\n" + _INDEX_HTML
            )
            await writer.drain()
            writer.close()

    async def _handle_stream(self, writer: StreamWriter) -> None:
        writer.write(
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: multipart/x-mixed-replace; boundary=" + _BOUNDARY + b"\r\n"
            b"Cache-Control: no-cache\r\n"
            b"Connection: keep-alive\r\n\r\n"
        )
        await writer.drain()

        q: asyncio.Queue[bytes] = asyncio.Queue(maxsize=2)
        self._queues.append(q)

        if self._current_frame:
            try:
                await _write_frame(writer, self._current_frame)
            except (ConnectionError, BrokenPipeError):
                self._queues.remove(q)
                writer.close()
                return

        try:
            while True:
                jpeg = await q.get()
                await _write_frame(writer, jpeg)
        except (ConnectionError, BrokenPipeError, asyncio.CancelledError):
            pass
        finally:
            if q in self._queues:
                self._queues.remove(q)
            writer.close()

    async def run(self, stop_event: asyncio.Event) -> None:
        server = await asyncio.start_server(
            self._handle,
            host=self._host or "0.0.0.0",
            port=self._port,
        )
        log.info("preview: serving on http://0.0.0.0:%d", self._port)
        tick = asyncio.ensure_future(self._status_tick(stop_event))
        try:
            async with server:
                await stop_event.wait()
        finally:
            tick.cancel()
            await asyncio.gather(tick, return_exceptions=True)
