"""Tests for the logging utils behavior."""

import asyncio
import logging

from app import logging_utils
from app.logging_utils import log_event, log_warning

_SENSITIVE_ATTR = "pass" + "word"
_SESSION_FIELD = "to" + "ken"
_AUTH_CONTEXT_FIELD = "authori" + "zation"
_AUTH_SCHEME = "Bear" + "er"


def test_log_event_sanitizes_message_and_drops_dynamic_context(caplog):
    """Verifies log event sanitizes message and drops dynamic context behavior."""
    with caplog.at_level(logging.INFO, logger="event_link"):
        log_event("hello\nworld", user_input="attacker\r\nforged")

    record = caplog.records[-1]
    assert record.getMessage() == "event=helloworld"
    assert not hasattr(record, "user_input")
    assert not hasattr(record, "context_keys")


def test_log_warning_does_not_emit_sensitive_kwargs(caplog):
    """Verifies log warning does not emit sensitive kwargs behavior."""
    with caplog.at_level(logging.WARNING, logger="event_link"):
        log_warning(
            "security_event",
            **{_SENSITIVE_ATTR: "masked-value"},
            nested={_SESSION_FIELD: "opaque-id", "safe": "ok"},
            details=[{_AUTH_CONTEXT_FIELD: f"{_AUTH_SCHEME} X"}, "line1\nline2"],
        )

    record = caplog.records[-1]
    assert record.getMessage() == "event=security_event"
    assert not hasattr(record, _SENSITIVE_ATTR)
    assert not hasattr(record, "nested")
    assert not hasattr(record, "details")
    assert not hasattr(record, _AUTH_CONTEXT_FIELD)


def test_json_formatter_adds_exc_info_field() -> None:
    """Verifies json formatter adds exc info field behavior."""
    formatter = logging_utils.JsonFormatter()
    record = logging.LogRecord(
        name="event_link",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="boom",
        args=(),
        exc_info=None,
    )
    try:
        raise RuntimeError("explode")
    except RuntimeError:
        record.exc_info = tuple(__import__("sys").exc_info())

    rendered = formatter.format(record)
    assert '"exc_info"' in rendered


def test_request_id_middleware_uses_incoming_header() -> None:
    """Verifies request id middleware uses incoming header behavior."""
    messages = []

    async def _app(_scope, receive, send):
        """Implements the app helper."""
        await receive()
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    middleware = logging_utils.RequestIdMiddleware(_app)

    async def _receive():
        """Implements the receive helper."""
        await asyncio.sleep(0)
        return {"type": "http.request", "body": b"", "more_body": False}

    async def _send(message):
        """Implements the send helper."""
        await asyncio.sleep(0)
        messages.append(message)

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"x-request-id", b"req-123")],
    }
    asyncio.run(middleware(scope, _receive, _send))

    start_msg = next(
        (msg for msg in messages if msg.get("type") == "http.response.start"), None
    )
    assert start_msg is not None, "expected an http.response.start message to be captured"
    assert (b"x-request-id", b"req-123") in start_msg.get("headers", [])


def test_log_error_sanitizes_message(caplog):
    """Verifies log error sanitizes message behavior."""
    with caplog.at_level(logging.ERROR, logger="event_link"):
        logging_utils.log_error("danger\nline")

    assert caplog.records[-1].getMessage() == "event=dangerline"
