"""
Haptic motor driver.

GPIO18 → N-MOSFET → small DC motor.
In real mode: gpiozero PWMOutputDevice, pattern = [ms_on, ms_off, ...].
In fake mode: logs the pattern.
"""
from __future__ import annotations

import asyncio
import logging

log = logging.getLogger(__name__)

# GPIO pin for haptic motor (BCM numbering)
HAPTIC_PIN = 18
PWM_FREQ = 1000  # Hz — audible buzz, fine for haptic motors

# Severity → default pattern if backend doesn't supply one
_DEFAULT_PATTERNS: dict[str, list[int]] = {
    "low": [80],
    "medium": [150, 100],
    "high": [200, 80, 200, 80, 200],
}


class HapticDriver:
    """Drives the haptic motor.

    pattern: list of alternating [on_ms, off_ms, on_ms, ...].
    Odd-indexed entries are "on" durations; even-indexed are "off" gaps.
    """

    def __init__(self, fake: bool = False) -> None:
        self._fake = fake
        self._motor = None
        if not fake:
            try:
                from gpiozero import PWMOutputDevice  # type: ignore[import]

                self._motor = PWMOutputDevice(HAPTIC_PIN, frequency=PWM_FREQ)
            except Exception as exc:
                log.warning("haptic: GPIO init failed (%s) — falling back to fake", exc)
                self._fake = True

    async def pulse(self, pattern: list[int], severity: str = "medium") -> None:
        if not pattern:
            pattern = _DEFAULT_PATTERNS.get(severity, [150])
        if self._fake:
            log.info("haptic FAKE pulse severity=%s pattern=%s", severity, pattern)
            return
        await self._drive(pattern)

    async def _drive(self, pattern: list[int]) -> None:
        on = True
        for ms in pattern:
            if self._motor is not None:
                self._motor.value = 1.0 if on else 0.0
            await asyncio.sleep(ms / 1000)
            on = not on
        if self._motor is not None:
            self._motor.value = 0.0

    def close(self) -> None:
        if self._motor is not None:
            try:
                self._motor.close()
            except Exception:
                pass
