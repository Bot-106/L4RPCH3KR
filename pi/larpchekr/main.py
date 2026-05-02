from __future__ import annotations

import asyncio
import logging
import signal
import sys
import time
import uuid

from larpchekr.audio import AudioCapture
from larpchekr.buffer import RingBuffer
from larpchekr.camera import CameraCapture, FaceDetector
from larpchekr.config import settings
from larpchekr.hardware.button import Button
from larpchekr.hardware.haptic import HapticDriver
from larpchekr.hardware.led import LEDController
from larpchekr.pairing import PAIR_TIMEOUT, PairingManager
from larpchekr.preview_server import PreviewServer
from larpchekr.ws_client import WsClient

log = logging.getLogger(__name__)


def _encode_pairing_frame(frame: object, remaining: float) -> bytes | None:
    """Resize to preview dimensions, draw QR-scan overlay, JPEG-encode."""
    try:
        import cv2  # type: ignore[import]
        from larpchekr.camera import PREVIEW_HEIGHT, PREVIEW_JPEG_QUALITY, PREVIEW_WIDTH

        frame = cv2.resize(frame, (PREVIEW_WIDTH, PREVIEW_HEIGHT))
        cv2.putText(
            frame, "Scan QR code",
            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 220, 80), 2,
        )
        cv2.putText(
            frame, f"{remaining:.0f}s remaining",
            (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (180, 180, 180), 1,
        )
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, PREVIEW_JPEG_QUALITY])
        return bytes(buf) if ok else None
    except Exception:
        return None


async def _pair_with_preview(
    pairing: PairingManager,
    preview: PreviewServer,
    loop: asyncio.AbstractEventLoop,
) -> None:
    """Run QR pairing fully async — camera, QR decode, and preview all in executor.

    update_frame() is called from the event loop thread after each await, so
    _broadcast_sync() needs no threading wrappers.
    """
    import cv2  # type: ignore[import]
    from pyzbar import pyzbar  # type: ignore[import]

    def _open_camera() -> object:
        from larpchekr.camera import _open_first_camera
        cap = _open_first_camera(cv2)
        if cap is None:
            return cv2.VideoCapture(-1)  # deliberately unopened
        # Warm-up: discard stale buffered frames
        for _ in range(4):
            cap.read()
        return cap

    cap = await loop.run_in_executor(None, _open_camera)
    cam_ok = cap.isOpened()
    log.info("pairing: camera %s", "ready" if cam_ok else "unavailable — scanning blind")

    found_token: str | None = None
    start = time.monotonic()

    try:
        while time.monotonic() - start < PAIR_TIMEOUT:
            remaining = PAIR_TIMEOUT - (time.monotonic() - start)

            if not cam_ok:
                preview.set_state("scanning", f"no camera — {remaining:.0f}s")
                await asyncio.sleep(1.0)
                continue

            ok, frame = await loop.run_in_executor(None, cap.read)
            if not ok:
                preview.set_state("scanning", f"camera read failed — {remaining:.0f}s")
                await asyncio.sleep(0.1)
                continue

            # QR detection is CPU-bound — run in executor so the event loop stays free
            codes = await loop.run_in_executor(None, pyzbar.decode, frame)
            for code in codes:
                data = code.data.decode("utf-8", errors="replace").strip()
                if data:
                    found_token = data
                    break

            if found_token:
                break

            # Encode frame with overlay — also CPU-bound
            jpeg = await loop.run_in_executor(
                None, _encode_pairing_frame, frame, remaining
            )
            if jpeg:
                # Called from event loop thread here — _broadcast_sync is safe
                preview.update_frame(jpeg)
            preview.set_state("scanning", f"{remaining:.0f}s remaining")

            await asyncio.sleep(0.1)  # ~10 fps cap

    finally:
        await loop.run_in_executor(None, cap.release)

    if found_token is None:
        raise TimeoutError(f"QR scan timed out after {PAIR_TIMEOUT}s")

    log.info("pairing: QR scanned — claiming token")
    preview.set_state("claimed", "QR detected — connecting to backend")
    pi_token = await loop.run_in_executor(None, pairing._claim, found_token)
    pairing._save_token(pi_token)


def _make_face_callbacks(ws_client: WsClient) -> tuple:
    """Return (on_start, on_end) async callbacks for the face detector."""
    _session_id: list[str | None] = [None]

    async def on_start() -> None:
        sid = uuid.uuid4().hex
        _session_id[0] = sid
        await ws_client.send_session_start(sid)
        log.info("face: session started id=%s", sid)

    async def on_end() -> None:
        sid = _session_id[0]
        if sid:
            await ws_client.send_session_end(sid, "face_lost")
            log.info("face: session ended id=%s", sid)
        _session_id[0] = None

    return on_start, on_end


async def _state_watcher(
    ws_client: WsClient,
    preview: PreviewServer,
    stop_event: asyncio.Event,
) -> None:
    while not stop_event.is_set():
        if ws_client.is_connected:
            sid = ws_client.session_id
            if sid:
                preview.set_state("recording", sid[:12])
            else:
                preview.set_state("armed", settings.device_id)
        else:
            preview.set_state("connecting", settings.backend_ws)
        await asyncio.sleep(1.0)


async def main() -> None:
    settings.configure_logging()
    log.info(
        "L4RPCH3KR Pi starting (device_id=%s, fake_hardware=%s)",
        settings.device_id,
        settings.fake_hardware,
    )

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    # Preview server starts immediately — port 8080 is live from the first second
    preview = PreviewServer(port=settings.preview_port)
    preview_task = asyncio.ensure_future(preview.run(stop_event))

    pairing = PairingManager(
        backend_rest=settings.backend_rest,
        pi_token_path=settings.pi_token_path,
        device_id=settings.device_id,
        fake=settings.fake_hardware,
    )
    if not pairing.is_paired():
        preview.set_state("pairing", "show QR code to camera")
        try:
            if settings.fake_hardware:
                pairing._fake_pair()
            else:
                await _pair_with_preview(pairing, preview, loop)
        except Exception as exc:
            log.error("pairing failed: %s — shutting down", exc)
            stop_event.set()
            await preview_task
            return

    preview.set_state("connecting", settings.backend_ws)

    led = LEDController(fake=settings.fake_hardware)
    haptic = HapticDriver(fake=settings.fake_hardware)
    buffer = RingBuffer()

    ws_client = WsClient(
        ws_url=settings.backend_ws,
        token=settings.pi_token,
        device_id=settings.device_id,
        buffer=buffer,
        led=led,
        haptic=haptic,
    )

    audio = AudioCapture(fake=settings.fake_hardware)
    camera = CameraCapture(fake=settings.fake_hardware)
    face_detector = FaceDetector(
        fake=settings.fake_hardware,
        start_frames=settings.face_start_frames,
        end_frames=settings.face_end_frames,
    )
    button = Button(fake=settings.fake_hardware)

    def _on_signal() -> None:
        log.info("shutdown signal received")
        stop_event.set()
        ws_client.stop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _on_signal)

    # Shared queue: preview_run pushes raw frames, face_detector reads them.
    # maxsize=2 so the detector always gets a fresh frame and never backs up.
    face_frame_queue: asyncio.Queue = asyncio.Queue(maxsize=2)

    on_face_start, on_face_end = _make_face_callbacks(ws_client)
    try:
        await asyncio.gather(
            preview_task,
            ws_client.run(),
            ws_client.heartbeat_loop(lambda: buffer.buffered_seconds),
            audio.run(
                ws_client.send_envelope,
                lambda: ws_client.session_id,
                stop_event,
                on_transcript=preview.set_last_transcript,
                get_face_ratio=lambda: preview.face_ratio(10.0),
            ),
            camera.run(
                ws_client.send_envelope,
                lambda: ws_client.session_id,
                stop_event,
            ),
            camera.preview_run(
                preview.update_frame,
                stop_event,
                get_overlay=preview.get_camera_overlay,
                face_queue=face_frame_queue,
            ),
            face_detector.run(
                face_frame_queue,
                on_face_start,
                on_face_end,
                stop_event,
                on_face_update=preview.set_face_detected,
            ),
            _state_watcher(ws_client, preview, stop_event),
        )
    finally:
        button.close()
        camera.close()
        led.close()
        haptic.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
