from datetime import datetime
from typing import Any

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field


class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: Any) -> Any:
        from pydantic_core import core_schema

        return core_schema.no_info_after_validator_function(cls.validate, core_schema.str_schema())

    @classmethod
    def validate(cls, value: str | ObjectId) -> ObjectId:
        if isinstance(value, ObjectId):
            return value
        if not ObjectId.is_valid(value):
            raise ValueError("Invalid ObjectId")
        return ObjectId(value)


class MongoModel(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True, json_encoders={ObjectId: str})

    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")


class EventDoc(MongoModel):
    name: str
    start_date: datetime
    end_date: datetime
    organizer_ids: list[str] = []


class AttendeeDoc(MongoModel):
    event_id: str
    firstname: str
    lastname: str
    socials: dict[str, str | None] = {}
    verified_profile: dict[str, Any] = {}
    profile_pic_url: str | None = None
    face_embedding: list[float] | None = None
    larp_score: float | None = None
    opt_in: dict[str, bool] = {"public": True, "friends": True, "private": False}
    processing_status: str = "pending"


class SessionDoc(MongoModel):
    wearer_id: str
    subject_id: str | None = None
    device_id: str
    started_at: datetime
    ended_at: datetime | None = None
    score: float | None = None
    score_label: str | None = None


class UtteranceDoc(MongoModel):
    session_id: str
    transcript: str
    audio_clip_url: str | None = None
    started_at: datetime
    ended_at: datetime


class ClaimDoc(MongoModel):
    utterance_id: str
    text: str
    claim_type: str
    confidence: float


class FlagDoc(MongoModel):
    claim_id: str
    session_id: str
    subject_id: str
    verified_against: str
    severity: str
    dispute_status: str = "none"
    created_at: datetime


class DeviceDoc(MongoModel):
    owner_attendee_id: str | None = None
    auth_token: str
    paired_at: datetime | None = None
    last_seen: datetime | None = None


class UserDoc(MongoModel):
    email: str
    attendee_id: str | None = None
    github_login: str | None = None
    pi_paired_token: str | None = None
