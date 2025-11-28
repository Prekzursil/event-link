import contextvars
import json
import logging
from uuid import uuid4
from typing import Any, Dict

request_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar('request_id', default=None)

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
            if key in {"args", "msg", "levelno", "levelname", "pathname", "filename", "module", "exc_text", "exc_info", "stack_info", "lineno", "funcName", "created", "msecs", "relativeCreated", "thread", "threadName", "processName", "process"}:
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
    logger.info(message, extra=kwargs)

def log_warning(message: str, **kwargs: Any) -> None:
    logger.warning(message, extra=kwargs)

def log_error(message: str, **kwargs: Any) -> None:
    logger.error(message, extra=kwargs)

