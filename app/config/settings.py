from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    telegram_bot_token: SecretStr | None = Field(None, alias="TELEGRAM_BOT_TOKEN")
    database_url: str = Field("sqlite+aiosqlite:///./linkdooni.db", alias="DATABASE_URL")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    config_dir: Path = Field(Path("app/config"), alias="CONFIG_DIR")
    auto_create_db: bool = Field(True, alias="LINKDOONI_AUTO_CREATE_DB")
    metadata_timeout_seconds: float = Field(8.0, alias="METADATA_TIMEOUT_SECONDS")
    metadata_max_response_bytes: int = Field(1_500_000, alias="METADATA_MAX_RESPONSE_BYTES")
    metadata_max_redirects: int = Field(5, alias="METADATA_MAX_REDIRECTS")


@lru_cache
def get_settings() -> Settings:
    return Settings()
