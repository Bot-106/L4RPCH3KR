from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongo_url: str = "mongodb://localhost:27017"
    mongo_db: str = "larpchekr"
    jwt_secret: str = "dev-secret-change-me"
    version: str = "0.1.0"
    fixture_mode: bool = False

    @field_validator("fixture_mode", mode="before")
    @classmethod
    def _strip_fixture_mode(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v
    llm_provider: str = "openai"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    llm_model: str = "gpt-4o-mini"

    whisper_model: str = "base.en"
    whisper_device: str = "auto"
    whisper_compute_type: str = "auto"
    asr_chunk_seconds: float = 3.0


settings = Settings()
