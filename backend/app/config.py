import json

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost:4200",
    "http://127.0.0.1:4200",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173"
]


class Settings(BaseSettings):
    database_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_minutes: int = 60 * 24 * 30
    allowed_origins: list[str] = DEFAULT_ALLOWED_ORIGINS
    admin_emails: list[str] = []
    auto_create_tables: bool = False
    auto_run_migrations: bool = False
    email_enabled: bool = True
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_sender: str | None = None
    smtp_use_tls: bool = True

    task_queue_enabled: bool = False
    task_queue_poll_interval_seconds: float = 1.0
    task_queue_max_attempts: int = 3
    task_queue_stale_after_seconds: int = 300

    public_api_rate_limit: int = 60
    public_api_rate_window_seconds: int = 60

    maintenance_mode_registrations_disabled: bool = False
    
    # `allowed_origins` supports comma-separated strings or JSON lists; disable pydantic-settings JSON decoding
    # so our validator can handle both formats.
    model_config = SettingsConfigDict(
        env_file=".topsecret",
        extra="ignore",
        case_sensitive=False,
        enable_decoding=False,
        env_ignore_empty=True,
    )

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

    @field_validator("admin_emails", mode="before")
    @classmethod
    def parse_admin_emails(cls, value):
        if value is None or value == "":
            return []

        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return [str(email).strip().lower() for email in parsed if str(email).strip()]
            except json.JSONDecodeError:
                pass

            parsed = [email.strip().lower() for email in value.split(",")]
            return [email for email in parsed if email]

        if isinstance(value, (list, tuple)):
            return [str(email).strip().lower() for email in value if str(email).strip()]

        raise ValueError("admin_emails must be a list or comma-separated string")


settings = Settings()
