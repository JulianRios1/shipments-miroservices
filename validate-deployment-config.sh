#!/bin/bash
# 🔍 Script de Validación de Configuración de Deployment
# Verifica que todos los archivos y configuraciones estén listos para deployment

set -e

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Contadores para el reporte
CHECKS_PASSED=0
CHECKS_FAILED=0
WARNINGS=0

echo -e "${PURPLE}"
echo "================================================================"
echo "🔍 VALIDACIÓN DE CONFIGURACIÓN DE DEPLOYMENT"
echo "📦 Shipments Processing Platform v2.0"
echo "================================================================"
echo -e "${NC}"

# Función para mostrar resultado de check
check_result() {
    local status=$1
    local message=$2
    local warning_msg=$3
    
    if [[ $status -eq 0 ]]; then
        echo -e "   ${GREEN}✅ $message${NC}"
        ((CHECKS_PASSED++))
    else
        if [[ -n "$warning_msg" ]]; then
            echo -e "   ${YELLOW}⚠️  $warning_msg${NC}"
            ((WARNINGS++))
        else
            echo -e "   ${RED}❌ $message${NC}"
            ((CHECKS_FAILED++))
        fi
    fi
}

# Función para validar archivo existe
validate_file_exists() {
    local file=$1
    local description=$2
    
    if [[ -f "$file" ]]; then
        check_result 0 "$description existe"
        return 0
    else
        check_result 1 "$description NO encontrado: $file"
        return 1
    fi
}

# Función para validar directorio existe
validate_dir_exists() {
    local dir=$1
    local description=$2
    
    if [[ -d "$dir" ]]; then
        check_result 0 "$description existe"
        return 0
    else
        check_result 1 "$description NO encontrado: $dir"
        return 1
    fi
}

# Función para validar archivo es ejecutable
validate_executable() {
    local file=$1
    local description=$2
    
    if [[ -x "$file" ]]; then
        check_result 0 "$description es ejecutable"
        return 0
    else
        check_result 1 "$description NO es ejecutable: $file"
        return 1
    fi
}

# Función para validar contenido de archivo
validate_file_content() {
    local file=$1
    local pattern=$2
    local description=$3
    
    if [[ -f "$file" ]] && grep -q "$pattern" "$file"; then
        check_result 0 "$description"
        return 0
    else
        check_result 1 "$description - patrón no encontrado: $pattern en $file"
        return 1
    fi
}

# =================================================================
# VALIDACIONES DE ESTRUCTURA DE PROYECTO
# =================================================================

echo -e "${BLUE}📁 Validando estructura de proyecto...${NC}"

# Archivos principales
validate_file_exists "docker-compose.yml" "Docker Compose"
validate_file_exists "requirements.txt" "Requirements Python"
validate_file_exists "README.md" "README principal"
validate_file_exists ".gitignore" "GitIgnore"

# Scripts de deployment
validate_file_exists "setup-gcp.sh" "Script de setup GCP"
validate_file_exists "deploy.sh" "Script de deployment"
validate_file_exists "run-tests.sh" "Script de tests"
validate_file_exists "validate-deployment-config.sh" "Script de validación"

# Verificar que scripts sean ejecutables
validate_executable "setup-gcp.sh" "Setup GCP script"
validate_executable "deploy.sh" "Deploy script"
validate_executable "run-tests.sh" "Test runner script"

# Documentación
validate_file_exists "DEPLOYMENT-GUIDE.md" "Guía de deployment completa"
validate_file_exists "QUICK-DEPLOYMENT.md" "Guía de deployment rápido"

# Workflows
validate_dir_exists "workflows" "Directorio de workflows"
validate_file_exists "workflows/shipment-processing-workflow.yaml" "Cloud Workflow YAML"

echo ""

# =================================================================
# VALIDACIONES DE SERVICIOS
# =================================================================

echo -e "${BLUE}🏗️ Validando estructura de servicios...${NC}"

# Directorio de servicios
validate_dir_exists "services" "Directorio de servicios"
validate_dir_exists "services/shared_utils" "Shared utilities"
validate_file_exists "services/shared_utils/src/__init__.py" "Shared utils __init__"

# Division Service
validate_dir_exists "services/division_service" "Division Service"
validate_file_exists "services/division_service/Dockerfile" "Division Service Dockerfile"
validate_file_exists "services/division_service/src/main.py" "Division Service main.py"

# Image Processing Service
validate_dir_exists "services/image_processing_service" "Image Processing Service"
validate_file_exists "services/image_processing_service/Dockerfile" "Image Processing Dockerfile"
validate_file_exists "services/image_processing_service/src/main.py" "Image Processing main.py"

# Email Service
validate_dir_exists "services/email_service" "Email Service"
validate_file_exists "services/email_service/Dockerfile" "Email Service Dockerfile"
validate_file_exists "services/email_service/src/main.py" "Email Service main.py"

echo ""

# =================================================================
# VALIDACIONES DE TESTING
# =================================================================

echo -e "${BLUE}🧪 Validando configuración de testing...${NC}"

# Directorio de tests
validate_dir_exists "tests" "Directorio de tests"
validate_file_exists "tests/conftest.py" "Configuración global de pytest"
validate_file_exists "tests/README.md" "Documentación de tests"
validate_file_exists "pytest.ini" "Configuración de pytest"

# Tests unitarios
validate_dir_exists "tests/unit" "Tests unitarios"
validate_file_exists "tests/unit/test_division_service.py" "Tests Division Service"
validate_file_exists "tests/unit/test_image_processing_service.py" "Tests Image Processing"
validate_file_exists "tests/unit/test_email_service.py" "Tests Email Service"

# Tests de integración
validate_dir_exists "tests/integration" "Tests de integración"
validate_file_exists "tests/integration/test_end_to_end_flow.py" "Tests end-to-end"

echo ""

# =================================================================
# VALIDACIONES DE CONTENIDO DE DOCKERFILES
# =================================================================

echo -e "${BLUE}🐳 Validando configuración de Dockerfiles...${NC}"

# Validar Dockerfiles tienen configuración correcta
validate_file_content "services/division_service/Dockerfile" "FROM python:3.11" "Division Service usa Python 3.11"
validate_file_content "services/division_service/Dockerfile" "EXPOSE 8081" "Division Service expone puerto 8081"
validate_file_content "services/division_service/Dockerfile" "HEALTHCHECK" "Division Service tiene healthcheck"

validate_file_content "services/image_processing_service/Dockerfile" "FROM python:3.11" "Image Processing usa Python 3.11"
validate_file_content "services/image_processing_service/Dockerfile" "ENV PORT=8082" "Image Processing usa puerto 8082"
validate_file_content "services/image_processing_service/Dockerfile" "HEALTHCHECK" "Image Processing tiene healthcheck"

validate_file_content "services/email_service/Dockerfile" "FROM python:3.11" "Email Service usa Python 3.11"
validate_file_content "services/email_service/Dockerfile" "ENV PORT=8083" "Email Service usa puerto 8083"
validate_file_content "services/email_service/Dockerfile" "HEALTHCHECK" "Email Service tiene healthcheck"

echo ""

# =================================================================
# VALIDACIONES DE DOCKER-COMPOSE
# =================================================================

echo -e "${BLUE}🔗 Validando configuración de Docker Compose...${NC}"

validate_file_content "docker-compose.yml" "version: '3.8'" "Docker Compose versión correcta"
validate_file_content "docker-compose.yml" "postgres:" "PostgreSQL configurado"
validate_file_content "docker-compose.yml" "division-service:" "Division Service en compose"
validate_file_content "docker-compose.yml" "image-processing-service:" "Image Processing en compose"
validate_file_content "docker-compose.yml" "email-service:" "Email Service en compose"
validate_file_content "docker-compose.yml" "mailhog:" "MailHog configurado para desarrollo"
validate_file_content "docker-compose.yml" "redis:" "Redis configurado"

# Verificar puertos no tienen conflictos
validate_file_content "docker-compose.yml" "8081:8081" "Puerto 8081 mapeado correctamente"
validate_file_content "docker-compose.yml" "8082:8082" "Puerto 8082 mapeado correctamente"
validate_file_content "docker-compose.yml" "8083:8083" "Puerto 8083 mapeado correctamente"

echo ""

# =================================================================
# VALIDACIONES DE REQUIREMENTS
# =================================================================

echo -e "${BLUE}📦 Validando dependencias de Python...${NC}"

# Verificar dependencias principales
validate_file_content "requirements.txt" "Flask==" "Flask framework incluido"
validate_file_content "requirements.txt" "psycopg2-binary==" "PostgreSQL driver incluido"
validate_file_content "requirements.txt" "google-cloud-storage==" "GCS SDK incluido"
validate_file_content "requirements.txt" "google-cloud-pubsub==" "Pub/Sub SDK incluido"
validate_file_content "requirements.txt" "google-cloud-workflows==" "Workflows SDK incluido"

# Verificar dependencias de testing
validate_file_content "requirements.txt" "pytest==" "Pytest incluido"
validate_file_content "requirements.txt" "pytest-cov==" "Coverage incluido"
validate_file_content "requirements.txt" "pytest-asyncio==" "Async testing incluido"

echo ""

# =================================================================
# VALIDACIONES DE SCRIPTS DE DEPLOYMENT
# =================================================================

echo -e "${BLUE}🚀 Validando scripts de deployment...${NC}"

# Setup GCP script
validate_file_content "setup-gcp.sh" "gcloud services enable" "Setup script habilita APIs"
validate_file_content "setup-gcp.sh" "gsutil mb" "Setup script crea buckets"
validate_file_content "setup-gcp.sh" ".env.production" "Setup script genera configuración"

# Deploy script
validate_file_content "deploy.sh" "gcloud run deploy" "Deploy script usa Cloud Run"
validate_file_content "deploy.sh" "division-service" "Deploy script incluye Division Service"
validate_file_content "deploy.sh" "image-processing-service" "Deploy script incluye Image Processing"
validate_file_content "deploy.sh" "email-service" "Deploy script incluye Email Service"
validate_file_content "deploy.sh" "gcloud workflows deploy" "Deploy script incluye Workflows"

echo ""

# =================================================================
# VALIDACIONES DE WORKFLOW
# =================================================================

echo -e "${BLUE}🔄 Validando Cloud Workflow...${NC}"

if [[ -f "workflows/shipment-processing-workflow.yaml" ]]; then
    validate_file_content "workflows/shipment-processing-workflow.yaml" "main:" "Workflow tiene función main"
    validate_file_content "workflows/shipment-processing-workflow.yaml" "http.post" "Workflow usa HTTP calls"
    validate_file_content "workflows/shipment-processing-workflow.yaml" "division-service" "Workflow llama a Division Service"
    validate_file_content "workflows/shipment-processing-workflow.yaml" "image-processing-service" "Workflow llama a Image Processing"
    validate_file_content "workflows/shipment-processing-workflow.yaml" "email-service" "Workflow llama a Email Service"
else
    check_result 1 "Workflow YAML no encontrado"
fi

echo ""

# =================================================================
# VALIDACIONES DE CONFIGURACIÓN AVANZADA
# =================================================================

echo -e "${BLUE}⚙️ Validando configuración avanzada...${NC}"

# Verificar configuración de pytest
if [[ -f "pytest.ini" ]]; then
    validate_file_content "pytest.ini" "testpaths = tests" "Pytest configurado para directorio tests"
    validate_file_content "pytest.ini" "markers =" "Pytest markers definidos"
    validate_file_content "pytest.ini" "asyncio_mode = auto" "Pytest async configurado"
else
    check_result 1 "pytest.ini no encontrado"
fi

# Verificar configuración de servicios compartidos
validate_file_content "services/shared_utils/src/config.py" "class" "Config compartida definida" "" "Config compartida podría no estar implementada"
validate_file_content "services/shared_utils/src/logger.py" "def" "Logger compartido definido" "" "Logger compartido podría no estar implementado"

echo ""

# =================================================================
# VALIDACIONES DE HERRAMIENTAS DE DESARROLLO
# =================================================================

echo -e "${BLUE}🛠️ Verificando herramientas requeridas...${NC}"

# Verificar gcloud CLI
if command -v gcloud &> /dev/null; then
    check_result 0 "gcloud CLI está instalado"
    gcloud_version=$(gcloud --version | head -n1 | awk '{print $4}')
    echo -e "   ${CYAN}   Versión: $gcloud_version${NC}"
else
    check_result 1 "gcloud CLI NO está instalado"
fi

# Verificar Docker
if command -v docker &> /dev/null; then
    check_result 0 "Docker está instalado"
    docker_version=$(docker --version | awk '{print $3}' | sed 's/,//')
    echo -e "   ${CYAN}   Versión: $docker_version${NC}"
else
    check_result 1 "Docker NO está instalado"
fi

# Verificar Python
if command -v python3 &> /dev/null; then
    check_result 0 "Python 3 está instalado"
    python_version=$(python3 --version | awk '{print $2}')
    echo -e "   ${CYAN}   Versión: $python_version${NC}"
    
    # Verificar versión mínima (3.11+)
    if python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)"; then
        check_result 0 "Python versión es 3.11+"
    else
        check_result 1 "Python versión debe ser 3.11+ (actual: $python_version)"
    fi
else
    check_result 1 "Python 3 NO está instalado"
fi

# Verificar pip
if command -v pip3 &> /dev/null; then
    check_result 0 "pip está instalado"
else
    check_result 1 "pip NO está instalado"
fi

# Verificar git
if command -v git &> /dev/null; then
    check_result 0 "Git está instalado"
    git_version=$(git --version | awk '{print $3}')
    echo -e "   ${CYAN}   Versión: $git_version${NC}"
else
    check_result 1 "Git NO está instalado"
fi

echo ""

# =================================================================
# VALIDACIONES DE VARIABLES DE ENTORNO
# =================================================================

echo -e "${BLUE}🌍 Verificando variables de entorno...${NC}"

# Variables opcionales pero recomendadas
if [[ -n "$GOOGLE_CLOUD_PROJECT" ]]; then
    check_result 0 "GOOGLE_CLOUD_PROJECT está configurado: $GOOGLE_CLOUD_PROJECT"
else
    check_result 1 "GOOGLE_CLOUD_PROJECT no está configurado" "Configurar antes del deployment"
fi

if [[ -n "$GCP_REGION" ]]; then
    check_result 0 "GCP_REGION está configurado: $GCP_REGION"
else
    check_result 1 "GCP_REGION no está configurado" "Se usará us-central1 por defecto"
fi

echo ""

# =================================================================
# REPORTE FINAL
# =================================================================

echo -e "${PURPLE}"
echo "================================================================"
echo "📊 REPORTE DE VALIDACIÓN"
echo "================================================================"
echo -e "${NC}"

echo -e "${GREEN}✅ Checks pasados:   $CHECKS_PASSED${NC}"
echo -e "${YELLOW}⚠️  Advertencias:    $WARNINGS${NC}"
echo -e "${RED}❌ Checks fallidos:  $CHECKS_FAILED${NC}"

total_checks=$((CHECKS_PASSED + CHECKS_FAILED + WARNINGS))
echo -e "${BLUE}📋 Total checks:     $total_checks${NC}"

# Calcular porcentaje de éxito
if [[ $total_checks -gt 0 ]]; then
    success_rate=$(( (CHECKS_PASSED * 100) / total_checks ))
    echo -e "${CYAN}📈 Tasa de éxito:    $success_rate%${NC}"
fi

echo ""

# Determinar estado general
if [[ $CHECKS_FAILED -eq 0 ]]; then
    echo -e "${GREEN}"
    echo "🎉 ¡CONFIGURACIÓN LISTA PARA DEPLOYMENT!"
    echo ""
    echo "✅ Todos los archivos y configuraciones están correctos"
    echo "✅ La estructura del proyecto es válida"
    echo "✅ Los servicios están correctamente configurados"
    echo "✅ Las herramientas requeridas están instaladas"
    echo ""
    echo "📋 Próximos pasos recomendados:"
    echo "   1. Ejecutar: ./setup-gcp.sh"
    echo "   2. Configurar credenciales en .env.production"  
    echo "   3. Ejecutar: ./deploy.sh"
    echo "   4. Ejecutar tests: ./run-tests.sh"
    echo -e "${NC}"
    exit 0
else
    echo -e "${RED}"
    echo "❌ PROBLEMAS ENCONTRADOS EN LA CONFIGURACIÓN"
    echo ""
    echo "Se encontraron $CHECKS_FAILED problemas que deben ser resueltos"
    echo "antes de proceder con el deployment."
    echo ""
    echo "📋 Acciones requeridas:"
    echo "   1. Revisar los errores mostrados arriba"
    echo "   2. Corregir los archivos faltantes o incorrectos"
    echo "   3. Re-ejecutar este script de validación"
    echo "   4. Proceder con el deployment una vez todo esté correcto"
    echo -e "${NC}"
    
    if [[ $WARNINGS -gt 0 ]]; then
        echo -e "${YELLOW}"
        echo "⚠️  ADVERTENCIAS:"
        echo "Las advertencias no impiden el deployment, pero se recomienda"
        echo "revisarlas para asegurar una configuración óptima."
        echo -e "${NC}"
    fi
    
    exit 1
fi
