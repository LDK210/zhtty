from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Load runtime configuration from environment variables and an optional .env file."""

    app_name: str = "HirePilot"
    database_url: str = "sqlite:///./hirepilot.db"
    upload_dir: str = "uploads"
    max_upload_size_mb: int = 10
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    log_level: str = "INFO"
    debug: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def mock_mode(self) -> bool:
        """Return whether deterministic local AI responses should be used."""
        return not self.openai_api_key

    @property
    def upload_path(self) -> Path:
        """Return the configured local upload directory."""
        return Path(self.upload_dir)

    @property
    def cors_origin_list(self) -> list[str]:
        """Return the configured CORS origins as a normalized list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings instance."""
    return Settings()
