import json
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def envelope(event_type: str, data: dict[str, Any], session_id: str | None = None) -> dict[str, Any]:
    import uuid

    return {"id": str(uuid.uuid4()), "type": event_type, "ts": now_iso(), "session_id": session_id, "data": data}


class WsManager:
    def __init__(self) -> None:
        self.phones: dict[str, set[WebSocket]] = {}
        self.pis: set[WebSocket] = set()

    async def subscribe_phone(self, session_id: str, ws: WebSocket) -> None:
        self.phones.setdefault(session_id, set()).add(ws)

    def unsubscribe(self, ws: WebSocket) -> None:
        self.pis.discard(ws)
        for subscribers in self.phones.values():
            subscribers.discard(ws)

    async def send_phone(self, session_id: str, event_type: str, data: dict[str, Any]) -> None:
        message = json.dumps(envelope(event_type, data, session_id))
        for ws in list(self.phones.get(session_id, set())):
            try:
                await ws.send_text(message)
            except RuntimeError:
                self.unsubscribe(ws)

    async def send_pi_haptic(self, severity: str) -> None:
        pattern = [150] if severity == "low" else [200, 100, 200] if severity == "medium" else [200, 80, 200, 80, 200]
        message = json.dumps(envelope("haptic_pulse", {"severity": severity, "pattern": pattern}))
        for ws in list(self.pis):
            try:
                await ws.send_text(message)
            except RuntimeError:
                self.unsubscribe(ws)


manager = WsManager()
