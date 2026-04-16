"""Support module: task queue shared."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from . import models


def _coerce_bool(value: object) -> bool:
    """Implements the coerce bool helper."""
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "t", "yes", "y", "on"}
    return bool(value)


def _load_personalization_exclusions(*, db: Session, user_id: int) -> tuple[set[int], set[int]]:
    """Loads the personalization exclusions resource."""
    hidden_tag_ids = {
        int(row[0])
        for row in db.query(models.user_hidden_tags.c.tag_id)
        .filter(models.user_hidden_tags.c.user_id == user_id)
        .all()
    }
    blocked_organizer_ids = {
        int(row[0])
        for row in db.query(models.user_blocked_organizers.c.organizer_id)
        .filter(models.user_blocked_organizers.c.user_id == user_id)
        .all()
    }
    return hidden_tag_ids, blocked_organizer_ids


def _preferred_lang(value: str | None) -> str:
    """Implements the preferred lang helper."""
    return "ro" if not value or value == "system" else value


def _notification_exists(*, db: Session, dedupe_key: str) -> bool:
    """Implements the notification exists helper."""
    return (
        db.query(models.NotificationDelivery.id)
        .filter(models.NotificationDelivery.dedupe_key == dedupe_key)
        .first()
        is not None
    )


def _send_email_payload(
    *,
    to_email: str,
    subject: str,
    body_text: str,
    body_html: str | None,
    context: dict[str, Any],
) -> dict[str, Any]:
    """Implements the send email payload helper."""
    return {
        "to_email": to_email,
        "subject": subject,
        "body_text": body_text,
        "body_html": body_html,
        "context": context,
    }
