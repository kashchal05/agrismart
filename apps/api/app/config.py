from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App configuration, read from environment / .env (prefix AGRISMART_)."""

    model_config = SettingsConfigDict(env_prefix="AGRISMART_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://localhost:5432/agrismart"
    jwt_secret: str = "dev-insecure-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # one week
    cors_origins: str = "http://localhost:5174,http://127.0.0.1:5174"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
