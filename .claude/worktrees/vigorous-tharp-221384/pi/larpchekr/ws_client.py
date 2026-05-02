"""
WebSocket client: connect/reconnect, send/recv, buffer drain.

Protocol:
  1. Connect → send `pi_hello`
  2. If buffer non-empty → send `buffer_drain_start`, replay items, `buffer_drain_end`
  3. Normal operation: relay envelopes and binary frames from audio/camera/heartbeat
  4. Dispatch inbound: `haptic_pulse`, `recording_indicator`, `session_ack`, `error`
  5. On disconnect → reconnect with exponential backoff (1→2→4→8→30s)

Inbound `recording_indicator` drives:
  - LED state machine
  - session_id tracking (sourced from envelope's session_id field)
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

log = logging.getLogger(__name__)

FIRMWARE_VERSION = "0.1.0"

# Reconnect backoff: initial, multiplier, maximum (seconds)
BACKOFF_INITIAL = 1.0
BACKOFF_MULT = 2.0
BACKOFF_MAX = 30.0

HEARTBEAT_INTERVAL = 10.0  # seconds


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _new_id() -> str:
    return uuid.uuid4().hex


def _envelope(msg_type: str, data: dict[str, Any], session_id: str | None = None) -> dict:
    return {
        "id": _new_id(),
        "type": msg_type,
        "ts": _now_iso(),
        "session_id": session_id,
        "data": data,
    }


class WsClient:
    def __init__(
        self,
        ws_url: str,
        token: str,
        device_id: str,
        buffer: "object",  # larpchekr.buffer.RingBuffer
        led: "object",  # larpchekr.hardware.led.LEDController
        haptic: "object",  # larpchekr.hardware.haptic.HapticDriver
        on_session_start_ack: Callable[[str], Awaitable[None]] | None = None,
    ) -> None:
        self._url = f"{ws_url}?token={token}"
        self._device_id = device_id
        self._buf = buffer
        self._led = led
        self._haptic = haptic
        self._on_session_start_ack = on_session_start_ack

        self._ws: Any = None
        self._session_id: str | None = None
        self._connected = asyncio.Event()
        self._stop = asyncio.Event()
        # Queue for outbound messages while connected
        self._send_q: asyncio.Queue[dict | bytes] = asyncio.Queue(maxsize=256)

    # ------------------------------------------------------------------
    # Public interface used by audio, camera, heartbeat, button tasks
    # ------------------------------------------------------------------

    @property
    def session_id(self) -> str | None:
        return self._session_id

    @property
    def is_connected(self) -> bool:
        return self._connected.is_set()

    async def send_envelope(self, env: dict) -> None:
        """Send a JSON envelope. Buffers when disconnected."""
        from larpchekr.buffer import JsonItem
        if self._connected.is_set():
            try:
                self._send_q.put_nowait(env)
            except asyncio.QueueFull:
                log.warning("ws send_q full — buffering envelope type=%s", env.get("type"))
                self._buf.push(JsonItem(envelope=env))
        else:
            self._buf.push(JsonItem(envelope=env))

    async def send_binary(self, data: bytes) -> None:
        """Send a binary PCM frame. Buffers when disconnected."""
        from larpchekr.buffer import BinaryItem
        if self._connected.is_set():
            try:
                self._send_q.put_nowait(data)
            except asyncio.QueueFull:
                log.warning("ws send_q full — buffering binary frame")
                self._buf.push(BinaryItem(data=data))
        else:
            self._buf.push(BinaryItem(data=data))

    async def send_session_start(self, session_id: str) -> None:
        await self.send_envelope(_envelope("session_start", {"session_id": session_id}, session_id))

    async def send_session_end(self, session_id: str, reason: str = "manual") -> None:
        await self.send_envelope(_envelope("session_end", {"session_id": session_id, "reason": reason}, session_id))

    def stop(self) -> None:
        self._stop.set()

    # ------------------------------------------------------------------
    # Main run loop
    # ------------------------------------------------------------------

    async def run(self) -> None:
        backoff = BACKOFF_INITIAL
        while not self._stop.is_set():
            try:
                await self._connect_and_run()
                backoff = BACKOFF_INITIAL  # reset on clean exit
            except Exception as exc:
                log.warning("ws: disconnected (%s) — reconnecting in %.1fs", exc, backoff)
            finally:
                self._connected.clear()
                self._led.set_state("offline")

            if self._stop.is_set():
                break
            await asyncio.sleep(backoff)
            backoff = min(backoff * BACKOFF_MULT, BACKOFF_MAX)

    async def _connect_and_run(self) -> None:
        import websockets  # type: ignore[import]

        log.info("ws: connecting to %s", self._url)
        async with websockets.connect(self._url, ping_interval=20, ping_timeout=10) as ws:
            self._ws = ws
            log.info("ws: connected")

            # Send hello
            await ws.send(json.dumps(_envelope(
                "pi_hello",
                {"device_id": self._device_id, "firmware_version": FIRMWARE_VERSION, "battery_pct": None},
            )))

            # Drain ring buffer if non-empty
            if not self._buf.is_empty():
                await self._drain_buffer(ws)

            self._connected.set()
            self._led.set_state("armed")

            # Run sender and receiver concurrently
            await asyncio.gather(
                self._sender(ws),
                self._receiver(ws),
            )

    async def _drain_buffer(self, ws: Any) -> None:
        from larpchekr.buffer import BinaryItem, JsonItem

        buffered_s = self._buf.buffered_seconds
        log.info("ws: draining buffer (%.1fs of audio)", buffered_s)

        await ws.send(json.dumps(_envelope(
            "buffer_drain_start",
            {"session_id": self._session_id, "buffered_seconds": buffered_s},
            self._session_id,
        )))

        for item in self._buf.drain():
            if isinstance(item, JsonItem):
                await ws.send(json.dumps(item.envelope))
            elif isinstance(item, BinaryItem):
                await ws.send(item.data)
            # Yield control periodically
            await asyncio.sleep(0)

        await ws.send(json.dumps(_envelope(
            "buffer_drain_end",
            {"session_id": self._session_id, "buffered_seconds": buffered_s},
            self._session_id,
        )))
        log.info("ws: buffer drain complete")

    async def _sender(self, ws: Any) -> None:
        """Drain the outbound send queue to the websocket."""
        while True:
            item = await self._send_q.get()
            if isinstance(item, bytes):
                await ws.send(item)
            else:
                await ws.send(json.dumps(item))

    async def _receiver(self, ws: Any) -> None:
        """Receive and dispatch inbound messages."""
        import websockets  # type: ignore[import]

        async for raw in ws:
            if isinstance(raw, bytes):
                # Backend shouldn't send raw binary to Pi in v1
                log.debug("ws: unexpected binary frame (%d bytes)", len(raw))
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                log.warning("ws: non-JSON message: %.80r", raw)
                continue
            await self._dispatch(msg)

    async def _dispatch(self, msg: dict) -> None:
        msg_type = msg.get("type")
        data = msg.get("data", {})
        envelope_session_id = msg.get("session_id")

        if msg_type == "recording_indicator":
            state = data.get("state", "off")
            self._led.set_state(state)
            if state == "recording" and envelope_session_id:
                self._session_id = envelope_session_id
                log.info("ws: recording started, session_id=%s", self._session_id)
            elif state == "armed" and envelope_session_id:
                self._session_id = envelope_session_id
                log.info("ws: armed, session_id=%s", self._session_id)
            elif state == "off":
                log.info("ws: recording stopped")
                self._session_id = None

        elif msg_type == "session_ack":
            sid = data.get("session_id") or envelope_session_id
            log.info("ws: session_ack received for session_id=%s", sid)
            if sid:
                self._session_id = sid
            if self._on_session_start_ack:
                await self._on_session_start_ack(sid)

        elif msg_type == "haptic_pulse":
            severity = data.get("severity", "medium")
            pattern = [int(p) for p in data.get("pattern", [])]
            log.info("ws: haptic_pulse severity=%s pattern=%s", severity, pattern)
            asyncio.ensure_future(self._haptic.pulse(pattern, severity))

        elif msg_type == "error":
            code = data.get("code", "unknown")
            message = data.get("message", "")
            log.error("ws: backend error code=%s message=%s", code, message)

        else:
            log.debug("ws: unhandled message type=%s", msg_type)

    # ------------------------------------------------------------------
    # Heartbeat (called from main.py as a separate task)
    # ------------------------------------------------------------------

    async def heartbeat_loop(self, get_buffer_seconds: Callable[[], float]) -> None:
        while not self._stop.is_set():
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            if not self._connected.is_set():
                continue
            await self.send_envelope(_envelope(
                "heartbeat",
                {
                    "battery_pct": 100,  # stub — no battery sensor in v1
                    "cpu_temp_c": _read_cpu_temp(),
                    "buffer_seconds": get_buffer_seconds(),
                },
                self._session_id,
            ))


def _read_cpu_temp() -> float:
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return int(f.read().strip()) / 1000.0
    except Exception:
        return 0.0
