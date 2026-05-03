"""
Remove all flags from MongoDB.
"""
import asyncio
from pathlib import Path
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import dotenv_values

# Load environment variables
env_path = Path(__file__).resolve().parent / ".env"
env_values = dotenv_values(env_path)

MONGO_URL = env_values.get("MONGO_URL", "").strip()
MONGO_DB = env_values.get("MONGO_DB", "larpchekr").strip()

if not MONGO_URL:
    print("ERROR: MONGO_URL not found in .env file")
    exit(1)


async def remove_flags():
    """Remove all flags from MongoDB."""
    print(f"🗑️  Connecting to MongoDB...")

    client = AsyncIOMotorClient(MONGO_URL)

    try:
        # Verify connection
        await client.admin.command("ping")
        print("✅ Connected to MongoDB\n")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

    db = client[MONGO_DB]
    flags_collection = db["flags"]

    try:
        # Count existing flags
        count = await flags_collection.count_documents({})
        print(f"Found {count} flags to remove...")

        if count > 0:
            # Delete all flags
            result = await flags_collection.delete_many({})
            print(f"✅ Removed {result.deleted_count} flags")
        else:
            print("No flags to remove")

        print("\n🎉 All flags removed successfully!")
        return True

    except Exception as e:
        print(f"❌ Operation failed: {e}")
        return False

    finally:
        # Close connection
        client.close()


if __name__ == "__main__":
    success = asyncio.run(remove_flags())
    exit(0 if success else 1)
