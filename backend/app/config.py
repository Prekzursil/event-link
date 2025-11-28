import json

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost:4200",
    "http://127.0.0.1:4200",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]


class Settings(BaseSettings):
    database_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_minutes: int = 60 * 24 * 30
    allowed_origins: list[str] = DEFAULT_ALLOWED_ORIGINS
    auto_create_tables: bool = False
    auto_run_migrations: bool = False
    organizer_invite_code: str | None = None
    email_enabled: bool = True
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_sender: str | None = None
    smtp_use_tls: bool = True
    
    model_config = SettingsConfigDict(env_file=".topsecret", extra="ignore")

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value):
        if value is None or value == "":
            return list(DEFAULT_ALLOWED_ORIGINS)

        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return [origin for origin in parsed if origin]
            except json.JSONDecodeError:
                pass

            parsed = [origin.strip() for origin in value.split(",")]
            return [origin for origin in parsed if origin]

        if isinstance(value, (list, tuple)):
            return [origin for origin in value if origin]

        raise ValueError("allowed_origins must be a list or comma-separated string")


settings = Settings()
