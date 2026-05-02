#!/usr/bin/env python3
"""
Haptic motor smoke test. Fires a series of patterns to verify GPIO wiring.

Usage:
  python scripts/haptic_test.py                   # real GPIO
  LARPCHEKR_FAKE_HARDWARE=1 python scripts/haptic_test.py   # fake (log only)
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from larpchekr.config import settings
from larpchekr.hardware.haptic import HapticDriver


async def main() -> None:
    settings.configure_logging()
    fake = settings.fake_hardware
    haptic = HapticDriver(fake=fake)
    print(f"Haptic test (fake={fake})")

    sequences = [
        ("low", "low", [80]),
        ("medium", "medium", [150, 100]),
        ("high", "high", [200, 80, 200, 80, 200]),
        ("custom short", "medium", [50, 50, 50]),
    ]

    for label, severity, pattern in sequences:
        print(f"  {label}: pattern={pattern}")
        await haptic.pulse(pattern, severity)
        await asyncio.sleep(0.5)

    haptic.close()
    print("Haptic test complete.")


if __name__ == "__main__":
    asyncio.run(main())
