"""
Image Processing Service Simplificado - Sin base de datos
Procesamiento directo y eficiente de paquetes de imágenes
"""

import os
import json
import zipfile
import shutil
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from flask import Flask, request, jsonify
from google.cloud import storage

app = Flask(__name__)

# Cliente de Google Cloud Storage
storage_client = storage.Client()

# Configuración
TEMP_BASE = "/tmp/shipments_processing"
PROCESSED_BUCKET = "shipments-processed"  # Corregido el nombre del bucket
os.makedirs(TEMP_BASE, exist_ok=True)

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return {
        'status': 'healthy',
        'service': 'image-processing-simple',
        'timestamp': datetime.now().isoformat()
    }, 200

@app.route('/process-package', methods=['POST'])
def process_package():
    """
    Endpoint principal para procesar un paquete de imágenes
    """
    temp_dir = None
    try:
        data = request.get_json()
        
        # Validar datos requeridos
        processing_uuid = data.get('processing_uuid')
        package_uri = data.get('package_uri')
        package_name = data.get('package_name', 'package')
        
        if not all([processing_uuid, package_uri]):
            return {'error': 'Campos requeridos: processing_uuid, package_uri'}, 400
        
        print(f"🚀 Procesando paquete: {package_name} ({processing_uuid})")
        
        # Crear directorio temporal
        temp_dir = os.path.join(TEMP_BASE, f"{processing_uuid}_{package_name}")
        os.makedirs(temp_dir, exist_ok=True)
        
        # 1. Leer paquete JSON
        package_data = read_package_from_gcs(package_uri)
        if not package_data:
            raise ValueError(f"No se pudo leer el paquete: {package_uri}")
        
        # 2. Extraer rutas de imágenes
        image_paths = extract_image_paths(package_data)
        if not image_paths:
            raise ValueError("No se encontraron imágenes en el paquete")
        
        print(f"📷 Encontradas {len(image_paths)} imágenes para procesar")
        
        # 3. Descargar imágenes
        downloaded_files = download_images(image_paths, temp_dir)
        if not downloaded_files:
            raise ValueError("No se pudieron descargar imágenes")
        
        print(f"✅ Descargadas {len(downloaded_files)} imágenes")
        
        # 4. Crear ZIP
        zip_filename = f"{package_name}.zip"
        zip_path = os.path.join(temp_dir, zip_filename)
        create_zip(downloaded_files, zip_path)
        
        # Obtener tamaño del ZIP
        zip_size_mb = os.path.getsize(zip_path) / (1024 * 1024)
        print(f"📦 ZIP creado: {zip_size_mb:.2f} MB")
        
        # 5. Subir ZIP a bucket de procesados
        blob_path = f"{processing_uuid}/{zip_filename}"
        upload_to_gcs(zip_path, PROCESSED_BUCKET, blob_path)
        
        # 6. Generar URL firmada (2 horas de expiración)
        signed_url = generate_signed_url(PROCESSED_BUCKET, blob_path, hours=2)
        
        # 7. Limpiar archivos temporales
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        
        # 8. Retornar resultado exitoso
        result = {
            "success": True,
            "processing_uuid": processing_uuid,
            "package_name": package_name,
            "images_processed": len(downloaded_files),
            "zip_created": True,
            "zip_size_mb": round(zip_size_mb, 2),
            "signed_url": signed_url,
            "signed_url_generated": True,
            "expiration_time": (datetime.now() + timedelta(hours=2)).isoformat()
        }
        
        print(f"✅ Procesamiento completado: {processing_uuid}")
        return result, 200
        
    except Exception as e:
        # Limpiar en caso de error
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        
        error_msg = str(e)
        print(f"❌ Error procesando paquete: {error_msg}")
        
        # Retornar error
        return {
            "success": False,
            "processing_uuid": data.get('processing_uuid', 'unknown'),
            "package_name": data.get('package_name', 'unknown'),
            "images_processed": 0,
            "zip_created": False,
            "signed_url": None,
            "signed_url_generated": False,
            "error": error_msg
        }, 500

@app.route('/processing-status/<processing_uuid>', methods=['GET'])
def get_processing_status(processing_uuid: str):
    """
    Endpoint simplificado de estado - solo verifica si existe el ZIP
    """
    try:
        # Verificar si existe algún archivo para este UUID
        bucket = storage_client.bucket(PROCESSED_BUCKET)
        blobs = list(bucket.list_blobs(prefix=f"{processing_uuid}/"))
        
        if blobs:
            return {
                'processing_uuid': processing_uuid,
                'status': 'completed',
                'files_found': len(blobs),
                'files': [blob.name for blob in blobs]
            }, 200
        else:
            return {
                'processing_uuid': processing_uuid,
                'status': 'not_found',
                'message': 'No se encontraron archivos procesados'
            }, 404
            
    except Exception as e:
        return {'error': str(e)}, 500

# Funciones auxiliares

def read_package_from_gcs(package_uri: str) -> Optional[Dict]:
    """Lee el paquete JSON desde GCS"""
    try:
        if not package_uri.startswith("gs://"):
            return None
        
        parts = package_uri[5:].split("/", 1)
        if len(parts) != 2:
            return None
        
        bucket_name, blob_path = parts
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        
        if not blob.exists():
            return None
        
        content = blob.download_as_text()
        return json.loads(content)
        
    except Exception as e:
        print(f"Error leyendo paquete: {e}")
        return None

def extract_image_paths(package_data: Dict) -> List[str]:
    """Extrae las rutas de imágenes del paquete"""
    image_paths = []
    
    envios = package_data.get("envios", [])
    for envio in envios:
        imagenes = envio.get("imagenes", [])
        image_paths.extend(imagenes)
    
    return image_paths

def download_images(image_paths: List[str], temp_dir: str) -> List[str]:
    """Descarga las imágenes a un directorio temporal"""
    downloaded = []
    
    for i, image_path in enumerate(image_paths):
        try:
            # Manejar diferentes formatos de rutas
            if image_path.startswith("gs://"):
                uri = image_path
            else:
                # Si no tiene gs://, asumir que está en shipments-images
                filename = os.path.basename(image_path)
                uri = f"gs://shipments-images/{filename}"
            
            # Parsear URI
            parts = uri[5:].split("/", 1)
            if len(parts) != 2:
                continue
            
            bucket_name, blob_path = parts
            
            # Descargar
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_path)
            
            if not blob.exists():
                # Intentar con .png si no existe
                if not blob_path.endswith('.png'):
                    blob = bucket.blob(blob_path + '.png')
                    if not blob.exists():
                        print(f"⚠️ Imagen no encontrada: {blob_path}")
                        continue
            
            # Guardar localmente
            local_filename = f"img_{i:04d}_{os.path.basename(blob_path)}"
            local_path = os.path.join(temp_dir, local_filename)
            blob.download_to_filename(local_path)
            downloaded.append(local_path)
            
        except Exception as e:
            print(f"Error descargando imagen {image_path}: {e}")
            continue
    
    return downloaded

def create_zip(files: List[str], zip_path: str):
    """Crea un archivo ZIP con las imágenes"""
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in files:
            if os.path.exists(file_path):
                arcname = os.path.basename(file_path)
                zipf.write(file_path, arcname)

def upload_to_gcs(local_path: str, bucket_name: str, blob_path: str):
    """Sube un archivo a GCS"""
    try:
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        blob.upload_from_filename(local_path)
        print(f"✅ Archivo subido a gs://{bucket_name}/{blob_path}")
    except Exception as e:
        raise Exception(f"Error subiendo archivo: {str(e)}")

def generate_signed_url(bucket_name: str, blob_path: str, hours: int = 2) -> str:
    """Genera una URL firmada para descarga"""
    try:
        bucket = storage_client.bucket(bucket_name)
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

# Endpoints que ya no necesitamos pero mantenemos para compatibilidad
@app.route('/update-workflow-completion', methods=['POST'])
def update_workflow_completion():
    """Endpoint vacío para compatibilidad con el workflow"""
    return {'status': 'ok', 'message': 'No database - nothing to update'}, 200

@app.route('/schedule-cleanup', methods=['POST'])
def schedule_cleanup():
    """Endpoint vacío para compatibilidad"""
    return {'status': 'ok', 'message': 'No cleanup needed - files in GCS'}, 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8082))
    print(f"🚀 Image Processing Service Simplificado iniciando en puerto {port}")
    app.run(host='0.0.0.0', port=port, debug=True)
