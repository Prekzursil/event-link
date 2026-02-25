import logging

from app.logging_utils import log_event, log_warning


def test_log_event_sanitizes_message_and_drops_dynamic_context(caplog):
    with caplog.at_level(logging.INFO, logger="event_link"):
        log_event("hello\nworld", user_input="attacker\r\nforged")

    record = caplog.records[-1]
    assert record.getMessage() == "event=helloworld"
    assert not hasattr(record, "user_input")
    assert not hasattr(record, "context_keys")


def test_log_warning_does_not_emit_sensitive_kwargs(caplog):
    with caplog.at_level(logging.WARNING, logger="event_link"):
        log_warning(
            "security_event",
            password="super-secret",
            nested={"token": "abc123", "safe": "ok"},
            details=[{"authorization": "Bearer X"}, "line1\nline2"],
        )

    record = caplog.records[-1]
    assert record.getMessage() == "event=security_event"
    assert not hasattr(record, "password")
    assert not hasattr(record, "nested")
    assert not hasattr(record, "details")
    assert not hasattr(record, "authorization")
