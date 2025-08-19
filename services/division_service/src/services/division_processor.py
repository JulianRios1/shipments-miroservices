"""
Division Processor - Lógica principal de división de archivos
Responsable de procesar archivos JSON, dividirlos con UUID y moverlos
"""

import uuid
import copy
import math
from datetime import datetime
from typing import Dict, Any, List, Optional
import sys

# Añadir shared_utils al path
sys.path.insert(0, '/app/services/shared_utils/src')

from logger import setup_logger
from storage_service import storage_service
from database_service import database_service
from pubsub_service import pubsub_service
from config import config


class DivisionProcessor:
    """
    Procesador principal para división de archivos JSON
    Implementa la lógica empresarial de división con UUID y numeración
    """
    
    def __init__(self):
        self.logger = setup_logger(__name__, 'division-processor', config.APP_VERSION)
    
    def process_file_with_division(self, bucket_name: str, file_name: str, 
                                 trace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Procesa archivo completo: lectura → división → enriquecimiento → movimiento → Pub/Sub
        
        Args:
            bucket_name: Nombre del bucket origen
            file_name: Nombre del archivo
            trace_id: ID de trazabilidad
            
        Returns:
            Dict con resultado del procesamiento
        """
        processing_uuid = str(uuid.uuid4())
        
        try:
            self.logger.processing(
                f"Iniciando procesamiento completo de archivo: {file_name}",
                context={'processing_uuid': processing_uuid},
                trace_id=trace_id
            )
            
            # Paso 1: Leer archivo JSON del bucket origen
            json_data = storage_service.read_json_file(bucket_name, file_name, trace_id=trace_id)
            shipments = json_data.get('envios', [])
            
            if not shipments:
                raise ValueError("Archivo no contiene envíos válidos")
            
            total_shipments = len(shipments)
            
            self.logger.info(
                f"Archivo cargado exitosamente",
                context={'total_shipments': total_shipments, 'processing_uuid': processing_uuid},
                trace_id=trace_id
            )
            
            # Paso 2: Calcular división y paquetes necesarios
            packages_needed = math.ceil(total_shipments / config.MAX_SHIPMENTS_PER_FILE)
            
            # Paso 3: Crear registro en base de datos
            db_record_id = database_service.create_file_processing_record(
                file_name=file_name,
                processing_uuid=processing_uuid,
                total_shipments=total_shipments,
                total_packages=packages_needed,
                trace_id=trace_id
            )
            
            # Paso 4: Obtener rutas de imágenes de la BD
            shipment_ids = [str(shipment.get('id', '')) for shipment in shipments]
            image_paths = database_service.get_image_paths_by_shipment_ids(shipment_ids, trace_id=trace_id)
            
            # Paso 5: Dividir archivo en paquetes
            packages = self._divide_file_into_packages(
                json_data=json_data,
                processing_uuid=processing_uuid,
                image_paths=image_paths,
                trace_id=trace_id
            )
            
            # Paso 6: Mover paquetes al bucket de procesamiento
            moved_files = []
            for package in packages:
                moved_file = self._move_package_to_processing_bucket(package, trace_id=trace_id)
                moved_files.append(moved_file)
            
            # Paso 7: Eliminar archivo original
            storage_service.delete_file(bucket_name, file_name, trace_id=trace_id)
            
            # Paso 8: Actualizar estado en BD
            result_data = {
                'packages_created': len(packages),
                'files_moved': moved_files,
                'total_shipments': total_shipments,
                'image_coverage_stats': self._calculate_coverage_stats(image_paths, shipment_ids)
            }
            
            database_service.update_file_processing_status(
                processing_uuid=processing_uuid,
                status='completed',
                result_data=result_data,
                trace_id=trace_id
            )
            
            # Paso 9: Publicar mensaje para activar workflow
            workflow_data = {
                'processing_uuid': processing_uuid,
                'original_file': file_name,
                'packages': moved_files,
                'total_shipments': total_shipments,
                'packages_created': len(packages)
            }
            
            pubsub_service.publish_workflow_trigger(
                processing_uuid=processing_uuid,
                workflow_data=workflow_data,
                trace_id=trace_id
            )
            
            # Resultado final
            result = {
                'status': 'success',
                'processing_uuid': processing_uuid,
                'original_file': file_name,
                'total_shipments': total_shipments,
                'packages_created': len(packages),
                'files_moved': moved_files,
                'database_record_id': db_record_id,
                'timestamp': datetime.now().isoformat()
            }
            
            self.logger.success(
                f"Procesamiento completo exitoso",
                context=result,
                trace_id=trace_id
            )
            
            return result
            
        except Exception as e:
            error_msg = f"Error en procesamiento: {str(e)}"
            self.logger.error(error_msg, trace_id=trace_id, exc_info=True)
            
            # Actualizar estado de error en BD
            try:
                database_service.update_file_processing_status(
                    processing_uuid=processing_uuid,
                    status='failed',
                    result_data={'error': error_msg},
                    trace_id=trace_id
                )
            except:
                self.logger.error("Error actualizando estado de fallo en BD", trace_id=trace_id)
            
            raise
    
    def _divide_file_into_packages(self, json_data: Dict[str, Any], processing_uuid: str,
                                 image_paths: Dict[str, List[str]], 
                                 trace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Divide archivo JSON en paquetes con UUID y numeración
        
        Args:
            json_data: Datos JSON originales
            processing_uuid: UUID del procesamiento
            image_paths: Rutas de imágenes obtenidas de BD
            trace_id: ID de trazabilidad
            
        Returns:
            List[Dict]: Lista de paquetes JSON
        """
        try:
            shipments = json_data.get('envios', [])
            total_shipments = len(shipments)
            max_per_package = config.MAX_SHIPMENTS_PER_FILE
            
            # Calcular número de paquetes
            total_packages = math.ceil(total_shipments / max_per_package)
            
            self.logger.processing(
                f"Dividiendo archivo en {total_packages} paquetes",
                context={
                    'total_shipments': total_shipments,
                    'max_per_package': max_per_package,
                    'total_packages': total_packages
                },
                trace_id=trace_id
            )
            
            packages = []
            
            for package_num in range(total_packages):
                # Calcular rango de envíos para este paquete
                start_idx = package_num * max_per_package
                end_idx = min(start_idx + max_per_package, total_shipments)
                package_shipments = shipments[start_idx:end_idx]
                
                # Crear paquete con metadatos empresariales
                package = self._create_package_with_metadata(
                    original_data=json_data,
                    package_shipments=package_shipments,
                    package_number=package_num + 1,  # 1-indexed
                    total_packages=total_packages,
                    processing_uuid=processing_uuid,
                    image_paths=image_paths,
                    trace_id=trace_id
                )
                
                packages.append(package)
                
                self.logger.debug(
                    f"Paquete creado: {package_num + 1}/{total_packages}",
                    context={
                        'shipments_in_package': len(package_shipments),
                        'package_uuid': package['metadatos']['package_uuid']
                    },
                    trace_id=trace_id
                )
            
            self.logger.success(
                f"División completada exitosamente",
                context={'packages_created': len(packages)},
                trace_id=trace_id
            )
            
            return packages
            
        except Exception as e:
            self.logger.error(f"Error dividiendo archivo: {str(e)}", trace_id=trace_id, exc_info=True)
            raise
    
    def _create_package_with_metadata(self, original_data: Dict[str, Any], 
                                    package_shipments: List[Dict[str, Any]],
                                    package_number: int, total_packages: int,
                                    processing_uuid: str, image_paths: Dict[str, List[str]],
                                    trace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Crea paquete individual con metadatos empresariales completos
        """
        try:
            # Generar UUID único para este paquete
            package_uuid = str(uuid.uuid4())
            
            # Crear copia del archivo original
            package_data = copy.deepcopy(original_data)
            
            # Reemplazar envíos con los del paquete
            package_data['envios'] = package_shipments
            
            # Enriquecer envíos con rutas de imágenes
            enriched_shipments = []
            total_images_in_package = 0
            
            for shipment in package_shipments:
                enriched_shipment = copy.deepcopy(shipment)
                shipment_id = str(shipment.get('id', ''))
                
                if shipment_id in image_paths:
                    enriched_shipment['imagenes'] = image_paths[shipment_id]
                    total_images_in_package += len(image_paths[shipment_id])
                else:
                    enriched_shipment['imagenes'] = []
                
                enriched_shipments.append(enriched_shipment)
            
            package_data['envios'] = enriched_shipments
            
            # Crear metadatos empresariales completos
            package_data['metadatos'] = {
                # Información de agrupamiento (REQUERIDO POR FLUJO EMPRESARIAL)
                'processing_uuid': processing_uuid,  # UUID de agrupamiento principal
                'package_uuid': package_uuid,        # UUID único del paquete
                'package_number': package_number,    # Número de paquete (ej: 2)
                'total_packages': total_packages,    # Total de paquetes (ej: 10)
                'package_label': f"{package_number}/{total_packages}",  # Label (ej: "2/10")
                
                # Información del archivo original
                'original_file': original_data.get('nombre_archivo', 'unknown'),
                'original_total_shipments': len(original_data.get('envios', [])),
                
                # Información del paquete
                'package_shipments_count': len(package_shipments),
                'package_images_count': total_images_in_package,
                
                # Timestamps y procesamiento
                'created_at': datetime.now().isoformat(),
                'service_origin': 'division-service',
                'service_version': config.APP_VERSION,
                
                # Información de rango
                'shipments_range': {
                    'start': package_shipments[0].get('id') if package_shipments else None,
                    'end': package_shipments[-1].get('id') if package_shipments else None
                }
            }
            
            # Información de imágenes para este paquete
            package_data['imagenes_stats'] = {
                'total_images': total_images_in_package,
                'shipments_with_images': len([s for s in enriched_shipments if s.get('imagenes')]),
                'shipments_without_images': len([s for s in enriched_shipments if not s.get('imagenes')]),
                'coverage_percentage': round(
                    (len([s for s in enriched_shipments if s.get('imagenes')]) / len(enriched_shipments) * 100), 2
                ) if enriched_shipments else 0.0
            }
            
            self.logger.debug(
                f"Paquete creado con metadatos completos",
                context={
                    'package_uuid': package_uuid,
                    'package_number': package_number,
                    'shipments': len(package_shipments),
                    'images': total_images_in_package
                },
                trace_id=trace_id
            )
            
            return package_data
            
        except Exception as e:
            self.logger.error(f"Error creando paquete: {str(e)}", trace_id=trace_id, exc_info=True)
            raise
    
    def _move_package_to_processing_bucket(self, package: Dict[str, Any], 
                                         trace_id: Optional[str] = None) -> str:
        """
        Mueve paquete al bucket de procesamiento
        
        Args:
            package: Datos del paquete
            trace_id: ID de trazabilidad
            
        Returns:
            str: URI del archivo movido
        """
        try:
            # Generar nombre de archivo para el paquete
            processing_uuid = package['metadatos']['processing_uuid']
            package_number = package['metadatos']['package_number']
            total_packages = package['metadatos']['total_packages']
            original_file = package['metadatos']['original_file']
            
            # Remover extensión del archivo original
            base_name = original_file.replace('.json', '')
            
            # Formato: nombreoriginal_uuid_paquete_N_de_M.json
            package_filename = f"{base_name}_{processing_uuid}_{package_number}_de_{total_packages}.json"
            
            # Escribir archivo al bucket de procesamiento
            uri = storage_service.write_json_file(
                bucket_name=config.BUCKET_JSON_A_PROCESAR,
                file_name=package_filename,
                data=package,
                metadata={
                    'processing_uuid': processing_uuid,
                    'package_number': str(package_number),
                    'total_packages': str(total_packages),
                    'original_file': original_file
                },
                trace_id=trace_id
            )
            
            self.logger.success(
                f"Paquete movido al bucket de procesamiento",
                context={
                    'package_filename': package_filename,
                    'uri': uri,
                    'package_number': package_number
                },
                trace_id=trace_id
            )
            
            return uri
            
        except Exception as e:
            self.logger.error(f"Error moviendo paquete: {str(e)}", trace_id=trace_id, exc_info=True)
            raise
    
    def _calculate_coverage_stats(self, image_paths: Dict[str, List[str]], 
                                shipment_ids: List[str]) -> Dict[str, Any]:
        """
        Calcula estadísticas de cobertura de imágenes
        """
        total_shipments = len(shipment_ids)
        shipments_with_images = len(image_paths)
        total_images = sum(len(paths) for paths in image_paths.values())
        
        coverage_percentage = (shipments_with_images / total_shipments * 100) if total_shipments > 0 else 0.0
        
        return {
            'total_shipments': total_shipments,
            'shipments_with_images': shipments_with_images,
            'shipments_without_images': total_shipments - shipments_with_images,
            'coverage_percentage': round(coverage_percentage, 2),
            'total_images': total_images,
            'avg_images_per_shipment': round(total_images / total_shipments, 2) if total_shipments > 0 else 0.0
        }
