import argparse
import asyncio
import json
from datetime import datetime, timezone

import httpx
import websockets

from app.db import database


def env(event_type: str, data: dict, session_id: str | None = None) -> str:
    import uuid

    return json.dumps(
        {
            "id": str(uuid.uuid4()),
            "type": event_type,
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "session_id": session_id,
            "data": data,
        }
    )


async def latest_session_id() -> str:
    session = await database().sessions.find_one(sort=[("started_at", -1)])
    if not session:
        raise RuntimeError("No seeded session found. Run python -m app.scripts.seed_event first.")
    return session["id"]


async def clear_session_outputs(session_id: str) -> None:
    db = database()
    utterances = await db.utterances.find({"session_id": session_id}).to_list(None)
    utterance_ids = [utterance["id"] for utterance in utterances]
    claims = await db.claims.find({"utterance_id": {"$in": utterance_ids}}).to_list(None)
    claim_ids = [claim["id"] for claim in claims]
    await db.flags.delete_many({"claim_id": {"$in": claim_ids}})
    await db.claims.delete_many({"utterance_id": {"$in": utterance_ids}})
    await db.utterances.delete_many({"session_id": session_id})


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--session-id", default=None)
    args = parser.parse_args()

    session_id = args.session_id or await latest_session_id()
    await clear_session_outputs(session_id)

    ws_base = args.base_url.replace("http://", "ws://").replace("https://", "wss://")
    flag_events = []

    async with websockets.connect(f"{ws_base}/ws/phone/dev") as phone:
        await phone.send(env("phone_hello", {"user_id": "01HX0000000000000000000000", "app_version": "verify"}))
        await phone.recv()
        await phone.send(env("subscribe_session", {"session_id": session_id}, session_id))
        await phone.recv()

        subject_events = []
        async with websockets.connect(f"{ws_base}/ws/pi/dev-pi") as pi:
            await pi.send(env("pi_hello", {"device_id": "sim-pi", "firmware_version": "0.1.0", "battery_pct": 95}))
            await pi.recv()
            await pi.send(env("session_start", {"session_id": session_id}, session_id))
            await pi.recv()
            await pi.send(env("frame_snapshot", {"image_b64": "fixture", "width": 1, "height": 1, "face_embedding": [1.0] + [0.0] * 511}, session_id))
            subject_resolved = json.loads(await pi.recv())
            if subject_resolved.get("type") == "subject_resolved":
                subject_events.append(subject_resolved)
            await pi.send(env("audio_meta", {"sample_rate": 16000, "encoding": "pcm_s16le", "channels": 1, "frame_ms": 250, "speaker_hint": "partner"}, session_id))
            await pi.recv()
            await pi.send(b"truthful utterance frame")
            await pi.send(b"larp utterance frame")

            deadline = asyncio.get_running_loop().time() + 8
            while asyncio.get_running_loop().time() < deadline:
                try:
                    raw = await asyncio.wait_for(phone.recv(), timeout=0.5)
                except TimeoutError:
                    continue
                event = json.loads(raw)
                if event.get("type") == "flag_raised":
                    flag_events.append(event)
                    break

    async with httpx.AsyncClient(base_url=args.base_url, timeout=10) as client:
        response = await client.get(f"/sessions/{session_id}/recap")
        response.raise_for_status()
        recap = response.json()

    if len(flag_events) != 1:
        raise RuntimeError(f"Expected exactly one flag_raised WS event, got {len(flag_events)}")
    if len(subject_events) != 1 or not subject_events[0]["data"].get("attendee_id"):
        raise RuntimeError("Expected face matcher to resolve exactly one subject")
    if len(recap["flags"]) != 1:
        raise RuntimeError(f"Expected exactly one recap flag, got {len(recap['flags'])}")

    print(f"verified session_id={session_id} flag_id={recap['flags'][0]['id']}")


if __name__ == "__main__":
    asyncio.run(main())
