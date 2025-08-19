"""
Servicio de almacenamiento para gestión de Google Cloud Storage
Implementa operaciones CRUD para buckets de GCS siguiendo Clean Architecture
"""

import json
import logging
from typing import Dict, Any, Optional
from google.cloud import storage
from google.cloud.exceptions import NotFound, GoogleCloudError
from utils.config import Config
from utils.logger import setup_logger


class StorageService:
    """
    Servicio para operaciones de Google Cloud Storage
    Maneja lectura, escritura y gestión de archivos en buckets
    """
    
    def __init__(self):
        self.logger = setup_logger(__name__)
        self.config = Config()
        self.client = storage.Client()
        
    def read_json_file(self, bucket_name: str, file_name: str) -> Dict[Any, Any]:
        """
        Lee un archivo JSON desde un bucket de GCS
        
        Args:
            bucket_name: Nombre del bucket
            file_name: Nombre del archivo
            
        Returns:
            Dict con el contenido JSON parseado
            
        Raises:
            NotFound: Si el archivo o bucket no existe
            GoogleCloudError: Para otros errores de GCS
            json.JSONDecodeError: Si el archivo no es JSON válido
        """
        try:
            self.logger.info(f"📖 Leyendo archivo: gs://{bucket_name}/{file_name}")
            
            bucket = self.client.bucket(bucket_name)
            blob = bucket.blob(file_name)
            
            if not blob.exists():
                raise NotFound(f"Archivo no encontrado: gs://{bucket_name}/{file_name}")
            
            contenido = blob.download_as_text()
            json_data = json.loads(contenido)
            
            self.logger.info(f"✅ Archivo leído exitosamente: {len(contenido)} caracteres")
            return json_data
            
        except NotFound:
            self.logger.error(f"❌ Archivo no encontrado: gs://{bucket_name}/{file_name}")
            raise
        except json.JSONDecodeError as e:
            self.logger.error(f"❌ Error parseando JSON: {str(e)}")
            raise
        except GoogleCloudError as e:
            self.logger.error(f"❌ Error de GCS: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"❌ Error inesperado leyendo archivo: {str(e)}")
            raise
    
    def write_json_file(self, bucket_name: str, file_name: str, data: Dict[Any, Any]) -> str:
        """
        Escribe un archivo JSON a un bucket de GCS
        
        Args:
            bucket_name: Nombre del bucket de destino
            file_name: Nombre del archivo a crear
            data: Diccionario a serializar como JSON
            
        Returns:
            str: URI completa del archivo creado (gs://bucket/file)
            
        Raises:
            GoogleCloudError: Para errores de GCS
        """
        try:
            self.logger.info(f"📝 Escribiendo archivo: gs://{bucket_name}/{file_name}")
            
            bucket = self.client.bucket(bucket_name)
            blob = bucket.blob(file_name)
            
            # Serializar a JSON con formato legible
            json_content = json.dumps(data, indent=2, ensure_ascii=False)
            
            # Subir archivo con metadata
            blob.upload_from_string(
                json_content,
                content_type='application/json'
            )
            
            # Agregar metadata personalizada
            blob.metadata = {
                'processed_by': 'shipments-json-splitter',
                'processing_timestamp': str(data.get('metadatos', {}).get('fecha_procesamiento', '')),
                'original_file': data.get('nombre_archivo', 'unknown')
            }
            blob.patch()
            
            uri = f"gs://{bucket_name}/{file_name}"
            self.logger.info(f"✅ Archivo escrito exitosamente: {uri}")
            
            return uri
            
        except GoogleCloudError as e:
            self.logger.error(f"❌ Error escribiendo archivo: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"❌ Error inesperado escribiendo archivo: {str(e)}")
            raise
    
    def mover_archivo_procesado(self, archivo_original: Optional[str], 
                              contenido_procesado: Dict[Any, Any], 
                              nombre_destino: str) -> str:
        """
        Mueve un archivo procesado al bucket de destino y elimina el original
        
        Args:
            archivo_original: Nombre del archivo original (None para no eliminar)
            contenido_procesado: Contenido JSON procesado
            nombre_destino: Nombre del archivo de destino
            
        Returns:
            str: URI del archivo procesado
            
        Raises:
            GoogleCloudError: Para errores de GCS
        """
        try:
            # Escribir archivo procesado al bucket destino
            archivo_path = self.write_json_file(
                self.config.BUCKET_PROCESADO,
                f"procesados/{nombre_destino}",
                contenido_procesado
            )
            
            # Eliminar archivo original si se especifica
            if archivo_original:
                self.eliminar_archivo_original(self.config.BUCKET_ORIGEN, archivo_original)
            
            self.logger.info(f"🔄 Archivo movido: {archivo_original} → procesados/{nombre_destino}")
            return archivo_path
            
        except Exception as e:
            self.logger.error(f"❌ Error moviendo archivo: {str(e)}")
            raise
    
    def eliminar_archivo_original(self, bucket_name: str, file_name: str) -> bool:
        """
        Elimina un archivo original del bucket de origen
        
        Args:
            bucket_name: Nombre del bucket
            file_name: Nombre del archivo a eliminar
            
        Returns:
            bool: True si se eliminó exitosamente
            
        Raises:
            GoogleCloudError: Para errores de GCS
        """
        try:
            self.logger.info(f"🗑️  Eliminando archivo original: gs://{bucket_name}/{file_name}")
            
            bucket = self.client.bucket(bucket_name)
            blob = bucket.blob(file_name)
            
            if blob.exists():
                blob.delete()
                self.logger.info(f"✅ Archivo eliminado exitosamente: {file_name}")
                return True
            else:
                self.logger.warning(f"⚠️  Archivo no encontrado para eliminar: {file_name}")
                return False
                
        except GoogleCloudError as e:
            self.logger.error(f"❌ Error eliminando archivo: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"❌ Error inesperado eliminando archivo: {str(e)}")
            raise
    
    def listar_archivos(self, bucket_name: str, prefix: str = "") -> list:
        """
        Lista archivos en un bucket con un prefijo específico
        
        Args:
            bucket_name: Nombre del bucket
            prefix: Prefijo para filtrar archivos
            
        Returns:
            list: Lista de nombres de archivos
        """
        try:
            self.logger.info(f"📋 Listando archivos: gs://{bucket_name}/{prefix}")
            
            bucket = self.client.bucket(bucket_name)
            blobs = bucket.list_blobs(prefix=prefix)
            
            archivos = [blob.name for blob in blobs]
            
            self.logger.info(f"✅ {len(archivos)} archivos encontrados")
            return archivos
            
        except GoogleCloudError as e:
            self.logger.error(f"❌ Error listando archivos: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"❌ Error inesperado listando archivos: {str(e)}")
            raise
    
    def verificar_bucket_existe(self, bucket_name: str) -> bool:
        """
        Verifica si un bucket existe y es accesible
        
        Args:
            bucket_name: Nombre del bucket
            
        Returns:
            bool: True si el bucket existe y es accesible
        """
        try:
            bucket = self.client.bucket(bucket_name)
            bucket.reload()
            self.logger.info(f"✅ Bucket verificado: {bucket_name}")
            return True
            
        except NotFound:
            self.logger.warning(f"⚠️  Bucket no encontrado: {bucket_name}")
            return False
        except GoogleCloudError as e:
            self.logger.error(f"❌ Error verificando bucket {bucket_name}: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"❌ Error inesperado verificando bucket: {str(e)}")
            return False
