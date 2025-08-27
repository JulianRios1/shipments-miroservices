"""
Configuración centralizada para todos los servicios de procesamiento de shipments
Maneja variables de entorno y configuraciones siguiendo Clean Architecture
"""

import os
from typing import Optional
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()


class BaseConfig:
    """
    Configuración base compartida por todos los servicios
    """
    
    def __init__(self):
        # Configuración general de la aplicación
        self.APP_NAME = os.getenv('APP_NAME', 'shipments-processing-platform')
        self.APP_VERSION = os.getenv('APP_VERSION', '2.0.0')
        self.ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')
        self.DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
        self.PORT = int(os.getenv('PORT', 8080))
        
        # Configuración de GCP
        self.GOOGLE_CLOUD_PROJECT = os.getenv('GOOGLE_CLOUD_PROJECT')
        self.GOOGLE_APPLICATION_CREDENTIALS = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        self.GCP_REGION = os.getenv('GCP_REGION', 'us-central1')
        
        # Configuración de buckets - ARQUITECTURA EMPRESARIAL CORRECTA
        self.BUCKET_JSON_PENDIENTES = os.getenv('BUCKET_JSON_PENDIENTES', 'json-pendientes')
        self.BUCKET_JSON_A_PROCESAR = os.getenv('BUCKET_JSON_A_PROCESAR', 'json-a-procesar') 
        self.BUCKET_IMAGENES_TEMP = os.getenv('BUCKET_IMAGENES_TEMP', 'imagenes-temp')
        self.BUCKET_IMAGENES_ORIGINALES = os.getenv('BUCKET_IMAGENES_ORIGINALES', 'imagenes-originales')
        
        # Configuración de PostgreSQL
        self.DB_HOST = os.getenv('DB_HOST', 'localhost')
        self.DB_PORT = int(os.getenv('DB_PORT', 5432))
        self.DB_NAME = os.getenv('DB_NAME', 'shipments_db')
        self.DB_USER = os.getenv('DB_USER', 'postgres')
        self.DB_PASSWORD = os.getenv('DB_PASSWORD', '')
        self.DB_SSL_MODE = os.getenv('DB_SSL_MODE', 'prefer')
        self.DB_POOL_SIZE = int(os.getenv('DB_POOL_SIZE', 10))
        self.DB_MAX_OVERFLOW = int(os.getenv('DB_MAX_OVERFLOW', 20))
        
        # Configuración de procesamiento
        self.MAX_SHIPMENTS_PER_FILE = int(os.getenv('MAX_SHIPMENTS_PER_FILE', 100))
        self.BATCH_SIZE = int(os.getenv('BATCH_SIZE', 1000))
        self.MAX_FILE_SIZE_MB = int(os.getenv('MAX_FILE_SIZE_MB', 100))
        self.CHUNK_SIZE = int(os.getenv('CHUNK_SIZE', 8192))
        
        # Configuración de Pub/Sub
        self.PUBSUB_TOPIC_FILE_PROCESSED = os.getenv('PUBSUB_TOPIC_FILE_PROCESSED', 'file-processed')
        self.PUBSUB_TOPIC_IMAGES_READY = os.getenv('PUBSUB_TOPIC_IMAGES_READY', 'images-ready')
        self.PUBSUB_TOPIC_EMAIL_SEND = os.getenv('PUBSUB_TOPIC_EMAIL_SEND', 'email-send')
        self.PUBSUB_TOPIC_ERRORS = os.getenv('PUBSUB_TOPIC_ERRORS', 'processing-errors')
        
        # Configuración de logging
        self.LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
        self.LOG_FORMAT = os.getenv('LOG_FORMAT', 
                                  '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # Configuración de URLs de servicios (Cloud Run)
        self.IMAGE_PROCESSING_SERVICE_URL = os.getenv('IMAGE_PROCESSING_SERVICE_URL', 'http://localhost:8082')
        self.EMAIL_SERVICE_URL = os.getenv('EMAIL_SERVICE_URL', 'http://localhost:8083')
        
        # Configuración de URLs firmadas
        self.SIGNED_URL_EXPIRATION_HOURS = int(os.getenv('SIGNED_URL_EXPIRATION_HOURS', 2))
        self.TEMP_FILES_CLEANUP_HOURS = int(os.getenv('TEMP_FILES_CLEANUP_HOURS', 24))
        
        # Configuración de email
        self.SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
        self.SMTP_USER = os.getenv('SMTP_USER', '')
        self.SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
        self.FROM_EMAIL = os.getenv('FROM_EMAIL', 'noreply@company.com')
        
        # Validar configuraciones críticas
        self._validate_configuration()
    
    def _validate_configuration(self):
        """
        Valida configuraciones críticas requeridas
        
        Raises:
            ValueError: Si falta alguna configuración crítica
        """
        # Verificar configuraciones obligatorias de GCP
        if not self.GOOGLE_CLOUD_PROJECT:
            raise ValueError("GOOGLE_CLOUD_PROJECT es requerido")
        
        # Verificar que MAX_SHIPMENTS_PER_FILE sea válido
        if self.MAX_SHIPMENTS_PER_FILE <= 0:
            raise ValueError("MAX_SHIPMENTS_PER_FILE debe ser mayor que 0")
        
        # Verificar buckets requeridos
        required_buckets = [
            self.BUCKET_JSON_PENDIENTES,
            self.BUCKET_JSON_A_PROCESAR,
            self.BUCKET_IMAGENES_TEMP,
            self.BUCKET_IMAGENES_ORIGINALES
        ]
        
        for bucket in required_buckets:
            if not bucket:
                raise ValueError(f"Bucket requerido no configurado: {bucket}")
    
    def get_database_url(self) -> str:
        """
        Construye URL de conexión a PostgreSQL
        
        Returns:
            str: URL de conexión completa
        """
        return (
            f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@"
            f"{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            f"?sslmode={self.DB_SSL_MODE}"
        )
    
    def get_gcs_uri(self, bucket: str, object_name: str) -> str:
        """
        Construye URI de Google Cloud Storage
        
        Args:
            bucket: Nombre del bucket
            object_name: Nombre del objeto
            
        Returns:
            str: URI completa gs://bucket/object
        """
        return f"gs://{bucket}/{object_name}"
    
    def is_production(self) -> bool:
        """Determina si está en producción"""
        return self.ENVIRONMENT.lower() == 'production'
    
    def is_development(self) -> bool:
        """Determina si está en desarrollo"""
        return self.ENVIRONMENT.lower() == 'development'
    
    def get_service_config_summary(self) -> dict:
        """
        Obtiene resumen de configuración (sin datos sensibles)
        
        Returns:
            dict: Resumen de configuración segura
        """
        return {
            'app_name': self.APP_NAME,
            'app_version': self.APP_VERSION,
            'environment': self.ENVIRONMENT,
            'debug_mode': self.DEBUG,
            'gcp_project': self.GOOGLE_CLOUD_PROJECT,
            'gcp_region': self.GCP_REGION,
            'buckets': {
                'json_pendientes': self.BUCKET_JSON_PENDIENTES,
                'json_a_procesar': self.BUCKET_JSON_A_PROCESAR,
                'imagenes_temp': self.BUCKET_IMAGENES_TEMP,
                'imagenes_originales': self.BUCKET_IMAGENES_ORIGINALES
            },
            'max_shipments_per_file': self.MAX_SHIPMENTS_PER_FILE,
            'batch_size': self.BATCH_SIZE,
            'log_level': self.LOG_LEVEL,
            'pubsub_topics': {
                'file_processed': self.PUBSUB_TOPIC_FILE_PROCESSED,
                'images_ready': self.PUBSUB_TOPIC_IMAGES_READY,
                'email_send': self.PUBSUB_TOPIC_EMAIL_SEND,
                'errors': self.PUBSUB_TOPIC_ERRORS
            },
            'service_urls': {
                'image_processing_service': self.IMAGE_PROCESSING_SERVICE_URL,
                'email_service': self.EMAIL_SERVICE_URL
            }
        }
    
    def __repr__(self) -> str:
        return f"BaseConfig(app={self.APP_NAME}, env={self.ENVIRONMENT}, project={self.GOOGLE_CLOUD_PROJECT})"


# Instancia global de configuración
config = BaseConfig()
