"""
Cleanup Scheduler Service
Responsable de programar y ejecutar limpieza de archivos temporales
"""

import os
import shutil
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from google.cloud import storage, scheduler_v1
from google.cloud.exceptions import NotFound

import sys
sys.path.insert(0, '/app/services/shared_utils/src')

from config import config
from logger import setup_logger
from database_service import database_service


class CleanupScheduler:
    """
    Servicio especializado para programar y ejecutar limpieza de archivos temporales
    """
    
    def __init__(self):
        self.logger = setup_logger(__name__, 'cleanup-scheduler', config.APP_VERSION)
        self.storage_client = storage.Client()
        
        # Inicializar Cloud Scheduler client (opcional, depende de si usamos scheduler)
        try:
            self.scheduler_client = scheduler_v1.CloudSchedulerClient()
            self.scheduler_available = True
        except Exception as e:
            self.logger.warning(f"Cloud Scheduler no disponible: {str(e)}")
            self.scheduler_client = None
            self.scheduler_available = False
        
        self.logger.info("✅ Cleanup Scheduler inicializado")
    
    def schedule_cleanup(self, processing_uuid: str, cleanup_after_hours: int = None,
                        trace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Programa limpieza de archivos temporales para un procesamiento específico
        
        Args:
            processing_uuid: UUID del procesamiento
            cleanup_after_hours: Horas después de las cuales limpiar
            trace_id: ID de trazabilidad
            
        Returns:
            Dict con información de programación
        """
        try:
            if cleanup_after_hours is None:
                cleanup_after_hours = config.TEMP_FILES_CLEANUP_HOURS
            
            self.logger.processing(
                f"Programando cleanup para procesamiento {processing_uuid}",
                context={
                    'processing_uuid': processing_uuid,
                    'cleanup_after_hours': cleanup_after_hours
                },
                trace_id=trace_id
            )
            
            # Calcular timestamp de cuando ejecutar cleanup
            cleanup_at = datetime.now() + timedelta(hours=cleanup_after_hours)
            
            # Registrar en base de datos la programación de cleanup
            cleanup_record_id = database_service.create_cleanup_record(
                processing_uuid=processing_uuid,
                cleanup_scheduled_for=cleanup_at,
                cleanup_after_hours=cleanup_after_hours,
                trace_id=trace_id
            )
            
            # Si Cloud Scheduler está disponible, crear job programado
            scheduler_job_name = None
            if self.scheduler_available:
                try:
                    scheduler_job_name = self._create_scheduler_job(
                        processing_uuid, cleanup_at, trace_id
                    )
                except Exception as e:
                    self.logger.warning(f"No se pudo crear job en Cloud Scheduler: {str(e)}", trace_id=trace_id)
            
            result = {
                'success': True,
                'processing_uuid': processing_uuid,
                'cleanup_record_id': cleanup_record_id,
                'scheduled_for': cleanup_at.isoformat(),
                'cleanup_after_hours': cleanup_after_hours,
                'scheduler_job_name': scheduler_job_name,
                'scheduled_at': datetime.now().isoformat()
            }
            
            self.logger.success(
                f"Cleanup programado exitosamente",
                context={
                    'processing_uuid': processing_uuid,
                    'scheduled_for': cleanup_at.isoformat()
                },
                trace_id=trace_id
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error programando cleanup: {str(e)}", trace_id=trace_id, exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'processing_uuid': processing_uuid
            }
    
    def execute_cleanup_now(self, processing_uuid: str, trace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Ejecuta limpieza inmediata para un procesamiento específico
        
        Args:
            processing_uuid: UUID del procesamiento
            trace_id: ID de trazabilidad
            
        Returns:
            Dict con resultado de limpieza
        """
        try:
            self.logger.processing(
                f"Ejecutando cleanup inmediato para procesamiento {processing_uuid}",
                context={'processing_uuid': processing_uuid},
                trace_id=trace_id
            )
            
            # Obtener información del procesamiento desde BD
            processing_info = database_service.get_image_processing_record(processing_uuid, trace_id)
            
            if not processing_info:
                raise ValueError(f"Procesamiento no encontrado: {processing_uuid}")
            
            # Limpiar archivos temporales en GCS
            gcs_cleanup_result = self._cleanup_gcs_temp_files(processing_uuid, trace_id)
            
            # Limpiar directorios temporales locales (si existen)
            local_cleanup_result = self._cleanup_local_temp_files(processing_uuid, trace_id)
            
            # Actualizar estado en base de datos
            database_service.update_cleanup_status(
                processing_uuid=processing_uuid,
                cleanup_completed=True,
                cleanup_result={
                    'gcs_cleanup': gcs_cleanup_result,
                    'local_cleanup': local_cleanup_result
                },
                trace_id=trace_id
            )
            
            # Calcular totales
            total_files_deleted = (
                gcs_cleanup_result.get('files_deleted', 0) + 
                local_cleanup_result.get('files_deleted', 0)
            )
            total_storage_freed_mb = (
                gcs_cleanup_result.get('storage_freed_mb', 0) + 
                local_cleanup_result.get('storage_freed_mb', 0)
            )
            
            result = {
                'success': True,
                'processing_uuid': processing_uuid,
                'files_deleted': total_files_deleted,
                'storage_freed_mb': round(total_storage_freed_mb, 2),
                'gcs_cleanup': gcs_cleanup_result,
                'local_cleanup': local_cleanup_result,
                'cleaned_at': datetime.now().isoformat()
            }
            
            self.logger.success(
                f"Cleanup ejecutado exitosamente",
                context={
                    'processing_uuid': processing_uuid,
                    'files_deleted': total_files_deleted,
                    'storage_freed_mb': total_storage_freed_mb
                },
                trace_id=trace_id
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error ejecutando cleanup: {str(e)}", trace_id=trace_id, exc_info=True)
            
            # Marcar como fallido en base de datos
            try:
                database_service.update_cleanup_status(
                    processing_uuid=processing_uuid,
                    cleanup_completed=False,
                    cleanup_result={'error': str(e)},
                    trace_id=trace_id
                )
            except:
                pass
            
            return {
                'success': False,
                'error': str(e),
                'processing_uuid': processing_uuid
            }
    
    def _cleanup_gcs_temp_files(self, processing_uuid: str, trace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Limpia archivos temporales en Google Cloud Storage
        """
        try:
            bucket = self.storage_client.bucket(config.BUCKET_IMAGENES_TEMP)
            
            # Listar todos los archivos con el processing_uuid como prefijo
            prefix = f"{processing_uuid}/"
            blobs = list(bucket.list_blobs(prefix=prefix))
            
            files_deleted = 0
            total_size_bytes = 0
            
            for blob in blobs:
                try:
                    # Obtener tamaño antes de eliminar
                    blob.reload()
                    size_bytes = blob.size or 0
                    total_size_bytes += size_bytes
                    
                    # Eliminar archivo
                    blob.delete()
                    files_deleted += 1
                    
                    self.logger.debug(f"Archivo GCS eliminado: {blob.name}", trace_id=trace_id)
                    
                except Exception as e:
                    self.logger.warning(f"Error eliminando archivo GCS {blob.name}: {str(e)}", trace_id=trace_id)
            
            return {
                'success': True,
                'files_deleted': files_deleted,
                'storage_freed_bytes': total_size_bytes,
                'storage_freed_mb': round(total_size_bytes / (1024 * 1024), 2),
                'bucket': config.BUCKET_IMAGENES_TEMP,
                'prefix': prefix
            }
            
        except Exception as e:
            self.logger.error(f"Error en cleanup de GCS: {str(e)}", trace_id=trace_id)
            return {
                'success': False,
                'error': str(e),
                'files_deleted': 0,
                'storage_freed_mb': 0
            }
    
    def _cleanup_local_temp_files(self, processing_uuid: str, trace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Limpia directorios temporales locales
        """
        try:
            import tempfile
            
            # Buscar directorios temporales relacionados con este procesamiento
            temp_base = tempfile.gettempdir()
            processing_temp_dir = os.path.join(temp_base, 'shipments_processing', processing_uuid)
            
            if not os.path.exists(processing_temp_dir):
                return {
                    'success': True,
                    'files_deleted': 0,
                    'storage_freed_mb': 0,
                    'reason': 'No temp directory found'
                }
            
            # Calcular tamaño del directorio antes de eliminarlo
            total_size_bytes = 0
            files_count = 0
            
            for dirpath, dirnames, filenames in os.walk(processing_temp_dir):
                for filename in filenames:
                    file_path = os.path.join(dirpath, filename)
                    try:
                        total_size_bytes += os.path.getsize(file_path)
                        files_count += 1
                    except (OSError, IOError):
                        pass
            
            # Eliminar directorio completo
            shutil.rmtree(processing_temp_dir)
            
            return {
                'success': True,
                'files_deleted': files_count,
                'storage_freed_bytes': total_size_bytes,
                'storage_freed_mb': round(total_size_bytes / (1024 * 1024), 2),
                'directory_removed': processing_temp_dir
            }
            
        except Exception as e:
            self.logger.error(f"Error en cleanup local: {str(e)}", trace_id=trace_id)
            return {
                'success': False,
                'error': str(e),
                'files_deleted': 0,
                'storage_freed_mb': 0
            }
    
    def _create_scheduler_job(self, processing_uuid: str, cleanup_at: datetime, 
                            trace_id: Optional[str] = None) -> Optional[str]:
        """
        Crea job en Cloud Scheduler para ejecutar cleanup automático
        """
        try:
            if not self.scheduler_available:
                return None
            
            project_id = config.GOOGLE_CLOUD_PROJECT
            location = config.GCP_REGION
            
            # Nombre único para el job
            job_name = f"cleanup-{processing_uuid}"
            
            # URL del endpoint de cleanup
            cleanup_url = f"{config.IMAGE_PROCESSING_SERVICE_URL}/cleanup/execute/{processing_uuid}"
            
            # Configurar el job para que se ejecute una sola vez
            parent = self.scheduler_client.location_path(project_id, location)
            
            job = {
                'name': self.scheduler_client.job_path(project_id, location, job_name),
                'http_target': {
                    'uri': cleanup_url,
                    'http_method': 'POST',
                    'headers': {
                        'Content-Type': 'application/json'
                    }
                },
                'schedule': self._datetime_to_cron(cleanup_at),
                'time_zone': 'UTC',
                'description': f'Cleanup automático para procesamiento {processing_uuid}'
            }
            
            # Crear job
            created_job = self.scheduler_client.create_job(parent=parent, job=job)
            
            self.logger.info(f"Job de Cloud Scheduler creado: {job_name}", trace_id=trace_id)
            
            return job_name
            
        except Exception as e:
            self.logger.warning(f"Error creando job de Cloud Scheduler: {str(e)}", trace_id=trace_id)
            return None
    
    def _datetime_to_cron(self, dt: datetime) -> str:
        """
        Convierte datetime a expresión cron para Cloud Scheduler
        """
        # Formato: minuto hora dia mes dia_semana
        return f"{dt.minute} {dt.hour} {dt.day} {dt.month} *"
    
    def get_pending_cleanups(self, trace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Obtiene lista de cleanups pendientes de ejecutar
        """
        try:
            pending_cleanups = database_service.get_pending_cleanups(trace_id=trace_id)
            
            now = datetime.now()
            ready_for_cleanup = []
            
            for cleanup in pending_cleanups:
                cleanup_scheduled_for = cleanup['cleanup_scheduled_for']
                if cleanup_scheduled_for <= now:
                    ready_for_cleanup.append(cleanup)
            
            return {
                'success': True,
                'total_pending': len(pending_cleanups),
                'ready_for_cleanup': len(ready_for_cleanup),
                'pending_cleanups': pending_cleanups,
                'ready_cleanups': ready_for_cleanup
            }
            
        except Exception as e:
            self.logger.error(f"Error obteniendo cleanups pendientes: {str(e)}", trace_id=trace_id)
            return {
                'success': False,
                'error': str(e)
            }
    
    def execute_pending_cleanups(self, trace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Ejecuta todos los cleanups que están listos para ejecutarse
        """
        try:
            pending_result = self.get_pending_cleanups(trace_id)
            
            if not pending_result['success']:
                return pending_result
            
            ready_cleanups = pending_result['ready_cleanups']
            
            if not ready_cleanups:
                return {
                    'success': True,
                    'cleanups_executed': 0,
                    'message': 'No hay cleanups listos para ejecutar'
                }
            
            self.logger.processing(
                f"Ejecutando {len(ready_cleanups)} cleanups pendientes",
                context={'count': len(ready_cleanups)},
                trace_id=trace_id
            )
            
            successful_cleanups = 0
            failed_cleanups = 0
            cleanup_results = []
            
            for cleanup in ready_cleanups:
                processing_uuid = cleanup['processing_uuid']
                try:
                    result = self.execute_cleanup_now(processing_uuid, trace_id)
                    cleanup_results.append(result)
                    
                    if result['success']:
                        successful_cleanups += 1
                    else:
                        failed_cleanups += 1
                        
                except Exception as e:
                    failed_cleanups += 1
                    cleanup_results.append({
                        'success': False,
                        'processing_uuid': processing_uuid,
                        'error': str(e)
                    })
            
            return {
                'success': successful_cleanups > 0,
                'cleanups_executed': successful_cleanups + failed_cleanups,
                'successful_cleanups': successful_cleanups,
                'failed_cleanups': failed_cleanups,
                'results': cleanup_results
            }
            
        except Exception as e:
            self.logger.error(f"Error ejecutando cleanups pendientes: {str(e)}", trace_id=trace_id, exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
