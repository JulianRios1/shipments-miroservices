#!/bin/bash
# 🚀 DEPLOY SCRIPT - Shipments Processing Platform v2.0
# Automatiza el deployment de TODOS los microservicios en GCP
# Arquitectura empresarial completa: División + Imágenes + Email

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
echo "🚀 SHIPMENTS PROCESSING PLATFORM v2.0"
echo "📦 Deploying Microservices Architecture"
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

# Función para deploy de servicios
deploy_service() {
    local service_name=$1
    local service_path=$2
    local port=$3
    
    echo -e "${BLUE}🚀 Deploying $service_name...${NC}"
    
    gcloud run deploy $service_name \
        --source $service_path \
        --platform managed \
        --region $REGION \
        --allow-unauthenticated \
        --port $port \
        --memory 1Gi \
        --cpu 1 \
        --concurrency 80 \
        --max-instances 10 \
        --timeout 3600 \
        --set-env-vars="APP_VERSION=2.0.0,ENVIRONMENT=production,GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GCP_REGION=$REGION"
        
    echo -e "${GREEN}✅ $service_name deployed successfully${NC}"
    echo ""
}

# Deploy servicios en orden correcto
echo -e "${YELLOW}📦 PASO 1: Deploying Division Service...${NC}"
deploy_service "division-service" "services/division_service" "8081"

echo -e "${YELLOW}📦 PASO 2: Deploying Image Processing Service...${NC}" 
deploy_service "image-processing-service" "services/image_processing_service" "8082"

echo -e "${YELLOW}📦 PASO 3: Deploying Email Service...${NC}"
deploy_service "email-service" "services/email_service" "8083"

# Deploy Cloud Workflow
echo -e "${YELLOW}📦 PASO 4: Deploying Cloud Workflow...${NC}"
echo -e "${BLUE}🔄 Deploying shipment-processing-workflow...${NC}"

gcloud workflows deploy shipment-processing-workflow \
    --source workflows/shipment-processing-workflow.yaml \
    --location $REGION

echo -e "${GREEN}✅ Cloud Workflow deployed successfully${NC}"
echo ""

# Configurar triggers de Pub/Sub (opcional)
echo -e "${YELLOW}📦 PASO 5: Configurando Pub/Sub triggers...${NC}"
echo -e "${CYAN}ℹ️  Configuración de triggers debe hacerse manualmente en GCP Console${NC}"
echo ""

# Mostrar URLs de servicios
echo -e "${GREEN}"
echo "=========================================="
echo "🎉 DEPLOYMENT COMPLETADO EXITOSAMENTE"
echo "=========================================="
echo -e "${NC}"

echo -e "${CYAN}📋 URLs de Servicios:${NC}"
echo "   • Division Service:       https://division-service-${PROJECT_ID}.${REGION}.run.app"
echo "   • Image Processing:       https://image-processing-service-${PROJECT_ID}.${REGION}.run.app"  
echo "   • Email Service:          https://email-service-${PROJECT_ID}.${REGION}.run.app"
echo ""

echo -e "${CYAN}📋 Endpoints Principales:${NC}"
echo "   • Health Check:           GET /health"
echo "   • Status Check:           GET /status"
echo "   • Process File:           POST /process-file"
echo "   • Process Package:        POST /process-package"
echo "   • Send Email:            POST /send-completion-email"
echo ""

echo -e "${YELLOW}⚠️  Configuración Pendiente:${NC}"
echo "   1. Configurar triggers de Cloud Storage → Pub/Sub"
echo "   2. Configurar variables de entorno específicas por ambiente"
echo "   3. Configurar credenciales de base de datos"
echo "   4. Configurar credenciales de SMTP"
echo ""

echo -e "${GREEN}🎯 La arquitectura de microservicios está lista para procesamiento empresarial!${NC}"
