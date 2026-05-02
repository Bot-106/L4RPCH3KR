#!/usr/bin/env python3
"""
One-shot pairing helper. Run this once to scan the QR code and persist the pi_token.

Usage:
  python scripts/pair.py                     # real camera + real backend
  LARPCHEKR_FAKE_HARDWARE=1 python scripts/pair.py   # fake token, local backend
"""
import asyncio
import sys
from pathlib import Path

# Allow running from project root or pi/ directory
sys.path.insert(0, str(Path(__file__).parent.parent))

from larpchekr.config import settings
from larpchekr.pairing import PairingManager


async def main() -> None:
    settings.configure_logging()
    mgr = PairingManager(
        backend_rest=settings.backend_rest,
        pi_token_path=settings.pi_token_path,
        device_id=settings.device_id,
        fake=settings.fake_hardware,
    )
    if mgr.is_paired():
        print(f"Already paired. Token at {settings.pi_token_path}")
        print("Delete the token file and re-run to re-pair.")
        return

    print("Starting pairing flow …")
    token = await mgr.pair()
    print(f"Pairing complete. pi_token={token!r}")
    print(f"Token saved to {settings.pi_token_path}")


if __name__ == "__main__":
    asyncio.run(main())
