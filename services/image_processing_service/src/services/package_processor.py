"""
Package Processor Service
Servicio orquestador principal para el procesamiento completo de paquetes de imágenes
"""

from datetime import datetime
from typing import Dict, Any, Optional, List
import json

import sys
sys.path.insert(0, '/app/services/shared_utils/src')

from config import config
from logger import setup_logger
from storage_service import storage_service
from database_service import database_service
from pubsub_service import pubsub_service

from .image_downloader import ImageDownloader
from .zip_creator import ZipCreator
from .signed_url_generator import SignedUrlGenerator
from .cleanup_scheduler import CleanupScheduler


class PackageProcessor:
    """
    Servicio orquestador principal que coordina todo el flujo de procesamiento de paquetes
    """
    
    def __init__(self):
        self.logger = setup_logger(__name__, 'package-processor', config.APP_VERSION)
        
        # Inicializar servicios especializados
        self.image_downloader = ImageDownloader()
        self.zip_creator = ZipCreator()
        self.signed_url_generator = SignedUrlGenerator()
        self.cleanup_scheduler = CleanupScheduler()
        
        self.logger.info("✅ Package Processor inicializado")
    
    def process_complete_package(self, processing_uuid: str, package_uri: str, 
                               package_name: str, trace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Procesa un paquete completo: descarga → ZIP → URL firmada → cleanup programado
        
        Args:
            processing_uuid: UUID del procesamiento
            package_uri: URI del paquete en bucket json-a-procesar
            package_name: Nombre del paquete
            trace_id: ID de trazabilidad
            
        Returns:
            Dict con resultado completo del procesamiento
        """
        try:
            self.logger.processing(
                f"🚀 INICIANDO PROCESAMIENTO COMPLETO DE PAQUETE: {package_name}",
                context={
                    'processing_uuid': processing_uuid,
                    'package_uri': package_uri,
                    'package_name': package_name
                },
                trace_id=trace_id
            )
            
            # Crear registro de procesamiento en BD
            processing_record_id = database_service.create_image_processing_record(
                processing_uuid=processing_uuid,
                package_name=package_name,
                package_uri=package_uri,
                trace_id=trace_id
            )
            
            # PASO 1: Leer archivo del paquete desde bucket json-a-procesar
            self.logger.processing("📂 PASO 1: Leyendo archivo del paquete", trace_id=trace_id)
            
            package_data = self._read_package_from_uri(package_uri, trace_id)
            if not package_data:
                raise ValueError(f"No se pudo leer paquete desde: {package_uri}")
            
            # PASO 2: Extraer rutas de imágenes del paquete
            self.logger.processing("🔍 PASO 2: Extrayendo rutas de imágenes", trace_id=trace_id)
            
            image_paths = self._extract_image_paths_from_package(package_data, trace_id)
            if not image_paths:
                raise ValueError("No se encontraron rutas de imágenes en el paquete")
            
            # PASO 3: Descargar imágenes
            self.logger.processing(
                f"⬇️ PASO 3: Descargando {len(image_paths)} imágenes", 
                trace_id=trace_id
            )
            
            download_result = self.image_downloader.download_images_for_package(
                image_paths=image_paths,
                processing_uuid=processing_uuid,
                package_number=self._extract_package_number(package_name),
                trace_id=trace_id
            )
            
            if not download_result['success'] or download_result['successful_downloads'] == 0:
                raise ValueError("No se pudieron descargar imágenes válidas")
            
            # PASO 4: Crear archivo ZIP
            self.logger.processing("🗜️ PASO 4: Creando archivo ZIP", trace_id=trace_id)
            
            zip_result = self.zip_creator.create_zip_from_downloaded_images(
                download_result, trace_id
            )
            
            if not zip_result['success']:
                raise ValueError(f"Error creando ZIP: {zip_result.get('error', 'Unknown error')}")
            
            # PASO 5: Subir ZIP a bucket temporal
            self.logger.processing("☁️ PASO 5: Subiendo ZIP a GCS", trace_id=trace_id)
            
            gcs_upload_result = self.zip_creator.upload_zip_to_gcs(zip_result, trace_id)
            
            if not gcs_upload_result['success']:
                raise ValueError(f"Error subiendo ZIP a GCS: {gcs_upload_result.get('error', 'Unknown error')}")
            
            # PASO 6: Generar URL firmada
            self.logger.processing("🔐 PASO 6: Generando URL firmada", trace_id=trace_id)
            
            signed_url_result = self.signed_url_generator.generate_signed_url(
                gcs_upload_result, trace_id=trace_id
            )
            
            if not signed_url_result['success']:
                raise ValueError(f"Error generando URL firmada: {signed_url_result.get('error', 'Unknown error')}")
            
            # PASO 7: Programar cleanup automático
            self.logger.processing("🧹 PASO 7: Programando cleanup automático", trace_id=trace_id)
            
            cleanup_result = self.cleanup_scheduler.schedule_cleanup(
                processing_uuid=processing_uuid,
                cleanup_after_hours=config.TEMP_FILES_CLEANUP_HOURS,
                trace_id=trace_id
            )
            
            # PASO 8: Limpiar archivos temporales locales inmediatamente
            self.logger.processing("🧽 PASO 8: Limpiando archivos temporales locales", trace_id=trace_id)
            
            local_cleanup = self.image_downloader.cleanup_temp_directory(
                download_result['temp_directory'], trace_id
            )
            
            # PASO 9: Actualizar registro en BD con resultado exitoso
            processing_result = {
                'package_name': package_name,
                'images_processed': download_result['successful_downloads'],
                'zip_created': True,
                'zip_size_mb': zip_result['zip_size_mb'],
                'signed_url_generated': True,
                'signed_url': signed_url_result['signed_url'],
                'expiration_datetime': signed_url_result['expiration_datetime'],
                'cleanup_scheduled': cleanup_result.get('success', False),
                'local_cleanup': local_cleanup.get('cleaned', False)
            }
            
            database_service.update_image_processing_status(
                processing_uuid=processing_uuid,
                status='completed',
                result_data=processing_result,
                trace_id=trace_id
            )
            
            # PASO 10: Publicar mensaje para Email Service
            self.logger.processing("📧 PASO 10: Publicando mensaje para Email Service", trace_id=trace_id)
            
            email_data = self._prepare_email_data(
                processing_uuid, package_name, signed_url_result, download_result, zip_result
            )
            
            pubsub_service.publish_email_request(
                processing_uuid=processing_uuid,
                email_data=email_data,
                trace_id=trace_id
            )
            
            # Resultado final completo
            final_result = {
                'success': True,
                'processing_uuid': processing_uuid,
                'package_name': package_name,
                'processing_record_id': processing_record_id,
                'images_processed': download_result['successful_downloads'],
                'images_failed': download_result['failed_downloads'],
                'zip_created': True,
                'zip_filename': zip_result['zip_filename'],
                'zip_size_mb': zip_result['zip_size_mb'],
                'compression_ratio_percent': zip_result['compression_ratio_percent'],
                'signed_url_generated': True,
                'signed_url': signed_url_result['signed_url'],
                'expiration_hours': signed_url_result['expiration_hours'],
                'expiration_datetime': signed_url_result['expiration_datetime'],
                'cleanup_scheduled': cleanup_result.get('success', False),
                'email_published': True,
                'completed_at': datetime.now().isoformat()
            }
            
            self.logger.success(
                f"🎉 PROCESAMIENTO COMPLETO EXITOSO: {package_name}",
                context={
                    'processing_uuid': processing_uuid,
                    'images_processed': final_result['images_processed'],
                    'zip_size_mb': final_result['zip_size_mb'],
                    'signed_url_generated': final_result['signed_url_generated']
                },
                trace_id=trace_id
            )
            
            return final_result
            
        except Exception as e:
            error_msg = f"Error en procesamiento completo: {str(e)}"
            self.logger.error(error_msg, trace_id=trace_id, exc_info=True)
            
            # Actualizar estado de error en BD
            try:
                database_service.update_image_processing_status(
                    processing_uuid=processing_uuid,
                    status='failed',
                    result_data={'error': error_msg, 'package_name': package_name},
                    trace_id=trace_id
                )
            except:
                self.logger.error("Error actualizando estado de fallo en BD", trace_id=trace_id)
            
            return {
                'success': False,
                'error': error_msg,
                'processing_uuid': processing_uuid,
                'package_name': package_name,
                'failed_at': datetime.now().isoformat()
            }
    
    def _read_package_from_uri(self, package_uri: str, trace_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Lee archivo de paquete desde URI de GCS
        
        Args:
            package_uri: URI del archivo (ej: gs://bucket/path/file.json)
            trace_id: ID de trazabilidad
            
        Returns:
            Dict con datos del paquete o None si error
        """
        try:
            # Extraer bucket y path del URI
            if not package_uri.startswith('gs://'):
                raise ValueError(f"URI inválido: {package_uri}")
            
            uri_parts = package_uri[5:].split('/', 1)  # Remover 'gs://'
            if len(uri_parts) != 2:
                raise ValueError(f"Formato URI inválido: {package_uri}")
            
            bucket_name, file_path = uri_parts
            
            # Leer archivo JSON
            package_data = storage_service.read_json_file(bucket_name, file_path, trace_id)
            
            self.logger.debug(
                f"Paquete leído exitosamente: {file_path}",
                context={'bucket': bucket_name, 'file': file_path},
                trace_id=trace_id
            )
            
            return package_data
            
        except Exception as e:
            self.logger.error(f"Error leyendo paquete desde {package_uri}: {str(e)}", trace_id=trace_id)
            return None
    
    def _extract_image_paths_from_package(self, package_data: Dict[str, Any], 
                                        trace_id: Optional[str] = None) -> List[str]:
        """
        Extrae rutas de imágenes desde los datos del paquete
        
        Args:
            package_data: Datos del paquete JSON
            trace_id: ID de trazabilidad
            
        Returns:
            Lista de rutas de imágenes
        """
        try:
            image_paths = []
            
            # Obtener envíos del paquete
            envios = package_data.get('envios', [])
            if not envios:
                self.logger.warning("No se encontraron envíos en el paquete", trace_id=trace_id)
                return image_paths
            
            # Extraer rutas de imágenes enriquecidas
            rutas_imagenes = package_data.get('rutas_imagenes', {})
            
            for envio in envios:
                envio_id = str(envio.get('id', ''))
                if envio_id in rutas_imagenes:
                    envio_image_paths = rutas_imagenes[envio_id]
                    if isinstance(envio_image_paths, list):
                        image_paths.extend(envio_image_paths)
                    else:
                        self.logger.warning(f"Rutas de imágenes inválidas para envío {envio_id}", trace_id=trace_id)
            
            # Eliminar duplicados preservando orden
            unique_paths = []
            seen = set()
            for path in image_paths:
                if path and path not in seen:
                    unique_paths.append(path)
                    seen.add(path)
            
            self.logger.info(
                f"Extraídas {len(unique_paths)} rutas de imágenes únicas",
                context={'total_envios': len(envios), 'unique_paths': len(unique_paths)},
                trace_id=trace_id
            )
            
            return unique_paths
            
        except Exception as e:
            self.logger.error(f"Error extrayendo rutas de imágenes: {str(e)}", trace_id=trace_id, exc_info=True)
            return []
    
    def _extract_package_number(self, package_name: str) -> str:
        """
        Extrae número de paquete desde el nombre del archivo
        """
        try:
            # Buscar patrón como "parte_1_de_5" o "1_de_5"
            import re
            match = re.search(r'(?:parte_)?(\d+)_de_(\d+)', package_name)
            if match:
                return f"{match.group(1)}_de_{match.group(2)}"
            
            # Si no encuentra patrón, generar uno genérico
            return "1_de_1"
            
        except Exception:
            return "unknown"
    
    def _prepare_email_data(self, processing_uuid: str, package_name: str, 
                          signed_url_result: Dict[str, Any], download_result: Dict[str, Any],
                          zip_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepara datos para el servicio de email
        """
        return {
            'processing_uuid': processing_uuid,
            'package_name': package_name,
            'signed_url': signed_url_result['signed_url'],
            'download_filename': signed_url_result['download_filename'],
            'expiration_datetime': signed_url_result['expiration_datetime'],
            'expiration_hours': signed_url_result['expiration_hours'],
            'file_size_mb': signed_url_result['file_size_mb'],
            'images_processed': download_result['successful_downloads'],
            'images_failed': download_result['failed_downloads'],
            'compression_ratio_percent': zip_result['compression_ratio_percent'],
            'created_at': datetime.now().isoformat()
        }
    
    def verify_package_completeness(self, processing_uuid: str, 
                                  trace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Verifica si todos los paquetes de un procesamiento han sido completados
        
        Args:
            processing_uuid: UUID del procesamiento
            trace_id: ID de trazabilidad
            
        Returns:
            Dict con estado de completitud
        """
        try:
            # Obtener información del procesamiento original
            processing_record = database_service.get_processing_record(processing_uuid, trace_id)
            
            if not processing_record:
                raise ValueError(f"Procesamiento no encontrado: {processing_uuid}")
            
            # Obtener estado de procesamiento de imágenes
            image_processing_records = database_service.get_all_image_processing_records(
                processing_uuid, trace_id
            )
            
            total_packages_expected = processing_record.get('total_paquetes', 0)
            packages_completed = len([r for r in image_processing_records if r['estado'] == 'completed'])
            packages_failed = len([r for r in image_processing_records if r['estado'] == 'failed'])
            packages_in_progress = len([r for r in image_processing_records if r['estado'] == 'in_progress'])
            
            is_complete = packages_completed >= total_packages_expected
            
            result = {
                'processing_uuid': processing_uuid,
                'is_complete': is_complete,
                'total_packages_expected': total_packages_expected,
                'packages_completed': packages_completed,
                'packages_failed': packages_failed,
                'packages_in_progress': packages_in_progress,
                'completion_percentage': round((packages_completed / total_packages_expected * 100), 2) if total_packages_expected > 0 else 0,
                'verified_at': datetime.now().isoformat()
            }
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error verificando completitud de paquetes: {str(e)}", trace_id=trace_id, exc_info=True)
            return {
                'processing_uuid': processing_uuid,
                'is_complete': False,
                'error': str(e),
                'verified_at': datetime.now().isoformat()
            }
