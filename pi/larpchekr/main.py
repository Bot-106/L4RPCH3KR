"""
L4RPCH3KR Pi capture device — main entrypoint.

Orchestrates:
  - WsClient (connect/reconnect loop)
  - AudioCapture (VAD-gated streaming)
  - CameraCapture (10s snapshots)
  - HapticDriver, LEDController, Button (hardware I/O)
  - Heartbeat task
  - Button task (arm → start → stop session)

Run:
  python -m larpchekr.main                      # real hardware
  LARPCHEKR_FAKE_HARDWARE=1 python -m larpchekr.main  # laptop dev
"""
from __future__ import annotations

import asyncio
import logging
import signal

from larpchekr.audio import AudioCapture
from larpchekr.buffer import RingBuffer
from larpchekr.camera import CameraCapture
from larpchekr.config import settings
from larpchekr.hardware.button import Button
from larpchekr.hardware.haptic import HapticDriver
from larpchekr.hardware.led import LEDController, LedState
from larpchekr.pairing import PairingManager
from larpchekr.preview_server import PreviewServer
from larpchekr.ws_client import WsClient

log = logging.getLogger(__name__)


async def button_task(
    button: Button,
    ws: WsClient,
    led: LEDController,
    stop_event: asyncio.Event,
) -> None:
    """
    Button state machine:
      - While armed (session_id known, not yet streaming): press → session_start
      - While recording: press → session_end
      - Otherwise: press is a no-op (logged)
    """
    log.info("button: task started (FAKE=%s)", settings.fake_hardware)
    while not stop_event.is_set():
        await button.wait_press()
        sid = ws.session_id
        state = led.state

        if sid and state == LedState.armed:
            log.info("button: pressed while armed → sending session_start")
            await ws.send_session_start(sid)
            led.set_state(LedState.recording)

        elif sid and state == LedState.recording:
            log.info("button: pressed while recording → sending session_end")
            led.set_state(LedState.armed)
            await ws.send_session_end(sid, reason="manual")

        else:
            log.info("button: pressed but no active session (state=%s, sid=%s)", state, sid)


async def main() -> None:
    settings.configure_logging()
    log.info("L4RPCH3KR Pi starting (fake_hardware=%s)", settings.fake_hardware)

    fake = settings.fake_hardware

    # --- Pairing ---
    pairing = PairingManager(
        backend_rest=settings.backend_rest,
        pi_token_path=settings.pi_token_path,
        device_id=settings.device_id,
        fake=fake,
    )
    if not pairing.is_paired():
        log.info("Not paired — running pairing flow")
        await pairing.pair()

    token = settings.pi_token

    # --- Hardware ---
    led = LEDController(fake=fake)
    haptic = HapticDriver(fake=fake)
    button = Button(fake=fake)
    buf = RingBuffer()

    # --- Subsystems ---
    audio = AudioCapture(fake=fake)
    camera = CameraCapture(fake=fake)
    preview = PreviewServer(host="0.0.0.0", port=settings.preview_port)

    ws = WsClient(
        ws_url=settings.backend_ws,
        token=token,
        device_id=settings.device_id,
        buffer=buf,
        led=led,
        haptic=haptic,
    )

    led.set_state(LedState.offline)
    stop_event = asyncio.Event()

    def _handle_shutdown(sig: int, frame: object) -> None:
        log.info("shutdown signal %d received", sig)
        stop_event.set()
        ws.stop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, _handle_shutdown)

    tasks = [
        asyncio.create_task(ws.run(), name="ws"),
        asyncio.create_task(
            audio.run(
                send_envelope=ws.send_envelope,
                send_binary=ws.send_binary,
                get_session_id=lambda: ws.session_id,
                stop_event=stop_event,
            ),
            name="audio",
        ),
        asyncio.create_task(
            camera.run(
                send_envelope=ws.send_envelope,
                get_session_id=lambda: ws.session_id,
                stop_event=stop_event,
            ),
            name="camera",
        ),
        asyncio.create_task(
            camera.preview_run(on_frame=preview.update_frame, stop_event=stop_event),
            name="camera_preview",
        ),
        asyncio.create_task(
            preview.run(stop_event=stop_event),
            name="preview_server",
        ),
        asyncio.create_task(
            ws.heartbeat_loop(get_buffer_seconds=lambda: buf.buffered_seconds),
            name="heartbeat",
        ),
        asyncio.create_task(
            button_task(button=button, ws=ws, led=led, stop_event=stop_event),
            name="button",
        ),
    ]

    log.info("All tasks started. Running until stop signal.")
    try:
        done, pending = await asyncio.wait(
            tasks, return_when=asyncio.FIRST_EXCEPTION
        )
        for t in done:
            exc = t.exception()
            if exc:
                log.error("Task %s raised: %s", t.get_name(), exc)
    finally:
        stop_event.set()
        ws.stop()
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

        # Cleanup hardware
        led.close()
        haptic.close()
        button.close()
        camera.close()
        log.info("shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
