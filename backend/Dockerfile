FROM python:3.12-slim AS backend

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app
RUN addgroup --system eventlink && adduser --system --ingroup eventlink eventlink && chown -R eventlink:eventlink /app

USER eventlink

# Default command: run migrations then start the API
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.api:app --host 0.0.0.0 --port 8000"]
