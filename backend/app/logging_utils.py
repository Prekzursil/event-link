"""Structured logging helpers and request-id propagation middleware."""

import contextvars
import json
import logging
from typing import Any, Dict
from uuid import uuid4


def _sanitize_log_text(value: str) -> str:
    """Strip line breaks from log messages before emission."""
    # Prevent forged multi-line entries in downstream plain-text log sinks.
    return value.replace("\r", "").replace("\n", "")


request_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)


def _inject_request_id(record: logging.LogRecord) -> bool:
    """Attach the request id to every log record."""
    record.request_id = request_id_ctx.get() or "-"
    return True


class JsonFormatter(logging.Formatter):
    """Render log records as JSON payloads."""

    def format(self, record: logging.LogRecord) -> str:
        """Serialize a log record into the API log schema."""
        payload: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        # Attach any extra fields already on the record
        for key, value in record.__dict__.items():
            if key in payload or key.startswith("_"):
                continue
            if key in {
                "args",
                "msg",
                "levelno",
                "levelname",
                "pathname",
                "filename",
                "module",
                "exc_text",
                "exc_info",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
            }:
                continue
            payload[key] = value
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: int = logging.INFO) -> None:
    """Configure root logging with JSON output and request ids."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(_inject_request_id)
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    root.addHandler(handler)
    # Silence overly noisy loggers or inherit root formatting
    for noisy in ("uvicorn.access",):
        logging.getLogger(noisy).handlers.clear()


class RequestIdMiddleware:
    """Attach a request identifier to each HTTP request lifecycle."""

    def __init__(self, app):
        """Store the downstream ASGI application."""
        self.app = app

    async def __call__(self, scope, receive, send):
        """Inject and echo a request id for HTTP traffic."""
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        request_id = None
        headers = dict(scope.get("headers") or [])
        if b"x-request-id" in headers:
            request_id = headers[b"x-request-id"].decode() or None
        if not request_id:
            request_id = str(uuid4())
        token = request_id_ctx.set(request_id)

        async def send_wrapper(message):
            """Append the request id header to the outgoing HTTP response."""
            if message.get("type") == "http.response.start":
                headers_list = message.setdefault("headers", [])
                headers_list.append((b"x-request-id", request_id.encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            request_id_ctx.reset(token)


logger = logging.getLogger("event_link")
_EVENT_LOG_TEMPLATE = "event=%s"


def log_event(message: str, **_kwargs: Any) -> None:
    """Emit an informational structured event log."""
    # Fixed-format logging avoids user-controlled format strings and avoids
    # leaking raw dynamic context data.
    logger.info(_EVENT_LOG_TEMPLATE, _sanitize_log_text(message))


def log_warning(message: str, **_kwargs: Any) -> None:
    """Emit a warning structured event log."""
    logger.warning(_EVENT_LOG_TEMPLATE, _sanitize_log_text(message))


def log_error(message: str, **_kwargs: Any) -> None:
    """Emit an error structured event log."""
    logger.error(_EVENT_LOG_TEMPLATE, _sanitize_log_text(message))
