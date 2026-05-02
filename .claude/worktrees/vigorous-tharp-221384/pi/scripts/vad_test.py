#!/usr/bin/env python3
"""
Local VAD debugging. Captures from the mic and prints speech/silence labels in real time.

Usage:
  python scripts/vad_test.py [--aggressiveness 2] [--duration 10]

Requires: sounddevice, webrtcvad, numpy
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def run(aggressiveness: int, duration_s: float) -> None:
    import numpy as np
    import sounddevice as sd
    import webrtcvad

    SAMPLE_RATE = 16000
    FRAME_MS = 250
    FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000
    VAD_FRAME_MS = 10
    VAD_FRAME_SAMPLES = SAMPLE_RATE * VAD_FRAME_MS // 1000
    VAD_FRAME_BYTES = VAD_FRAME_SAMPLES * 2
    SUB_FRAMES = FRAME_MS // VAD_FRAME_MS

    vad = webrtcvad.Vad(aggressiveness)
    print(f"VAD aggressiveness={aggressiveness}, recording {duration_s}s from default mic ...")

    start = time.monotonic()
    frame_count = 0

    with sd.RawInputStream(
        samplerate=SAMPLE_RATE, channels=1, dtype="int16", blocksize=FRAME_SAMPLES
    ) as stream:
        while time.monotonic() - start < duration_s:
            raw, overflow = stream.read(FRAME_SAMPLES)
            pcm = bytes(raw)
            votes = 0
            for i in range(SUB_FRAMES):
                sub = pcm[i * VAD_FRAME_BYTES : (i + 1) * VAD_FRAME_BYTES]
                if len(sub) == VAD_FRAME_BYTES:
                    try:
                        if vad.is_speech(sub, SAMPLE_RATE):
                            votes += 1
                    except Exception:
                        pass
            ratio = votes / SUB_FRAMES
            label = "SPEECH" if ratio >= 0.4 else "silence"
            energy_db = 10 * np.log10(np.frombuffer(pcm, dtype="<i2").astype(float).var() + 1e-9)
            frame_count += 1
            bar = "#" * int(ratio * 20)
            print(f"frame {frame_count:4d} | {label:<7s} | speech={ratio:.2f} [{bar:<20s}] | rms {energy_db:6.1f} dBfs")

    print(f"\n{frame_count} frames processed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VAD test")
    parser.add_argument("--aggressiveness", type=int, default=2, choices=[0, 1, 2, 3])
    parser.add_argument("--duration", type=float, default=10.0)
    args = parser.parse_args()
    run(args.aggressiveness, args.duration)
