from collections.abc import AsyncIterator

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import settings


client = AsyncIOMotorClient(settings.mongo_url)


def database() -> AsyncIOMotorDatabase:
    return client[settings.mongo_db]


async def get_db() -> AsyncIterator[AsyncIOMotorDatabase]:
    yield database()
