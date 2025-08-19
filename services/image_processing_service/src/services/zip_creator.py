"""
ZIP Creator Service
Responsable de crear archivos ZIP con imágenes agrupadas por procesamiento
"""

import os
import zipfile
import hashlib
from datetime import datetime
from typing import Dict, List, Any, Optional
from google.cloud import storage

import sys
sys.path.insert(0, '/app/services/shared_utils/src')

from config import config
from logger import setup_logger
from storage_service import storage_service


class ZipCreator:
    """
    Servicio especializado para crear archivos ZIP con imágenes
    """
    
    def __init__(self):
        self.logger = setup_logger(__name__, 'zip-creator', config.APP_VERSION)
        self.storage_client = storage.Client()
        
        # Configuración de compresión
        self.compression_level = zipfile.ZIP_DEFLATED
        self.compresslevel = 6  # Nivel medio de compresión (más rápido que máximo)
        
        self.logger.info("✅ ZIP Creator inicializado")
    
    def create_zip_from_downloaded_images(self, download_result: Dict[str, Any], 
                                        trace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Crea archivo ZIP desde imágenes descargadas localmente
        
        Args:
            download_result: Resultado del ImageDownloader
            trace_id: ID de trazabilidad
            
        Returns:
            Dict con información del ZIP creado
        """
        try:
            processing_uuid = download_result['processing_uuid']
            package_number = download_result['package_number']
            temp_directory = download_result['temp_directory']
            
            self.logger.processing(
                f"Iniciando creación de ZIP para paquete {package_number}",
                context={
                    'processing_uuid': processing_uuid,
                    'package_number': package_number,
                    'successful_downloads': download_result['successful_downloads']
                },
                trace_id=trace_id
            )
            
            if download_result['successful_downloads'] == 0:
                raise ValueError("No hay imágenes válidas para crear ZIP")
            
            # Crear nombre del archivo ZIP
            zip_filename = f"{processing_uuid}_{package_number}_images.zip"
            zip_path = os.path.join(temp_directory, zip_filename)
            
            # Crear archivo ZIP
            files_added = 0
            total_original_size = 0
            
            with zipfile.ZipFile(zip_path, 'w', self.compression_level, compresslevel=self.compresslevel) as zip_file:
                
                # Añadir metadata del paquete
                metadata = self._create_package_metadata(download_result)
                zip_file.writestr('package_metadata.json', metadata)
                
                # Añadir imágenes válidas al ZIP
                for download_item in download_result['download_results']:
                    if download_item['success'] and download_item['local_path']:
                        local_path = download_item['local_path']
                        
                        if os.path.exists(local_path):
                            # Usar nombre limpio en el ZIP
                            archive_name = os.path.basename(local_path)
                            zip_file.write(local_path, archive_name)
                            
                            files_added += 1
                            total_original_size += download_item['size_bytes']
                            
                            self.logger.debug(f"Añadido al ZIP: {archive_name}", trace_id=trace_id)
            
            # Verificar que el ZIP fue creado
            if not os.path.exists(zip_path):
                raise Exception("Error creando archivo ZIP")
            
            # Obtener información del ZIP creado
            zip_size = os.path.getsize(zip_path)
            compression_ratio = round(((total_original_size - zip_size) / total_original_size * 100), 2) if total_original_size > 0 else 0
            
            # Calcular hash del ZIP para integridad
            zip_hash = self._calculate_file_hash(zip_path)
            
            result = {
                'success': True,
                'processing_uuid': processing_uuid,
                'package_number': package_number,
                'zip_filename': zip_filename,
                'zip_path': zip_path,
                'files_added': files_added,
                'zip_size_bytes': zip_size,
                'zip_size_mb': round(zip_size / (1024 * 1024), 2),
                'original_size_bytes': total_original_size,
                'original_size_mb': round(total_original_size / (1024 * 1024), 2),
                'compression_ratio_percent': compression_ratio,
                'zip_hash': zip_hash,
                'timestamp': datetime.now().isoformat()
            }
            
            self.logger.success(
                f"ZIP creado exitosamente: {zip_filename}",
                context={
                    'files_added': files_added,
                    'zip_size_mb': result['zip_size_mb'],
                    'compression_ratio': compression_ratio
                },
                trace_id=trace_id
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error creando ZIP: {str(e)}", trace_id=trace_id, exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'processing_uuid': download_result.get('processing_uuid', 'unknown'),
                'package_number': download_result.get('package_number', 'unknown')
            }
    
    def upload_zip_to_gcs(self, zip_result: Dict[str, Any], trace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Sube archivo ZIP al bucket temporal de GCS
        
        Args:
            zip_result: Resultado de create_zip_from_downloaded_images
            trace_id: ID de trazabilidad
            
        Returns:
            Dict con información del archivo subido
        """
        try:
            if not zip_result['success']:
                raise ValueError("ZIP no fue creado exitosamente")
            
            processing_uuid = zip_result['processing_uuid']
            zip_filename = zip_result['zip_filename']
            local_zip_path = zip_result['zip_path']
            
            self.logger.processing(
                f"Subiendo ZIP a GCS: {zip_filename}",
                context={
                    'processing_uuid': processing_uuid,
                    'bucket': config.BUCKET_IMAGENES_TEMP,
                    'zip_size_mb': zip_result['zip_size_mb']
                },
                trace_id=trace_id
            )
            
            # Crear path en GCS organizado por UUID
            gcs_object_name = f"{processing_uuid}/{zip_filename}"
            
            # Subir a GCS
            bucket = self.storage_client.bucket(config.BUCKET_IMAGENES_TEMP)
            blob = bucket.blob(gcs_object_name)
            
            # Metadata para el blob
            blob.metadata = {
                'processing_uuid': processing_uuid,
                'package_number': zip_result['package_number'],
                'files_count': str(zip_result['files_added']),
                'original_size_mb': str(zip_result['original_size_mb']),
                'compression_ratio': str(zip_result['compression_ratio_percent']),
                'created_at': zip_result['timestamp'],
                'zip_hash': zip_result['zip_hash']
            }
            
            # Subir archivo
            blob.upload_from_filename(local_zip_path)
            
            # Verificar subida
            blob.reload()
            gcs_size = blob.size
            
            if gcs_size != zip_result['zip_size_bytes']:
                raise Exception(f"Error en subida: tamaño local {zip_result['zip_size_bytes']} vs GCS {gcs_size}")
            
            gcs_uri = f"gs://{config.BUCKET_IMAGENES_TEMP}/{gcs_object_name}"
            
            result = {
                'success': True,
                'processing_uuid': processing_uuid,
                'gcs_uri': gcs_uri,
                'gcs_object_name': gcs_object_name,
                'bucket_name': config.BUCKET_IMAGENES_TEMP,
                'gcs_size_bytes': gcs_size,
                'upload_timestamp': datetime.now().isoformat(),
                'metadata': blob.metadata
            }
            
            self.logger.success(
                f"ZIP subido exitosamente a GCS",
                context={
                    'gcs_uri': gcs_uri,
                    'gcs_size_mb': round(gcs_size / (1024 * 1024), 2)
                },
                trace_id=trace_id
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error subiendo ZIP a GCS: {str(e)}", trace_id=trace_id, exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'processing_uuid': zip_result.get('processing_uuid', 'unknown')
            }
    
    def _create_package_metadata(self, download_result: Dict[str, Any]) -> str:
        """
        Crea metadata JSON para incluir en el ZIP
        """
        import json
        
        metadata = {
            'package_info': {
                'processing_uuid': download_result['processing_uuid'],
                'package_number': download_result['package_number'],
                'created_at': download_result['timestamp'],
                'service_version': config.APP_VERSION
            },
            'images_summary': {
                'total_requested': download_result['total_images'],
                'successful_downloads': download_result['successful_downloads'],
                'failed_downloads': download_result['failed_downloads'],
                'total_size_bytes': download_result['total_size_bytes'],
                'total_size_mb': download_result['total_size_mb']
            },
            'download_details': []
        }
        
        # Añadir detalles de cada imagen (solo las exitosas para no inflar el metadata)
        for item in download_result['download_results']:
            if item['success']:
                metadata['download_details'].append({
                    'original_path': item['image_path'],
                    'size_bytes': item['size_bytes'],
                    'file_extension': item.get('file_extension', 'unknown'),
                    'source_type': item.get('source_type', 'unknown')
                })
        
        return json.dumps(metadata, indent=2, ensure_ascii=False)
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """
        Calcula hash SHA256 del archivo para verificación de integridad
        """
        hash_sha256 = hashlib.sha256()
        
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        
        return hash_sha256.hexdigest()
    
    def verify_zip_integrity(self, zip_path: str, trace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Verifica la integridad de un archivo ZIP
        
        Args:
            zip_path: Path al archivo ZIP
            trace_id: ID de trazabilidad
            
        Returns:
            Dict con resultado de verificación
        """
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_file:
                # Probar abrir y leer el ZIP
                file_list = zip_file.namelist()
                
                # Verificar que no esté corrupto
                bad_files = zip_file.testzip()
                
                if bad_files:
                    return {
                        'valid': False,
                        'error': f'Archivo corrupto en ZIP: {bad_files}',
                        'files_in_zip': len(file_list)
                    }
                
                return {
                    'valid': True,
                    'files_in_zip': len(file_list),
                    'file_list': file_list[:10]  # Primeros 10 archivos para referencia
                }
                
        except Exception as e:
            self.logger.error(f"Error verificando ZIP: {str(e)}", trace_id=trace_id)
            return {
                'valid': False,
                'error': str(e)
            }
