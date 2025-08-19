# Usar Python 3.11 slim como imagen base
FROM python:3.11-slim

# Establecer directorio de trabajo
WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copiar archivos de dependencias
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código de la aplicación
COPY app/ ./app/
COPY migrations/ ./migrations/

# Crear directorio para credenciales
RUN mkdir -p credentials

# Crear usuario no-root para seguridad
RUN adduser --disabled-password --gecos '' appuser
RUN chown -R appuser:appuser /app
USER appuser

# Exponer el puerto
EXPOSE 5000

# Variables de entorno
ENV PYTHONPATH=/app
ENV FLASK_APP=app/main.py

# Comando de inicio
CMD ["python", "-m", "flask", "run", "--host=0.0.0.0", "--port=5000"]
