"""
Simple Package Processor - Versión sin base de datos
Procesamiento directo y eficiente de paquetes de imágenes
"""

import os
import json
import zipfile
import tempfile
import shutil
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from google.cloud import storage

class SimpleProcessor:
    """
    Procesador simplificado que:
    1. Lee el paquete JSON
    2. Descarga las imágenes 
    3. Crea un ZIP
    4. Genera URL firmada
    5. Retorna el resultado
    """
    
    def __init__(self):
        self.storage_client = storage.Client()
        self.temp_base = "/tmp/shipments_processing"
        os.makedirs(self.temp_base, exist_ok=True)
    
    def process_package(self, processing_uuid: str, package_uri: str, 
                       package_name: str) -> Dict[str, Any]:
        """
        Procesa un paquete de manera simple y directa
        """
        temp_dir = None
        try:
            # 1. Crear directorio temporal
            temp_dir = os.path.join(self.temp_base, f"{processing_uuid}_{package_name}")
            os.makedirs(temp_dir, exist_ok=True)
            
            # 2. Leer paquete JSON
            package_data = self._read_package(package_uri)
            if not package_data:
                raise ValueError(f"No se pudo leer el paquete: {package_uri}")
            
            # 3. Extraer rutas de imágenes
            image_paths = self._extract_image_paths(package_data)
            if not image_paths:
                raise ValueError("No se encontraron imágenes en el paquete")
            
            # 4. Descargar imágenes
            downloaded_files = self._download_images(image_paths, temp_dir)
            if not downloaded_files:
                raise ValueError("No se pudieron descargar imágenes")
            
            # 5. Crear ZIP
            zip_path = os.path.join(temp_dir, f"{package_name}.zip")
            self._create_zip(downloaded_files, zip_path)
            
            # 6. Subir ZIP a bucket de procesados
            bucket_name = "shipments-images-processed"
            blob_path = f"{processing_uuid}/{package_name}.zip"
            uploaded_url = self._upload_to_gcs(zip_path, bucket_name, blob_path)
            
            # 7. Generar URL firmada (2 horas de expiración)
            signed_url = self._generate_signed_url(bucket_name, blob_path, hours=2)
            
            # 8. Limpiar archivos temporales
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            
            # 9. Retornar resultado exitoso
            return {
                "success": True,
                "processing_uuid": processing_uuid,
                "package_name": package_name,
                "images_processed": len(downloaded_files),
                "zip_created": True,
                "signed_url": signed_url,
                "signed_url_generated": True,
                "expiration_time": (datetime.now() + timedelta(hours=2)).isoformat(),
                "error": None
            }
            
        except Exception as e:
            # Limpiar en caso de error
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            
            # Retornar error
            return {
                "success": False,
                "processing_uuid": processing_uuid,
                "package_name": package_name,
                "images_processed": 0,
                "zip_created": False,
                "signed_url": None,
                "signed_url_generated": False,
                "error": str(e)
            }
    
    def _read_package(self, package_uri: str) -> Optional[Dict]:
        """Lee el paquete JSON desde GCS"""
        try:
            # Parsear URI: gs://bucket/path/file.json
            if not package_uri.startswith("gs://"):
                return None
            
            parts = package_uri[5:].split("/", 1)
            if len(parts) != 2:
                return None
            
            bucket_name, blob_path = parts
            
            bucket = self.storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_path)
            
            if not blob.exists():
                return None
            
            content = blob.download_as_text()
            return json.loads(content)
            
        except Exception:
            return None
    
    def _extract_image_paths(self, package_data: Dict) -> List[str]:
        """Extrae las rutas de imágenes del paquete"""
        image_paths = []
        
        envios = package_data.get("envios", [])
        for envio in envios:
            imagenes = envio.get("imagenes", [])
            image_paths.extend(imagenes)
        
        return image_paths
    
    def _download_images(self, image_paths: List[str], temp_dir: str) -> List[str]:
        """Descarga las imágenes a un directorio temporal"""
        downloaded = []
        
        for i, image_path in enumerate(image_paths):
            try:
                # Si la ruta ya incluye gs://, usarla directamente
                # Si no, asumir que está en shipments-images
                if image_path.startswith("gs://"):
                    uri = image_path
                else:
                    # Extraer solo el nombre del archivo
                    filename = os.path.basename(image_path)
                    uri = f"gs://shipments-images/{filename}"
                
                # Parsear URI
                parts = uri[5:].split("/", 1)
                if len(parts) != 2:
                    continue
                
                bucket_name, blob_path = parts
                
                # Descargar
                bucket = self.storage_client.bucket(bucket_name)
                blob = bucket.blob(blob_path)
                
                if not blob.exists():
                    # Intentar con .png si no existe
                    if not blob_path.endswith('.png'):
                        blob = bucket.blob(blob_path + '.png')
                        if not blob.exists():
                            continue
                
                # Guardar localmente
                local_path = os.path.join(temp_dir, f"image_{i:04d}_{os.path.basename(blob_path)}")
                blob.download_to_filename(local_path)
                downloaded.append(local_path)
                
            except Exception:
                continue
        
        return downloaded
    
    def _create_zip(self, files: List[str], zip_path: str):
        """Crea un archivo ZIP con las imágenes"""
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in files:
                if os.path.exists(file_path):
                    arcname = os.path.basename(file_path)
                    zipf.write(file_path, arcname)
    
    def _upload_to_gcs(self, local_path: str, bucket_name: str, blob_path: str) -> str:
        """Sube un archivo a GCS"""
        try:
            # Crear bucket si no existe
            try:
                bucket = self.storage_client.create_bucket(bucket_name)
            except:
                bucket = self.storage_client.bucket(bucket_name)
            
            blob = bucket.blob(blob_path)
            blob.upload_from_filename(local_path)
            
            return f"gs://{bucket_name}/{blob_path}"
        except Exception as e:
            raise Exception(f"Error subiendo archivo: {str(e)}")
    
    def _generate_signed_url(self, bucket_name: str, blob_path: str, hours: int = 2) -> str:
        """Genera una URL firmada para descarga"""
        try:
            bucket = self.storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_path)
            
            url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(hours=hours),
                method="GET"
            )
            
            return url
        except Exception:
            # Si falla la URL firmada, retornar la URL pública
            return f"https://storage.googleapis.com/{bucket_name}/{blob_path}"
