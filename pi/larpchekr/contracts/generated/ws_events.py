# Manually maintained until datamodel-codegen can handle the full schema set.
# NOTE: datamodel-codegen 0.25.6 cannot generate from the full contracts/schemas/
# directory because profile-facts.schema.json has a hyphen in its filename,
# producing invalid Python import syntax (`from ..profile-facts import ...`).
# ws_envelope.py IS generated; this file covers only the Pi-relevant WS event
# payloads (Pi → backend sends + backend → Pi receives).
#
# Source of truth: contracts/schemas/ws-events.schema.json
# Re-generate ws_envelope.py with: make contracts
# Update this file manually whenever ws-events.schema.json changes for Pi events.

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Shared enums (from _common.schema.json)
# ---------------------------------------------------------------------------


class Severity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class Speaker(str, Enum):
    self_ = "self"
    partner = "partner"
    unknown = "unknown"


# ---------------------------------------------------------------------------
# Pi → backend payloads
# ---------------------------------------------------------------------------


class PiHello(BaseModel):
    """Payload for type='pi_hello'. First message after WS connect."""

    device_id: str
    firmware_version: str
    battery_pct: int | None = Field(None, ge=0, le=100)


class SessionStart(BaseModel):
    """Payload for type='session_start'."""

    session_id: str


class SessionEnd(BaseModel):
    """Payload for type='session_end'."""

    session_id: str
    reason: str


class AudioMeta(BaseModel):
    """Payload for type='audio_meta'. Scopes the following binary PCM frames."""

    sample_rate: int = Field(16000)
    encoding: str = Field("pcm_s16le")
    channels: int = Field(1)
    frame_ms: int = Field(250)
    speaker_hint: Speaker | None = None


class FrameSnapshot(BaseModel):
    """Payload for type='frame_snapshot'."""

    image_b64: str
    width: int = Field(..., le=640)
    height: int = Field(..., le=480)


class Heartbeat(BaseModel):
    """Payload for type='heartbeat'."""

    battery_pct: int = Field(..., ge=0, le=100)
    cpu_temp_c: float
    buffer_seconds: float = Field(..., ge=0)


class BufferDrainBracket(BaseModel):
    """Payload for type='buffer_drain_start' and 'buffer_drain_end'."""

    session_id: str | None = None
    buffered_seconds: float


# ---------------------------------------------------------------------------
# Backend → Pi payloads
# ---------------------------------------------------------------------------


class HapticPulse(BaseModel):
    """Payload for type='haptic_pulse'."""

    severity: Severity
    pattern: list[int] = Field(..., min_length=1, max_length=16)


class RecordingIndicatorState(str, Enum):
    off = "off"
    armed = "armed"
    recording = "recording"


class RecordingIndicator(BaseModel):
    """Payload for type='recording_indicator'. Drives Pi LED."""

    state: RecordingIndicatorState


class SessionAck(BaseModel):
    """Payload for type='session_ack'."""

    session_id: str


class ErrorPayload(BaseModel):
    """Payload for type='error'."""

    code: str
    message: str
