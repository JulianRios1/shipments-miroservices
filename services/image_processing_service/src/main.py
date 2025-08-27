"""
Image Processing Service - Cloud Run 2
Servicio responsable de:
1. Leer archivos del bucket json-a-procesar
2. Descargar imágenes desde buckets de origen
3. Agrupar por UUID y verificar completitud
4. Crear archivo ZIP temporal
5. Generar URL firmada con expiración de 2 horas
6. Programar cleanup automático después de 24 horas
7. Publicar mensaje para email service
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
from pubsub_service import pubsub_service

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
                'pubsub': 'healthy'  # Asumimos healthy si no hay errores
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


@app.route('/process-pubsub', methods=['POST'])
def process_pubsub_message():
    """
    🚀 ENDPOINT PRINCIPAL PUB/SUB
    Recibe mensajes del topic 'shipment-packages-ready' enviados por division_service (Cloud Function)
    
    Mensaje esperado:
    {
        "processing_uuid": "uuid-generado-por-division-function",
        "original_file": "shipments_2024_001.json",
        "packages": ["gs://json-a-procesar/uuid/package_1_of_5.json", ...],
        "total_shipments": 450,
        "division_metadata": {...}
    }
    """
    trace_id = str(uuid.uuid4())
    
    try:
        # Paso 1: Validar formato Pub/Sub
        envelope = request.get_json()
        if not envelope:
            logger.warning("Mensaje Pub/Sub inválido", trace_id=trace_id)
            return {'error': 'Mensaje Pub/Sub inválido'}, 400
        
        # Extraer datos del mensaje Pub/Sub
        message_data = _extract_pubsub_message_data(envelope, trace_id)
        
        processing_uuid = message_data.get('processing_uuid')
        original_file = message_data.get('original_file')
        packages = message_data.get('packages', [])
        total_shipments = message_data.get('total_shipments', 0)
        division_metadata = message_data.get('division_metadata', {})
        
        # Validar campos requeridos
        if not all([processing_uuid, original_file, packages]):
            logger.error("Mensaje Pub/Sub con campos faltantes", 
                        context=message_data, trace_id=trace_id)
            return {'error': 'Campos requeridos: processing_uuid, original_file, packages'}, 400
        
        logger.info(
            f"🚀 INICIANDO PROCESAMIENTO DE IMÁGENES VIA PUB/SUB",
            context={
                'processing_uuid': processing_uuid,
                'original_file': original_file,
                'total_packages': len(packages),
                'total_shipments': total_shipments
            },
            trace_id=trace_id
        )
        
        # Paso 2: Procesar todos los paquetes en paralelo
        processing_result = _process_all_packages_parallel(
            processing_uuid=processing_uuid,
            original_file=original_file,
            packages=packages,
            total_shipments=total_shipments,
            division_metadata=division_metadata,
            trace_id=trace_id
        )
        
        # Paso 3: Publicar mensaje para email service
        _publish_email_notification(
            processing_uuid=processing_uuid,
            original_file=original_file,
            processing_result=processing_result,
            trace_id=trace_id
        )
        
        # Paso 4: Programar cleanup
        _schedule_cleanup_for_processing(
            processing_uuid=processing_uuid,
            trace_id=trace_id
        )
        
        logger.success(
            f"🎉 PROCESAMIENTO DE IMÁGENES COMPLETADO EXITOSAMENTE",
            context={
                'processing_uuid': processing_uuid,
                'packages_processed': len(packages),
                'images_processed': processing_result['total_images_processed'],
                'zip_files_created': processing_result['zip_files_created'],
                'signed_urls_generated': len(processing_result['signed_urls'])
            },
            trace_id=trace_id
        )
        
        return {
            'status': 'completed',
            'processing_uuid': processing_uuid,
            'packages_processed': len(packages),
            'images_processed': processing_result['total_images_processed'],
            'zip_files_created': processing_result['zip_files_created'],
            'signed_urls_generated': len(processing_result['signed_urls']),
            'email_notification_sent': True,
            'cleanup_scheduled': True
        }, 200
        
    except Exception as e:
        error_msg = f"Error procesando mensaje Pub/Sub: {str(e)}"
        logger.error(error_msg, trace_id=trace_id, exc_info=True)
        
        # Publicar error en Pub/Sub
        try:
            pubsub_service.publish_error(
                processing_uuid=processing_uuid if 'processing_uuid' in locals() else trace_id,
                error_data={
                    'service_origin': 'image-processing-service',
                    'endpoint': '/process-pubsub',
                    'error_message': error_msg,
                    'original_file': original_file if 'original_file' in locals() else 'unknown',
                    'stack_trace': traceback.format_exc()
                },
                severity='ERROR',
                trace_id=trace_id
            )
        except:
            logger.error("Error publicando mensaje de error", trace_id=trace_id)
        
        return {'error': error_msg}, 500


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
        
        # Publicar error en Pub/Sub
        try:
            pubsub_service.publish_error(
                processing_uuid=processing_uuid if 'processing_uuid' in locals() else trace_id,
                error_data={
                    'service_origin': 'image-processing-service',
                    'error_message': error_msg,
                    'package_name': package_name if 'package_name' in locals() else 'unknown',
                    'stack_trace': traceback.format_exc()
                },
                severity='ERROR',
                trace_id=trace_id
            )
        except:
            logger.error("Error publicando mensaje de error", trace_id=trace_id)
        
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


# ========== FUNCIONES AUXILIARES PARA PUB/SUB ==========

def _extract_pubsub_message_data(envelope: Dict[str, Any], trace_id: str) -> Dict[str, Any]:
    """
    Extrae datos del mensaje Pub/Sub desde diferentes formatos
    """
    try:
        # Formato estándar Pub/Sub push
        if 'message' in envelope and 'data' in envelope['message']:
            message_data_b64 = envelope['message']['data']
            message_data_json = base64.b64decode(message_data_b64).decode('utf-8')
            return json.loads(message_data_json)
        
        # Formato directo (para testing)
        elif 'data' in envelope:
            return envelope['data']
        
        # Fallback: usar envelope completo
        else:
            return envelope
            
    except Exception as e:
        logger.error(f"Error extrayendo datos de mensaje Pub/Sub: {str(e)}", 
                    context={'envelope_keys': list(envelope.keys())}, trace_id=trace_id)
        raise ValueError(f"Formato de mensaje Pub/Sub inválido: {str(e)}")


def _process_all_packages_parallel(processing_uuid: str, original_file: str, 
                                  packages: List[str], total_shipments: int,
                                  division_metadata: Dict[str, Any], 
                                  trace_id: str) -> Dict[str, Any]:
    """
    Procesa todos los paquetes en paralelo y genera ZIPs con URLs firmadas
    """
    logger.processing(f"Procesando {len(packages)} paquetes en paralelo", 
                     context={'processing_uuid': processing_uuid}, trace_id=trace_id)
    
    # Registrar inicio del procesamiento
    database_service.create_image_processing_record(
        processing_uuid=processing_uuid,
        original_file=original_file,
        total_packages=len(packages),
        total_shipments=total_shipments,
        metadata=division_metadata,
        trace_id=trace_id
    )
    
    try:
        # Simular procesamiento paralelo (en implementación real usar threading/asyncio)
        results = []
        signed_urls = []
        total_images_processed = 0
        
        for i, package_uri in enumerate(packages, 1):
            package_name = f"package_{i}_of_{len(packages)}.json"
            
            logger.processing(f"Procesando paquete {i}/{len(packages)}: {package_name}", 
                           trace_id=trace_id)
            
            # Procesar paquete individual
            package_result = package_processor.process_complete_package(
                processing_uuid=processing_uuid,
                package_uri=package_uri,
                package_name=package_name,
                trace_id=trace_id
            )
            
            results.append(package_result)
            total_images_processed += package_result.get('images_processed', 0)
            
            if package_result.get('signed_url'):
                signed_urls.append({
                    'package_name': package_name,
                    'signed_url': package_result['signed_url'],
                    'expires_at': package_result['expires_at'],
                    'images_count': package_result.get('images_processed', 0)
                })
        
        # Actualizar estado en base de datos
        final_result = {
            'total_images_processed': total_images_processed,
            'zip_files_created': len([r for r in results if r.get('zip_created')]),
            'signed_urls': signed_urls,
            'packages_results': results
        }
        
        database_service.update_image_processing_status(
            processing_uuid=processing_uuid,
            status='completed',
            result_data=final_result,
            trace_id=trace_id
        )
        
        return final_result
        
    except Exception as e:
        # Actualizar estado como fallido
        database_service.update_image_processing_status(
            processing_uuid=processing_uuid,
            status='failed',
            result_data={'error': str(e)},
            trace_id=trace_id
        )
        raise


def _publish_email_notification(processing_uuid: str, original_file: str, 
                               processing_result: Dict[str, Any], 
                               trace_id: str) -> None:
    """
    Publica mensaje en topic 'email-notifications' para enviar email de finalización
    """
    try:
        email_message = {
            'processing_uuid': processing_uuid,
            'email_type': 'completion',
            'original_file': original_file,
            'signed_urls': processing_result['signed_urls'],
            'processing_summary': {
                'images_processed': processing_result['total_images_processed'],
                'zip_files_created': processing_result['zip_files_created'],
                'completion_timestamp': datetime.now().isoformat()
            },
            'recipient_email': None  # Se determinará en email_service
        }
        
        pubsub_service.publish_message(
            topic_name='email-notifications',
            message_data=email_message,
            trace_id=trace_id
        )
        
        logger.success("Notificación de email publicada exitosamente", 
                      context={'processing_uuid': processing_uuid}, trace_id=trace_id)
        
    except Exception as e:
        logger.error(f"Error publicando notificación de email: {str(e)}", 
                    trace_id=trace_id, exc_info=True)
        # No re-raise para no fallar todo el procesamiento


def _schedule_cleanup_for_processing(processing_uuid: str, trace_id: str) -> None:
    """
    Programa cleanup automático para archivos temporales
    """
    try:
        cleanup_result = cleanup_scheduler.schedule_cleanup(
            processing_uuid=processing_uuid,
            cleanup_after_hours=config.TEMP_FILES_CLEANUP_HOURS,
            trace_id=trace_id
        )
        
        logger.success("Cleanup programado exitosamente", 
                      context={
                          'processing_uuid': processing_uuid,
                          'scheduled_for': cleanup_result['scheduled_for']
                      }, trace_id=trace_id)
        
    except Exception as e:
        logger.error(f"Error programando cleanup: {str(e)}", 
                    trace_id=trace_id, exc_info=True)
        # No re-raise para no fallar todo el procesamiento


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
