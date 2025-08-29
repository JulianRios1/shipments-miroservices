# 📦 Shipments Microservices

Sistema de procesamiento de paquetes de imágenes para envíos en Google Cloud Platform.

## 🚀 Arquitectura Actual (Simplificada)

```
JSON Files → Cloud Workflow → Image Processing → ZIP Files
                    ↓
              Email Service
```

## 📋 Servicios

| Servicio | Función |
|----------|---------|
| Image Processing | Procesa imágenes y crea ZIPs |
| Email Service | Envía notificaciones |

## 🔧 Uso Rápido

```bash
# Ejecutar workflow
gcloud workflows run shipment-processing-workflow \
  --location=us-central1 \
  --project=airy-semiotics-468114-a7 \
  --data='{"processing_uuid": "test-123", "packages": ["gs://path/to/file.json"]}'
```

## 📁 Estructura

```
├── services/          # Microservicios
├── workflows/         # Cloud Workflows
├── docs/             # Documentación
└── examples/         # Ejemplos
```

## 📄 Documentación

- [Formato JSON](docs/JSON_FORMAT_SPECIFICATION.md)
- [Estructura del Proyecto](docs/README_STRUCTURE.md)
- [Ejemplos](examples/)

---
Sistema simplificado sin base de datos ✅
