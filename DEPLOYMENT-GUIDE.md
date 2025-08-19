# 🚀 **GUÍA COMPLETA DE DEPLOYMENT A GCP**

## 📋 **REQUISITOS PREVIOS**

### 1. **Google Cloud SDK**
```bash
# Instalar gcloud CLI
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
gcloud init
```

### 2. **Proyecto GCP**
- Tener un proyecto de GCP activo
- Facturación habilitada
- Permisos de administrador

### 3. **Herramientas Locales**
```bash
# Verificar instalaciones
gcloud --version
docker --version
git --version
```

---

## 🎯 **PROCESO DE DEPLOYMENT**

### **PASO 1: Configurar Entorno GCP**

```bash
# Ejecutar script de configuración
./setup-gcp.sh
```

Este script:
- ✅ Configura el proyecto y región
- ✅ Habilita todas las APIs necesarias
- ✅ Crea los buckets de almacenamiento
- ✅ Genera archivo .env.production
- ✅ (Opcional) Crea instancia Cloud SQL

### **PASO 2: Configurar Variables de Entorno**

```bash
# Configurar variables para esta sesión
export GOOGLE_CLOUD_PROJECT="tu-project-id"
export GCP_REGION="us-central1"
```

### **PASO 3: Actualizar Configuración**

Edita el archivo `.env.production` con tus credenciales:

```bash
# Editar configuración de producción
nano .env.production
```

**Configuraciones importantes a actualizar:**
```env
# Base de datos
DB_HOST=10.x.x.x  # IP de Cloud SQL
DB_PASSWORD=tu-password-seguro

# Email
SMTP_USER=tu-email@gmail.com
SMTP_PASSWORD=tu-app-password
FROM_EMAIL=noreply@tuempresa.com
```

### **PASO 4: Desplegar Microservicios**

```bash
# Ejecutar deployment completo
./deploy.sh
```

Este script despliega **TODOS** los microservicios:
- 🔀 Division Service (puerto 8081)
- 🖼️ Image Processing Service (puerto 8082)
- 📧 Email Service (puerto 8083)
- 🔄 Cloud Workflow

---

## ⚙️ **CONFIGURACIÓN POST-DEPLOYMENT**

### **1. Configurar Storage Triggers**

```bash
# Crear trigger de Pub/Sub para bucket json-pendientes
gcloud eventarc triggers create bucket-trigger \
    --destination-run-service=division-service \
    --destination-run-region=$GCP_REGION \
    --event-filters="type=google.cloud.storage.object.v1.finalized" \
    --event-filters="bucket=$GOOGLE_CLOUD_PROJECT-json-pendientes" \
    --location=$GCP_REGION
```

### **2. Configurar Pub/Sub Topics**

```bash
# Crear topics necesarios
gcloud pubsub topics create file-processed
gcloud pubsub topics create images-ready
gcloud pubsub topics create email-send
gcloud pubsub topics create processing-errors

# Crear suscripciones
gcloud pubsub subscriptions create workflow-trigger-sub \
    --topic=file-processed \
    --push-endpoint=https://workflowexecutions.googleapis.com/v1/projects/$GOOGLE_CLOUD_PROJECT/locations/$GCP_REGION/workflows/shipment-processing-workflow/executions
```

### **3. Configurar IAM Permissions**

```bash
# Dar permisos entre servicios
gcloud projects add-iam-policy-binding $GOOGLE_CLOUD_PROJECT \
    --member="serviceAccount:division-service@$GOOGLE_CLOUD_PROJECT.iam.gserviceaccount.com" \
    --role="roles/storage.admin"

gcloud projects add-iam-policy-binding $GOOGLE_CLOUD_PROJECT \
    --member="serviceAccount:image-processing-service@$GOOGLE_CLOUD_PROJECT.iam.gserviceaccount.com" \
    --role="roles/storage.admin"
```

---

## 🧪 **VERIFICACIÓN DEL DEPLOYMENT**

### **1. Health Checks**

```bash
# Verificar todos los servicios
curl https://division-service-$GOOGLE_CLOUD_PROJECT.$GCP_REGION.run.app/health
curl https://image-processing-service-$GOOGLE_CLOUD_PROJECT.$GCP_REGION.run.app/health
curl https://email-service-$GOOGLE_CLOUD_PROJECT.$GCP_REGION.run.app/health
```

### **2. Status Checks**

```bash
# Verificar estado detallado
curl https://division-service-$GOOGLE_CLOUD_PROJECT.$GCP_REGION.run.app/status
```

### **3. Test End-to-End**

```bash
# Subir archivo de prueba
gsutil cp test-file.json gs://$GOOGLE_CLOUD_PROJECT-json-pendientes/

# Monitorear logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=division-service" --limit 50
```

---

## 📊 **MONITOREO Y LOGS**

### **Ver Logs en Tiempo Real**

```bash
# Division Service
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=division-service" --limit 50 --format="value(textPayload)"

# Image Processing Service  
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=image-processing-service" --limit 50 --format="value(textPayload)"

# Email Service
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=email-service" --limit 50 --format="value(textPayload)"
```

### **Métricas en Cloud Console**
- Cloud Run → Métricas
- Cloud Storage → Métricas de buckets
- Cloud SQL → Métricas de base de datos

---

## 🔧 **COMANDOS ÚTILES**

### **Gestión de Servicios**

```bash
# Listar servicios
gcloud run services list --region=$GCP_REGION

# Ver detalles de servicio
gcloud run services describe division-service --region=$GCP_REGION

# Actualizar variables de entorno
gcloud run services update division-service \
    --region=$GCP_REGION \
    --set-env-vars="NEW_VAR=value"

# Ver revisiones
gcloud run revisions list --service=division-service --region=$GCP_REGION
```

### **Gestión de Tráfico**

```bash
# Dividir tráfico entre revisiones
gcloud run services update-traffic division-service \
    --region=$GCP_REGION \
    --to-revisions=revision-001=50,revision-002=50

# Rollback a revisión anterior
gcloud run services update-traffic division-service \
    --region=$GCP_REGION \
    --to-latest
```

### **Debugging**

```bash
# Ver logs de errores
gcloud logging read "resource.type=cloud_run_revision AND severity>=ERROR" --limit 100

# Conectar a Cloud SQL
gcloud sql connect shipments-postgres --user=postgres

# Listar buckets y contenido
gsutil ls -r gs://$GOOGLE_CLOUD_PROJECT-json-pendientes/
```

---

## 🚨 **TROUBLESHOOTING**

### **Problemas Comunes**

#### **Error: "Service not found"**
```bash
# Verificar que el servicio fue desplegado
gcloud run services list --region=$GCP_REGION

# Re-desplegar si es necesario
./deploy.sh
```

#### **Error: "Permission denied"**
```bash
# Verificar permisos IAM
gcloud projects get-iam-policy $GOOGLE_CLOUD_PROJECT

# Añadir permisos necesarios
gcloud projects add-iam-policy-binding $GOOGLE_CLOUD_PROJECT \
    --member="user:tu-email@gmail.com" \
    --role="roles/run.admin"
```

#### **Error de conexión a base de datos**
```bash
# Verificar Cloud SQL está ejecutándose
gcloud sql instances list

# Verificar conectividad de red
gcloud sql connect shipments-postgres --user=postgres
```

#### **Buckets no accesibles**
```bash
# Verificar permisos de buckets
gsutil iam get gs://$GOOGLE_CLOUD_PROJECT-json-pendientes

# Añadir permisos
gsutil iam ch serviceAccount:service-account@project.iam.gserviceaccount.com:storage.admin gs://$GOOGLE_CLOUD_PROJECT-json-pendientes
```

---

## 🎉 **DEPLOYMENT EXITOSO**

Si todo fue configurado correctamente, deberías ver:

✅ **3 Cloud Run Services** ejecutándose  
✅ **4 Storage Buckets** creados  
✅ **1 Cloud Workflow** desplegado  
✅ **Cloud SQL** (opcional) funcionando  
✅ **Pub/Sub Topics** configurados  
✅ **IAM Permissions** apropiados  

### **URLs de Servicios:**
- **Division Service**: `https://division-service-PROJECT_ID.REGION.run.app`
- **Image Processing**: `https://image-processing-service-PROJECT_ID.REGION.run.app`
- **Email Service**: `https://email-service-PROJECT_ID.REGION.run.app`

### **Próximo Paso:**
¡Tu arquitectura de microservicios está lista para procesar shipments en producción! 🚀

---

## 🔄 **ACTUALIZACIONES FUTURAS**

Para actualizar los servicios:

```bash
# Re-ejecutar deploy después de cambios en código
./deploy.sh

# O desplegar servicio específico
gcloud run deploy division-service \
    --source services/division_service \
    --region $GCP_REGION
```

---

## 📞 **SOPORTE**

Si encuentras problemas:

1. **Verificar logs**: `gcloud logging read`
2. **Verificar métricas**: Cloud Console → Monitoring
3. **Verificar configuración**: Revisar variables de entorno
4. **Verificar permisos**: IAM & Admin → IAM

¡La arquitectura está optimizada para escalabilidad y robustez en producción! 🎯
