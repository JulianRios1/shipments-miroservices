FROM python:3.11-slim

WORKDIR /app

# Instalar solo Flask (no necesitamos más)
RUN pip install --no-cache-dir flask gunicorn

# Copiar solo el archivo principal
COPY services/email_service/src/main_simple.py /app/main.py

# Puerto por defecto
ENV PORT=8083

# Ejecutar con gunicorn para producción
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 main:app
