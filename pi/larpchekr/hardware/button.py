"""
Debounced button input.

GPIO22, active-low (pull-up resistor).
In fake mode: SIGUSR1 triggers a press (useful for laptop testing).
"""
from __future__ import annotations

import asyncio
import logging
import signal

log = logging.getLogger(__name__)

BUTTON_PIN = 22
DEBOUNCE_MS = 50


class Button:
    """Async-friendly button that delivers press events to a queue."""

    def __init__(self, fake: bool = False) -> None:
        self._fake = fake
        self._queue: asyncio.Queue[None] = asyncio.Queue()
        self._btn = None

        if not fake:
            try:
                from gpiozero import Button as GPIOButton  # type: ignore[import]

                self._btn = GPIOButton(
                    BUTTON_PIN,
                    pull_up=True,
                    bounce_time=DEBOUNCE_MS / 1000,
                )
                self._btn.when_pressed = self._on_press
            except Exception as exc:
                log.warning("button: GPIO init failed (%s) — falling back to fake", exc)
                self._fake = True

        if self._fake:
            # SIGUSR1 simulates a button press
            try:
                signal.signal(signal.SIGUSR1, self._on_signal)
                log.info(
                    "button: FAKE mode — send SIGUSR1 (kill -USR1 %d) to simulate press",
                    __import__("os").getpid(),
                )
            except (OSError, ValueError):
                # signal can fail in non-main threads; ignore
                pass

    def _on_press(self) -> None:
        try:
            self._queue.put_nowait(None)
        except asyncio.QueueFull:
            pass

    def _on_signal(self, signum: int, frame: object) -> None:
        self._on_press()

    async def wait_press(self) -> None:
        """Block until the next button press."""
        await self._queue.get()

    def close(self) -> None:
        if self._btn is not None:
            try:
                self._btn.close()
            except Exception:
                pass
