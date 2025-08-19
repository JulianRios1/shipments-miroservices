"""
Image Downloader Service
Responsable de descargar imágenes desde buckets de origen con validación
"""

import os
import tempfile
import hashlib
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import urlparse
import requests
from google.cloud import storage
from google.cloud.exceptions import NotFound, GoogleCloudError

import sys
sys.path.insert(0, '/app/services/shared_utils/src')

from config import config
from logger import setup_logger
from storage_service import storage_service


class ImageDownloader:
    """
    Servicio especializado para descarga de imágenes con validación y gestión de errores
    """
    
    def __init__(self):
        self.logger = setup_logger(__name__, 'image-downloader', config.APP_VERSION)
        self.storage_client = storage.Client()
        
        # Configuración de descarga
        self.max_file_size_mb = 50  # Máximo 50MB por imagen
        self.timeout_seconds = 30
        self.chunk_size = 8192
        
        # Extensiones de imagen válidas
        self.valid_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.tif', '.svg'}
        
        self.logger.info("✅ Image Downloader inicializado")
    
    def download_images_for_package(self, image_paths: List[str], processing_uuid: str, 
                                  package_number: str, trace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Descarga todas las imágenes para un paquete específico
        
        Args:
            image_paths: Lista de rutas de imágenes a descargar
            processing_uuid: UUID del procesamiento
            package_number: Número del paquete (ej: "1_de_5")
            trace_id: ID de trazabilidad
            
        Returns:
            Dict con resultado de descarga
        """
        try:
            self.logger.processing(
                f"Iniciando descarga de imágenes para paquete {package_number}",
                context={
                    'processing_uuid': processing_uuid,
                    'package_number': package_number,
                    'total_images': len(image_paths)
                },
                trace_id=trace_id
            )
            
            # Crear directorio temporal para el paquete
            temp_dir = self._create_temp_directory(processing_uuid, package_number)
            
            download_results = []
            successful_downloads = 0
            failed_downloads = 0
            total_size_bytes = 0
            
            for i, image_path in enumerate(image_paths):
                try:
                    # Descargar imagen individual
                    download_result = self._download_single_image(
                        image_path, temp_dir, f"image_{i+1}", trace_id
                    )
                    
                    download_results.append(download_result)
                    
                    if download_result['success']:
                        successful_downloads += 1
                        total_size_bytes += download_result['size_bytes']
                    else:
                        failed_downloads += 1
                        
                except Exception as e:
                    self.logger.error(f"Error descargando imagen {image_path}: {str(e)}", trace_id=trace_id)
                    failed_downloads += 1
                    download_results.append({
                        'image_path': image_path,
                        'success': False,
                        'error': str(e),
                        'local_path': None,
                        'size_bytes': 0
                    })
            
            result = {
                'success': successful_downloads > 0,
                'processing_uuid': processing_uuid,
                'package_number': package_number,
                'temp_directory': temp_dir,
                'total_images': len(image_paths),
                'successful_downloads': successful_downloads,
                'failed_downloads': failed_downloads,
                'total_size_bytes': total_size_bytes,
                'total_size_mb': round(total_size_bytes / (1024 * 1024), 2),
                'download_results': download_results,
                'timestamp': datetime.now().isoformat()
            }
            
            self.logger.success(
                f"Descarga completada para paquete {package_number}",
                context={
                    'successful_downloads': successful_downloads,
                    'failed_downloads': failed_downloads,
                    'total_size_mb': result['total_size_mb']
                },
                trace_id=trace_id
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error en descarga de paquete: {str(e)}", trace_id=trace_id, exc_info=True)
            raise
    
    def _download_single_image(self, image_path: str, temp_dir: str, 
                             filename_prefix: str, trace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Descarga una imagen individual con validación
        """
        try:
            # Determinar tipo de fuente (GCS, HTTP, etc.)
            if image_path.startswith('gs://'):
                return self._download_from_gcs(image_path, temp_dir, filename_prefix, trace_id)
            elif image_path.startswith(('http://', 'https://')):
                return self._download_from_http(image_path, temp_dir, filename_prefix, trace_id)
            else:
                # Asumir que es un path relativo en el bucket de imágenes originales
                gcs_path = f"gs://{config.BUCKET_IMAGENES_ORIGINALES}/{image_path}"
                return self._download_from_gcs(gcs_path, temp_dir, filename_prefix, trace_id)
                
        except Exception as e:
            return {
                'image_path': image_path,
                'success': False,
                'error': str(e),
                'local_path': None,
                'size_bytes': 0
            }
    
    def _download_from_gcs(self, gcs_path: str, temp_dir: str, 
                          filename_prefix: str, trace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Descarga imagen desde Google Cloud Storage
        """
        try:
            # Parsear GCS path
            if not gcs_path.startswith('gs://'):
                raise ValueError(f"Path GCS inválido: {gcs_path}")
            
            path_parts = gcs_path[5:].split('/', 1)  # Remover 'gs://'
            if len(path_parts) != 2:
                raise ValueError(f"Formato GCS inválido: {gcs_path}")
            
            bucket_name, object_name = path_parts
            
            # Validar extensión
            file_extension = self._get_file_extension(object_name)
            if not self._is_valid_image_extension(file_extension):
                raise ValueError(f"Extensión no válida: {file_extension}")
            
            # Crear nombre de archivo local
            local_filename = f"{filename_prefix}{file_extension}"
            local_path = os.path.join(temp_dir, local_filename)
            
            # Descargar desde GCS
            bucket = self.storage_client.bucket(bucket_name)
            blob = bucket.blob(object_name)
            
            if not blob.exists():
                raise NotFound(f"Imagen no encontrada: {gcs_path}")
            
            # Verificar tamaño antes de descargar
            blob.reload()
            size_bytes = blob.size
            
            if size_bytes > self.max_file_size_mb * 1024 * 1024:
                raise ValueError(f"Imagen muy grande: {size_bytes} bytes (máximo: {self.max_file_size_mb}MB)")
            
            # Descargar archivo
            blob.download_to_filename(local_path)
            
            # Validar descarga
            if not os.path.exists(local_path):
                raise Exception("Archivo no descargado correctamente")
            
            actual_size = os.path.getsize(local_path)
            if actual_size != size_bytes:
                raise Exception(f"Tamaño de descarga incorrecto: esperado {size_bytes}, obtenido {actual_size}")
            
            return {
                'image_path': gcs_path,
                'success': True,
                'local_path': local_path,
                'size_bytes': actual_size,
                'file_extension': file_extension,
                'source_type': 'gcs'
            }
            
        except Exception as e:
            return {
                'image_path': gcs_path,
                'success': False,
                'error': str(e),
                'local_path': None,
                'size_bytes': 0
            }
    
    def _download_from_http(self, http_url: str, temp_dir: str, 
                           filename_prefix: str, trace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Descarga imagen desde URL HTTP/HTTPS
        """
        try:
            # Validar URL
            parsed_url = urlparse(http_url)
            if not all([parsed_url.scheme, parsed_url.netloc]):
                raise ValueError(f"URL inválida: {http_url}")
            
            # Determinar extensión del archivo
            file_extension = self._get_file_extension(parsed_url.path)
            if not file_extension:
                file_extension = '.jpg'  # Extensión por defecto
            
            if not self._is_valid_image_extension(file_extension):
                raise ValueError(f"Extensión no válida: {file_extension}")
            
            # Crear nombre de archivo local
            local_filename = f"{filename_prefix}{file_extension}"
            local_path = os.path.join(temp_dir, local_filename)
            
            # Descargar con requests
            headers = {
                'User-Agent': 'ShipmentProcessingPlatform/2.0.0'
            }
            
            with requests.get(http_url, headers=headers, timeout=self.timeout_seconds, 
                            stream=True) as response:
                response.raise_for_status()
                
                # Verificar Content-Type si está disponible
                content_type = response.headers.get('content-type', '')
                if content_type and not content_type.startswith('image/'):
                    self.logger.warning(f"Content-Type sospechoso: {content_type}", trace_id=trace_id)
                
                # Descargar por chunks
                size_bytes = 0
                with open(local_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=self.chunk_size):
                        if chunk:
                            f.write(chunk)
                            size_bytes += len(chunk)
                            
                            # Verificar tamaño máximo durante descarga
                            if size_bytes > self.max_file_size_mb * 1024 * 1024:
                                raise ValueError(f"Imagen muy grande durante descarga: {size_bytes} bytes")
            
            return {
                'image_path': http_url,
                'success': True,
                'local_path': local_path,
                'size_bytes': size_bytes,
                'file_extension': file_extension,
                'source_type': 'http'
            }
            
        except Exception as e:
            return {
                'image_path': http_url,
                'success': False,
                'error': str(e),
                'local_path': None,
                'size_bytes': 0
            }
    
    def _create_temp_directory(self, processing_uuid: str, package_number: str) -> str:
        """
        Crea directorio temporal para el paquete
        """
        temp_base = tempfile.gettempdir()
        temp_dir = os.path.join(temp_base, 'shipments_processing', processing_uuid, package_number)
        os.makedirs(temp_dir, exist_ok=True)
        
        self.logger.debug(f"Directorio temporal creado: {temp_dir}")
        return temp_dir
    
    def _get_file_extension(self, filename: str) -> str:
        """
        Extrae extensión de archivo
        """
        return os.path.splitext(filename.lower())[1]
    
    def _is_valid_image_extension(self, extension: str) -> bool:
        """
        Valida si la extensión es de imagen válida
        """
        return extension.lower() in self.valid_extensions
    
    def cleanup_temp_directory(self, temp_dir: str, trace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Limpia directorio temporal después del procesamiento
        """
        try:
            if not os.path.exists(temp_dir):
                return {'cleaned': False, 'reason': 'Directory does not exist'}
            
            import shutil
            shutil.rmtree(temp_dir)
            
            self.logger.info(f"Directorio temporal limpiado: {temp_dir}", trace_id=trace_id)
            
            return {
                'cleaned': True,
                'directory': temp_dir,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error limpiando directorio temporal: {str(e)}", trace_id=trace_id)
            return {
                'cleaned': False,
                'error': str(e),
                'directory': temp_dir
            }
