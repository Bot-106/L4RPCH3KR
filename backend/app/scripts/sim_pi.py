import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import websockets


def env(event_type: str, data: dict, session_id: str | None = None) -> str:
    import uuid

    return json.dumps({"id": str(uuid.uuid4()), "type": event_type, "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "session_id": session_id, "data": data})


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--url", default="ws://100.76.124.67:8000/ws/pi?token=dev-token")
    parser.add_argument("--wav", default=None, help="Optional WAV path. The MVP stub splits it into two utterance frames deterministically.")
    args = parser.parse_args()

    async with websockets.connect(args.url) as ws:
        await ws.send(env("pi_hello", {"device_id": "sim-pi", "firmware_version": "0.1.0", "battery_pct": 95}))
        await ws.recv()
        await ws.send(env("session_start", {"session_id": args.session_id}, args.session_id))
        await ws.recv()
        await ws.send(env("frame_snapshot", {"image_b64": "fixture", "width": 1, "height": 1, "face_embedding": [1.0] + [0.0] * 511}, args.session_id))
        await ws.recv()
        await ws.send(env("audio_meta", {"sample_rate": 16000, "encoding": "pcm_s16le", "channels": 1, "frame_ms": 250, "speaker_hint": "partner"}, args.session_id))
        if args.wav:
            wav_bytes = Path(args.wav).read_bytes()
            midpoint = max(1, len(wav_bytes) // 2)
            first_frame = wav_bytes[:midpoint]
            second_frame = wav_bytes[midpoint:] or b"larp utterance frame"
        else:
            first_frame = b"truthful utterance frame"
            second_frame = b"larp utterance frame"
        await ws.send(first_frame)
        await asyncio.sleep(0.2)
        await ws.send(second_frame)
        await asyncio.sleep(0.5)


if __name__ == "__main__":
    asyncio.run(main())
