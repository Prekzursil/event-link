"""Application settings loaded from environment variables."""

import json

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost:4200",
    "http://127.0.0.1:4200",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


def _is_empty_setting(value: object) -> bool:
    """Return whether an environment-provided setting is effectively empty."""
    return value is None or value == ""


def _json_list(value: str) -> list[object] | None:
    """Parse a JSON list string when possible."""
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, list) else None


def _string_items(values: list[object] | tuple[object, ...], *, lower: bool = False) -> list[str]:
    """Normalize an iterable of raw items into trimmed strings."""
    items: list[str] = []
    for raw in values:
        text = str(raw).strip()
        if not text:
            continue
        items.append(text.lower() if lower else text)
    return items


def _parse_list_setting(value: object, *, lower: bool = False) -> list[str]:
    """Accept JSON, CSV, or list inputs for string-list settings."""
    if isinstance(value, str):
        parsed = _json_list(value)
        if parsed is not None:
            return _string_items(parsed, lower=lower)
        return _string_items(tuple(value.split(",")), lower=lower)
    if isinstance(value, (list, tuple)):
        return _string_items(value, lower=lower)
    raise ValueError


class Settings(BaseSettings):
    """Runtime configuration for the API and background workers."""

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

    recommendations_use_ml_cache: bool = True
    recommendations_cache_max_age_seconds: int = 60 * 60 * 24
    recommendations_realtime_refresh_enabled: bool = False
    recommendations_realtime_refresh_min_interval_seconds: int = 300
    recommendations_realtime_refresh_top_n: int = 50
    recommendations_online_learning_enabled: bool = False
    recommendations_online_learning_dwell_threshold_seconds: int = 10
    recommendations_online_learning_decay_half_life_hours: int = 72
    recommendations_online_learning_max_score: float = 10.0

    personalization_guardrails_enabled: bool = False
    personalization_guardrails_days: int = 7
    personalization_guardrails_min_impressions: int = 200
    personalization_guardrails_ctr_drop_ratio: float = 0.5
    personalization_guardrails_conversion_drop_ratio: float = 0.5
    personalization_guardrails_click_to_register_window_hours: int = 72

    analytics_enabled: bool = True
    analytics_rate_limit: int = 120
    analytics_rate_window_seconds: int = 60

    experiments_personalization_ml_percent: int = 0

    # `allowed_origins` supports comma-separated strings or JSON lists.
    # Disable pydantic-settings JSON decoding so our validator can handle
    # both formats.
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
        """Normalize allowed CORS origins from env-compatible inputs."""
        if _is_empty_setting(value):
            return list(DEFAULT_ALLOWED_ORIGINS)
        try:
            return _parse_list_setting(value)
        except ValueError as exc:
            raise ValueError("allowed_origins must be a list or comma-separated string") from exc

    @field_validator("admin_emails", mode="before")
    @classmethod
    def parse_admin_emails(cls, value):
        """Normalize administrator email addresses from env-compatible inputs."""
        if _is_empty_setting(value):
            return []
        try:
            return _parse_list_setting(value, lower=True)
        except ValueError as exc:
            raise ValueError("admin_emails must be a list or comma-separated string") from exc


settings = Settings()
