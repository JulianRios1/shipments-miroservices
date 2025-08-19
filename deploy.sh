#!/bin/bash

# Script de deployment para Cloud Run
# Basado en el tutorial implementado

set -e

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Iniciando deployment de Shipments JSON Splitter${NC}"

# Verificar que estemos en el directorio correcto
if [ ! -f "app/main.py" ]; then
    echo -e "${RED}❌ Error: Debe ejecutar este script desde el directorio raíz del proyecto${NC}"
    exit 1
fi

# Cargar variables de entorno
if [ -f ".env" ]; then
    export $(cat .env | grep -v '^#' | xargs)
    echo -e "${GREEN}✅ Variables de entorno cargadas desde .env${NC}"
else
    echo -e "${YELLOW}⚠️  Archivo .env no encontrado. Usando variables de entorno del sistema.${NC}"
fi

# Verificar variables requeridas
REQUIRED_VARS=("GOOGLE_CLOUD_PROJECT" "BUCKET_ORIGEN" "BUCKET_PROCESADO")
for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        echo -e "${RED}❌ Error: Variable de entorno $var es requerida${NC}"
        exit 1
    fi
done

echo -e "${GREEN}✅ Variables de entorno verificadas${NC}"

# Configurar proyecto de GCP
echo -e "${YELLOW}📋 Configurando proyecto de GCP: $GOOGLE_CLOUD_PROJECT${NC}"
gcloud config set project $GOOGLE_CLOUD_PROJECT

# Construir imagen Docker
SERVICE_NAME="shipments-json-splitter"
IMAGE_NAME="gcr.io/$GOOGLE_CLOUD_PROJECT/$SERVICE_NAME"

echo -e "${YELLOW}🔨 Construyendo imagen Docker...${NC}"
gcloud builds submit --tag $IMAGE_NAME

# Verificar que la imagen se construyó correctamente
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Imagen Docker construida exitosamente${NC}"
else
    echo -e "${RED}❌ Error construyendo imagen Docker${NC}"
    exit 1
fi

# Deploy a Cloud Run
echo -e "${YELLOW}☁️  Desplegando a Cloud Run...${NC}"
gcloud run deploy $SERVICE_NAME \\
    --image $IMAGE_NAME \\
    --platform managed \\
    --region us-central1 \\
    --set-env-vars "FLASK_ENV=production" \\
    --set-env-vars "GOOGLE_CLOUD_PROJECT=$GOOGLE_CLOUD_PROJECT" \\
    --set-env-vars "BUCKET_ORIGEN=$BUCKET_ORIGEN" \\
    --set-env-vars "BUCKET_PROCESADO=$BUCKET_PROCESADO" \\
    --set-env-vars "MAX_ENVIOS=${MAX_ENVIOS:-100}" \\
    --set-env-vars "PUBSUB_TOPIC_PROCESAMIENTO=${PUBSUB_TOPIC_PROCESAMIENTO:-procesar-imagenes}" \\
    --set-env-vars "LOG_LEVEL=INFO" \\
    --set-env-vars "LOG_FORMAT=json" \\
    --memory 2Gi \\
    --cpu 2 \\
    --timeout 3600 \\
    --concurrency 10 \\
    --max-instances 10 \\
    --allow-unauthenticated

# Verificar deployment
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Deployment de Cloud Run exitoso${NC}"
    
    # Obtener URL del servicio
    SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=us-central1 --format='value(status.url)')
    echo -e "${GREEN}🌐 Servicio disponible en: $SERVICE_URL${NC}"
    
    # Verificar health check
    echo -e "${YELLOW}🏥 Verificando health check...${NC}"
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$SERVICE_URL/health")
    if [ "$HTTP_CODE" = "200" ]; then
        echo -e "${GREEN}✅ Health check exitoso${NC}"
    else
        echo -e "${YELLOW}⚠️  Health check retornó código: $HTTP_CODE${NC}"
    fi
    
else
    echo -e "${RED}❌ Error en deployment de Cloud Run${NC}"
    exit 1
fi

# Crear o actualizar trigger de Eventarc
echo -e "${YELLOW}⚡ Configurando trigger de Eventarc...${NC}"

# Verificar si el trigger ya existe
TRIGGER_NAME="$SERVICE_NAME-trigger"
if gcloud eventarc triggers describe $TRIGGER_NAME --location=us-central1 &>/dev/null; then
    echo -e "${YELLOW}📝 Trigger existente encontrado, actualizando...${NC}"
    gcloud eventarc triggers update $TRIGGER_NAME \\
        --location=us-central1 \\
        --destination-run-service=$SERVICE_NAME \\
        --destination-run-region=us-central1
else
    echo -e "${YELLOW}🆕 Creando nuevo trigger de Eventarc...${NC}"
    gcloud eventarc triggers create $TRIGGER_NAME \\
        --location=us-central1 \\
        --destination-run-service=$SERVICE_NAME \\
        --destination-run-region=us-central1 \\
        --event-filters="type=google.cloud.storage.object.v1.finalized" \\
        --event-filters="bucket=$BUCKET_ORIGEN"
fi

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Trigger de Eventarc configurado exitosamente${NC}"
else
    echo -e "${RED}❌ Error configurando trigger de Eventarc${NC}"
    exit 1
fi

# Verificar buckets existen
echo -e "${YELLOW}🪣 Verificando buckets de GCS...${NC}"
for bucket in "$BUCKET_ORIGEN" "$BUCKET_PROCESADO"; do
    if gsutil ls "gs://$bucket" &>/dev/null; then
        echo -e "${GREEN}✅ Bucket $bucket existe${NC}"
    else
        echo -e "${YELLOW}⚠️  Bucket $bucket no encontrado, creando...${NC}"
        gsutil mb -p $GOOGLE_CLOUD_PROJECT -c STANDARD -l us-central1 "gs://$bucket"
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✅ Bucket $bucket creado exitosamente${NC}"
        else
            echo -e "${RED}❌ Error creando bucket $bucket${NC}"
            exit 1
        fi
    fi
done

# Verificar tópicos de Pub/Sub
echo -e "${YELLOW}📬 Verificando tópicos de Pub/Sub...${NC}"
TOPICS=("$PUBSUB_TOPIC_PROCESAMIENTO" "${PUBSUB_TOPIC_ERRORES:-errores-procesamiento}" "${PUBSUB_TOPIC_METRICAS:-metricas-procesamiento}")

for topic in "${TOPICS[@]}"; do
    if [ -n "$topic" ]; then
        if gcloud pubsub topics describe "$topic" &>/dev/null; then
            echo -e "${GREEN}✅ Tópico $topic existe${NC}"
        else
            echo -e "${YELLOW}⚠️  Tópico $topic no encontrado, creando...${NC}"
            gcloud pubsub topics create "$topic"
            if [ $? -eq 0 ]; then
                echo -e "${GREEN}✅ Tópico $topic creado exitosamente${NC}"
            else
                echo -e "${RED}❌ Error creando tópico $topic${NC}"
            fi
        fi
    fi
done

echo -e "${GREEN}🎉 ¡Deployment completado exitosamente!${NC}"
echo ""
echo -e "${GREEN}📋 Resumen del deployment:${NC}"
echo -e "  • Servicio: $SERVICE_NAME"
echo -e "  • URL: $SERVICE_URL"
echo -e "  • Región: us-central1"
echo -e "  • Bucket origen: $BUCKET_ORIGEN"
echo -e "  • Bucket procesado: $BUCKET_PROCESADO"
echo -e "  • Trigger: $TRIGGER_NAME"
echo ""
echo -e "${YELLOW}🧪 Para probar el servicio:${NC}"
echo -e "  1. Sube un archivo JSON al bucket: gs://$BUCKET_ORIGEN"
echo -e "  2. Revisa los logs: gcloud logging read 'resource.type=cloud_run_revision' --limit=50"
echo -e "  3. Verifica archivos procesados en: gs://$BUCKET_PROCESADO/procesados/"
echo ""
echo -e "${GREEN}✨ ¡Listo para procesar archivos JSON de envíos!${NC}"
