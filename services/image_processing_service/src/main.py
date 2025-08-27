"""
Image Processing Service - Cloud Run 2
Servicio responsable de:
1. Procesar paquetes individuales de imágenes
2. Descargar imágenes desde buckets de origen
3. Crear archivo ZIP temporal por paquete
4. Generar URL firmada con expiración de 2 horas
5. Programar cleanup automático después de 24 horas
6. Gestionar estado de procesamiento en base de datos
"""

import os
import uuid
import json
import base64
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from flask import Flask, request, jsonify
import sys
import traceback

# Añadir shared_utils al path
sys.path.insert(0, '/app/services/shared_utils/src')

from config import config
from logger import setup_logger
from storage_service import storage_service
from database_service import database_service

from services.image_downloader import ImageDownloader
from services.zip_creator import ZipCreator  
from services.signed_url_generator import SignedUrlGenerator
from services.cleanup_scheduler import CleanupScheduler
from services.package_processor import PackageProcessor

# Configurar Flask app
app = Flask(__name__)

# Configurar logger para este servicio
logger = setup_logger(__name__, 'image-processing-service', config.APP_VERSION)

# Inicializar servicios
image_downloader = ImageDownloader()
zip_creator = ZipCreator()
signed_url_generator = SignedUrlGenerator()
cleanup_scheduler = CleanupScheduler()
package_processor = PackageProcessor()


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint para Cloud Run"""
    return {
        'status': 'healthy',
        'service': 'image-processing-service',
        'version': config.APP_VERSION,
        'timestamp': datetime.now().isoformat()
    }, 200


@app.route('/status', methods=['GET'])
def status_check():
    """Status endpoint con información detallada del servicio"""
    try:
        # Verificar conectividad a servicios dependientes
        db_healthy = database_service.check_connectivity()
        storage_healthy = storage_service.check_bucket_access(config.BUCKET_IMAGENES_TEMP)
        
        return {
            'service': 'image-processing-service', 
            'version': config.APP_VERSION,
            'status': 'ready',
            'dependencies': {
                'database': 'healthy' if db_healthy else 'unhealthy',
                'storage': 'healthy' if storage_healthy else 'unhealthy',
            },
            'configuration': {
                'bucket_imagenes_temp': config.BUCKET_IMAGENES_TEMP,
                'bucket_imagenes_originales': config.BUCKET_IMAGENES_ORIGINALES,
                'signed_url_expiration_hours': config.SIGNED_URL_EXPIRATION_HOURS,
                'cleanup_after_hours': config.TEMP_FILES_CLEANUP_HOURS
            },
            'timestamp': datetime.now().isoformat()
        }, 200
        
    except Exception as e:
        logger.error(f"Error en status check: {str(e)}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }, 500




@app.route('/process-package', methods=['POST'])
def process_image_package():
    """
    Endpoint principal para procesar un paquete individual de imágenes
    Llamado por Cloud Workflow para cada paquete
    """
    trace_id = str(uuid.uuid4())
    
    try:
        # Paso 1: Validar request
        data = request.get_json()
        if not data:
            logger.warning("No se recibieron datos válidos", trace_id=trace_id)
            return {'error': 'No se recibieron datos válidos'}, 400
        
        processing_uuid = data.get('processing_uuid')
        package_uri = data.get('package_uri')
        package_name = data.get('package_name')
        
        if not all([processing_uuid, package_uri, package_name]):
            logger.error("Faltan campos requeridos", context=data, trace_id=trace_id)
            return {'error': 'Campos requeridos: processing_uuid, package_uri, package_name'}, 400
        
        logger.info(
            f"🚀 INICIANDO PROCESAMIENTO DE PAQUETE: {package_name}",
            context={
                'processing_uuid': processing_uuid,
                'package_uri': package_uri,
                'package_name': package_name
            },
            trace_id=trace_id
        )
        
        # Paso 2: Procesar paquete completo
        result = package_processor.process_complete_package(
            processing_uuid=processing_uuid,
            package_uri=package_uri,
            package_name=package_name,
            trace_id=trace_id
        )
        
        logger.success(
            f"🎉 PROCESAMIENTO DE PAQUETE COMPLETADO",
            context={
                'processing_uuid': processing_uuid,
                'package_name': package_name,
                'images_processed': result['images_processed'],
                'zip_created': result['zip_created'],
                'signed_url_generated': result['signed_url_generated']
            },
            trace_id=trace_id
        )
        
        return result, 200
        
    except Exception as e:
        error_msg = f"Error procesando paquete: {str(e)}"
        logger.error(error_msg, trace_id=trace_id, exc_info=True)
        
        # Log error for monitoring
        logger.error(f"Error en procesamiento de paquete: {error_msg}", 
                    context={
                        'processing_uuid': processing_uuid if 'processing_uuid' in locals() else trace_id,
                        'package_name': package_name if 'package_name' in locals() else 'unknown',
                        'stack_trace': traceback.format_exc()
                    },
                    trace_id=trace_id)
        
        return {'error': error_msg}, 500


@app.route('/processing-status/<processing_uuid>', methods=['GET'])
def get_processing_status(processing_uuid: str):
    """
    Endpoint para consultar estado de procesamiento de imágenes por UUID
    """
    trace_id = str(uuid.uuid4())
    
    try:
        logger.processing(f"Consultando estado de procesamiento de imágenes: {processing_uuid}", trace_id=trace_id)
        
        # Buscar registro en base de datos
        record = database_service.get_image_processing_record(processing_uuid, trace_id=trace_id)
        
        if not record:
            return {'error': 'Procesamiento de imágenes no encontrado'}, 404
        
        # Formatear respuesta
        response = {
            'processing_uuid': processing_uuid,
            'status': record['estado'],
            'packages_completed': record['paquetes_completados'],
            'total_packages': record['total_paquetes'],
            'images_processed': record['imagenes_procesadas'],
            'zip_files_created': record['archivos_zip_creados'],
            'signed_urls_generated': record['urls_firmadas_generadas'],
            'start_time': record['fecha_inicio'].isoformat() if record['fecha_inicio'] else None,
            'end_time': record['fecha_finalizacion'].isoformat() if record['fecha_finalizacion'] else None,
            'metadata': record['metadatos'],
            'result': record['resultado']
        }
        
        if record['error_mensaje']:
            response['error_message'] = record['error_mensaje']
        
        return response, 200
        
    except Exception as e:
        logger.error(f"Error consultando estado de procesamiento de imágenes: {str(e)}", trace_id=trace_id, exc_info=True)
        return {'error': str(e)}, 500


@app.route('/schedule-cleanup', methods=['POST'])
def schedule_cleanup():
    """
    Endpoint para programar limpieza de archivos temporales
    """
    trace_id = str(uuid.uuid4())
    
    try:
        data = request.get_json()
        processing_uuid = data.get('processing_uuid')
        cleanup_after_hours = data.get('cleanup_after_hours', config.TEMP_FILES_CLEANUP_HOURS)
        
        if not processing_uuid:
            return {'error': 'processing_uuid es requerido'}, 400
        
        logger.processing(f"Programando cleanup para procesamiento: {processing_uuid}", trace_id=trace_id)
        
        # Programar cleanup
        cleanup_result = cleanup_scheduler.schedule_cleanup(
            processing_uuid=processing_uuid,
            cleanup_after_hours=cleanup_after_hours,
            trace_id=trace_id
        )
        
        logger.success(
            f"Cleanup programado exitosamente",
            context={
                'processing_uuid': processing_uuid,
                'cleanup_after_hours': cleanup_after_hours,
                'scheduled_for': cleanup_result['scheduled_for']
            },
            trace_id=trace_id
        )
        
        return cleanup_result, 200
        
    except Exception as e:
        logger.error(f"Error programando cleanup: {str(e)}", trace_id=trace_id, exc_info=True)
        return {'error': str(e)}, 500


@app.route('/cleanup/execute/<processing_uuid>', methods=['POST'])
def execute_cleanup(processing_uuid: str):
    """
    Endpoint para ejecutar cleanup inmediato (usado por Cloud Scheduler)
    """
    trace_id = str(uuid.uuid4())
    
    try:
        logger.processing(f"Ejecutando cleanup inmediato para: {processing_uuid}", trace_id=trace_id)
        
        # Ejecutar cleanup
        cleanup_result = cleanup_scheduler.execute_cleanup_now(
            processing_uuid=processing_uuid,
            trace_id=trace_id
        )
        
        logger.success(
            f"Cleanup ejecutado exitosamente",
            context={
                'processing_uuid': processing_uuid,
                'files_deleted': cleanup_result['files_deleted'],
                'storage_freed_mb': cleanup_result['storage_freed_mb']
            },
            trace_id=trace_id
        )
        
        return cleanup_result, 200
        
    except Exception as e:
        logger.error(f"Error ejecutando cleanup: {str(e)}", trace_id=trace_id, exc_info=True)
        return {'error': str(e)}, 500


@app.route('/update-workflow-completion', methods=['POST'])
def update_workflow_completion():
    """
    Endpoint llamado por Cloud Workflow para actualizar el estado final
    """
    trace_id = str(uuid.uuid4())
    
    try:
        data = request.get_json()
        processing_uuid = data.get('processing_uuid')
        workflow_completed = data.get('workflow_completed', False)
        
        if not processing_uuid:
            return {'error': 'processing_uuid es requerido'}, 400
        
        logger.info(
            f"Actualizando estado final de workflow: {processing_uuid}",
            context={
                'workflow_completed': workflow_completed,
                'completion_data': data
            },
            trace_id=trace_id
        )
        
        # Actualizar estado en base de datos
        database_service.update_workflow_completion_status(
            processing_uuid=processing_uuid,
            workflow_data=data,
            trace_id=trace_id
        )
        
        return {
            'status': 'updated',
            'processing_uuid': processing_uuid,
            'workflow_completed': workflow_completed
        }, 200
        
    except Exception as e:
        logger.error(f"Error actualizando estado final: {str(e)}", trace_id=trace_id, exc_info=True)
        return {'error': str(e)}, 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8082))
    debug = config.DEBUG
    
    logger.info(
        f"🚀 Iniciando Image Processing Service",
        context={
            'port': port,
            'debug': debug,
            'version': config.APP_VERSION,
            'bucket_imagenes_temp': config.BUCKET_IMAGENES_TEMP,
            'bucket_imagenes_originales': config.BUCKET_IMAGENES_ORIGINALES
        }
    )
    
    app.run(host='0.0.0.0', port=port, debug=debug)
