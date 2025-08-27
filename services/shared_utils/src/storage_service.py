"""
Servicio de almacenamiento compartido para gestión de Google Cloud Storage
Implementa operaciones CRUD siguiendo Clean Architecture y mejores prácticas
"""

import json
import tempfile
import zipfile
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from google.cloud import storage
from google.cloud.exceptions import NotFound, GoogleCloudError
from config import config
from logger import setup_logger


class CloudStorageService:
    """
    Servicio centralizado para operaciones de Google Cloud Storage
    Maneja lectura, escritura y gestión de archivos en buckets
    """
    
    def __init__(self, service_name: str = 'storage-service'):
        self.logger = setup_logger(__name__, service_name, config.APP_VERSION)
        self.client = storage.Client()
    
    # ========== MÉTODOS DE LECTURA ==========
    
    def read_json_file(self, bucket_name: str, file_name: str, trace_id: Optional[str] = None) -> Dict[Any, Any]:
        """
        Lee archivo JSON desde bucket de GCS
        
        Args:
            bucket_name: Nombre del bucket
            file_name: Nombre del archivo
            trace_id: ID de trazabilidad opcional
            
        Returns:
            Dict con contenido JSON parseado
            
        Raises:
            NotFound: Si archivo no existe
            GoogleCloudError: Para errores de GCS
            json.JSONDecodeError: Si archivo no es JSON válido
        """
        try:
            self.logger.processing(
                f"Leyendo archivo JSON: gs://{bucket_name}/{file_name}",
                context={'bucket': bucket_name, 'file': file_name},
                trace_id=trace_id
            )
            
            bucket = self.client.bucket(bucket_name)
            blob = bucket.blob(file_name)
            
            if not blob.exists():
                raise NotFound(f"Archivo no encontrado: gs://{bucket_name}/{file_name}")
            
            # Obtener metadatos del archivo
            blob.reload()
            file_size = blob.size
            content_type = blob.content_type
            
            # Leer contenido
            content = blob.download_as_text()
            json_data = json.loads(content)
            
            self.logger.success(
                f"Archivo JSON leído exitosamente",
                context={
                    'bucket': bucket_name,
                    'file': file_name,
                    'size_bytes': file_size,
                    'content_type': content_type,
                    'size_mb': round(file_size / (1024 * 1024), 2)
                },
                trace_id=trace_id
            )
            
            return json_data
            
        except NotFound as e:
            self.logger.error(f"Archivo no encontrado: {str(e)}", trace_id=trace_id)
            raise
        except json.JSONDecodeError as e:
            self.logger.error(f"Error parseando JSON: {str(e)}", trace_id=trace_id)
            raise
        except GoogleCloudError as e:
            self.logger.error(f"Error de GCS: {str(e)}", trace_id=trace_id)
            raise
        except Exception as e:
            self.logger.error(f"Error inesperado leyendo archivo: {str(e)}", trace_id=trace_id, exc_info=True)
            raise
    
    def check_file_exists(self, bucket_name: str, file_name: str, trace_id: Optional[str] = None) -> bool:
        """
        Verifica si un archivo existe en el bucket
        
        Args:
            bucket_name: Nombre del bucket
            file_name: Nombre del archivo
            trace_id: ID de trazabilidad opcional
            
        Returns:
            bool: True si el archivo existe
        """
        try:
            bucket = self.client.bucket(bucket_name)
            blob = bucket.blob(file_name)
            exists = blob.exists()
            
            self.logger.debug(
                f"Verificación de existencia: gs://{bucket_name}/{file_name} = {exists}",
                context={'bucket': bucket_name, 'file': file_name, 'exists': exists},
                trace_id=trace_id
            )
            
            return exists
            
        except Exception as e:
            self.logger.error(f"Error verificando existencia de archivo: {str(e)}", trace_id=trace_id)
            return False
    
    def wait_for_file_completion(self, bucket_name: str, file_name: str, 
                               timeout_seconds: int = 300, trace_id: Optional[str] = None) -> bool:
        """
        Espera a que un archivo esté completamente subido (no cambie de tamaño)
        
        Args:
            bucket_name: Nombre del bucket
            file_name: Nombre del archivo
            timeout_seconds: Timeout en segundos
            trace_id: ID de trazabilidad opcional
            
        Returns:
            bool: True si el archivo está completo
        """
        import time
        
        try:
            self.logger.processing(
                f"Esperando completitud de archivo: gs://{bucket_name}/{file_name}",
                context={'timeout_seconds': timeout_seconds},
                trace_id=trace_id
            )
            
            bucket = self.client.bucket(bucket_name)
            blob = bucket.blob(file_name)
            
            start_time = time.time()
            previous_size = -1
            stable_count = 0
            
            while time.time() - start_time < timeout_seconds:
                if not blob.exists():
                    time.sleep(1)
                    continue
                
                blob.reload()
                current_size = blob.size
                
                if current_size == previous_size and current_size > 0:
                    stable_count += 1
                    if stable_count >= 3:  # Archivo estable por 3 verificaciones
                        self.logger.success(
                            f"Archivo completo y estable",
                            context={'final_size_bytes': current_size},
                            trace_id=trace_id
                        )
                        return True
                else:
                    stable_count = 0
                
                previous_size = current_size
                time.sleep(1)
            
            self.logger.warning(
                f"Timeout esperando completitud de archivo",
                context={'timeout_seconds': timeout_seconds},
                trace_id=trace_id
            )
            return False
            
        except Exception as e:
            self.logger.error(f"Error esperando completitud de archivo: {str(e)}", trace_id=trace_id)
            return False
    
    # ========== MÉTODOS DE ESCRITURA ==========
    
    def write_json_file(self, bucket_name: str, file_name: str, data: Dict[Any, Any], 
                       metadata: Optional[Dict[str, str]] = None, trace_id: Optional[str] = None) -> str:
        """
        Escribe archivo JSON a bucket de GCS
        
        Args:
            bucket_name: Nombre del bucket de destino
            file_name: Nombre del archivo a crear
            data: Diccionario a serializar como JSON
            metadata: Metadatos personalizados opcionales
            trace_id: ID de trazabilidad opcional
            
        Returns:
            str: URI completa del archivo creado
            
        Raises:
            GoogleCloudError: Para errores de GCS
        """
        try:
            self.logger.processing(
                f"Escribiendo archivo JSON: gs://{bucket_name}/{file_name}",
                context={'bucket': bucket_name, 'file': file_name},
                trace_id=trace_id
            )
            
            bucket = self.client.bucket(bucket_name)
            blob = bucket.blob(file_name)
            
            # Serializar a JSON con formato legible
            json_content = json.dumps(data, indent=2, ensure_ascii=False)
            
            # Subir archivo con tipo de contenido correcto
            blob.upload_from_string(
                json_content,
                content_type='application/json'
            )
            
            # Agregar metadatos personalizados
            blob_metadata = {
                'processed_by': 'shipments-processing-platform',
                'processing_timestamp': datetime.now().isoformat(),
                'service_version': config.APP_VERSION
            }
            
            if metadata:
                blob_metadata.update(metadata)
            
            # Agregar metadatos del archivo original si existe
            if 'metadatos' in data:
                blob_metadata['original_file'] = data['metadatos'].get('archivo_original', 'unknown')
                blob_metadata['total_shipments'] = str(data['metadatos'].get('total_envios_archivo', 0))
            
            blob.metadata = blob_metadata
            blob.patch()
            
            uri = f"gs://{bucket_name}/{file_name}"
            
            self.logger.success(
                f"Archivo JSON escrito exitosamente",
                context={
                    'uri': uri,
                    'size_bytes': len(json_content.encode('utf-8')),
                    'metadata_count': len(blob_metadata)
                },
                trace_id=trace_id
            )
            
            return uri
            
        except GoogleCloudError as e:
            self.logger.error(f"Error escribiendo archivo: {str(e)}", trace_id=trace_id)
            raise
        except Exception as e:
            self.logger.error(f"Error inesperado escribiendo archivo: {str(e)}", trace_id=trace_id, exc_info=True)
            raise
    
    def create_zip_file(self, bucket_name: str, zip_file_name: str, files_to_zip: List[Tuple[str, str]], 
                       trace_id: Optional[str] = None) -> str:
        """
        Crea archivo ZIP con archivos desde otros buckets
        
        Args:
            bucket_name: Bucket destino para el ZIP
            zip_file_name: Nombre del archivo ZIP
            files_to_zip: Lista de tuplas (source_bucket, source_file)
            trace_id: ID de trazabilidad opcional
            
        Returns:
            str: URI del archivo ZIP creado
        """
        try:
            self.logger.processing(
                f"Creando archivo ZIP: gs://{bucket_name}/{zip_file_name}",
                context={'files_count': len(files_to_zip)},
                trace_id=trace_id
            )
            
            # Crear archivo ZIP temporal
            with tempfile.NamedTemporaryFile() as temp_zip:
                with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as zip_ref:
                    
                    for source_bucket, source_file in files_to_zip:
                        try:
                            # Descargar archivo fuente
                            source_blob = self.client.bucket(source_bucket).blob(source_file)
                            file_content = source_blob.download_as_bytes()
                            
                            # Agregar al ZIP
                            zip_ref.writestr(source_file, file_content)
                            
                            self.logger.debug(
                                f"Archivo agregado al ZIP: {source_file}",
                                context={'size_bytes': len(file_content)},
                                trace_id=trace_id
                            )
                            
                        except Exception as e:
                            self.logger.warning(f"Error agregando archivo {source_file} al ZIP: {str(e)}", trace_id=trace_id)
                
                # Subir ZIP al bucket destino
                temp_zip.seek(0)
                dest_bucket = self.client.bucket(bucket_name)
                dest_blob = dest_bucket.blob(zip_file_name)
                
                dest_blob.upload_from_file(
                    temp_zip,
                    content_type='application/zip'
                )
                
                # Agregar metadatos
                dest_blob.metadata = {
                    'created_by': 'shipments-processing-platform',
                    'creation_timestamp': datetime.now().isoformat(),
                    'files_count': str(len(files_to_zip)),
                    'content_type': 'application/zip'
                }
                dest_blob.patch()
            
            uri = f"gs://{bucket_name}/{zip_file_name}"
            
            self.logger.success(
                f"Archivo ZIP creado exitosamente",
                context={'uri': uri, 'files_included': len(files_to_zip)},
                trace_id=trace_id
            )
            
            return uri
            
        except Exception as e:
            self.logger.error(f"Error creando archivo ZIP: {str(e)}", trace_id=trace_id, exc_info=True)
            raise
    
    # ========== MÉTODOS DE GESTIÓN ==========
    
    def move_file(self, source_bucket: str, source_file: str, 
                 dest_bucket: str, dest_file: str, delete_source: bool = True,
                 trace_id: Optional[str] = None) -> str:
        """
        Mueve archivo entre buckets
        
        Args:
            source_bucket: Bucket origen
            source_file: Archivo origen
            dest_bucket: Bucket destino
            dest_file: Archivo destino
            delete_source: Si eliminar archivo origen
            trace_id: ID de trazabilidad opcional
            
        Returns:
            str: URI del archivo en destino
        """
        try:
            self.logger.processing(
                f"Moviendo archivo: gs://{source_bucket}/{source_file} → gs://{dest_bucket}/{dest_file}",
                context={'delete_source': delete_source},
                trace_id=trace_id
            )
            
            # Copiar archivo
            source_blob = self.client.bucket(source_bucket).blob(source_file)
            dest_blob = self.client.bucket(dest_bucket).blob(dest_file)
            
            # Realizar copia
            dest_blob.rewrite(source_blob)
            
            # Eliminar origen si se solicita
            if delete_source:
                source_blob.delete()
                self.logger.debug(f"Archivo origen eliminado", trace_id=trace_id)
            
            uri = f"gs://{dest_bucket}/{dest_file}"
            
            self.logger.success(
                f"Archivo movido exitosamente",
                context={'destination_uri': uri},
                trace_id=trace_id
            )
            
            return uri
            
        except Exception as e:
            self.logger.error(f"Error moviendo archivo: {str(e)}", trace_id=trace_id, exc_info=True)
            raise
    
    def delete_file(self, bucket_name: str, file_name: str, trace_id: Optional[str] = None) -> bool:
        """
        Elimina archivo del bucket
        
        Args:
            bucket_name: Nombre del bucket
            file_name: Nombre del archivo
            trace_id: ID de trazabilidad opcional
            
        Returns:
            bool: True si se eliminó exitosamente
        """
        try:
            self.logger.processing(
                f"Eliminando archivo: gs://{bucket_name}/{file_name}",
                trace_id=trace_id
            )
            
            bucket = self.client.bucket(bucket_name)
            blob = bucket.blob(file_name)
            
            if blob.exists():
                blob.delete()
                self.logger.success(f"Archivo eliminado exitosamente", trace_id=trace_id)
                return True
            else:
                self.logger.warning(f"Archivo no encontrado para eliminar", trace_id=trace_id)
                return False
                
        except Exception as e:
            self.logger.error(f"Error eliminando archivo: {str(e)}", trace_id=trace_id)
            raise
    
    def generate_signed_url(self, bucket_name: str, file_name: str, 
                          expiration_hours: int = None, trace_id: Optional[str] = None) -> str:
        """
        Genera URL firmada con expiración
        
        Args:
            bucket_name: Nombre del bucket
            file_name: Nombre del archivo
            expiration_hours: Horas de expiración (default: config)
            trace_id: ID de trazabilidad opcional
            
        Returns:
            str: URL firmada
        """
        try:
            if expiration_hours is None:
                expiration_hours = config.SIGNED_URL_EXPIRATION_HOURS
            
            self.logger.processing(
                f"Generando URL firmada: gs://{bucket_name}/{file_name}",
                context={'expiration_hours': expiration_hours},
                trace_id=trace_id
            )
            
            bucket = self.client.bucket(bucket_name)
            blob = bucket.blob(file_name)
            
            # Calcular tiempo de expiración
            expiration_time = datetime.now() + timedelta(hours=expiration_hours)
            
            # Generar URL firmada
            signed_url = blob.generate_signed_url(
                version="v4",
                expiration=expiration_time,
                method="GET"
            )
            
            self.logger.success(
                f"URL firmada generada exitosamente",
                context={'expiration_time': expiration_time.isoformat()},
                trace_id=trace_id
            )
            
            return signed_url
            
        except Exception as e:
            self.logger.error(f"Error generando URL firmada: {str(e)}", trace_id=trace_id)
            raise
    
    def list_files(self, bucket_name: str, prefix: str = "", trace_id: Optional[str] = None) -> List[str]:
        """
        Lista archivos en bucket con prefijo
        
        Args:
            bucket_name: Nombre del bucket
            prefix: Prefijo para filtrar archivos
            trace_id: ID de trazabilidad opcional
            
        Returns:
            List[str]: Lista de nombres de archivos
        """
        try:
            self.logger.processing(
                f"Listando archivos en gs://{bucket_name}/ con prefijo '{prefix}'",
                trace_id=trace_id
            )
            
            bucket = self.client.bucket(bucket_name)
            blobs = bucket.list_blobs(prefix=prefix)
            
            file_list = [blob.name for blob in blobs]
            
            self.logger.success(
                f"Archivos listados exitosamente",
                context={'files_count': len(file_list), 'prefix': prefix},
                trace_id=trace_id
            )
            
            return file_list
            
        except Exception as e:
            self.logger.error(f"Error listando archivos: {str(e)}", trace_id=trace_id)
            raise


# Instancia global del servicio
storage_service = CloudStorageService()
