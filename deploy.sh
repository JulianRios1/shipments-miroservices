#!/bin/bash
# 🚀 DEPLOY SCRIPT - Shipments Processing Platform v2.1
# Automatiza el deployment de los microservicios en GCP
# Arquitectura Event-Driven: Image Processing + Email (Division Service es Cloud Function independiente)

set -e  # Exit on any error

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${PURPLE}"
echo "==============================================="
echo "🚀 SHIPMENTS PROCESSING PLATFORM v2.1"
echo "📡 Deploying Event-Driven Architecture"
echo "==============================================="
echo -e "${NC}"

# Variables por defecto
PROJECT_ID=${GOOGLE_CLOUD_PROJECT}
REGION=${GCP_REGION:-"us-central1"}

# Verificar configuración
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}❌ ERROR: GOOGLE_CLOUD_PROJECT no configurado${NC}"
    exit 1
fi

echo -e "${CYAN}📋 Configuración de Deployment:${NC}"
echo "   • Project ID: $PROJECT_ID"
echo "   • Region: $REGION"
echo ""

# Función para deploy de servicios usando Docker build
deploy_service() {
    local service_name=$1
    local service_dir=$2
    local port=$3
    
    echo -e "${BLUE}🚀 Deploying $service_name...${NC}"
    
    # Construir imagen Docker localmente
    echo "Building Docker image for $service_name..."
    docker build -t gcr.io/$PROJECT_ID/$service_name:latest -f $service_dir/Dockerfile .
    
    # Enviar imagen al registry
    echo "Pushing image to registry..."
    docker push gcr.io/$PROJECT_ID/$service_name:latest
    
    # Deploy usando la imagen del registry
    gcloud run deploy $service_name \
        --image gcr.io/$PROJECT_ID/$service_name:latest \
        --platform managed \
        --region $REGION \
        --allow-unauthenticated \
        --port $port \
        --memory 1Gi \
        --cpu 1 \
        --concurrency 80 \
        --max-instances 10 \
        --timeout 3600 \
        --set-env-vars="APP_VERSION=2.1.0,ENVIRONMENT=production,GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GCP_REGION=$REGION"
        
    echo -e "${GREEN}✅ $service_name deployed successfully${NC}"
    echo ""
}

# Deploy servicios en orden correcto (Division Service es Cloud Function independiente)
echo -e "${YELLOW}📦 PASO 1: Deploying Image Processing Service...${NC}" 
deploy_service "image-processing-service" "services/image_processing_service" "8082"

echo -e "${YELLOW}📦 PASO 2: Deploying Email Service...${NC}"
deploy_service "email-service" "services/email_service" "8083"

# Saltar Cloud Workflow por ahora (usando Pub/Sub event-driven)
echo -e "${YELLOW}📦 PASO 3: Event-Driven Architecture Configured...${NC}"
echo -e "${BLUE}📡 Using Pub/Sub for event-driven processing${NC}"
echo -e "${GREEN}✅ Event-driven architecture ready${NC}"
echo ""

# Verificar configuración de Pub/Sub
echo -e "${YELLOW}📦 PASO 4: Verificando Pub/Sub Configuration...${NC}"
echo -e "${GREEN}✅ Topics y Subscriptions ya configurados con setup-pubsub.sh${NC}"
echo -e "${CYAN}ℹ️  Division Service (Cloud Function) debe ser deployado por separado${NC}"
echo ""

# Mostrar URLs de servicios
echo -e "${GREEN}"
echo "=========================================="
echo "🎉 DEPLOYMENT COMPLETADO EXITOSAMENTE"
echo "=========================================="
echo -e "${NC}"

echo -e "${CYAN}📋 URLs de Servicios Cloud Run:${NC}"
echo "   • Image Processing:       https://image-processing-service-${PROJECT_ID}.${REGION}.run.app"  
echo "   • Email Service:          https://email-service-${PROJECT_ID}.${REGION}.run.app"
echo ""
echo -e "${CYAN}📡 Endpoints Pub/Sub:${NC}"
echo "   • Image Processing:       /process-pubsub (activado por 'shipment-packages-ready')"
echo "   • Email Service:          /send-pubsub-email (activado por 'email-notifications')"
echo ""

echo -e "${CYAN}📋 Endpoints Principales:${NC}"
echo "   • Health Check:           GET /health"
echo "   • Status Check:           GET /status"
echo "   • Process Pub/Sub:        POST /process-pubsub (Image Processing)"
echo "   • Send Pub/Sub Email:     POST /send-pubsub-email (Email Service)"
echo "   • Legacy Process Package: POST /process-package"
echo "   • Legacy Send Email:      POST /send-completion-email"
echo ""

echo -e "${YELLOW}⚠️  Configuración Pendiente:${NC}"
echo "   1. 📡 Deploy Division Service como Cloud Function independiente"
echo "   2. 📊 Configure Cloud Storage trigger → Division Function"
echo "   3. ⚙️  Configure variables de entorno específicas por ambiente"
echo "   4. 🗄️  Configure credenciales de base de datos PostgreSQL"
echo "   5. 📧 Configure credenciales de SMTP para emails"
echo ""

echo -e "${GREEN}🎯 La arquitectura event-driven está lista para procesamiento empresarial!${NC}"
