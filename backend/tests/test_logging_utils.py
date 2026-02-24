import logging

from app.logging_utils import log_event, log_warning


def test_log_event_sanitizes_newlines_in_message_and_fields(caplog):
    with caplog.at_level(logging.INFO, logger="event_link"):
        log_event("hello\nworld", user_input="attacker\r\nforged")

    record = caplog.records[-1]
    assert record.getMessage() == "hello\\nworld"
    assert record.user_input == "attacker\\r\\nforged"


def test_log_warning_redacts_sensitive_fields_recursively(caplog):
    with caplog.at_level(logging.WARNING, logger="event_link"):
        log_warning(
            "security_event",
            password="super-secret",
            nested={"token": "abc123", "safe": "ok"},
            details=[{"authorization": "Bearer X"}, "line1\nline2"],
        )

    record = caplog.records[-1]
    assert record.password == "[REDACTED]"
    assert record.nested["token"] == "[REDACTED]"
    assert record.nested["safe"] == "ok"
    assert record.details[0]["authorization"] == "[REDACTED]"
    assert record.details[1] == "line1\\nline2"
