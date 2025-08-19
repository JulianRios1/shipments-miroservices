"""
Shared utilities para la plataforma de procesamiento de shipments
Contiene servicios y utilidades compartidas por todos los microservicios
"""

# Importar configuración
from .config import config, BaseConfig

# Importar logger
from .logger import setup_logger, StructuredLogger

# Importar servicios compartidos
from .storage_service import CloudStorageService, storage_service
from .database_service import DatabaseService, database_service
from .pubsub_service import PubSubService, pubsub_service

__all__ = [
    # Configuración
    'config',
    'BaseConfig',
    
    # Logger
    'setup_logger',
    'StructuredLogger',
    
    # Servicios
    'CloudStorageService',
    'storage_service',
    'DatabaseService',
    'database_service',
    'PubSubService',
    'pubsub_service'
]

__version__ = "2.0.0"
