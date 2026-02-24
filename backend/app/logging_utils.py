import contextvars
import json
import logging
from typing import Any, Dict
from uuid import uuid4

SENSITIVE_KEY_MARKERS = (
    "password",
    "passwd",
    "pwd",
    "token",
    "secret",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "set-cookie",
)


def _sanitize_string(value: str) -> str:
    return value.replace("\r", "\\r").replace("\n", "\\n")


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(marker in lowered for marker in SENSITIVE_KEY_MARKERS)


def _sanitize_value(value: Any, key: str | None = None) -> Any:
    if key and _is_sensitive_key(key):
        return "[REDACTED]"
    if isinstance(value, str):
        return _sanitize_string(value)
    if isinstance(value, dict):
        return {dict_key: _sanitize_value(dict_value, str(dict_key)) for dict_key, dict_value in value.items()}
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_sanitize_value(item) for item in value)
    return value


def sanitize_log_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {key: _sanitize_value(value, key) for key, value in payload.items()}


request_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get() or "-"
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
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
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RequestIdFilter())
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    root.addHandler(handler)
    # Silence overly noisy loggers or inherit root formatting
    for noisy in ("uvicorn.access",):
        logging.getLogger(noisy).handlers.clear()


class RequestIdMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
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
            if message.get("type") == "http.response.start":
                headers_list = message.setdefault("headers", [])
                headers_list.append((b"x-request-id", request_id.encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            request_id_ctx.reset(token)


logger = logging.getLogger("event_link")


def log_event(message: str, **kwargs: Any) -> None:
    logger.info(_sanitize_string(message), extra=sanitize_log_payload(kwargs))


def log_warning(message: str, **kwargs: Any) -> None:
    logger.warning(_sanitize_string(message), extra=sanitize_log_payload(kwargs))


def log_error(message: str, **kwargs: Any) -> None:
    logger.error(_sanitize_string(message), extra=sanitize_log_payload(kwargs))
