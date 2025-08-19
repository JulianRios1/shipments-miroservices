"""
Division Service - Cloud Run 1
Servicio independiente responsable de:
1. Leer archivos del bucket json-pendientes
2. Esperar completitud del archivo
3. Dividir archivos JSON con UUID de agrupamiento
4. Consultar rutas de imágenes en BD
5. Mover archivos procesados a bucket json-a-procesar
6. Publicar mensaje Pub/Sub para activar workflow
"""

import os
import uuid
from datetime import datetime
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

from services.division_processor import DivisionProcessor
from services.uuid_generator import UUIDGenerator
from services.file_validator import FileValidator


# Configurar Flask app
app = Flask(__name__)

# Configurar logger para este servicio
logger = setup_logger(__name__, 'division-service', config.APP_VERSION)

# Inicializar servicios
division_processor = DivisionProcessor()
uuid_generator = UUIDGenerator()
file_validator = FileValidator()


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint para Cloud Run"""
    return {
        'status': 'healthy',
        'service': 'division-service',
        'version': config.APP_VERSION,
        'timestamp': datetime.now().isoformat()
    }, 200


@app.route('/status', methods=['GET'])
def status_check():
    """Status endpoint con información detallada del servicio"""
    try:
        # Verificar conectividad a servicios
        db_healthy = database_service.check_connectivity()
        
        return {
            'service': 'division-service',
            'version': config.APP_VERSION,
            'status': 'ready',
            'dependencies': {
                'database': 'healthy' if db_healthy else 'unhealthy',
                'storage': 'healthy',  # Asumimos healthy si no hay errores
                'pubsub': 'healthy'
            },
            'configuration': {
                'bucket_pendientes': config.BUCKET_JSON_PENDIENTES,
                'bucket_a_procesar': config.BUCKET_JSON_A_PROCESAR,
                'max_shipments_per_file': config.MAX_SHIPMENTS_PER_FILE
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


@app.route('/process-file', methods=['POST'])
def process_file_from_bucket():
    """
    Endpoint principal que recibe triggers de Cloud Storage
    Implementa el flujo: 
    - json-pendientes → Validación → División → json-a-procesar → Pub/Sub
    """
    trace_id = str(uuid.uuid4())
    
    try:
        # Paso 1: Recibir y validar notificación
        envelope = request.get_json()
        if not envelope:
            logger.warning("No se recibió notificación válida", trace_id=trace_id)
            return {'error': 'No se recibió notificación válida'}, 400
        
        # Extraer datos del evento
        event_data = _extract_event_data(envelope)
        bucket_name = event_data.get('bucket')
        file_name = event_data.get('name')
        
        logger.info(
            f"🚀 INICIANDO DIVISIÓN DE ARCHIVO: {file_name}",
            context={
                'bucket': bucket_name,
                'file_name': file_name,
                'event_type': event_data.get('eventType', 'unknown')
            },
            trace_id=trace_id
        )
        
        # Validar que sea archivo JSON y del bucket correcto
        if not _validate_file_request(bucket_name, file_name, trace_id):
            return {'message': f'Archivo {file_name} ignorado'}, 200
        
        # Paso 2: Esperar completitud del archivo
        logger.processing(f"Esperando completitud del archivo", trace_id=trace_id)
        if not storage_service.wait_for_file_completion(bucket_name, file_name, trace_id=trace_id):
            logger.warning(f"Archivo no completado en tiempo esperado", trace_id=trace_id)
            return {'error': 'Archivo no completado en tiempo esperado'}, 408
        
        # Paso 3: Validar estructura del archivo
        if not file_validator.validate_file_structure(bucket_name, file_name, trace_id=trace_id):
            logger.error(f"Archivo con estructura inválida", trace_id=trace_id)
            return {'error': 'Estructura de archivo inválida'}, 400
        
        # Paso 4: Procesar archivo con división
        result = division_processor.process_file_with_division(
            bucket_name=bucket_name,
            file_name=file_name,
            trace_id=trace_id
        )
        
        logger.success(
            f"🎉 DIVISIÓN DE ARCHIVO COMPLETADA",
            context={
                'original_file': file_name,
                'processing_uuid': result['processing_uuid'],
                'packages_created': result['packages_created'],
                'total_shipments': result['total_shipments']
            },
            trace_id=trace_id
        )
        
        return result, 200
        
    except Exception as e:
        error_msg = f"Error procesando archivo: {str(e)}"
        logger.error(error_msg, trace_id=trace_id, exc_info=True)
        
        # Publicar error en Pub/Sub
        try:
            pubsub_service.publish_error(
                processing_uuid=trace_id,
                error_data={
                    'service_origin': 'division-service',
                    'error_message': error_msg,
                    'file_name': file_name if 'file_name' in locals() else 'unknown',
                    'stack_trace': traceback.format_exc()
                },
                severity='ERROR',
                trace_id=trace_id
            )
        except:
            logger.error("Error publicando mensaje de error", trace_id=trace_id)
        
        return {'error': error_msg}, 500


@app.route('/process-by-uuid/<processing_uuid>', methods=['GET'])
def get_processing_status(processing_uuid: str):
    """
    Endpoint para consultar estado de procesamiento por UUID
    """
    trace_id = str(uuid.uuid4())
    
    try:
        logger.processing(f"Consultando estado de procesamiento: {processing_uuid}", trace_id=trace_id)
        
        # Buscar registro en base de datos
        record = database_service.get_processing_record(processing_uuid, trace_id=trace_id)
        
        if not record:
            return {'error': 'Procesamiento no encontrado'}, 404
        
        # Formatear respuesta
        response = {
            'processing_uuid': processing_uuid,
            'status': record['estado'],
            'original_file': record['nombre_archivo'],
            'total_shipments': record['total_envios'],
            'total_packages': record['total_paquetes'],
            'start_time': record['fecha_inicio'].isoformat() if record['fecha_inicio'] else None,
            'end_time': record['fecha_finalizacion'].isoformat() if record['fecha_finalizacion'] else None,
            'metadata': record['metadatos'],
            'result': record['resultado']
        }
        
        if record['error_mensaje']:
            response['error_message'] = record['error_mensaje']
        
        return response, 200
        
    except Exception as e:
        logger.error(f"Error consultando estado de procesamiento: {str(e)}", trace_id=trace_id, exc_info=True)
        return {'error': str(e)}, 500


# ========== FUNCIONES AUXILIARES ==========

def _extract_event_data(envelope: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extrae datos del evento desde diferentes formatos de Cloud Storage
    """
    # Formato Pub/Sub con data base64
    if 'message' in envelope and 'data' in envelope['message']:
        import base64
        import json
        pubsub_message = envelope['message']
        event_data = json.loads(base64.b64decode(pubsub_message['data']).decode())
        return event_data
    
    # Formato Eventarc directo
    elif 'bucket' in envelope and 'name' in envelope:
        return envelope
    
    # Formato CloudEvent (Eventarc v2)
    elif 'data' in envelope:
        return envelope['data']
    
    # Fallback: usar envelope completo
    else:
        return envelope


def _validate_file_request(bucket_name: str, file_name: str, trace_id: str) -> bool:
    """
    Valida que la request sea para un archivo válido
    """
    # Verificar que sea del bucket correcto
    if bucket_name != config.BUCKET_JSON_PENDIENTES:
        logger.debug(
            f"Archivo ignorado - bucket incorrecto: {bucket_name}",
            context={'expected_bucket': config.BUCKET_JSON_PENDIENTES},
            trace_id=trace_id
        )
        return False
    
    # Verificar que sea archivo JSON
    if not file_name or not file_name.endswith('.json'):
        logger.debug(f"Archivo ignorado - no es JSON: {file_name}", trace_id=trace_id)
        return False
    
    # Verificar que no sea archivo temporal o de sistema
    if file_name.startswith('.') or '/tmp/' in file_name:
        logger.debug(f"Archivo ignorado - archivo temporal: {file_name}", trace_id=trace_id)
        return False
    
    return True


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8081))
    debug = config.DEBUG
    
    logger.info(
        f"🚀 Iniciando Division Service",
        context={
            'port': port,
            'debug': debug,
            'version': config.APP_VERSION,
            'bucket_pendientes': config.BUCKET_JSON_PENDIENTES,
            'bucket_a_procesar': config.BUCKET_JSON_A_PROCESAR
        }
    )
    
    app.run(host='0.0.0.0', port=port, debug=debug)
