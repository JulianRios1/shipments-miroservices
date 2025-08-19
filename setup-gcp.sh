#!/bin/bash
# 🔧 Setup GCP Environment - Shipments Processing Platform
# Configura todo el entorno de GCP para los microservicios

set -e

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

echo -e "${PURPLE}"
echo "==============================================="
echo "🔧 CONFIGURANDO ENTORNO GCP"
echo "📦 Shipments Processing Platform v2.0"
echo "==============================================="
echo -e "${NC}"

# Verificar si gcloud está instalado
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}❌ gcloud CLI no está instalado${NC}"
    echo "Instala desde: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Configurar proyecto
echo -e "${BLUE}📋 Configurando proyecto...${NC}"
read -p "Ingresa tu PROJECT_ID de GCP: " PROJECT_ID
read -p "Ingresa la REGION (default: us-central1): " REGION
REGION=${REGION:-"us-central1"}

# Configurar gcloud
gcloud config set project $PROJECT_ID
gcloud config set compute/region $REGION

echo -e "${GREEN}✅ Proyecto configurado: $PROJECT_ID${NC}"

# Habilitar APIs necesarias
echo -e "${BLUE}🔌 Habilitando APIs de GCP...${NC}"
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable storage-component.googleapis.com
gcloud services enable pubsub.googleapis.com
gcloud services enable workflows.googleapis.com
gcloud services enable cloudscheduler.googleapis.com
gcloud services enable sqladmin.googleapis.com

echo -e "${GREEN}✅ APIs habilitadas${NC}"

# Crear buckets
echo -e "${BLUE}🪣 Creando buckets de almacenamiento...${NC}"
gsutil mb -p $PROJECT_ID -c STANDARD -l $REGION gs://$PROJECT_ID-json-pendientes || true
gsutil mb -p $PROJECT_ID -c STANDARD -l $REGION gs://$PROJECT_ID-json-a-procesar || true
gsutil mb -p $PROJECT_ID -c STANDARD -l $REGION gs://$PROJECT_ID-imagenes-temp || true
gsutil mb -p $PROJECT_ID -c STANDARD -l $REGION gs://$PROJECT_ID-imagenes-originales || true

echo -e "${GREEN}✅ Buckets creados${NC}"

# Configurar variables de entorno
echo -e "${BLUE}⚙️ Creando archivo de configuración...${NC}"
cat > .env.production << EOF
# Configuración de Producción - GCP
GOOGLE_CLOUD_PROJECT=$PROJECT_ID
GCP_REGION=$REGION
ENVIRONMENT=production
APP_VERSION=2.0.0

# Buckets
BUCKET_JSON_PENDIENTES=$PROJECT_ID-json-pendientes
BUCKET_JSON_A_PROCESAR=$PROJECT_ID-json-a-procesar
BUCKET_IMAGENES_TEMP=$PROJECT_ID-imagenes-temp
BUCKET_IMAGENES_ORIGINALES=$PROJECT_ID-imagenes-originales

# URLs de servicios (se actualizarán después del deploy)
DIVISION_SERVICE_URL=https://division-service-$PROJECT_ID.$REGION.run.app
IMAGE_PROCESSING_SERVICE_URL=https://image-processing-service-$PROJECT_ID.$REGION.run.app
EMAIL_SERVICE_URL=https://email-service-$PROJECT_ID.$REGION.run.app

# Configuración de procesamiento
MAX_SHIPMENTS_PER_FILE=100
SIGNED_URL_EXPIRATION_HOURS=2
TEMP_FILES_CLEANUP_HOURS=24

# Base de datos (configura según tu instancia)
DB_HOST=your-postgres-host
DB_NAME=shipments_db
DB_USER=postgres
DB_PASSWORD=your-secure-password

# Email (configura con tus credenciales)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
FROM_EMAIL=noreply@yourcompany.com

# Logging
LOG_LEVEL=INFO
EOF

echo -e "${GREEN}✅ Archivo .env.production creado${NC}"

# Crear Cloud SQL (opcional)
read -p "¿Quieres crear una instancia de Cloud SQL PostgreSQL? (y/n): " create_sql
if [[ $create_sql =~ ^[Yy]$ ]]; then
    echo -e "${BLUE}🗄️ Creando instancia de Cloud SQL...${NC}"
    
    gcloud sql instances create shipments-postgres \
        --database-version=POSTGRES_15 \
        --tier=db-f1-micro \
        --region=$REGION \
        --storage-type=SSD \
        --storage-size=10GB
    
    gcloud sql databases create shipments_db --instance=shipments-postgres
    
    # Crear usuario
    gcloud sql users create postgres --instance=shipments-postgres --password=shipments-prod-2024
    
    echo -e "${GREEN}✅ Cloud SQL creado${NC}"
    echo -e "${YELLOW}⚠️  Actualiza DB_HOST en .env.production con la IP de Cloud SQL${NC}"
fi

echo -e "${GREEN}"
echo "=========================================="
echo "🎉 ENTORNO GCP CONFIGURADO"
echo "=========================================="
echo -e "${NC}"

echo -e "${CYAN}📋 Próximos pasos:${NC}"
echo "1. Revisar y actualizar .env.production con tus credenciales"
echo "2. Ejecutar: export GOOGLE_CLOUD_PROJECT=$PROJECT_ID"
echo "3. Ejecutar: export GCP_REGION=$REGION"
echo "4. Ejecutar: ./deploy.sh"
echo ""

export GOOGLE_CLOUD_PROJECT=$PROJECT_ID
export GCP_REGION=$REGION

echo -e "${GREEN}Variables de entorno configuradas para esta sesión${NC}"
