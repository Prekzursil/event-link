"""Development entrypoint for running the FastAPI application."""

import ipaddress
import os

import uvicorn

from app.api import app

_DEFAULT_HOST = "127.0.0.1"


def _is_unspecified_host(host: str) -> bool:
    """Return whether the host string resolves to an unspecified bind address."""
    candidate = host.strip()
    if candidate.startswith("[") and candidate.endswith("]"):
        candidate = candidate[1:-1]
    try:
        address = ipaddress.ip_address(candidate)
        return address == type(address)(0)
    except ValueError:
        return False


def _resolve_host() -> str:
    """Resolve and validate the host used by the development entrypoint."""
    host = os.environ.get("APP_HOST", _DEFAULT_HOST).strip() or _DEFAULT_HOST
    if _is_unspecified_host(host):
        raise RuntimeError(
            "APP_HOST must not bind to all network interfaces in this entrypoint."
        )
    return host


if __name__ == "__main__":
    port = int(os.environ.get("APP_PORT", "8000"))
    uvicorn.run(app, host=_resolve_host(), port=port)
