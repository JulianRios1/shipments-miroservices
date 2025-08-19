# ⚡ **GUÍA DE DEPLOYMENT RÁPIDO A GCP**
## Shipments Processing Platform v2.0 - Microservicios

> **⏱️ Tiempo estimado:** 40 minutos  
> **💰 Costo estimado:** $5-15 USD/mes (desarrollo)  
> **🎯 Resultado:** Plataforma empresarial completa en producción

---

## 📋 **TABLA DE CONTENIDOS**

1. [Requisitos Previos](#-requisitos-previos)
2. [Configuración Inicial](#-configuración-inicial)
3. [Configurar Entorno GCP](#-configurar-entorno-gcp)
4. [Configurar Credenciales](#-configurar-credenciales)
5. [Desplegar Microservicios](#-desplegar-microservicios)
6. [Verificar Deployment](#-verificar-deployment)
7. [Configuración Final](#-configuración-final)
8. [Prueba End-to-End](#-prueba-end-to-end)
9. [Monitoreo y Logs](#-monitoreo-y-logs)
10. [Troubleshooting](#-troubleshooting)

---

## 🔧 **REQUISITOS PREVIOS**

### **1. Google Cloud SDK**

```bash
# Instalar gcloud CLI (si no está instalado)
curl https://sdk.cloud.google.com | bash
exec -l $SHELL

# Inicializar y autenticar
gcloud init
gcloud auth login
```

### **2. Proyecto GCP**

- ✅ Proyecto de GCP activo con facturación habilitada
- ✅ Permisos de administrador o Editor
- ✅ APIs de Cloud Run y Cloud Build habilitadas

### **3. Herramientas Locales**

```bash
# Verificar instalaciones requeridas
gcloud --version          # Google Cloud SDK
docker --version          # Docker (para desarrollo local)
git --version             # Git
```

**Salida esperada:**
```
Google Cloud SDK 456.0.0
Docker version 24.0.0
git version 2.34.1
```

---

## 🚀 **CONFIGURACIÓN INICIAL**

### **Paso 1: Preparar el Repositorio**

```bash
# Navegar al directorio del proyecto
cd /aplicativos/shipments-json-splitter-gcp

# Verificar estructura de archivos
ls -la
```

**Deberías ver:**
```
services/
├── division_service/
├── image_processing_service/
├── email_service/
└── shared_utils/
workflows/
setup-gcp.sh
deploy.sh
DEPLOYMENT-GUIDE.md
```

### **Paso 2: Hacer Scripts Ejecutables**

```bash
# Dar permisos de ejecución
chmod +x setup-gcp.sh
chmod +x deploy.sh

# Verificar permisos
ls -la setup-gcp.sh deploy.sh
```

---

## ⚙️ **CONFIGURAR ENTORNO GCP**

### **Ejecutar Script de Configuración**

```bash
# Ejecutar configuración automática
./setup-gcp.sh
```

**El script te solicitará:**

1. **PROJECT_ID de GCP**
   ```
   Ingresa tu PROJECT_ID de GCP: mi-proyecto-shipments
   ```

2. **Región** (opcional)
   ```
   Ingresa la REGION (default: us-central1): us-central1
   ```

3. **Cloud SQL** (opcional)
   ```
   ¿Quieres crear una instancia de Cloud SQL PostgreSQL? (y/n): y
   ```

### **¿Qué hace este script automáticamente?**

✅ **Habilita APIs necesarias:**
- Cloud Run API
- Cloud Build API  
- Cloud Storage API
- Pub/Sub API
- Cloud Workflows API
- Cloud Scheduler API
- Cloud SQL API

✅ **Crea buckets de almacenamiento:**
- `PROJECT_ID-json-pendientes`
- `PROJECT_ID-json-a-procesar`
- `PROJECT_ID-imagenes-temp`
- `PROJECT_ID-imagenes-originales`

✅ **Genera archivo de configuración:**
- `.env.production` con todas las variables

✅ **Configura Cloud SQL** (opcional):
- Instancia PostgreSQL
- Base de datos `shipments_db`
- Usuario y contraseña

**⏱️ Tiempo:** ~10 minutos

---

## 🔐 **CONFIGURAR CREDENCIALES**

### **Editar Configuración de Producción**

```bash
# Abrir archivo de configuración
nano .env.production

# O usar tu editor preferido
code .env.production
```

### **Variables Críticas a Configurar:**

#### **🗄️ Base de Datos**
```env
# Si usas Cloud SQL (reemplaza con IP real)
DB_HOST=10.128.0.3
DB_NAME=shipments_db
DB_USER=postgres
DB_PASSWORD=tu-password-super-seguro-2024

# Si usas base de datos externa
DB_HOST=tu-servidor-postgres.com
DB_PORT=5432
```

#### **📧 Configuración de Email**
```env
# Gmail (recomendado para desarrollo)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=tu-email@gmail.com
SMTP_PASSWORD=tu-app-password-gmail
FROM_EMAIL=noreply@tuempresa.com

# SendGrid (recomendado para producción)
# SMTP_HOST=smtp.sendgrid.net
# SMTP_PORT=587
# SMTP_USER=apikey
# SMTP_PASSWORD=tu-sendgrid-api-key
```

#### **☁️ URLs de Servicios**
```env
# Se actualizan automáticamente después del deploy
DIVISION_SERVICE_URL=https://division-service-PROJECT_ID.REGION.run.app
IMAGE_PROCESSING_SERVICE_URL=https://image-processing-service-PROJECT_ID.REGION.run.app
EMAIL_SERVICE_URL=https://email-service-PROJECT_ID.REGION.run.app
```

### **💡 Consejos de Seguridad**

- 🔒 Usa contraseñas fuertes (mínimo 16 caracteres)
- 🔑 Para Gmail, usa **App Passwords**, no tu contraseña personal
- 🛡️ Para producción, considera **Secret Manager** de GCP

**⏱️ Tiempo:** ~5 minutos

---

## 🚀 **DESPLEGAR MICROSERVICIOS**

### **Configurar Variables de Entorno**

```bash
# Reemplaza con tu PROJECT_ID real
export GOOGLE_CLOUD_PROJECT="mi-proyecto-shipments"
export GCP_REGION="us-central1"

# Verificar configuración
echo "Proyecto: $GOOGLE_CLOUD_PROJECT"
echo "Región: $GCP_REGION"
```

### **Ejecutar Deployment Completo**

```bash
# Ejecutar script de deployment
./deploy.sh
```

### **¿Qué despliega este script?**

El script ejecuta el deployment en **orden secuencial** para evitar dependencias:

#### **🔀 PASO 1: Division Service (Cloud Run 1)**
```
🚀 Deploying division-service...
✅ division-service deployed successfully
```
- **Puerto:** 8081
- **Función:** División de archivos con UUID
- **Memoria:** 1GB, CPU: 1, Concurrencia: 80

#### **🖼️ PASO 2: Image Processing Service (Cloud Run 2)**
```
🚀 Deploying image-processing-service...
✅ image-processing-service deployed successfully
```
- **Puerto:** 8082  
- **Función:** Procesamiento de imágenes, ZIP, URLs firmadas
- **Memoria:** 1GB, CPU: 1, Concurrencia: 80

#### **📧 PASO 3: Email Service (Cloud Run 3)**
```
🚀 Deploying email-service...
✅ email-service deployed successfully
```
- **Puerto:** 8083
- **Función:** Envío de emails con templates
- **Memoria:** 1GB, CPU: 1, Concurrencia: 80

#### **🔄 PASO 4: Cloud Workflow**
```
🔄 Deploying shipment-processing-workflow...
✅ Cloud Workflow deployed successfully
```
- **Función:** Orquestación de microservicios
- **Procesamiento:** Paralelo por paquetes

### **Salida Esperada del Deployment:**

```
==========================================
🎉 DEPLOYMENT COMPLETADO EXITOSAMENTE
==========================================

📋 URLs de Servicios:
• Division Service:       https://division-service-mi-proyecto.us-central1.run.app
• Image Processing:       https://image-processing-service-mi-proyecto.us-central1.run.app
• Email Service:          https://email-service-mi-proyecto.us-central1.run.app

📋 Endpoints Principales:
• Health Check:           GET /health
• Status Check:           GET /status
• Process File:           POST /process-file
• Process Package:        POST /process-package
• Send Email:            POST /send-completion-email
```

**⏱️ Tiempo:** ~15 minutos

---

## ✅ **VERIFICAR DEPLOYMENT**

### **Health Checks Automáticos**

```bash
# Verificar que todos los servicios responden
curl -f https://division-service-$GOOGLE_CLOUD_PROJECT.$GCP_REGION.run.app/health
curl -f https://image-processing-service-$GOOGLE_CLOUD_PROJECT.$GCP_REGION.run.app/health  
curl -f https://email-service-$GOOGLE_CLOUD_PROJECT.$GCP_REGION.run.app/health
```

**Respuesta esperada:**
```json
{
  "status": "healthy",
  "service": "division-service", 
  "version": "2.0.0",
  "timestamp": "2024-XX-XXTXX:XX:XX"
}
```

### **Status Checks Detallados**

```bash
# Verificar estado detallado con dependencias
curl https://division-service-$GOOGLE_CLOUD_PROJECT.$GCP_REGION.run.app/status | jq
```

**Respuesta esperada:**
```json
{
  "service": "division-service",
  "version": "2.0.0", 
  "status": "ready",
  "dependencies": {
    "database": "healthy",
    "storage": "healthy",
    "pubsub": "healthy"
  },
  "configuration": {
    "bucket_pendientes": "mi-proyecto-json-pendientes",
    "max_shipments_per_file": 100
  }
}
```

### **Verificar Cloud Run Services**

```bash
# Listar todos los servicios desplegados
gcloud run services list --region=$GCP_REGION

# Ver detalles de servicio específico
gcloud run services describe division-service --region=$GCP_REGION
```

**⏱️ Tiempo:** ~3 minutos

---

## 🔗 **CONFIGURACIÓN FINAL**

### **Configurar Storage Triggers**

```bash
# Crear trigger automático para bucket json-pendientes
gcloud eventarc triggers create bucket-trigger \
    --destination-run-service=division-service \
    --destination-run-region=$GCP_REGION \
    --event-filters="type=google.cloud.storage.object.v1.finalized" \
    --event-filters="bucket=$GOOGLE_CLOUD_PROJECT-json-pendientes" \
    --location=$GCP_REGION
```

### **Configurar Pub/Sub Topics (Opcional)**

```bash
# Crear topics para comunicación entre servicios
gcloud pubsub topics create file-processed
gcloud pubsub topics create images-ready  
gcloud pubsub topics create email-send
gcloud pubsub topics create processing-errors
```

### **Verificar Triggers**

```bash
# Listar triggers configurados
gcloud eventarc triggers list --location=$GCP_REGION
```

**⏱️ Tiempo:** ~5 minutos

---

## 🧪 **PRUEBA END-TO-END**

### **Crear Archivo de Prueba**

```bash
# Crear archivo JSON de prueba
cat > test-shipment.json << EOF
{
  "nombre_archivo": "test-shipment.json",
  "envios": [
    {
      "id": "12345",
      "destinatario": "Juan Pérez", 
      "direccion": "Calle 123, Ciudad",
      "peso": 2.5,
      "estado": "pendiente"
    },
    {
      "id": "12346", 
      "destinatario": "María García",
      "direccion": "Avenida 456, Ciudad",
      "peso": 1.8,
      "estado": "pendiente"
    }
  ],
  "metadata": {
    "fecha_creacion": "2024-01-19",
    "version": "1.0"
  }
}
EOF
```

### **Subir al Bucket de Entrada**

```bash
# Subir archivo al bucket json-pendientes
gsutil cp test-shipment.json gs://$GOOGLE_CLOUD_PROJECT-json-pendientes/

# Verificar que se subió correctamente
gsutil ls gs://$GOOGLE_CLOUD_PROJECT-json-pendientes/
```

### **Monitorear Procesamiento**

```bash
# Ver logs de Division Service en tiempo real
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=division-service" \
  --limit 10 \
  --format="value(textPayload,timestamp)"
```

### **Verificar Resultados**

```bash
# Verificar que el archivo fue procesado y movido
gsutil ls gs://$GOOGLE_CLOUD_PROJECT-json-a-procesar/

# Verificar logs de todos los servicios
gcloud logging read \
  "resource.type=cloud_run_revision AND (resource.labels.service_name=division-service OR resource.labels.service_name=image-processing-service OR resource.labels.service_name=email-service)" \
  --limit 20 \
  --format="table(timestamp,resource.labels.service_name,textPayload)"
```

**⏱️ Tiempo:** ~3 minutos

---

## 📊 **MONITOREO Y LOGS**

### **Dashboards en Cloud Console**

1. **Cloud Run Dashboard:**
   ```
   https://console.cloud.google.com/run?project=PROJECT_ID
   ```

2. **Cloud Storage Dashboard:**
   ```
   https://console.cloud.google.com/storage?project=PROJECT_ID
   ```

3. **Cloud Workflows Dashboard:**
   ```
   https://console.cloud.google.com/workflows?project=PROJECT_ID
   ```

### **Comandos de Monitoreo**

#### **Ver Métricas de Servicios**
```bash
# Métricas de Cloud Run
gcloud run services list --region=$GCP_REGION

# Estado de workflows
gcloud workflows list --location=$GCP_REGION

# Uso de buckets
gsutil du -sh gs://$GOOGLE_CLOUD_PROJECT-*
```

#### **Logs Estructurados**
```bash
# Logs por servicio
gcloud logging read "resource.labels.service_name=division-service" --limit=50

# Logs por severidad
gcloud logging read "resource.type=cloud_run_revision AND severity>=WARNING" --limit=20

# Logs de errores únicamente
gcloud logging read "resource.type=cloud_run_revision AND severity=ERROR" --limit=10
```

#### **Métricas de Performance**
```bash
# Ver revisiones activas
gcloud run revisions list --service=division-service --region=$GCP_REGION

# Tráfico por revisión
gcloud run services describe division-service --region=$GCP_REGION --format="value(status.traffic)"
```

---

## 🚨 **TROUBLESHOOTING**

### **Problemas Comunes y Soluciones**

#### **❌ Error: "Service not found"**

**Síntoma:**
```bash
curl: (22) The requested URL returned error: 404 Not Found
```

**Solución:**
```bash
# Verificar que el servicio fue desplegado
gcloud run services list --region=$GCP_REGION

# Si no aparece, re-ejecutar deployment
./deploy.sh
```

#### **❌ Error: "Permission denied"**

**Síntoma:**
```
ERROR: (gcloud.run.deploy) User [user@email.com] does not have permission to access...
```

**Solución:**
```bash
# Verificar permisos actuales
gcloud projects get-iam-policy $GOOGLE_CLOUD_PROJECT

# Añadir permisos necesarios
gcloud projects add-iam-policy-binding $GOOGLE_CLOUD_PROJECT \
    --member="user:tu-email@gmail.com" \
    --role="roles/run.admin"

gcloud projects add-iam-policy-binding $GOOGLE_CLOUD_PROJECT \
    --member="user:tu-email@gmail.com" \
    --role="roles/storage.admin"
```

#### **❌ Error de conexión a base de datos**

**Síntoma:**
```json
{
  "dependencies": {
    "database": "unhealthy"
  }
}
```

**Solución:**
```bash
# Verificar que Cloud SQL está ejecutándose
gcloud sql instances list

# Obtener IP de Cloud SQL
gcloud sql instances describe shipments-postgres --format="value(ipAddresses[0].ipAddress)"

# Actualizar .env.production con la IP correcta
# Luego re-desplegar
./deploy.sh
```

#### **❌ Buckets inaccesibles**

**Síntoma:**
```
AccessDeniedException: 403 Caller does not have storage.objects.list access
```

**Solución:**
```bash
# Verificar permisos de buckets
gsutil iam get gs://$GOOGLE_CLOUD_PROJECT-json-pendientes

# Añadir permisos al service account
gsutil iam ch serviceAccount:$(gcloud projects describe $GOOGLE_CLOUD_PROJECT --format="value(projectNumber)")-compute@developer.gserviceaccount.com:storage.admin gs://$GOOGLE_CLOUD_PROJECT-json-pendientes
```

#### **❌ Error en envío de emails**

**Síntoma:**
```
SMTPAuthenticationError: Username and Password not accepted
```

**Solución:**
```bash
# Verificar credenciales SMTP en .env.production
# Para Gmail, usar App Passwords:
# 1. Habilitar 2FA en Gmail
# 2. Generar App Password específica
# 3. Usar esa password en SMTP_PASSWORD

# Probar conectividad SMTP
curl https://email-service-$GOOGLE_CLOUD_PROJECT.$GCP_REGION.run.app/test-email \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"to_email": "tu-email@gmail.com"}'
```

### **Comandos de Debugging**

```bash
# Ver logs detallados de errores
gcloud logging read "resource.type=cloud_run_revision AND severity>=ERROR AND timestamp>=\"$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S)Z\"" --limit=50

# Conectar directamente a Cloud SQL
gcloud sql connect shipments-postgres --user=postgres --database=shipments_db

# Verificar configuración de servicios
gcloud run services describe division-service --region=$GCP_REGION --format="yaml"

# Test manual de endpoints
curl -X POST https://division-service-$GOOGLE_CLOUD_PROJECT.$GCP_REGION.run.app/process-file \
  -H "Content-Type: application/json" \
  -d '{"test": true}'
```

---

## 🎉 **DEPLOYMENT EXITOSO**

### **✅ Checklist Final**

Después de un deployment exitoso, deberías tener:

- [ ] **3 Cloud Run Services** ejecutándose y respondiendo a health checks
- [ ] **4 Storage Buckets** creados con permisos correctos
- [ ] **1 Cloud Workflow** desplegado para orquestación
- [ ] **Storage Triggers** configurados para procesamiento automático
- [ ] **Cloud SQL** funcionando (si fue configurado)
- [ ] **Logs estructurados** visibles en Cloud Console
- [ ] **Prueba end-to-end** exitosa

### **🌐 URLs de Servicios Activas**

```
✅ Division Service:       https://division-service-PROJECT_ID.REGION.run.app
✅ Image Processing:       https://image-processing-service-PROJECT_ID.REGION.run.app
✅ Email Service:          https://email-service-PROJECT_ID.REGION.run.app
```

### **📊 Métricas Esperadas**

- **Latencia promedio:** < 200ms por request
- **Disponibilidad:** > 99.9%
- **Escalabilidad:** 0-10 instancias automáticamente
- **Costo mensual:** $5-15 USD (desarrollo), $30-100 USD (producción)

---

## 🔄 **ACTUALIZACIONES FUTURAS**

### **Deploy de Cambios**

```bash
# Para cambios en el código, simplemente re-ejecutar
git pull  # Si hay cambios remotos
./deploy.sh

# Deploy de servicio específico
gcloud run deploy division-service \
    --source services/division_service \
    --region $GCP_REGION
```

### **Rollback a Versión Anterior**

```bash
# Listar revisiones
gcloud run revisions list --service=division-service --region=$GCP_REGION

# Cambiar tráfico a revisión anterior
gcloud run services update-traffic division-service \
    --region=$GCP_REGION \
    --to-revisions=PREVIOUS_REVISION=100
```

### **Escalabilidad**

```bash
# Ajustar límites de instancias
gcloud run services update division-service \
    --region=$GCP_REGION \
    --min-instances=1 \
    --max-instances=20
```

---

## 📞 **SOPORTE Y RECURSOS**

### **Documentación Oficial**
- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Cloud Workflows Documentation](https://cloud.google.com/workflows/docs)
- [Cloud Storage Documentation](https://cloud.google.com/storage/docs)

### **Monitoreo y Alertas**
- [Cloud Monitoring](https://console.cloud.google.com/monitoring)
- [Cloud Logging](https://console.cloud.google.com/logs)
- [Error Reporting](https://console.cloud.google.com/errors)

### **Comunidad y Soporte**
- [Google Cloud Community](https://cloud.google.com/community)
- [Stack Overflow - google-cloud-platform](https://stackoverflow.com/questions/tagged/google-cloud-platform)

---

## 🏆 **CONCLUSIÓN**

**¡Felicitaciones!** Has desplegado exitosamente una **arquitectura de microservicios empresarial completa** en Google Cloud Platform que:

- ✅ **Cumple 100%** con el proceso empresarial especificado
- ✅ **Escala automáticamente** según demanda
- ✅ **Procesa archivos** de forma paralela y eficiente
- ✅ **Maneja errores** de forma robusta
- ✅ **Envía notificaciones** automáticamente
- ✅ **Mantiene logs estructurados** para debugging
- ✅ **Optimiza costos** con serverless computing

**Tu plataforma está lista para procesar shipments en producción** con capacidad empresarial y escalabilidad cloud-native. 🚀

---

**📝 Última actualización:** Enero 2024  
**🏗️ Versión de arquitectura:** 2.0  
**☁️ Plataforma:** Google Cloud Platform  
**🔧 Patrón arquitectónico:** Microservicios + Event-Driven + Serverless
