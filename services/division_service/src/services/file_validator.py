"""
File Validator - Validador de estructura y contenido de archivos
Responsable de validar archivos antes del procesamiento
"""

import json
from typing import Dict, Any, List, Optional, Tuple
import sys

# Añadir shared_utils al path
sys.path.insert(0, '/app/services/shared_utils/src')

from logger import setup_logger
from storage_service import storage_service
from config import config


class FileValidator:
    """
    Validador de archivos JSON para procesamiento empresarial
    Implementa validaciones exhaustivas antes del procesamiento
    """
    
    def __init__(self):
        self.logger = setup_logger(__name__, 'file-validator', config.APP_VERSION)
        
        # Campos requeridos en el JSON
        self.required_fields = ['envios']
        self.required_shipment_fields = ['id']  # Campos mínimos en cada envío
    
    def validate_file_structure(self, bucket_name: str, file_name: str, 
                              trace_id: Optional[str] = None) -> bool:
        """
        Valida estructura completa del archivo antes del procesamiento
        
        Args:
            bucket_name: Nombre del bucket
            file_name: Nombre del archivo
            trace_id: ID de trazabilidad
            
        Returns:
            bool: True si el archivo es válido
        """
        try:
            self.logger.processing(
                f"Iniciando validación de estructura: {file_name}",
                trace_id=trace_id
            )
            
            # Paso 1: Validar existencia y accesibilidad
            if not storage_service.check_file_exists(bucket_name, file_name, trace_id):
                self.logger.error(f"Archivo no existe o no es accesible", trace_id=trace_id)
                return False
            
            # Paso 2: Leer y parsear JSON
            try:
                json_data = storage_service.read_json_file(bucket_name, file_name, trace_id)
            except json.JSONDecodeError as e:
                self.logger.error(f"Archivo no contiene JSON válido: {str(e)}", trace_id=trace_id)
                return False
            
            # Paso 3: Validar estructura JSON
            structure_valid = self._validate_json_structure(json_data, trace_id)
            if not structure_valid:
                return False
            
            # Paso 4: Validar contenido de envíos
            shipments_valid = self._validate_shipments_content(json_data.get('envios', []), trace_id)
            if not shipments_valid:
                return False
            
            # Paso 5: Validaciones empresariales adicionales
            business_valid = self._validate_business_rules(json_data, trace_id)
            if not business_valid:
                return False
            
            self.logger.success(
                f"Validación de estructura completada exitosamente",
                context={
                    'file_name': file_name,
                    'total_shipments': len(json_data.get('envios', [])),
                    'validation_passed': True
                },
                trace_id=trace_id
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error durante validación: {str(e)}", trace_id=trace_id, exc_info=True)
            return False
    
    def _validate_json_structure(self, json_data: Dict[str, Any], 
                               trace_id: Optional[str] = None) -> bool:
        """
        Valida estructura básica del JSON
        """
        try:
            validation_errors = []
            
            # Verificar campos requeridos
            for field in self.required_fields:
                if field not in json_data:
                    validation_errors.append(f"Campo requerido faltante: '{field}'")
            
            # Verificar que 'envios' sea una lista
            if 'envios' in json_data:
                if not isinstance(json_data['envios'], list):
                    validation_errors.append("Campo 'envios' debe ser una lista")
                elif len(json_data['envios']) == 0:
                    validation_errors.append("Lista 'envios' no puede estar vacía")
            
            # Log de errores encontrados
            if validation_errors:
                self.logger.error(
                    f"Errores en estructura JSON",
                    context={'validation_errors': validation_errors},
                    trace_id=trace_id
                )
                return False
            
            self.logger.debug("Estructura JSON válida", trace_id=trace_id)
            return True
            
        except Exception as e:
            self.logger.error(f"Error validando estructura JSON: {str(e)}", trace_id=trace_id)
            return False
    
    def _validate_shipments_content(self, shipments: List[Dict[str, Any]], 
                                  trace_id: Optional[str] = None) -> bool:
        """
        Valida contenido de los envíos
        """
        try:
            validation_errors = []
            shipment_ids = set()
            
            for idx, shipment in enumerate(shipments):
                # Verificar campos requeridos en envío
                for field in self.required_shipment_fields:
                    if field not in shipment:
                        validation_errors.append(f"Envío #{idx}: campo requerido '{field}' faltante")
                
                # Verificar unicidad de IDs
                shipment_id = shipment.get('id')
                if shipment_id:
                    if shipment_id in shipment_ids:
                        validation_errors.append(f"Envío #{idx}: ID duplicado '{shipment_id}'")
                    else:
                        shipment_ids.add(shipment_id)
                
                # Validaciones adicionales del envío
                if not self._validate_single_shipment(shipment, idx):
                    validation_errors.append(f"Envío #{idx}: validación de contenido fallida")
            
            # Límite de errores para no sobrecargar logs
            if len(validation_errors) > 10:
                self.logger.error(
                    f"Demasiados errores de validación en envíos",
                    context={
                        'total_errors': len(validation_errors),
                        'first_10_errors': validation_errors[:10]
                    },
                    trace_id=trace_id
                )
                return False
            elif validation_errors:
                self.logger.error(
                    f"Errores en contenido de envíos",
                    context={'validation_errors': validation_errors},
                    trace_id=trace_id
                )
                return False
            
            self.logger.debug(
                f"Contenido de envíos válido",
                context={'total_shipments': len(shipments), 'unique_ids': len(shipment_ids)},
                trace_id=trace_id
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validando contenido de envíos: {str(e)}", trace_id=trace_id)
            return False
    
    def _validate_single_shipment(self, shipment: Dict[str, Any], index: int) -> bool:
        """
        Valida un envío individual
        
        Args:
            shipment: Datos del envío
            index: Índice del envío en la lista
            
        Returns:
            bool: True si el envío es válido
        """
        try:
            # Validar ID no vacío
            shipment_id = shipment.get('id')
            if not shipment_id or (isinstance(shipment_id, str) and len(shipment_id.strip()) == 0):
                return False
            
            # Validar que ID sea string o número
            if not isinstance(shipment_id, (str, int, float)):
                return False
            
            # Si hay campos adicionales requeridos, validarlos aquí
            # Por ejemplo: destino, peso, etc.
            
            return True
            
        except Exception:
            return False
    
    def _validate_business_rules(self, json_data: Dict[str, Any], 
                               trace_id: Optional[str] = None) -> bool:
        """
        Validaciones de reglas empresariales
        """
        try:
            shipments = json_data.get('envios', [])
            total_shipments = len(shipments)
            
            # Validación 1: Límite máximo de envíos por archivo
            max_shipments_per_file = config.MAX_SHIPMENTS_PER_FILE * 100  # Límite empresarial
            if total_shipments > max_shipments_per_file:
                self.logger.error(
                    f"Archivo excede límite empresarial de envíos",
                    context={
                        'total_shipments': total_shipments,
                        'max_allowed': max_shipments_per_file
                    },
                    trace_id=trace_id
                )
                return False
            
            # Validación 2: Mínimo de envíos para procesamiento
            min_shipments_for_processing = 1
            if total_shipments < min_shipments_for_processing:
                self.logger.error(
                    f"Archivo no tiene suficientes envíos para procesamiento",
                    context={
                        'total_shipments': total_shipments,
                        'min_required': min_shipments_for_processing
                    },
                    trace_id=trace_id
                )
                return False
            
            # Validación 3: Verificar metadatos si existen
            if 'metadatos' in json_data:
                if not self._validate_metadata_structure(json_data['metadatos'], trace_id):
                    return False
            
            self.logger.debug(
                f"Reglas empresariales validadas exitosamente",
                context={'total_shipments': total_shipments},
                trace_id=trace_id
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validando reglas empresariales: {str(e)}", trace_id=trace_id)
            return False
    
    def _validate_metadata_structure(self, metadata: Dict[str, Any], 
                                   trace_id: Optional[str] = None) -> bool:
        """
        Valida estructura de metadatos si están presentes
        """
        try:
            # Los metadatos son opcionales, pero si existen deben tener estructura válida
            if not isinstance(metadata, dict):
                self.logger.warning("Metadatos no son un objeto válido", trace_id=trace_id)
                return False
            
            # Validar campos específicos de metadatos si son críticos
            # Por ahora, aceptamos cualquier estructura de metadatos
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validando metadatos: {str(e)}", trace_id=trace_id)
            return False
    
    def get_file_statistics(self, bucket_name: str, file_name: str, 
                          trace_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Obtiene estadísticas del archivo para análisis
        
        Args:
            bucket_name: Nombre del bucket
            file_name: Nombre del archivo
            trace_id: ID de trazabilidad
            
        Returns:
            Dict con estadísticas del archivo o None si hay error
        """
        try:
            self.logger.processing(f"Obteniendo estadísticas de archivo: {file_name}", trace_id=trace_id)
            
            # Leer archivo
            json_data = storage_service.read_json_file(bucket_name, file_name, trace_id)
            shipments = json_data.get('envios', [])
            
            # Calcular estadísticas
            stats = {
                'file_name': file_name,
                'total_shipments': len(shipments),
                'estimated_packages': max(1, len(shipments) // config.MAX_SHIPMENTS_PER_FILE + 
                                        (1 if len(shipments) % config.MAX_SHIPMENTS_PER_FILE > 0 else 0)),
                'has_metadata': 'metadatos' in json_data,
                'unique_shipment_ids': len(set(str(s.get('id', '')) for s in shipments)),
                'validation_score': self._calculate_validation_score(json_data, trace_id)
            }
            
            # Análisis adicional
            if shipments:
                stats['first_shipment_id'] = shipments[0].get('id')
                stats['last_shipment_id'] = shipments[-1].get('id')
                
                # Análisis de campos comunes
                all_fields = set()
                for shipment in shipments[:10]:  # Analizar primeros 10 para eficiencia
                    all_fields.update(shipment.keys())
                stats['common_fields'] = list(all_fields)
            
            self.logger.success(
                f"Estadísticas calculadas exitosamente",
                context=stats,
                trace_id=trace_id
            )
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error obteniendo estadísticas: {str(e)}", trace_id=trace_id, exc_info=True)
            return None
    
    def _calculate_validation_score(self, json_data: Dict[str, Any], 
                                  trace_id: Optional[str] = None) -> int:
        """
        Calcula score de validación (0-100) basado en calidad de datos
        """
        try:
            score = 0
            shipments = json_data.get('envios', [])
            
            # Score base por tener estructura válida
            score += 30
            
            # Score por tener envíos
            if shipments:
                score += 20
            
            # Score por unicidad de IDs
            unique_ids = len(set(str(s.get('id', '')) for s in shipments))
            if unique_ids == len(shipments):
                score += 25
            else:
                score += int((unique_ids / len(shipments)) * 25)
            
            # Score por completitud de datos
            filled_fields = 0
            total_fields = 0
            for shipment in shipments[:5]:  # Muestra de primeros 5
                for value in shipment.values():
                    total_fields += 1
                    if value is not None and str(value).strip():
                        filled_fields += 1
            
            if total_fields > 0:
                score += int((filled_fields / total_fields) * 25)
            
            return min(100, max(0, score))
            
        except Exception as e:
            self.logger.error(f"Error calculando validation score: {str(e)}", trace_id=trace_id)
            return 0
