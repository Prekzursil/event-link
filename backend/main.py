import os

import uvicorn

from app.api import app


if __name__ == "__main__":
    host = os.environ.get("APP_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = int(os.environ.get("APP_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)
