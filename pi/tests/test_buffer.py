"""Tests for the ring buffer (no hardware required)."""
import struct
import time

import pytest

from larpchekr.buffer import (
    FRAME_MS,
    MAX_ITEMS,
    BinaryItem,
    JsonItem,
    RingBuffer,
)


def _make_binary(ms: int | None = None) -> BinaryItem:
    ts = ms if ms is not None else int(time.time() * 1000)
    header = struct.pack(">q", ts)
    pcm = b"\x00" * 8000  # 250 ms of silence
    return BinaryItem(data=header + pcm)


def _make_json(msg_type: str = "heartbeat") -> JsonItem:
    return JsonItem(envelope={"type": msg_type, "id": "test", "ts": "2026-05-01T00:00:00Z", "data": {}})


class TestRingBuffer:
    def test_push_and_drain_order(self):
        buf = RingBuffer(maxlen=5)
        items = [_make_binary(i) for i in range(3)]
        for it in items:
            buf.push(it)
        drained = list(buf.drain())
        assert len(drained) == 3
        assert drained[0].data[:8] == items[0].data[:8]

    def test_drain_empties_buffer(self):
        buf = RingBuffer(maxlen=5)
        buf.push(_make_binary())
        list(buf.drain())
        assert buf.is_empty()
        assert len(buf) == 0

    def test_overflow_drops_oldest(self):
        buf = RingBuffer(maxlen=3)
        for i in range(5):
            buf.push(_make_binary(i))
        assert len(buf) == 3
        drained = list(buf.drain())
        # Oldest two (0, 1) should be dropped; keep 2, 3, 4
        timestamps = [struct.unpack(">q", it.data[:8])[0] for it in drained]
        assert timestamps == [2, 3, 4]

    def test_buffered_seconds_only_counts_binary(self):
        buf = RingBuffer(maxlen=20)
        for _ in range(4):
            buf.push(_make_binary())
        buf.push(_make_json())
        # 4 binary × 0.25s = 1.0s
        assert buf.buffered_seconds == pytest.approx(4 * FRAME_MS / 1000)

    def test_buffered_seconds_reset_on_drain(self):
        buf = RingBuffer(maxlen=10)
        for _ in range(3):
            buf.push(_make_binary())
        list(buf.drain())
        assert buf.buffered_seconds == 0.0

    def test_mixed_items_preserve_order(self):
        buf = RingBuffer(maxlen=10)
        items = [_make_json("audio_meta"), _make_binary(1), _make_binary(2), _make_json("heartbeat")]
        for it in items:
            buf.push(it)
        drained = list(buf.drain())
        assert drained[0].kind == "json"
        assert drained[1].kind == "binary"
        assert drained[2].kind == "binary"
        assert drained[3].kind == "json"

    def test_large_buffer_capacity(self):
        buf = RingBuffer(maxlen=MAX_ITEMS)
        for i in range(MAX_ITEMS):
            buf.push(_make_binary(i))
        assert len(buf) == MAX_ITEMS
        # One more should evict oldest
        buf.push(_make_binary(MAX_ITEMS))
        drained = list(buf.drain())
        first_ts = struct.unpack(">q", drained[0].data[:8])[0]
        assert first_ts == 1  # 0 was dropped

    def test_thread_safety(self):
        import threading

        buf = RingBuffer(maxlen=500)
        errors: list[Exception] = []

        def producer():
            try:
                for i in range(100):
                    buf.push(_make_binary(i))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=producer) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
        assert len(buf) <= 500
