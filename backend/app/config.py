from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongo_url: str = "mongodb://localhost:27017"
    mongo_db: str = "larpchekr"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "dev-secret-change-me"
    version: str = "0.1.0"
    whisper_model: str = "base.en"
    whisper_device: str = "auto"
    whisper_compute_type: str = "auto"
    asr_chunk_seconds: float = 3.0


settings = Settings()
