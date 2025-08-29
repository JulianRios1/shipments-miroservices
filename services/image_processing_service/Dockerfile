FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias mínimas
RUN pip install --no-cache-dir \
    flask \
    gunicorn \
    google-cloud-storage

# Copiar solo el archivo principal
COPY services/image_processing_service/src/main_simple.py /app/main.py

# Puerto por defecto
ENV PORT=8082

# Ejecutar con gunicorn para producción
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 main:app
