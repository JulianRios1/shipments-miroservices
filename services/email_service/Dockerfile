# Email Service - Dockerfile
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=True
ENV PYTHONDONTWRITEBYTECODE=True
ENV PYTHONPATH=/app
ENV PORT=8083

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home --shell /bin/bash app

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/shared_utils /app/services/shared_utils
COPY services/email_service/src /app/services/email_service/src

RUN chown -R app:app /app
USER app

WORKDIR /app/services/email_service/src
CMD exec python main.py

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

LABEL service="email-service" version="2.0.0"
