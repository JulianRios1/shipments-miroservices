pipeline {
    agent {
        docker {
            image 'google/cloud-sdk:latest'
            args '--user root -v /home/jenkins/.config/gcloud:/root/.config/gcloud --entrypoint=""'
        }
    }

    environment {
        // GCP Configuration
        GCP_PROJECT_ID = 'airy-semiotics-468114-a7'
        GCP_SERVICE_ACCOUNT_KEY = credentials('gcp_uat')
        GCP_REGION = 'us-central1'
        
        // Service Names
        IMAGE_PROCESSING_SERVICE = 'image-processing-service'
        EMAIL_SERVICE = 'email-service'
        WORKFLOW_NAME = 'shipment-processing-workflow'
        
        // Docker Registry
        GCR_REGISTRY = "gcr.io/${GCP_PROJECT_ID}"
        
        // Buckets
        BUCKET_JSON_TO_PROCESS = 'airy-semiotics-468114-a7-json-to-process'
        BUCKET_SHIPMENTS_IMAGES = 'shipments-images'
        BUCKET_SHIPMENTS_PROCESSED = 'shipments-processed'
        
        // Repository
        REPO_URL = 'https://github.com/your-org/shipments-microservices.git'
        BRANCH = "${env.BRANCH_NAME ?: 'master'}"
        
        // Version
        VERSION = "${env.BUILD_NUMBER}"
    }

    stages {
        stage('🧹 Cleanup') {
            steps {
                script {
                    sh """
                        echo "Limpiando workspace..."
                        rm -rf coverage archived-components deployment-scripts || true
                    """
                }
            }
        }

        stage('📥 Checkout') {
            steps {
                script {
                    echo "Clonando repositorio desde ${REPO_URL} de la rama ${BRANCH}"
                    checkout scm
                }
            }
        }

        stage('🔐 Setup GCP Auth') {
            steps {
                script {
                    sh """
                        echo "Configurando autenticación GCP..."
                        gcloud auth activate-service-account --key-file=${GCP_SERVICE_ACCOUNT_KEY}
                        gcloud config set project ${GCP_PROJECT_ID}
                        gcloud auth configure-docker gcr.io
                        echo "✅ Proyecto configurado: ${GCP_PROJECT_ID}"
                    """
                }
            }
        }

        stage('🔌 Enable APIs') {
            steps {
                script {
                    sh """
                        echo "Habilitando APIs necesarias..."
                        gcloud services enable \
                            cloudbuild.googleapis.com \
                            run.googleapis.com \
                            storage.googleapis.com \
                            workflows.googleapis.com \
                            logging.googleapis.com \
                            --project=${GCP_PROJECT_ID}
                    """
                }
            }
        }

        stage('🪣 Setup Buckets') {
            steps {
                script {
                    sh """
                        echo "Verificando buckets..."
                        
                        # Función para crear bucket si no existe
                        create_bucket_if_needed() {
                            BUCKET=\$1
                            if ! gsutil ls "gs://\${BUCKET}" > /dev/null 2>&1; then
                                echo "  ✅ Creando bucket: \${BUCKET}"
                                gsutil mb -l ${GCP_REGION} "gs://\${BUCKET}"
                            else
                                echo "  ⏭️  Bucket ya existe: \${BUCKET}"
                            fi
                        }
                        
                        create_bucket_if_needed "${BUCKET_JSON_TO_PROCESS}"
                        create_bucket_if_needed "${BUCKET_SHIPMENTS_IMAGES}"
                        create_bucket_if_needed "${BUCKET_SHIPMENTS_PROCESSED}"
                    """
                }
            }
        }

        stage('🗑️ Setup Lifecycle Policies') {
            steps {
                script {
                    sh """
                        echo "Configurando políticas de limpieza automática..."
                        
                        # Crear política de 7 días para ZIPs
                        cat > /tmp/lifecycle-7days.json << EOF
                        {
                          "lifecycle": {
                            "rule": [{
                              "action": {"type": "Delete"},
                              "condition": {"age": 7}
                            }]
                          }
                        }
                        EOF
                        
                        # Crear política de 30 días para JSONs
                        cat > /tmp/lifecycle-30days.json << EOF
                        {
                          "lifecycle": {
                            "rule": [{
                              "action": {"type": "Delete"},
                              "condition": {"age": 30}
                            }]
                          }
                        }
                        EOF
                        
                        # Aplicar políticas
                        gsutil lifecycle set /tmp/lifecycle-7days.json gs://${BUCKET_SHIPMENTS_PROCESSED}
                        gsutil lifecycle set /tmp/lifecycle-30days.json gs://${BUCKET_JSON_TO_PROCESS}
                        
                        echo "✅ Políticas de limpieza configuradas"
                    """
                }
            }
        }

        stage('🐳 Build Docker Images') {
            parallel {
                stage('Build Image Processing') {
                    steps {
                        script {
                            sh """
                                echo "Construyendo Image Processing Service..."
                                docker build \
                                    -t ${GCR_REGISTRY}/${IMAGE_PROCESSING_SERVICE}:${VERSION} \
                                    -t ${GCR_REGISTRY}/${IMAGE_PROCESSING_SERVICE}:latest \
                                    -f services/image_processing_service/Dockerfile \
                                    .
                            """
                        }
                    }
                }
                
                stage('Build Email Service') {
                    steps {
                        script {
                            sh """
                                echo "Construyendo Email Service..."
                                docker build \
                                    -t ${GCR_REGISTRY}/${EMAIL_SERVICE}:${VERSION} \
                                    -t ${GCR_REGISTRY}/${EMAIL_SERVICE}:latest \
                                    -f services/email_service/Dockerfile \
                                    .
                            """
                        }
                    }
                }
            }
        }

        stage('📤 Push Docker Images') {
            parallel {
                stage('Push Image Processing') {
                    steps {
                        script {
                            sh """
                                echo "Subiendo Image Processing Service..."
                                docker push ${GCR_REGISTRY}/${IMAGE_PROCESSING_SERVICE}:${VERSION}
                                docker push ${GCR_REGISTRY}/${IMAGE_PROCESSING_SERVICE}:latest
                            """
                        }
                    }
                }
                
                stage('Push Email Service') {
                    steps {
                        script {
                            sh """
                                echo "Subiendo Email Service..."
                                docker push ${GCR_REGISTRY}/${EMAIL_SERVICE}:${VERSION}
                                docker push ${GCR_REGISTRY}/${EMAIL_SERVICE}:latest
                            """
                        }
                    }
                }
            }
        }

        stage('🚀 Deploy Services') {
            parallel {
                stage('Deploy Image Processing') {
                    steps {
                        script {
                            sh """
                                echo "Desplegando Image Processing Service..."
                                gcloud run deploy ${IMAGE_PROCESSING_SERVICE} \
                                    --image ${GCR_REGISTRY}/${IMAGE_PROCESSING_SERVICE}:${VERSION} \
                                    --platform managed \
                                    --region ${GCP_REGION} \
                                    --memory 2Gi \
                                    --timeout 540 \
                                    --concurrency 80 \
                                    --max-instances 10 \
                                    --allow-unauthenticated \
                                    --set-env-vars "PROJECT_ID=${GCP_PROJECT_ID},VERSION=${VERSION}" \
                                    --project ${GCP_PROJECT_ID}
                            """
                        }
                    }
                }
                
                stage('Deploy Email Service') {
                    steps {
                        script {
                            sh """
                                echo "Desplegando Email Service..."
                                gcloud run deploy ${EMAIL_SERVICE} \
                                    --image ${GCR_REGISTRY}/${EMAIL_SERVICE}:${VERSION} \
                                    --platform managed \
                                    --region ${GCP_REGION} \
                                    --memory 512Mi \
                                    --timeout 60 \
                                    --concurrency 100 \
                                    --max-instances 5 \
                                    --allow-unauthenticated \
                                    --set-env-vars "PROJECT_ID=${GCP_PROJECT_ID},VERSION=${VERSION}" \
                                    --project ${GCP_PROJECT_ID}
                            """
                        }
                    }
                }
            }
        }

        stage('📋 Deploy Workflow') {
            steps {
                script {
                    sh """
                        echo "Desplegando Cloud Workflow..."
                        
                        # Obtener URLs de los servicios
                        IMAGE_SERVICE_URL=\$(gcloud run services describe ${IMAGE_PROCESSING_SERVICE} \
                            --region=${GCP_REGION} \
                            --format='value(status.url)')
                        
                        EMAIL_SERVICE_URL=\$(gcloud run services describe ${EMAIL_SERVICE} \
                            --region=${GCP_REGION} \
                            --format='value(status.url)')
                        
                        # Actualizar workflow con las URLs correctas
                        sed -i "s|https://image-processing-service-.*\\.run\\.app|\${IMAGE_SERVICE_URL}|g" \
                            workflows/shipment-processing-workflow.yaml
                        
                        sed -i "s|https://email-service-.*\\.run\\.app|\${EMAIL_SERVICE_URL}|g" \
                            workflows/shipment-processing-workflow.yaml
                        
                        # Desplegar workflow
                        gcloud workflows deploy ${WORKFLOW_NAME} \
                            --source=workflows/shipment-processing-workflow.yaml \
                            --location=${GCP_REGION} \
                            --project=${GCP_PROJECT_ID}
                        
                        echo "✅ Workflow desplegado"
                    """
                }
            }
        }

        stage('✅ Verify Deployment') {
            steps {
                script {
                    sh """
                        echo "🔍 Verificando despliegue..."
                        echo ""
                        
                        echo "📦 Servicios Cloud Run:"
                        gcloud run services list --platform managed --region ${GCP_REGION} \
                            --filter="metadata.name:${IMAGE_PROCESSING_SERVICE} OR metadata.name:${EMAIL_SERVICE}" \
                            --format="table(SERVICE,REGION,URL,LAST_DEPLOYED_BY,LAST_DEPLOYED_AT)"
                        
                        echo ""
                        echo "📋 Workflow:"
                        gcloud workflows describe ${WORKFLOW_NAME} \
                            --location=${GCP_REGION} \
                            --format="value(name,state,updateTime)"
                        
                        echo ""
                        echo "🪣 Buckets con políticas:"
                        echo "  • ${BUCKET_SHIPMENTS_PROCESSED}: Limpieza después de 7 días"
                        echo "  • ${BUCKET_JSON_TO_PROCESS}: Limpieza después de 30 días"
                    """
                }
            }
        }

        stage('🧪 Smoke Test') {
            steps {
                script {
                    sh """
                        echo "Ejecutando prueba de salud..."
                        
                        # Test Image Processing Service
                        IMAGE_SERVICE_URL=\$(gcloud run services describe ${IMAGE_PROCESSING_SERVICE} \
                            --region=${GCP_REGION} \
                            --format='value(status.url)')
                        
                        echo "Testing Image Processing: \${IMAGE_SERVICE_URL}/health"
                        curl -f "\${IMAGE_SERVICE_URL}/health" || exit 1
                        
                        # Test Email Service
                        EMAIL_SERVICE_URL=\$(gcloud run services describe ${EMAIL_SERVICE} \
                            --region=${GCP_REGION} \
                            --format='value(status.url)')
                        
                        echo "Testing Email Service: \${EMAIL_SERVICE_URL}/health"
                        curl -f "\${EMAIL_SERVICE_URL}/health" || exit 1
                        
                        echo "✅ Servicios respondiendo correctamente"
                    """
                }
            }
        }
    }

    post {
        success {
            script {
                sh """
                    echo "═══════════════════════════════════════════════════"
                    echo "🎉 DESPLIEGUE EXITOSO - Build #${BUILD_NUMBER}"
                    echo "═══════════════════════════════════════════════════"
                    echo ""
                    echo "📦 Versión desplegada: ${VERSION}"
                    echo "🌍 Región: ${GCP_REGION}"
                    echo "📋 Servicios:"
                    echo "  • Image Processing: ${IMAGE_PROCESSING_SERVICE}"
                    echo "  • Email Service: ${EMAIL_SERVICE}"
                    echo "  • Workflow: ${WORKFLOW_NAME}"
                    echo ""
                    echo "✅ Sistema listo para procesar paquetes"
                    echo "═══════════════════════════════════════════════════"
                """
            }
        }
        
        failure {
            script {
                echo "❌ Error en el despliegue. Revisa los logs para más detalles."
                
                // Opcional: Rollback a versión anterior
                sh """
                    echo "Considerando rollback..."
                    # gcloud run services update-traffic ${IMAGE_PROCESSING_SERVICE} --to-revisions=PREVIOUS=100
                    # gcloud run services update-traffic ${EMAIL_SERVICE} --to-revisions=PREVIOUS=100
                """
            }
        }
        
        always {
            script {
                // Limpiar archivos temporales
                sh """
                    rm -f /tmp/lifecycle-*.json
                    rm -f /tmp/function-env-vars.yaml
                """
                
                // Limpiar imágenes Docker locales para ahorrar espacio
                sh """
                    docker rmi ${GCR_REGISTRY}/${IMAGE_PROCESSING_SERVICE}:${VERSION} || true
                    docker rmi ${GCR_REGISTRY}/${EMAIL_SERVICE}:${VERSION} || true
                """
            }
        }
    }
}
