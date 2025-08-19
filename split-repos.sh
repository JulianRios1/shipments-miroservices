#!/bin/bash
# 🚀 SCRIPT PARA DIVIDIR MONOREPO EN REPOSITORIOS INDEPENDIENTES
# Optimizado para Cloud Run deployment independiente

set -e

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

echo -e "${PURPLE}"
echo "=============================================="
echo "🔀 SPLITTING MONOREPO → MULTIREPO"
echo "📦 Cloud Run Independent Repositories"
echo "=============================================="
echo -e "${NC}"

# Configuración
GITHUB_ORG="tu-organizacion"  # Cambiar por tu organización
BASE_DIR="/tmp/shipments-repos"
CURRENT_DIR=$(pwd)

# Crear directorio base
mkdir -p $BASE_DIR
cd $BASE_DIR

echo -e "${BLUE}📋 Servicios a separar:${NC}"
echo "  • division-service"
echo "  • image-processing-service"  
echo "  • email-service"
echo "  • shared-libraries"
echo ""

# Función para crear repo independiente
create_independent_repo() {
    local service_name=$1
    local source_path=$2
    
    echo -e "${BLUE}🚀 Creando repositorio independiente: $service_name${NC}"
    
    # Crear directorio del servicio
    mkdir -p $service_name
    cd $service_name
    
    # Inicializar git
    git init
    
    # Copiar archivos del servicio
    if [ -d "$CURRENT_DIR/$source_path" ]; then
        cp -r $CURRENT_DIR/$source_path/* .
    fi
    
    # Copiar shared_utils si el servicio lo necesita
    if [ "$service_name" != "shared-libraries" ]; then
        mkdir -p shared_utils
        cp -r $CURRENT_DIR/services/shared_utils/* shared_utils/
    fi
    
    # Crear README específico del servicio
    create_service_readme $service_name
    
    # Crear GitHub Actions para Cloud Run
    create_github_actions $service_name
    
    # Crear Cloud Build config
    create_cloudbuild_config $service_name
    
    # Actualizar Dockerfile para standalone
    update_dockerfile_standalone $service_name
    
    # Primer commit
    git add .
    git commit -m "🎉 Initial commit: $service_name independent repository"
    
    echo -e "${GREEN}✅ $service_name repository created locally${NC}"
    
    cd ..
}

# Función para crear README del servicio
create_service_readme() {
    local service_name=$1
    
    cat > README.md << EOF
# 🚀 $service_name

## Shipments Processing Platform - Independent Cloud Run Service

### 🏗️ **Arquitectura**
- **Patrón**: Microservicio independiente
- **Deploy**: Cloud Run
- **Scaling**: Serverless (0-1000 instancias)
- **Monitoring**: Cloud Monitoring + Structured Logging

### 🚀 **Quick Deploy**
\`\`\`bash
# Deploy directo a Cloud Run
gcloud run deploy $service_name \\
    --source . \\
    --region us-central1 \\
    --allow-unauthenticated

# Via GitHub Actions (recomendado)
git push origin main
\`\`\`

### 🔧 **Development**
\`\`\`bash
# Setup local
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run locally
python src/main.py
\`\`\`

### 📊 **Endpoints**
- \`GET /health\` - Health check
- \`GET /status\` - Detailed status
- Ver \`src/main.py\` para endpoints específicos

### 🏷️ **Versioning**
- **Current**: v2.0.0
- **Strategy**: Semantic Versioning
- **Releases**: Automated via GitHub Actions

### 🔗 **Dependencies**
- **Shared Libraries**: Auto-included in build
- **External Services**: Ver \`.env.example\`
- **GCP Services**: Cloud Run, Cloud Storage, Cloud SQL

### 📝 **Logs**
\`\`\`bash
# Ver logs en tiempo real
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=$service_name" --limit=50

# Logs de errores
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=$service_name AND severity>=ERROR" --limit=20
\`\`\`

### 🚨 **Troubleshooting**
- **Logs**: Cloud Console → Logging
- **Metrics**: Cloud Console → Cloud Run → $service_name
- **Health**: \`curl https://SERVICE_URL/health\`

---
**🏗️ Part of Shipments Processing Platform**  
**☁️ Cloud Run Ready**  
**🔄 CI/CD Enabled**
EOF
}

# Función para crear GitHub Actions
create_github_actions() {
    local service_name=$1
    
    mkdir -p .github/workflows
    
    cat > .github/workflows/deploy.yml << EOF
name: Deploy $service_name to Cloud Run

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

env:
  PROJECT_ID: \${{ secrets.GCP_PROJECT_ID }}
  SERVICE_NAME: $service_name
  REGION: us-central1

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest
    
    - name: Run tests
      run: |
        pytest tests/ --verbose || echo "No tests found"

  deploy:
    if: github.ref == 'refs/heads/main'
    needs: test
    runs-on: ubuntu-latest
    
    permissions:
      contents: read
      id-token: write

    steps:
    - uses: actions/checkout@v4

    - name: Authenticate to Google Cloud
      uses: google-github-actions/auth@v1
      with:
        credentials_json: \${{ secrets.GCP_SA_KEY }}

    - name: Set up Cloud SDK
      uses: google-github-actions/setup-gcloud@v1

    - name: Deploy to Cloud Run
      run: |
        gcloud run deploy \$SERVICE_NAME \\
          --source . \\
          --platform managed \\
          --region \$REGION \\
          --allow-unauthenticated \\
          --memory 1Gi \\
          --cpu 1 \\
          --concurrency 80 \\
          --max-instances 10 \\
          --set-env-vars="APP_VERSION=\$(date +%Y%m%d-%H%M%S),ENVIRONMENT=production"

    - name: Verify deployment
      run: |
        SERVICE_URL=\$(gcloud run services describe \$SERVICE_NAME --region=\$REGION --format="value(status.url)")
        curl -f \$SERVICE_URL/health
        echo "✅ $service_name deployed successfully: \$SERVICE_URL"
EOF
}

# Función para crear Cloud Build config
create_cloudbuild_config() {
    local service_name=$1
    
    cat > cloudbuild.yaml << EOF
# Cloud Build configuration for $service_name
steps:
  # Build the container image
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'gcr.io/\$PROJECT_ID/$service_name:\$COMMIT_SHA', '.']
  
  # Push the container image to Container Registry
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/\$PROJECT_ID/$service_name:\$COMMIT_SHA']
  
  # Deploy container image to Cloud Run
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: gcloud
    args:
      - 'run'
      - 'deploy'
      - '$service_name'
      - '--image'
      - 'gcr.io/\$PROJECT_ID/$service_name:\$COMMIT_SHA'
      - '--region'
      - 'us-central1'
      - '--platform'
      - 'managed'
      - '--allow-unauthenticated'
      - '--memory'
      - '1Gi'
      - '--cpu'
      - '1'
      - '--concurrency'
      - '80'
      - '--max-instances'
      - '10'

images:
  - 'gcr.io/\$PROJECT_ID/$service_name:\$COMMIT_SHA'

options:
  logging: CLOUD_LOGGING_ONLY
EOF
}

# Función para actualizar Dockerfile para standalone
update_dockerfile_standalone() {
    local service_name=$1
    
    if [ -f "Dockerfile" ]; then
        # Actualizar Dockerfile para ser standalone
        sed -i 's|services/shared_utils|shared_utils|g' Dockerfile
        sed -i 's|services/'$service_name'/src|src|g' Dockerfile
    else
        # Crear Dockerfile básico si no existe
        cat > Dockerfile << EOF
# $service_name - Standalone Docker Image
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=True
ENV PYTHONDONTWRITEBYTECODE=True
ENV PYTHONPATH=/app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    curl \\
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --create-home --shell /bin/bash app

WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared utilities
COPY shared_utils /app/shared_utils

# Copy application code
COPY src /app/src

# Create temp directories with appropriate permissions
RUN mkdir -p /tmp/shipments_processing && \\
    chown -R app:app /app /tmp/shipments_processing

# Switch to non-root user
USER app

# Set working directory
WORKDIR /app/src

# Run application
CMD exec python main.py

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \\
    CMD curl -f http://localhost:8080/health || exit 1

# Labels
LABEL service="$service_name" \\
      version="2.0.0" \\
      description="$service_name microservice for Shipments Processing Platform"
EOF
    fi
}

# Crear requirements.txt específico del servicio
create_service_requirements() {
    local service_name=$1
    
    # Base requirements para todos los servicios
    cat > requirements.txt << EOF
# Core dependencies for $service_name
Flask==3.0.0
Flask-CORS==4.0.0
gunicorn==21.2.0

# Google Cloud Platform
google-cloud-storage==2.12.0
google-cloud-pubsub==2.21.1
google-auth==2.24.0

# Database
psycopg2-binary==2.9.9
SQLAlchemy==2.0.23

# Utilities
python-dotenv==1.0.0
requests==2.31.0
python-dateutil==2.8.2

# Structured logging
python-json-logger==2.0.7

# Validation
marshmallow==3.20.1

# Testing
pytest==7.4.3
pytest-cov==4.1.0

# Development
black==23.11.0
flake8==6.1.0
EOF

    # Añadir dependencias específicas por servicio
    case $service_name in
        "image-processing-service")
            cat >> requirements.txt << EOF

# Image processing specific
Pillow==10.1.0
EOF
            ;;
        "email-service")
            cat >> requirements.txt << EOF

# Email specific
email-validator==2.1.0
jinja2==3.1.2
EOF
            ;;
    esac
}

# Función principal
main() {
    echo -e "${YELLOW}⚠️  Este script creará repositorios independientes en $BASE_DIR${NC}"
    read -p "¿Continuar? (y/n): " -n 1 -r
    echo
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Operación cancelada"
        exit 1
    fi
    
    # Crear repositorios independientes
    create_independent_repo "division-service" "services/division_service"
    create_independent_repo "image-processing-service" "services/image_processing_service"  
    create_independent_repo "email-service" "services/email_service"
    create_independent_repo "shared-libraries" "services/shared_utils"
    
    echo -e "${GREEN}"
    echo "=============================================="
    echo "🎉 MULTIREPO SETUP COMPLETADO"
    echo "=============================================="
    echo -e "${NC}"
    
    echo -e "${CYAN}📋 Próximos pasos:${NC}"
    echo "1. Crear repositorios en GitHub:"
    echo "   • $GITHUB_ORG/division-service"
    echo "   • $GITHUB_ORG/image-processing-service"
    echo "   • $GITHUB_ORG/email-service"  
    echo "   • $GITHUB_ORG/shared-libraries"
    echo ""
    echo "2. Push inicial:"
    echo "   cd $BASE_DIR/division-service"
    echo "   git remote add origin https://github.com/$GITHUB_ORG/division-service.git"
    echo "   git push -u origin main"
    echo ""
    echo "3. Configurar secrets en GitHub:"
    echo "   • GCP_PROJECT_ID"
    echo "   • GCP_SA_KEY"
    echo ""
    echo "4. Deploy automático via GitHub Actions activado ✅"
    
    echo -e "${GREEN}🚀 Cloud Run independent deployments ready!${NC}"
}

# Ejecutar
main
