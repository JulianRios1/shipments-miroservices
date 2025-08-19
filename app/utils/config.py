"""
Configuración centralizada de la aplicación
Maneja todas las variables de entorno y configuraciones siguiendo Clean Architecture
"""

import os
from typing import Optional
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()


class Config:
    """
    Clase de configuración centralizada que maneja todas las variables de entorno
    y configuraciones de la aplicación
    """
    
    def __init__(self):
        # Configuración de la aplicación
        self.APP_NAME = os.getenv('APP_NAME', 'shipments-json-splitter')
        self.APP_VERSION = os.getenv('APP_VERSION', '1.0.0')
        self.FLASK_ENV = os.getenv('FLASK_ENV', 'development')
        self.FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
        self.PORT = int(os.getenv('PORT', 5000))
        
        # Configuración de GCP
        self.GOOGLE_CLOUD_PROJECT = os.getenv('GOOGLE_CLOUD_PROJECT')
        self.GOOGLE_APPLICATION_CREDENTIALS = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        
        # Configuración de buckets
        self.BUCKET_ORIGEN = os.getenv('BUCKET_ORIGEN', 'shipments-origen')
        self.BUCKET_PROCESADO = os.getenv('BUCKET_PROCESADO', 'shipments-procesados')
        
        # Configuración de Cloud Storage
        self.GCS_BUCKET_NAME = os.getenv('GCS_BUCKET_NAME', self.BUCKET_ORIGEN)
        self.GCS_REGION = os.getenv('GCS_REGION', 'us-central1')
        
        # Configuración de PostgreSQL
        self.DB_HOST = os.getenv('DB_HOST', 'localhost')
        self.DB_PORT = int(os.getenv('DB_PORT', 5432))
        self.DB_NAME = os.getenv('DB_NAME', 'shipments_db')
        self.DB_USER = os.getenv('DB_USER', 'postgres')
        self.DB_PASSWORD = os.getenv('DB_PASSWORD', '')
        self.DB_SSL_MODE = os.getenv('DB_SSL_MODE', 'prefer')
        
        # Configuración de procesamiento
        self.MAX_ENVIOS = int(os.getenv('MAX_ENVIOS', 100))
        self.BATCH_SIZE = int(os.getenv('BATCH_SIZE', 1000))
        self.MAX_FILE_SIZE_MB = int(os.getenv('MAX_FILE_SIZE_MB', 100))
        self.CHUNK_SIZE = int(os.getenv('CHUNK_SIZE', 8192))
        
        # Configuración de Pub/Sub
        self.PUBSUB_TOPIC_PROCESAMIENTO = os.getenv('PUBSUB_TOPIC_PROCESAMIENTO', 'procesar-imagenes')
        self.PUBSUB_TOPIC_ERRORES = os.getenv('PUBSUB_TOPIC_ERRORES', 'errores-procesamiento')
        self.PUBSUB_TOPIC_METRICAS = os.getenv('PUBSUB_TOPIC_METRICAS', 'metricas-procesamiento')
        
        # Configuración de logging
        self.LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
        self.LOG_FORMAT = os.getenv('LOG_FORMAT', 
                                  '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # Validar configuraciones críticas
        self._validar_configuracion()
    
    def _validar_configuracion(self):
        """
        Valida que las configuraciones críticas estén presentes
        
        Raises:
            ValueError: Si falta alguna configuración crítica
        """
        # Verificar configuraciones obligatorias de GCP
        if not self.GOOGLE_CLOUD_PROJECT:
            raise ValueError("GOOGLE_CLOUD_PROJECT es requerido")
        
        # Verificar que MAX_ENVIOS sea válido
        if self.MAX_ENVIOS <= 0:
            raise ValueError("MAX_ENVIOS debe ser mayor que 0")
        
        # Verificar que los nombres de buckets sean válidos
        if not self.BUCKET_ORIGEN:
            raise ValueError("BUCKET_ORIGEN es requerido")
        
        if not self.BUCKET_PROCESADO:
            raise ValueError("BUCKET_PROCESADO es requerido")
    
    def get_database_url(self) -> str:
        """
        Construye la URL de conexión a la base de datos PostgreSQL
        
        Returns:
            str: URL de conexión a PostgreSQL
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
    
    def es_produccion(self) -> bool:
        """
        Determina si la aplicación está ejecutándose en producción
        
        Returns:
            bool: True si está en producción
        """
        return self.FLASK_ENV.lower() == 'production'
    
    def es_desarrollo(self) -> bool:
        """
        Determina si la aplicación está ejecutándose en desarrollo
        
        Returns:
            bool: True si está en desarrollo
        """
        return self.FLASK_ENV.lower() == 'development'
    
    def get_timeout_requests(self) -> int:
        """
        Obtiene el timeout para requests HTTP basado en el entorno
        
        Returns:
            int: Timeout en segundos
        """
        if self.es_produccion():
            return 30  # Timeout más largo en producción
        return 10  # Timeout más corto en desarrollo
    
    def get_max_workers_validacion(self) -> int:
        """
        Obtiene el número máximo de workers para validación concurrente
        
        Returns:
            int: Número de workers
        """
        if self.es_produccion():
            return 10  # Más workers en producción
        return 5   # Menos workers en desarrollo
    
    def get_configuracion_summary(self) -> dict:
        """
        Obtiene un resumen de la configuración (sin datos sensibles)
        
        Returns:
            dict: Resumen de configuración
        """
        return {
            'app_name': self.APP_NAME,
            'app_version': self.APP_VERSION,
            'environment': self.FLASK_ENV,
            'debug_mode': self.FLASK_DEBUG,
            'port': self.PORT,
            'gcp_project': self.GOOGLE_CLOUD_PROJECT,
            'bucket_origen': self.BUCKET_ORIGEN,
            'bucket_procesado': self.BUCKET_PROCESADO,
            'max_envios': self.MAX_ENVIOS,
            'batch_size': self.BATCH_SIZE,
            'log_level': self.LOG_LEVEL,
            'pubsub_topics': {
                'procesamiento': self.PUBSUB_TOPIC_PROCESAMIENTO,
                'errores': self.PUBSUB_TOPIC_ERRORES,
                'metricas': self.PUBSUB_TOPIC_METRICAS
            },
            'database': {
                'host': self.DB_HOST,
                'port': self.DB_PORT,
                'database': self.DB_NAME,
                'ssl_mode': self.DB_SSL_MODE
                # Nota: No incluimos credenciales por seguridad
            }
        }
    
    def __repr__(self) -> str:
        """
        Representación string de la configuración
        
        Returns:
            str: Representación de la configuración
        """
        return f"Config(app={self.APP_NAME}, env={self.FLASK_ENV}, project={self.GOOGLE_CLOUD_PROJECT})"
