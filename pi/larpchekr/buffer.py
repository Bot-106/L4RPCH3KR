"""
Ring buffer for offline degradation.

When the WS connection drops, audio frames and JSON envelopes are pushed here
instead of discarded. On reconnect the client drains the buffer in order,
bracketed by buffer_drain_start / buffer_drain_end envelopes.

Storage layout:
  - JsonItem  — a pre-serialised JSON envelope dict
  - BinaryItem — raw PCM bytes (with 8-byte int64 ms timestamp header)

Capacity: MAX_FRAMES binary frames ≈ 5 minutes of continuous audio.
The deque drops the oldest item when full (FIFO overflow).
"""
from __future__ import annotations

import logging
import struct
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Iterator

log = logging.getLogger(__name__)

# 250 ms frames × 1200 = 300 s ≈ 5 min
MAX_FRAMES = 1200
# Allow some extra headroom for JSON envelopes interleaved with audio
MAX_ITEMS = MAX_FRAMES + 300

# Audio frame constants (PCM s16le, 16kHz mono, 250ms)
FRAME_MS = 250
SAMPLE_RATE = 16000
BYTES_PER_SAMPLE = 2
PCM_BYTES_PER_FRAME = SAMPLE_RATE * FRAME_MS // 1000 * BYTES_PER_SAMPLE  # 8 000
HEADER_BYTES = 8  # int64 ms-since-epoch, big-endian
FRAME_BYTES = HEADER_BYTES + PCM_BYTES_PER_FRAME


@dataclass
class JsonItem:
    envelope: dict
    kind: str = field(default="json", init=False)


@dataclass
class BinaryItem:
    data: bytes  # 8-byte header + PCM
    kind: str = field(default="binary", init=False)


BufferItem = JsonItem | BinaryItem


def _ms_from_header(data: bytes) -> int:
    return struct.unpack(">q", data[:8])[0]


class RingBuffer:
    """Thread-safe ring buffer with bounded capacity."""

    def __init__(self, maxlen: int = MAX_ITEMS) -> None:
        self._buf: deque[BufferItem] = deque(maxlen=maxlen)
        self._lock = threading.Lock()
        self._binary_count = 0

    def push(self, item: BufferItem) -> None:
        with self._lock:
            if len(self._buf) == self._buf.maxlen:
                dropped = self._buf[0]
                if dropped.kind == "binary":
                    self._binary_count = max(0, self._binary_count - 1)
                log.debug("Buffer full — dropping oldest item (kind=%s)", dropped.kind)
            self._buf.append(item)
            if item.kind == "binary":
                self._binary_count += 1

    def drain(self) -> Iterator[BufferItem]:
        """Yield and remove all items in FIFO order."""
        with self._lock:
            items = list(self._buf)
            self._buf.clear()
            self._binary_count = 0
        yield from items

    @property
    def buffered_seconds(self) -> float:
        with self._lock:
            return self._binary_count * (FRAME_MS / 1000)

    def __len__(self) -> int:
        with self._lock:
            return len(self._buf)

    def is_empty(self) -> bool:
        with self._lock:
            return len(self._buf) == 0
