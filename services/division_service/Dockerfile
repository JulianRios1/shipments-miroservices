# Division Service Dockerfile
# Cloud Run optimizado para procesamiento de división de archivos

FROM python:3.11-slim

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Configurar directorio de trabajo
WORKDIR /app

# Copiar requirements específicos del servicio
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar shared utils
COPY services/shared_utils /app/services/shared_utils

# Copiar código del servicio
COPY services/division_service/src /app/services/division_service/src

# Crear usuario no-root para seguridad
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Variables de entorno
ENV PYTHONPATH="/app/services/division_service/src:/app/services/shared_utils/src"
ENV PORT=8081
ENV PYTHONUNBUFFERED=1

# Exponer puerto
EXPOSE 8081

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8081/health || exit 1

# Comando de inicio
CMD ["python", "/app/services/division_service/src/main.py"]
