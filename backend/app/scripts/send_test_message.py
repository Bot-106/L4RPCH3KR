import argparse
import asyncio
import json
from datetime import datetime, timezone

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
        raise RuntimeError("No session found. Create one first or pass --session-id.")
    return session["id"]


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--session-id", default=None)
    parser.add_argument("--text", default="Hello, I built 5 production systems in Go.")
    parser.add_argument("--speaker-hint", default="partner")
    parser.add_argument("--device-id", default="sim-pi")
    args = parser.parse_args()

    session_id = args.session_id or await latest_session_id()
    ws_base = args.base_url.replace("http://", "ws://").replace("https://", "wss://")

    async with websockets.connect(f"{ws_base}/ws/phone?token=dev") as phone:
        await phone.send(env("phone_hello", {"user_id": "test-script", "app_version": "test"}))
        await phone.recv()
        await phone.send(env("subscribe_session", {"session_id": session_id}, session_id))
        await phone.recv()

        async with websockets.connect(f"{ws_base}/ws/pi?token=dev-pi") as pi:
            await pi.send(env("pi_hello", {"device_id": args.device_id, "firmware_version": "test-script", "battery_pct": 100}))
            await pi.recv()
            await pi.send(env("session_start", {"session_id": session_id}, session_id))
            await pi.recv()
            await pi.send(
                env(
                    "browser_transcript",
                    {"text": args.text, "speaker_hint": args.speaker_hint, "session_id": session_id},
                    session_id,
                )
            )
            await pi.recv()

        score_logged = False
        deadline = asyncio.get_running_loop().time() + 5
        while asyncio.get_running_loop().time() < deadline:
            try:
                raw = await asyncio.wait_for(phone.recv(), timeout=0.5)
            except TimeoutError:
                continue
            event = json.loads(raw)
            if event.get("type") == "score_update":
                data = event.get("data") or {}
                score = data.get("score")
                label = data.get("label")
                print(f"larp_score={score} label={label}")
                score_logged = True
                break

        if not score_logged:
            print("no score_update received")

    print(f"sent transcript to session_id={session_id}")


if __name__ == "__main__":
    asyncio.run(main())
