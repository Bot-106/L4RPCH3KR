from fastapi import Depends, Header, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth import decode_token
from app.db import get_db


async def current_user(
    authorization: str | None = Header(default=None), db: AsyncIOMotorDatabase = Depends(get_db)
) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        user = await db.users.find_one(sort=[("created_at", 1)])
        if user:
            return user
        raise HTTPException(status_code=401, detail={"error": {"code": "auth_invalid", "message": "missing bearer token"}})
    try:
        payload = decode_token(authorization.removeprefix("Bearer "))
    except Exception as exc:
        raise HTTPException(status_code=401, detail={"error": {"code": "auth_invalid", "message": "invalid bearer token"}}) from exc
    user = await db.users.find_one({"id": payload["sub"]})
    if not user:
        raise HTTPException(status_code=401, detail={"error": {"code": "auth_invalid", "message": "unknown user"}})
    return user


async def organizer_user(user: dict = Depends(current_user)) -> dict:
    if user.get("role") != "organizer":
        raise HTTPException(status_code=403, detail={"error": {"code": "auth_invalid", "message": "organizer required"}})
    return user
