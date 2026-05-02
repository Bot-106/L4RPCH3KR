"""
Recording-indicator LED state machine.

RGB LED on GPIO12 (R) / GPIO13 (G) / GPIO16 (B).

States and colours:
  off        → (0, 0, 0) — not initialised / session ended
  armed      → (0, 0, 1) blue — connected, waiting for partner consent
  recording  → (0, 1, 0) green — actively streaming (CONSENT INDICATOR — MANDATORY)
  degraded   → (1, 1, 0) yellow — WS down, buffering
  offline    → (1, 0, 0) red — no network, not recording

The `recording` state MUST be visually distinct and MUST be on whenever
audio is being streamed to the backend. This is a consent requirement.
"""
from __future__ import annotations

import asyncio
import logging
from enum import Enum

log = logging.getLogger(__name__)

LED_R_PIN = 12
LED_G_PIN = 13
LED_B_PIN = 16

# (R, G, B) — values in [0, 1]
_COLOURS: dict[str, tuple[float, float, float]] = {
    "off": (0.0, 0.0, 0.0),
    "armed": (0.0, 0.0, 1.0),
    "recording": (0.0, 1.0, 0.0),
    "degraded": (1.0, 1.0, 0.0),
    "offline": (1.0, 0.0, 0.0),
}


class LedState(str, Enum):
    off = "off"
    armed = "armed"
    recording = "recording"
    degraded = "degraded"
    offline = "offline"


class LEDController:
    def __init__(self, fake: bool = False) -> None:
        self._fake = fake
        self._state = LedState.off
        self._led = None
        if not fake:
            try:
                from gpiozero import RGBLED  # type: ignore[import]

                self._led = RGBLED(
                    red=LED_R_PIN,
                    green=LED_G_PIN,
                    blue=LED_B_PIN,
                    active_high=True,
                )
            except Exception as exc:
                log.warning("LED: GPIO init failed (%s) — falling back to fake", exc)
                self._fake = True

    @property
    def state(self) -> LedState:
        return self._state

    def set_state(self, state: LedState | str) -> None:
        state = LedState(state)
        if state == self._state:
            return
        self._state = state
        colour = _COLOURS.get(state.value, (0.0, 0.0, 0.0))
        log.info("LED → %s %s", state.value, colour)
        if self._fake:
            return
        if self._led is not None:
            self._led.color = colour

    async def blink_once(self, times: int = 1) -> None:
        """Brief flash at the current colour (visual acknowledgment)."""
        original = self._state
        for _ in range(times):
            self.set_state(LedState.off)
            await asyncio.sleep(0.05)
            self.set_state(original)
            await asyncio.sleep(0.05)

    def close(self) -> None:
        self.set_state(LedState.off)
        if self._led is not None:
            try:
                self._led.close()
            except Exception:
                pass
