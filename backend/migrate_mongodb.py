"""
Migrate data from local MongoDB to remote MongoDB Atlas cluster.
"""
import asyncio
import os
from pathlib import Path
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import dotenv_values

# Load environment variables
env_path = Path(__file__).resolve().parent / ".env"
env_values = dotenv_values(env_path)

LOCAL_MONGO_URL = "mongodb://localhost:27017"
REMOTE_MONGO_URL = env_values.get("MONGO_URL", "").strip()
MONGO_DB = env_values.get("MONGO_DB", "larpchekr").strip()

if not REMOTE_MONGO_URL:
    print("ERROR: MONGO_URL not found in .env file")
    exit(1)

# Collections to migrate
COLLECTIONS = [
    "events",
    "attendees",
    "sessions",
    "utterances",
    "claims",
    "flags",
    "devices",
    "users",
]


async def migrate():
    """Migrate all collections from local to remote MongoDB."""
    print(f"📦 Starting MongoDB migration...")
    print(f"   Local:  {LOCAL_MONGO_URL}/{MONGO_DB}")
    print(f"   Remote: {REMOTE_MONGO_URL}{MONGO_DB}\n")

    # Connect to both databases
    local_client = AsyncIOMotorClient(LOCAL_MONGO_URL)
    remote_client = AsyncIOMotorClient(REMOTE_MONGO_URL)

    try:
        # Verify connections
        await local_client.admin.command("ping")
        await remote_client.admin.command("ping")
        print("✅ Both database connections successful\n")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

    local_db = local_client[MONGO_DB]
    remote_db = remote_client[MONGO_DB]

    total_migrated = 0

    try:
        for collection_name in COLLECTIONS:
            print(f"Migrating '{collection_name}'...", end=" ")

            # Get the collections
            local_collection = local_db[collection_name]
            remote_collection = remote_db[collection_name]

            # Count documents in local collection
            count = await local_collection.count_documents({})

            if count == 0:
                print("(empty)")
                continue

            # Fetch all documents from local
            documents = await local_collection.find({}).to_list(None)

            # Clear remote collection first
            await remote_collection.delete_many({})

            # Insert into remote
            if documents:
                result = await remote_collection.insert_many(documents)
                print(f"✅ {len(result.inserted_ids)} documents migrated")
                total_migrated += len(result.inserted_ids)
            else:
                print("(no documents)")

        print(f"\n🎉 Migration complete! Total documents: {total_migrated}")
        return True

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        return False

    finally:
        # Close connections
        local_client.close()
        remote_client.close()


if __name__ == "__main__":
    success = asyncio.run(migrate())
    exit(0 if success else 1)
