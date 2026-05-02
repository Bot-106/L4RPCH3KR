"""
Demo reset: clear everything that came from spoken observations.

Resets:
  - attendee.larp_score → profile_larp_score (the static GitHub+LinkedIn baseline)
  - attendee.real_statements → []
  - attendee.larp_score_updated_at → null

Deletes:
  - all sessions
  - all utterances
  - all claims
  - all flags

Keeps:
  - attendees, events, users, profiles (cached LinkedIn/GitHub data)
  - attendee.profile_larp_score (the baseline)
  - attendee.profile_summary (cached external profile data)

Run from the backend host where MongoDB is reachable:
    python scripts/reset-live-data.py            # dry run, prints counts
    python scripts/reset-live-data.py --apply    # actually do it
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Allow running from repo root: `python scripts/reset-live-data.py`
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db import database  # noqa: E402


async def main(apply: bool) -> None:
    db = database()

    attendees_total = await db.attendees.count_documents({})
    sessions_total = await db.sessions.count_documents({})
    utterances_total = await db.utterances.count_documents({})
    claims_total = await db.claims.count_documents({})
    flags_total = await db.flags.count_documents({})
    bumped = await db.attendees.count_documents({"larp_score": {"$gt": 0}})

    print(f"Will reset {bumped} attendees with non-zero larp_score (out of {attendees_total} total)")
    print(f"Will delete: {sessions_total} sessions, {utterances_total} utterances, "
          f"{claims_total} claims, {flags_total} flags")

    if not apply:
        print("\nDry run. Re-run with --apply to perform the reset.")
        return

    print("\nApplying reset...")

    # Reset attendee scoring fields back to the static profile baseline.
    # MongoDB pipeline update: larp_score := profile_larp_score (or 0 if absent).
    result = await db.attendees.update_many(
        {},
        [{
            "$set": {
                "larp_score": {"$ifNull": ["$profile_larp_score", 0]},
                "larp_score_updated_at": None,
                "real_statements": [],
            }
        }],
    )
    print(f"  attendees: {result.modified_count} reset to profile baseline")

    # Wipe ephemeral conversation collections.
    r1 = await db.flags.delete_many({})
    print(f"  flags: {r1.deleted_count} deleted")
    r2 = await db.claims.delete_many({})
    print(f"  claims: {r2.deleted_count} deleted")
    r3 = await db.utterances.delete_many({})
    print(f"  utterances: {r3.deleted_count} deleted")
    r4 = await db.sessions.delete_many({})
    print(f"  sessions: {r4.deleted_count} deleted")

    print("\nDone. Larperboard now shows GitHub+LinkedIn baseline scores only.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="actually perform the reset (default is dry run)")
    args = parser.parse_args()
    asyncio.run(main(args.apply))
