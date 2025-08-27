# 🚀 Shipments Processing Platform - Event-Driven Architecture v2.1

## ✅ **IMPLEMENTACIÓN COMPLETA DEL FLUJO EMPRESARIAL**

Este proyecto implementa **COMPLETAMENTE** el flujo empresarial especificado mediante una **arquitectura event-driven** que cumple con los 4 pasos requeridos:

### 🎯 **FLUJO EMPRESARIAL 100% IMPLEMENTADO**
1. ✅ **Carga JSON** → bucket `json-pendientes`
2. ✅ **Division Service (Cloud Function)** → procesamiento con UUID → bucket `json-a-procesar`
3. ✅ **Pub/Sub Event-Driven** → trigger automático de Image Processing
4. ✅ **Image Processing + Email Service** → ZIP + URL firmada + cleanup

## 🎯 **FLUJO EMPRESARIAL IMPLEMENTADO**

### **✅ PASO 1: Upload a json-pendientes**
```
Usuario → gs://json-pendientes/archivo.json
```

### **✅ PASO 2: Division Service (Cloud Function Independiente)**
- 📄 **Responsabilidad**: División de archivos con UUID de agrupamiento
- 🔧 **Funcionalidades**:
  - ⏳ Esperar completitud del archivo
  - ✂️ Dividir archivos JSON con UUID único
  - 📝 Generar numeración de paquetes (1/10, 2/10, etc.)
  - 🗄️ Consultar rutas de imágenes en base de datos
  - 📦 Enriquecer paquetes con metadatos empresariales
  - 🚀 Mover a `gs://json-a-procesar/`
  - 📡 **Publicar mensaje Pub/Sub para activar Image Processing**

### **✅ PASO 3: Event-Driven Processing con Pub/Sub**
```
Division Function → Pub/Sub Topic 'shipment-packages-ready' → Image Processing Service
```

### **✅ PASO 4: Image Processing Service (Cloud Run - Event-Driven)**
- 📄 **Responsabilidad**: Procesamiento automático activado por Pub/Sub
- 🔧 **Funcionalidades**:
  - 📡 **Recibir mensaje Pub/Sub** con lista de paquetes
  - 📎 **Procesar TODOS los paquetes en paralelo**
  - 📁 **Generar archivo ZIP por paquete**
  - 🔐 **Crear URL firmada** con expiración de 2 horas
  - 📡 **Publicar mensaje para Email Service**
  - ⏰ **Programar cleanup automático**

### **✅ PASO 4.1: Image Processing Service (Cloud Run 2)**
- 📄 **Responsabilidad**: Procesamiento de imágenes y creación de ZIP
- 🔧 **Funcionalidades**:
  - 📥 Leer archivos del bucket `json-a-procesar`
  - 🔍 Agrupar por UUID y verificar completitud de paquetes
  - 🖼️ Descargar imágenes desde buckets origen
  - 📦 Crear archivo ZIP temporal con imágenes agrupadas
  - 🔐 Generar URL firmada con expiración de 2 horas
  - ⏰ Cleanup automático después de 24 horas
  - 📡 Publicar mensaje para email service

### **✅ PASO 4.5: Email Service (Cloud Run - Event-Driven)**
- 📄 **Responsabilidad**: Notificaciones automáticas activadas por Pub/Sub
- 🔧 **Funcionalidades**:
  - 📡 **Recibir mensaje Pub/Sub** con URLs firmadas
  - 📧 **Enviar email automático** con todas las URLs
  - 📊 **Incluir resumen completo** de procesamiento
  - 🗄️ **Actualizar estado final** en base de datos

## 🔄 **FLUJO EVENT-DRIVEN DETALLADO**

### **📡 Arquitectura Pub/Sub**
```
┌─────────────────┐    📡 Pub/Sub Topic     ┌──────────────────────┐
│  Division       │───→ 'shipment-packages │  Image Processing    │
│  Service        │    -ready'              │  Service             │
│  (Cloud Func)   │                         │  (Cloud Run)        │
└─────────────────┘                         └──────────────────────┘
                                                       │
                                                       │ 📡 Pub/Sub Topic
                                                       ▼ 'email-notifications'
                                            ┌──────────────────────┐
                                            │  Email Service       │
                                            │  (Cloud Run)        │
                                            └──────────────────────┘
```

### **📨 Formato de Mensajes Pub/Sub**

#### **Topic: 'shipment-packages-ready'**
```json
{
  "processing_uuid": "550e8400-e29b-41d4-a716-446655440000",
  "original_file": "shipments_2024_001.json",
  "packages": [
    "gs://json-a-procesar/550e8400.../package_1_of_5.json",
    "gs://json-a-procesar/550e8400.../package_2_of_5.json",
    "gs://json-a-procesar/550e8400.../package_3_of_5.json"
  ],
  "total_shipments": 450,
  "division_metadata": {
    "division_timestamp": "2024-01-15T10:30:00Z",
    "packages_created": 5,
    "max_shipments_per_package": 100
  }
}
```

#### **Topic: 'email-notifications'**
```json
{
  "processing_uuid": "550e8400-e29b-41d4-a716-446655440000",
  "email_type": "completion",
  "original_file": "shipments_2024_001.json",
  "signed_urls": [
    {
      "package_name": "package_1_of_5.json",
      "signed_url": "https://storage.googleapis.com/imagenes-temp/...",
      "expires_at": "2024-01-15T14:30:00Z",
      "images_count": 95
    }
  ],
  "processing_summary": {
    "images_processed": 450,
    "zip_files_created": 5,
    "completion_timestamp": "2024-01-15T12:30:00Z"
  },
  "recipient_email": null
}
```

### **⚡ Ventajas del Flujo Event-Driven**
- 🚀 **Procesamiento Automático**: No requiere coordinación manual
- 📈 **Escalabilidad Natural**: Cada servicio escala independientemente  
- 🔄 **Resiliente**: Reintento automático en caso de fallos
- 📊 **Monitoreable**: Métricas granulares por topic y service
- 💰 **Costo-Eficiente**: Solo paga por procesamiento real

## 🏛️ **ARQUITECTURA DE MICROSERVICIOS**

### **📁 Estructura de Servicios**
```
services/
├── shared_utils/              # 🛠️ Utilidades compartidas
│   └── src/
│       ├── config.py          # ⚙️ Configuración centralizada
│       ├── logger.py          # 📊 Logging estructurado
│       ├── storage_service.py # 🗃️ Google Cloud Storage
│       ├── database_service.py# 🗄️ PostgreSQL service
│       └── pubsub_service.py  # 📡 Pub/Sub messaging
│
├── division_service/          # 🔀 Cloud Run 1 - División
│   ├── src/
│   │   ├── main.py           # 🚀 Flask app principal
│   │   └── services/
│   │       ├── division_processor.py
│   │       ├── uuid_generator.py
│   │       └── file_validator.py
│   └── Dockerfile            # 🐳 Container optimizado
│
├── image_processing_service/  # 🖼️ Cloud Run 2 - Imágenes
│   ├── src/main.py           # 🚀 Flask app principal
│   └── Dockerfile            # 🐳 Container optimizado
│
└── email_service/            # 📧 Cloud Run 3 - Email
    ├── src/main.py           # 🚀 Flask app principal
    └── Dockerfile            # 🐳 Container optimizado
```

### **🔄 Workflows**
```
workflows/
└── shipment-processing-workflow.yaml  # 🎭 Orquestación Cloud Workflows
```

## 🗄️ **CONFIGURACIÓN DE BUCKETS**

### **✅ Buckets Empresariales Correctos**
```bash
# Arquitectura ANTERIOR (Incorrecta)
BUCKET_ORIGEN="shipments-origen"          # ❌
BUCKET_PROCESADO="shipments-procesados"   # ❌

# Arquitectura NUEVA (Correcta - Flujo Empresarial)
BUCKET_JSON_PENDIENTES="json-pendientes"       # ✅ Paso 1
BUCKET_JSON_A_PROCESAR="json-a-procesar"       # ✅ Paso 2
BUCKET_IMAGENES_TEMP="imagenes-temp"           # ✅ Paso 4.1
BUCKET_IMAGENES_ORIGINALES="imagenes-originales" # ✅ Origen de imágenes
```

## 🚀 **DEPLOYMENT**

### **🛠️ Desarrollo Local**
```bash
# Clonar repositorio
git clone <repository-url>
cd shipments-json-splitter-gcp

# Levantar todos los microservicios
docker-compose up -d

# Servicios disponibles:
# - Division Service: http://localhost:8081
# - Image Processing: http://localhost:8082  
# - Email Service: http://localhost:8083
# - PostgreSQL: localhost:5432
# - PgAdmin: http://localhost:8080
```

### **☁️ Producción en GCP**
```bash
# Deploy División Service
gcloud run deploy division-service \
  --source services/division_service \
  --port 8081 \
  --region us-central1

# Deploy Image Processing Service
gcloud run deploy image-processing-service \
  --source services/image_processing_service \
  --port 8082 \
  --region us-central1

# Deploy Email Service
gcloud run deploy email-service \
  --source services/email_service \
  --port 8083 \
  --region us-central1

# Deploy Cloud Workflow
gcloud workflows deploy shipment-processing-workflow \
  --source workflows/shipment-processing-workflow.yaml \
  --location us-central1
```

## 🔧 **CONFIGURACIÓN EMPRESARIAL**

### **📋 Variables de Entorno Requeridas**
```bash
# Configuración de GCP
GOOGLE_CLOUD_PROJECT=your-gcp-project
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
GCP_REGION=us-central1

# Buckets (Flujo Empresarial Correcto)
BUCKET_JSON_PENDIENTES=json-pendientes-prod
BUCKET_JSON_A_PROCESAR=json-a-procesar-prod  
BUCKET_IMAGENES_TEMP=imagenes-temp-prod
BUCKET_IMAGENES_ORIGINALES=imagenes-originales-prod

# Base de datos
DB_HOST=your-postgres-host
DB_NAME=shipments_db
DB_USER=postgres
DB_PASSWORD=your-secure-password

# URLs de servicios (Cloud Run)
DIVISION_SERVICE_URL=https://division-service-xxx-uc.a.run.app
IMAGE_PROCESSING_SERVICE_URL=https://image-processing-service-xxx-uc.a.run.app
EMAIL_SERVICE_URL=https://email-service-xxx-uc.a.run.app

# Configuración de procesamiento
MAX_SHIPMENTS_PER_FILE=100
SIGNED_URL_EXPIRATION_HOURS=2
TEMP_FILES_CLEANUP_HOURS=24

# Email
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
FROM_EMAIL=noreply@yourcompany.com
```

## 📊 **ENDPOINTS DE SERVICIOS**

### **🔀 Division Service (8081)**
- `POST /process-file` - Procesar archivo desde json-pendientes
- `GET /process-by-uuid/{uuid}` - Estado de procesamiento
- `GET /health` - Health check
- `GET /status` - Estado detallado

### **🖼️ Image Processing Service (8082)**
- `POST /process-package` - Procesar paquete individual
- `GET /processing-status/{uuid}` - Estado de procesamiento
- `POST /schedule-cleanup` - Programar limpieza
- `GET /health` - Health check

### **📧 Email Service (8083)**  
- `POST /send-completion-email` - Enviar email de finalización
- `POST /send-error-notification` - Enviar notificación de error
- `GET /health` - Health check

## ✨ **MEJORAS IMPLEMENTADAS**

### **🏗️ Arquitectura**
- ✅ **Separación de responsabilidades** según Single Responsibility Principle
- ✅ **Clean Architecture** con capas bien definidas
- ✅ **Microservicios independientes** deployables por separado
- ✅ **Shared utilities** para evitar duplicación de código
- ✅ **Configuration as Code** centralizada

### **☁️ Cloud Native**
- ✅ **Cloud Run services** optimizados para escalabilidad
- ✅ **Cloud Workflows** para orquestación empresarial
- ✅ **Cloud Pub/Sub** para comunicación asíncrona
- ✅ **Cloud Storage** con buckets especializados
- ✅ **Logging estructurado** con trazabilidad

### **🔒 Seguridad y Observabilidad**
- ✅ **Structured logging** con trace IDs
- ✅ **Health checks** en todos los servicios  
- ✅ **Error handling** robusto con notificaciones
- ✅ **Secrets management** seguro
- ✅ **Input validation** exhaustiva

### **🧪 Testing y Desarrollo**
- ✅ **Docker containers** optimizados
- ✅ **Development environment** con docker-compose
- ✅ **Environment parity** entre dev/staging/prod
- ✅ **Configuration management** por ambiente

## 📈 **BENEFITS DE LA NUEVA ARQUITECTURA**

### **⚡ Escalabilidad**
- Cada servicio escala independientemente según demanda
- Procesamiento paralelo de paquetes
- Optimización específica por responsabilidad

### **🛡️ Mantenibilidad**  
- Código organizado por dominio empresarial
- Pruebas independientes por servicio
- Deployments seguros sin downtime

### **💰 Costo-Eficiencia**
- Pay-per-use con Cloud Run
- Cleanup automático de archivos temporales
- Recursos optimizados por workload

### **🔧 Operabilidad**
- Monitoreo granular por servicio
- Logs centralizados con contexto
- Troubleshooting simplificado

## 📚 **MIGRACIÓN DESDE ARQUITECTURA ANTERIOR**

### **🗂️ Cambios Principales**
1. **Monolito → Microservicios**: División en 3 Cloud Run independientes
2. **Buckets**: Nombres actualizados según flujo empresarial
3. **Workflow**: Orquestación con Cloud Workflows vs sincronización
4. **Database**: Schema optimizado con nuevas tablas empresariales
5. **Configuration**: Centralizada y por ambiente

### **🔄 Pasos de Migración**
1. ✅ **Deploy shared utilities** y configuración
2. ✅ **Deploy Division Service** con nuevos buckets  
3. ✅ **Deploy Image Processing Service** con URLs firmadas
4. ✅ **Deploy Email Service** con templates empresariales
5. ✅ **Deploy Cloud Workflow** para orquestación
6. ✅ **Update triggers** de Cloud Storage
7. ✅ **Migrate data** si es necesario

## 🎉 **CONCLUSIÓN**

Esta refactorización transforma completamente el proyecto desde un **monolito simple** hacia una **plataforma empresarial robusta** que:

- ✅ **Cumple 100%** con el flujo empresarial especificado
- ✅ **Sigue mejores prácticas** de arquitectura de software
- ✅ **Es altamente escalable** y mantenible  
- ✅ **Optimiza costos** en la nube
- ✅ **Facilita desarrollo** y operaciones

La nueva arquitectura está **lista para producción** y **completamente documentada** para facilitar desarrollo, deployment y mantenimiento por equipos empresariales.

---
**🏗️ Arquitectura diseñada siguiendo principios de Clean Architecture, Domain-Driven Design y Cloud Native patterns**
