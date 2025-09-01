# Image Processing Service - Dockerfile
# Servicio optimizado para procesamiento de imágenes en Cloud Run

FROM python:3.11-slim

# Configurar variables de entorno
ENV PYTHONUNBUFFERED=True
ENV PYTHONDONTWRITEBYTECODE=True
ENV PYTHONPATH=/app
ENV PORT=8082

# Instalar dependencias del sistema necesarias
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Crear usuario no-root para seguridad
RUN useradd --create-home --shell /bin/bash app

# Configurar directorio de trabajo
WORKDIR /app

# Copiar requirements y instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar shared_utils (dependencias compartidas)
COPY services/shared_utils /app/services/shared_utils

# Copiar código fuente del servicio
COPY services/image_processing_service/src /app/services/image_processing_service/src

# Crear directorios temporales con permisos apropiados
RUN mkdir -p /tmp/shipments_processing && \
    chown -R app:app /app /tmp/shipments_processing

# Cambiar a usuario no-root
USER app

# Configurar punto de entrada
WORKDIR /app/services/image_processing_service/src
CMD exec python main.py

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Etiquetas para metadata
LABEL \
    service="image-processing-service" \
    version="2.0.0" \
    description="Servicio para procesamiento de imágenes, creación de ZIP y URLs firmadas" \
    maintainer="shipments-platform-team"
