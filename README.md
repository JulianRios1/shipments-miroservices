# Shipments JSON Splitter - GCP

Aplicación Python Flask para procesar y dividir archivos JSON de datos de envíos utilizando Google Cloud Platform y PostgreSQL.

## Características

- ✅ Procesamiento de archivos JSON de envíos
- ✅ Integración con Google Cloud Storage
- ✅ Base de datos PostgreSQL para almacenar datos de envíos
- ✅ API REST con Flask
- ✅ Dockerización completa
- ✅ Logging estructurado

## Requisitos

- Python 3.11+
- Docker y Docker Compose
- Cuenta de Google Cloud Platform
- PostgreSQL

## Instalación

### 1. Clonar el repositorio
```bash
git clone <repository-url>
cd shipments-json-splitter-gcp
```

### 2. Configurar variables de entorno
Copiar el archivo `.env` y actualizar las variables:
```bash
cp .env .env.local
# Editar .env.local con tus valores específicos
```

### 3. Configurar credenciales de GCP
Colocar tu archivo de credenciales de servicio de GCP en:
```
credentials/service-account-key.json
```

### 4. Instalar dependencias (desarrollo local)
```bash
python -m venv venv
      # En Linux/Mac
# o
venv\Scripts\activate     # En Windows
pip install -r requirements.txt
```

## Uso con Docker

### Levantar todos los servicios
```bash
docker-compose up -d
```

Esto iniciará:
- Aplicación Flask en `http://localhost:5000`
- PostgreSQL en `localhost:5432`
- PgAdmin en `http://localhost:8080`

### Ver logs
```bash
docker-compose logs -f app
```

### Detener servicios
```bash
docker-compose down
```

## Estructura del proyecto

```
shipments-json-splitter-gcp/
├── app/
│   ├── routes/          # Endpoints de la API
│   ├── services/        # Lógica de negocio
│   └── utils/           # Utilidades y helpers
├── migrations/          # Scripts de migración de BD
├── credentials/         # Credenciales de GCP
├── Dockerfile           # Configuración de Docker
├── docker-compose.yml   # Orquestación de servicios
├── requirements.txt     # Dependencias de Python
└── README.md           # Este archivo
```

## Desarrollo

### Ejecutar tests
```bash
pytest
```

### Formatear código
```bash
black app/
isort app/
flake8 app/
```

## Variables de entorno principales

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `GOOGLE_CLOUD_PROJECT` | ID del proyecto GCP | `my-gcp-project` |
| `DB_HOST` | Host de PostgreSQL | `localhost` |
| `DB_NAME` | Nombre de la base de datos | `shipments_db` |
| `GCS_BUCKET_NAME` | Bucket de Cloud Storage | `shipments-data-bucket` |

## Contribuir

1. Fork el repositorio
2. Crear una rama feature (`git checkout -b feature/amazing-feature`)
3. Commit los cambios (`git commit -m 'Add amazing feature'`)
4. Push a la rama (`git push origin feature/amazing-feature`)
5. Abrir un Pull Request

## Licencia

Este proyecto está bajo la Licencia MIT.
