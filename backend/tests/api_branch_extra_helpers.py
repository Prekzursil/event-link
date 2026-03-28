"""Shared helpers for API branch-closure edge tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app import api, models, schemas


def auth_header(token: str) -> dict[str, str]:
    """Builds the auth header helper used by the test."""
    return {"Authorization": f"Bearer {token}"}


def event_payload(start_time: str, **overrides):
    """Creates the event payload helper value."""
    payload = {
        "title": "Coverage Event",
        "description": "desc",
        "category": "Edu",
        "start_time": start_time,
        "city": "Cluj",
        "location": "Hall",
        "max_seats": 10,
        "tags": ["alpha"],
    }
    payload.update(overrides)
    return payload


class ScalarQuery:
    """Test double for scalar query access."""

    def __init__(self, value):
        """Initializes the test double."""
        self._value = value

    def filter(self, *_args, **_kwargs):
        """Returns the fake query for chained filters."""
        return self

    def scalar(self):
        """Returns the configured scalar value."""
        return self._value


class ScalarDb:
    """Test double for scalar db access."""

    def __init__(self, value):
        """Initializes the test double."""
        self._value = value

    def query(self, *_args, **_kwargs):
        """Returns the scalar query for the intercepted call."""
        return ScalarQuery(self._value)
