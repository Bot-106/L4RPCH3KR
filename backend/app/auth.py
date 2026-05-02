from datetime import datetime, timedelta
from typing import Any

import jwt

from app.config import settings


def create_token(user_id: str, role: str = "attendee") -> str:
    payload = {"sub": user_id, "role": role, "exp": datetime.utcnow() + timedelta(days=7)}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
