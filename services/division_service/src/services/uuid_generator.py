"""
UUID Generator - Generador de identificadores únicos
Responsable de crear UUIDs consistentes para agrupamiento empresarial
"""

import uuid
import hashlib
from datetime import datetime
from typing import Optional
import sys

# Añadir shared_utils al path
sys.path.insert(0, '/app/services/shared_utils/src')

from logger import setup_logger
from config import config


class UUIDGenerator:
    """
    Generador de UUIDs para agrupamiento empresarial
    Proporciona diferentes estrategias de generación según necesidades
    """
    
    def __init__(self):
        self.logger = setup_logger(__name__, 'uuid-generator', config.APP_VERSION)
    
    def generate_processing_uuid(self, file_name: str, timestamp: Optional[datetime] = None) -> str:
        """
        Genera UUID principal para agrupamiento de procesamiento
        
        Args:
            file_name: Nombre del archivo original
            timestamp: Timestamp opcional (default: now)
            
        Returns:
            str: UUID de procesamiento
        """
        try:
            if timestamp is None:
                timestamp = datetime.now()
            
            # Usar UUID4 aleatorio para máxima unicidad
            processing_uuid = str(uuid.uuid4())
            
            self.logger.debug(
                f"UUID de procesamiento generado",
                context={
                    'processing_uuid': processing_uuid,
                    'file_name': file_name,
                    'timestamp': timestamp.isoformat()
                }
            )
            
            return processing_uuid
            
        except Exception as e:
            self.logger.error(f"Error generando UUID de procesamiento: {str(e)}", exc_info=True)
            # Fallback a UUID simple
            return str(uuid.uuid4())
    
    def generate_package_uuid(self, processing_uuid: str, package_number: int) -> str:
        """
        Genera UUID único para un paquete específico
        
        Args:
            processing_uuid: UUID del procesamiento padre
            package_number: Número del paquete
            
        Returns:
            str: UUID del paquete
        """
        try:
            # Usar UUID5 determinístico basado en procesamiento padre y número de paquete
            namespace = uuid.UUID('6ba7b810-9dad-11d1-80b4-00c04fd430c8')  # Namespace estándar
            name = f"{processing_uuid}-package-{package_number}"
            
            package_uuid = str(uuid.uuid5(namespace, name))
            
            self.logger.debug(
                f"UUID de paquete generado",
                context={
                    'package_uuid': package_uuid,
                    'processing_uuid': processing_uuid,
                    'package_number': package_number
                }
            )
            
            return package_uuid
            
        except Exception as e:
            self.logger.error(f"Error generando UUID de paquete: {str(e)}", exc_info=True)
            # Fallback a UUID aleatorio
            return str(uuid.uuid4())
    
    def generate_deterministic_uuid(self, seed_data: str) -> str:
        """
        Genera UUID determinístico basado en datos de entrada
        Útil para casos donde se requiere reproducibilidad
        
        Args:
            seed_data: Datos semilla para generar UUID
            
        Returns:
            str: UUID determinístico
        """
        try:
            # Usar UUID5 con namespace personalizado
            namespace = uuid.UUID('6ba7b811-9dad-11d1-80b4-00c04fd430c8')
            deterministic_uuid = str(uuid.uuid5(namespace, seed_data))
            
            self.logger.debug(
                f"UUID determinístico generado",
                context={'deterministic_uuid': deterministic_uuid, 'seed_length': len(seed_data)}
            )
            
            return deterministic_uuid
            
        except Exception as e:
            self.logger.error(f"Error generando UUID determinístico: {str(e)}", exc_info=True)
            return str(uuid.uuid4())
    
    def generate_trace_id(self) -> str:
        """
        Genera ID de trazabilidad para seguimiento de requests
        
        Returns:
            str: Trace ID único
        """
        try:
            trace_id = str(uuid.uuid4())
            
            self.logger.debug(f"Trace ID generado", context={'trace_id': trace_id})
            
            return trace_id
            
        except Exception as e:
            self.logger.error(f"Error generando trace ID: {str(e)}", exc_info=True)
            return str(uuid.uuid4())
    
    def validate_uuid_format(self, uuid_string: str) -> bool:
        """
        Valida formato de UUID
        
        Args:
            uuid_string: String a validar
            
        Returns:
            bool: True si es formato UUID válido
        """
        try:
            uuid.UUID(uuid_string)
            return True
        except (ValueError, TypeError):
            self.logger.warning(f"UUID inválido: {uuid_string}")
            return False
    
    def extract_uuid_info(self, uuid_string: str) -> dict:
        """
        Extrae información de un UUID
        
        Args:
            uuid_string: UUID a analizar
            
        Returns:
            dict: Información del UUID
        """
        try:
            uuid_obj = uuid.UUID(uuid_string)
            
            info = {
                'uuid': uuid_string,
                'version': uuid_obj.version,
                'variant': str(uuid_obj.variant),
                'is_valid': True
            }
            
            # Información adicional según la versión
            if uuid_obj.version == 1:
                info['timestamp'] = datetime.fromtimestamp(uuid_obj.time / 1e7 - 12219292800)
                info['node'] = uuid_obj.node
            elif uuid_obj.version == 4:
                info['type'] = 'random'
            elif uuid_obj.version == 5:
                info['type'] = 'deterministic'
            
            return info
            
        except (ValueError, TypeError) as e:
            self.logger.warning(f"Error analizando UUID {uuid_string}: {str(e)}")
            return {
                'uuid': uuid_string,
                'is_valid': False,
                'error': str(e)
            }
    
    def generate_short_id(self, length: int = 8) -> str:
        """
        Genera ID corto para casos donde UUID completo es demasiado largo
        
        Args:
            length: Longitud del ID (default: 8)
            
        Returns:
            str: ID corto alfanumérico
        """
        try:
            full_uuid = str(uuid.uuid4()).replace('-', '')
            short_id = full_uuid[:length].upper()
            
            self.logger.debug(f"ID corto generado", context={'short_id': short_id, 'length': length})
            
            return short_id
            
        except Exception as e:
            self.logger.error(f"Error generando ID corto: {str(e)}", exc_info=True)
            # Fallback usando timestamp
            return str(int(datetime.now().timestamp()))[:length]
