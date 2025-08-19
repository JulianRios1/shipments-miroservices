"""
Signed URL Generator Service
Responsable de generar URLs firmadas para descarga temporal de archivos ZIP
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from google.cloud import storage
from google.auth import default
from google.auth.exceptions import DefaultCredentialsError

import sys
sys.path.insert(0, '/app/services/shared_utils/src')

from config import config
from logger import setup_logger


class SignedUrlGenerator:
    """
    Servicio especializado para generar URLs firmadas de Google Cloud Storage
    """
    
    def __init__(self):
        self.logger = setup_logger(__name__, 'signed-url-generator', config.APP_VERSION)
        self.storage_client = storage.Client()
        
        # Configuración por defecto
        self.default_expiration_hours = config.SIGNED_URL_EXPIRATION_HOURS
        self.max_expiration_hours = 24  # Máximo permitido para URLs firmadas
        
        self.logger.info("✅ Signed URL Generator inicializado")
    
    def generate_signed_url(self, gcs_upload_result: Dict[str, Any], 
                          expiration_hours: Optional[int] = None,
                          trace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Genera URL firmada para archivo ZIP subido a GCS
        
        Args:
            gcs_upload_result: Resultado de ZipCreator.upload_zip_to_gcs
            expiration_hours: Horas de expiración (por defecto usa config)
            trace_id: ID de trazabilidad
            
        Returns:
            Dict con información de la URL firmada
        """
        try:
            if not gcs_upload_result.get('success'):
                raise ValueError("Subida a GCS no fue exitosa")
            
            processing_uuid = gcs_upload_result['processing_uuid']
            gcs_object_name = gcs_upload_result['gcs_object_name']
            bucket_name = gcs_upload_result['bucket_name']
            
            # Usar expiration_hours proporcionado o el por defecto
            if expiration_hours is None:
                expiration_hours = self.default_expiration_hours
            
            # Validar límites de expiración
            if expiration_hours < 1:
                expiration_hours = 1
            elif expiration_hours > self.max_expiration_hours:
                expiration_hours = self.max_expiration_hours
            
            self.logger.processing(
                f"Generando URL firmada para ZIP",
                context={
                    'processing_uuid': processing_uuid,
                    'bucket': bucket_name,
                    'object': gcs_object_name,
                    'expiration_hours': expiration_hours
                },
                trace_id=trace_id
            )
            
            # Obtener referencia al blob
            bucket = self.storage_client.bucket(bucket_name)
            blob = bucket.blob(gcs_object_name)
            
            # Verificar que el archivo existe
            if not blob.exists():
                raise ValueError(f"Archivo no encontrado en GCS: gs://{bucket_name}/{gcs_object_name}")
            
            # Calcular fecha de expiración
            expiration = datetime.now() + timedelta(hours=expiration_hours)
            
            # Generar URL firmada
            signed_url = blob.generate_signed_url(
                version="v4",
                expiration=expiration,
                method="GET",
                response_disposition=f'attachment; filename="{self._get_download_filename(processing_uuid, gcs_object_name)}"'
            )
            
            # Crear resultado
            result = {
                'success': True,
                'processing_uuid': processing_uuid,
                'signed_url': signed_url,
                'expiration_datetime': expiration.isoformat(),
                'expiration_hours': expiration_hours,
                'bucket_name': bucket_name,
                'object_name': gcs_object_name,
                'download_filename': self._get_download_filename(processing_uuid, gcs_object_name),
                'file_size_bytes': gcs_upload_result.get('gcs_size_bytes', 0),
                'file_size_mb': round(gcs_upload_result.get('gcs_size_bytes', 0) / (1024 * 1024), 2),
                'generated_at': datetime.now().isoformat(),
                'expires_in_seconds': int(expiration_hours * 3600)
            }
            
            self.logger.success(
                f"URL firmada generada exitosamente",
                context={
                    'processing_uuid': processing_uuid,
                    'expiration_hours': expiration_hours,
                    'file_size_mb': result['file_size_mb'],
                    'expires_at': result['expiration_datetime']
                },
                trace_id=trace_id
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error generando URL firmada: {str(e)}", trace_id=trace_id, exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'processing_uuid': gcs_upload_result.get('processing_uuid', 'unknown')
            }
    
    def generate_multiple_signed_urls(self, zip_results: list, 
                                    expiration_hours: Optional[int] = None,
                                    trace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Genera URLs firmadas para múltiples archivos ZIP
        
        Args:
            zip_results: Lista de resultados de upload_zip_to_gcs
            expiration_hours: Horas de expiración
            trace_id: ID de trazabilidad
            
        Returns:
            Dict con URLs firmadas y estadísticas
        """
        try:
            self.logger.processing(
                f"Generando URLs firmadas para {len(zip_results)} archivos",
                context={'total_files': len(zip_results)},
                trace_id=trace_id
            )
            
            signed_urls = []
            successful_generations = 0
            failed_generations = 0
            total_size_bytes = 0
            
            for zip_result in zip_results:
                try:
                    url_result = self.generate_signed_url(zip_result, expiration_hours, trace_id)
                    signed_urls.append(url_result)
                    
                    if url_result['success']:
                        successful_generations += 1
                        total_size_bytes += url_result.get('file_size_bytes', 0)
                    else:
                        failed_generations += 1
                        
                except Exception as e:
                    failed_generations += 1
                    signed_urls.append({
                        'success': False,
                        'error': str(e),
                        'processing_uuid': zip_result.get('processing_uuid', 'unknown')
                    })
            
            # Extraer solo las URLs exitosas para el email
            successful_urls = [url['signed_url'] for url in signed_urls if url.get('success')]
            
            result = {
                'success': successful_generations > 0,
                'total_files_requested': len(zip_results),
                'successful_generations': successful_generations,
                'failed_generations': failed_generations,
                'signed_urls': signed_urls,
                'download_urls': successful_urls,  # Lista limpia para usar en emails
                'total_size_bytes': total_size_bytes,
                'total_size_mb': round(total_size_bytes / (1024 * 1024), 2),
                'expiration_hours': expiration_hours or self.default_expiration_hours,
                'generated_at': datetime.now().isoformat()
            }
            
            self.logger.success(
                f"Generación masiva de URLs completada",
                context={
                    'successful': successful_generations,
                    'failed': failed_generations,
                    'total_size_mb': result['total_size_mb']
                },
                trace_id=trace_id
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error en generación masiva de URLs: {str(e)}", trace_id=trace_id, exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'total_files_requested': len(zip_results) if zip_results else 0
            }
    
    def validate_signed_url(self, signed_url: str, trace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Valida si una URL firmada es válida y no ha expirado
        
        Args:
            signed_url: URL firmada a validar
            trace_id: ID de trazabilidad
            
        Returns:
            Dict con resultado de validación
        """
        try:
            import requests
            
            # Hacer HEAD request para verificar sin descargar
            response = requests.head(signed_url, timeout=10)
            
            result = {
                'valid': response.status_code == 200,
                'status_code': response.status_code,
                'content_length': response.headers.get('content-length'),
                'content_type': response.headers.get('content-type'),
                'last_modified': response.headers.get('last-modified'),
                'validated_at': datetime.now().isoformat()
            }
            
            if not result['valid']:
                if response.status_code == 403:
                    result['error'] = 'URL firmada ha expirado o es inválida'
                elif response.status_code == 404:
                    result['error'] = 'Archivo no encontrado'
                else:
                    result['error'] = f'Error HTTP: {response.status_code}'
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error validando URL firmada: {str(e)}", trace_id=trace_id)
            return {
                'valid': False,
                'error': str(e),
                'validated_at': datetime.now().isoformat()
            }
    
    def get_url_expiration_info(self, signed_url: str) -> Dict[str, Any]:
        """
        Extrae información de expiración de una URL firmada
        (Esto es aproximado, basado en el parámetro X-Goog-Expires)
        
        Args:
            signed_url: URL firmada
            
        Returns:
            Dict con información de expiración
        """
        try:
            from urllib.parse import urlparse, parse_qs
            
            parsed_url = urlparse(signed_url)
            query_params = parse_qs(parsed_url.query)
            
            # Intentar extraer información de expiración
            expires_param = query_params.get('X-Goog-Expires', [''])[0]
            date_param = query_params.get('X-Goog-Date', [''])[0]
            
            result = {
                'has_expiration_info': bool(expires_param and date_param),
                'expires_in_seconds': int(expires_param) if expires_param.isdigit() else None,
                'signed_date': date_param if date_param else None,
                'extracted_at': datetime.now().isoformat()
            }
            
            if result['expires_in_seconds']:
                result['expires_in_hours'] = round(result['expires_in_seconds'] / 3600, 2)
            
            return result
            
        except Exception as e:
            return {
                'has_expiration_info': False,
                'error': str(e),
                'extracted_at': datetime.now().isoformat()
            }
    
    def _get_download_filename(self, processing_uuid: str, gcs_object_name: str) -> str:
        """
        Genera nombre de archivo amigable para descarga
        """
        # Extraer nombre base del objeto
        base_filename = gcs_object_name.split('/')[-1]
        
        # Si ya tiene un nombre descriptivo, usarlo
        if processing_uuid in base_filename:
            return base_filename
        
        # Sino, crear nombre descriptivo
        timestamp = datetime.now().strftime('%Y%m%d_%H%M')
        return f"shipment_images_{processing_uuid[:8]}_{timestamp}.zip"
