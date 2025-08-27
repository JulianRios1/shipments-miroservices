"""
Email Service - Cloud Run 3
Servicio responsable de:
1. Recibir notificaciones de procesamiento completado
2. Enviar emails con URLs firmadas
3. Actualizar tabla archivos con estado final
4. Gestionar templates y notificaciones
"""

import os
import uuid
import json
import base64
from datetime import datetime
from typing import Dict, Any, List, Optional
from flask import Flask, request, jsonify
import sys
import traceback

# Añadir shared_utils al path
sys.path.insert(0, '/app/services/shared_utils/src')

from config import config
from logger import setup_logger
from database_service import database_service

from services.email_sender import EmailSender
from services.template_manager import TemplateManager
from services.notification_manager import NotificationManager

# Configurar Flask app
app = Flask(__name__)

# Configurar logger para este servicio
logger = setup_logger(__name__, 'email-service', config.APP_VERSION)

# Inicializar servicios
email_sender = EmailSender()
template_manager = TemplateManager()
notification_manager = NotificationManager()


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint para Cloud Run"""
    return {
        'status': 'healthy',
        'service': 'email-service',
        'version': config.APP_VERSION,
        'timestamp': datetime.now().isoformat()
    }, 200


@app.route('/status', methods=['GET'])
def status_check():
    """Status endpoint con información detallada del servicio"""
    try:
        # Verificar conectividad a servicios dependientes
        db_healthy = database_service.check_connectivity()
        email_healthy = email_sender.check_smtp_connectivity()
        
        return {
            'service': 'email-service',
            'version': config.APP_VERSION,
            'status': 'ready',
            'dependencies': {
                'database': 'healthy' if db_healthy else 'unhealthy',
                'smtp_server': 'healthy' if email_healthy else 'unhealthy',
            },
            'configuration': {
                'smtp_host': config.SMTP_HOST,
                'smtp_port': config.SMTP_PORT,
                'from_email': config.FROM_EMAIL,
                'templates_available': template_manager.get_available_templates()
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


@app.route('/send-pubsub-email', methods=['POST'])
def send_pubsub_email():
    """
    🚀 ENDPOINT PRINCIPAL PUB/SUB PARA EMAIL
    Recibe mensajes del topic 'email-notifications' enviados por image_processing_service
    
    Mensaje esperado:
    {
        "processing_uuid": "uuid",
        "email_type": "completion",
        "original_file": "archivo.json",
        "signed_urls": [...],
        "processing_summary": {...},
        "recipient_email": "user@example.com" (opcional)
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
        message_data = _extract_pubsub_email_data(envelope, trace_id)
        
        processing_uuid = message_data.get('processing_uuid')
        email_type = message_data.get('email_type', 'completion')
        original_file = message_data.get('original_file')
        signed_urls = message_data.get('signed_urls', [])
        processing_summary = message_data.get('processing_summary', {})
        recipient_email = message_data.get('recipient_email')
        
        # Validar campos requeridos
        if not processing_uuid:
            logger.error("Mensaje Pub/Sub sin processing_uuid", 
                        context=message_data, trace_id=trace_id)
            return {'error': 'Campo processing_uuid requerido'}, 400
        
        logger.info(
            f"📧 RECIBIDO MENSAJE PUB/SUB PARA EMAIL: {email_type}",
            context={
                'processing_uuid': processing_uuid,
                'email_type': email_type,
                'original_file': original_file,
                'signed_urls_count': len(signed_urls)
            },
            trace_id=trace_id
        )
        
        # Paso 2: Procesar según tipo de email
        if email_type == 'completion':
            result = _process_completion_email(
                processing_uuid=processing_uuid,
                original_file=original_file,
                signed_urls=signed_urls,
                processing_summary=processing_summary,
                recipient_email=recipient_email,
                trace_id=trace_id
            )
        elif email_type == 'error':
            result = _process_error_email(
                processing_uuid=processing_uuid,
                error_data=message_data,
                trace_id=trace_id
            )
        else:
            logger.error(f"Tipo de email no reconocido: {email_type}", trace_id=trace_id)
            return {'error': f'Tipo de email no reconocido: {email_type}'}, 400
        
        logger.success(
            f"🎉 EMAIL PROCESADO EXITOSAMENTE VIA PUB/SUB",
            context={
                'processing_uuid': processing_uuid,
                'email_type': email_type,
                'emails_sent': result.get('emails_sent', 0)
            },
            trace_id=trace_id
        )
        
        return result, 200
        
    except Exception as e:
        error_msg = f"Error procesando mensaje Pub/Sub de email: {str(e)}"
        logger.error(error_msg, trace_id=trace_id, exc_info=True)
        
        # Publicar error en Pub/Sub
        try:
            pubsub_service.publish_error(
                processing_uuid=processing_uuid if 'processing_uuid' in locals() else trace_id,
                error_data={
                    'service_origin': 'email-service',
                    'endpoint': '/send-pubsub-email',
                    'error_message': error_msg,
                    'stack_trace': traceback.format_exc()
                },
                severity='ERROR',
                trace_id=trace_id
            )
        except:
            logger.error("Error publicando mensaje de error", trace_id=trace_id)
        
        return {'error': error_msg}, 500


@app.route('/send-completion-email', methods=['POST'])
def send_completion_email():
    """
    Endpoint principal para enviar email de procesamiento completado
    Llamado por Cloud Workflow o Pub/Sub
    """
    trace_id = str(uuid.uuid4())
    
    try:
        # Paso 1: Validar request
        data = request.get_json()
        if not data:
            logger.warning("No se recibieron datos válidos", trace_id=trace_id)
            return {'error': 'No se recibieron datos válidos'}, 400
        
        processing_uuid = data.get('processing_uuid')
        if not processing_uuid:
            logger.error("Campo processing_uuid requerido", context=data, trace_id=trace_id)
            return {'error': 'Campo processing_uuid requerido'}, 400
        
        logger.info(
            f"🚀 INICIANDO ENVÍO DE EMAIL: {processing_uuid}",
            context={
                'processing_uuid': processing_uuid,
                'data_keys': list(data.keys())
            },
            trace_id=trace_id
        )
        
        # Paso 2: Procesar solicitud de email completa
        result = notification_manager.process_completion_notification(
            processing_uuid=processing_uuid,
            notification_data=data,
            trace_id=trace_id
        )
        
        logger.success(
            f"🎉 EMAIL ENVIADO EXITOSAMENTE",
            context={
                'processing_uuid': processing_uuid,
                'emails_sent': result['emails_sent'],
                'database_updated': result['database_updated']
            },
            trace_id=trace_id
        )
        
        return result, 200
        
    except Exception as e:
        error_msg = f"Error enviando email: {str(e)}"
        logger.error(error_msg, trace_id=trace_id, exc_info=True)
        
        # Publicar error en Pub/Sub
        try:
            pubsub_service.publish_error(
                processing_uuid=processing_uuid if 'processing_uuid' in locals() else trace_id,
                error_data={
                    'service_origin': 'email-service',
                    'error_message': error_msg,
                    'stack_trace': traceback.format_exc()
                },
                severity='ERROR',
                trace_id=trace_id
            )
        except:
            logger.error("Error publicando mensaje de error", trace_id=trace_id)
        
        return {'error': error_msg}, 500


@app.route('/send-error-notification', methods=['POST'])
def send_error_notification():
    """
    Endpoint para enviar notificaciones de error
    """
    trace_id = str(uuid.uuid4())
    
    try:
        data = request.get_json()
        if not data:
            return {'error': 'No se recibieron datos válidos'}, 400
        
        error_type = data.get('error_type', 'general_error')
        error_message = data.get('error_message', 'Error no especificado')
        processing_uuid = data.get('processing_uuid', 'unknown')
        
        logger.info(
            f"📧 ENVIANDO NOTIFICACIÓN DE ERROR: {error_type}",
            context={
                'processing_uuid': processing_uuid,
                'error_type': error_type
            },
            trace_id=trace_id
        )
        
        # Enviar notificación de error
        result = notification_manager.send_error_notification(
            error_type=error_type,
            error_message=error_message,
            processing_uuid=processing_uuid,
            additional_data=data,
            trace_id=trace_id
        )
        
        return result, 200
        
    except Exception as e:
        logger.error(f"Error enviando notificación de error: {str(e)}", trace_id=trace_id, exc_info=True)
        return {'error': str(e)}, 500


@app.route('/send-custom-email', methods=['POST'])
def send_custom_email():
    """
    Endpoint para enviar emails personalizados
    """
    trace_id = str(uuid.uuid4())
    
    try:
        data = request.get_json()
        if not data:
            return {'error': 'No se recibieron datos válidos'}, 400
        
        to_email = data.get('to_email')
        subject = data.get('subject')
        template_name = data.get('template_name', 'custom')
        template_data = data.get('template_data', {})
        
        if not all([to_email, subject]):
            return {'error': 'Campos requeridos: to_email, subject'}, 400
        
        logger.info(
            f"📧 ENVIANDO EMAIL PERSONALIZADO",
            context={
                'to_email': to_email,
                'template_name': template_name
            },
            trace_id=trace_id
        )
        
        # Enviar email personalizado
        result = email_sender.send_templated_email(
            to_email=to_email,
            subject=subject,
            template_name=template_name,
            template_data=template_data,
            trace_id=trace_id
        )
        
        return result, 200
        
    except Exception as e:
        logger.error(f"Error enviando email personalizado: {str(e)}", trace_id=trace_id, exc_info=True)
        return {'error': str(e)}, 500


@app.route('/templates', methods=['GET'])
def list_templates():
    """
    Endpoint para listar templates de email disponibles
    """
    try:
        templates = template_manager.get_available_templates()
        
        return {
            'templates': templates,
            'total_templates': len(templates),
            'timestamp': datetime.now().isoformat()
        }, 200
        
    except Exception as e:
        logger.error(f"Error listando templates: {str(e)}", exc_info=True)
        return {'error': str(e)}, 500


@app.route('/templates/<template_name>', methods=['GET'])
def get_template_info(template_name: str):
    """
    Endpoint para obtener información de un template específico
    """
    try:
        template_info = template_manager.get_template_info(template_name)
        
        if not template_info:
            return {'error': f'Template {template_name} no encontrado'}, 404
        
        return template_info, 200
        
    except Exception as e:
        logger.error(f"Error obteniendo info de template: {str(e)}", exc_info=True)
        return {'error': str(e)}, 500


@app.route('/test-email', methods=['POST'])
def test_email():
    """
    Endpoint para probar configuración de email
    """
    trace_id = str(uuid.uuid4())
    
    try:
        data = request.get_json() or {}
        to_email = data.get('to_email', config.FROM_EMAIL)
        
        logger.info(f"📧 PROBANDO CONFIGURACIÓN DE EMAIL: {to_email}", trace_id=trace_id)
        
        # Enviar email de prueba
        result = email_sender.send_test_email(to_email, trace_id)
        
        return result, 200
        
    except Exception as e:
        logger.error(f"Error en prueba de email: {str(e)}", trace_id=trace_id, exc_info=True)
        return {'error': str(e)}, 500


@app.route('/statistics', methods=['GET'])
def get_email_statistics():
    """
    Endpoint para obtener estadísticas de emails enviados
    """
    try:
        days = request.args.get('days', 7, type=int)
        
        stats = notification_manager.get_email_statistics(days)
        
        return stats, 200
        
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas: {str(e)}", exc_info=True)
        return {'error': str(e)}, 500


# Endpoint para recibir mensajes de Pub/Sub
@app.route('/pubsub-handler', methods=['POST'])
def handle_pubsub_message():
    """
    Handler para mensajes de Pub/Sub
    """
    trace_id = str(uuid.uuid4())
    
    try:
        envelope = request.get_json()
        if not envelope:
            return {'error': 'No se recibió mensaje válido'}, 400
        
        # Extraer datos del mensaje Pub/Sub
        if 'message' in envelope:
            import base64
            import json
            
            pubsub_message = envelope['message']
            message_data = json.loads(base64.b64decode(pubsub_message['data']).decode())
            
            # Determinar tipo de acción
            action = message_data.get('action', 'send_completion_email')
            
            if action == 'send_completion_email':
                return send_completion_email()
            elif action == 'send_error_notification':
                return send_error_notification()
            else:
                logger.warning(f"Acción no reconocida: {action}", trace_id=trace_id)
                return {'error': f'Acción no reconocida: {action}'}, 400
        
        return {'error': 'Formato de mensaje inválido'}, 400
        
    except Exception as e:
        logger.error(f"Error procesando mensaje Pub/Sub: {str(e)}", trace_id=trace_id, exc_info=True)
        return {'error': str(e)}, 500


# ========== FUNCIONES AUXILIARES PARA PUB/SUB ==========

def _extract_pubsub_email_data(envelope: Dict[str, Any], trace_id: str) -> Dict[str, Any]:
    """
    Extrae datos del mensaje Pub/Sub para email desde diferentes formatos
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


def _process_completion_email(processing_uuid: str, original_file: str, 
                             signed_urls: List[Dict[str, Any]], 
                             processing_summary: Dict[str, Any],
                             recipient_email: Optional[str], 
                             trace_id: str) -> Dict[str, Any]:
    """
    Procesa email de finalización con URLs firmadas
    """
    logger.processing(f"Procesando email de finalización para: {processing_uuid}", 
                     trace_id=trace_id)
    
    try:
        # Determinar email del destinatario
        if not recipient_email:
            # Buscar email en base de datos o usar email por defecto
            recipient_email = _get_recipient_email(processing_uuid, trace_id)
        
        # Preparar datos del template
        template_data = {
            'processing_uuid': processing_uuid,
            'original_file': original_file,
            'signed_urls': signed_urls,
            'processing_summary': processing_summary,
            'total_packages': len(signed_urls),
            'total_images': processing_summary.get('images_processed', 0),
            'completion_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'expiration_info': '2 horas' if signed_urls else 'N/A'
        }
        
        # Generar subject dinámico
        subject = f"Procesamiento Completado - {original_file}"
        
        # Enviar email
        email_result = email_sender.send_templated_email(
            to_email=recipient_email,
            subject=subject,
            template_name='completion',
            template_data=template_data,
            trace_id=trace_id
        )
        
        # Actualizar estado en base de datos
        database_service.update_processing_final_status(
            processing_uuid=processing_uuid,
            status='completed',
            email_sent=True,
            email_recipient=recipient_email,
            trace_id=trace_id
        )
        
        return {
            'status': 'success',
            'processing_uuid': processing_uuid,
            'emails_sent': 1,
            'recipient': recipient_email,
            'template_used': 'completion',
            'database_updated': True,
            'email_details': email_result
        }
        
    except Exception as e:
        logger.error(f"Error procesando email de finalización: {str(e)}", 
                    trace_id=trace_id, exc_info=True)
        
        # Actualizar con error
        database_service.update_processing_final_status(
            processing_uuid=processing_uuid,
            status='completed_with_email_error',
            email_sent=False,
            error_message=str(e),
            trace_id=trace_id
        )
        
        raise


def _process_error_email(processing_uuid: str, error_data: Dict[str, Any], 
                        trace_id: str) -> Dict[str, Any]:
    """
    Procesa email de notificación de error
    """
    logger.processing(f"Procesando email de error para: {processing_uuid}", 
                     trace_id=trace_id)
    
    try:
        # Obtener email del administrador o del usuario
        recipient_email = _get_error_notification_email(trace_id)
        
        # Preparar datos del template
        template_data = {
            'processing_uuid': processing_uuid,
            'error_message': error_data.get('error_message', 'Error desconocido'),
            'error_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'original_file': error_data.get('original_file', 'No especificado'),
            'service_origin': error_data.get('service_origin', 'Desconocido'),
            'additional_info': error_data
        }
        
        # Enviar email de error
        email_result = email_sender.send_templated_email(
            to_email=recipient_email,
            subject=f"Error en Procesamiento - {processing_uuid}",
            template_name='error',
            template_data=template_data,
            trace_id=trace_id
        )
        
        return {
            'status': 'success',
            'processing_uuid': processing_uuid,
            'emails_sent': 1,
            'recipient': recipient_email,
            'template_used': 'error',
            'email_details': email_result
        }
        
    except Exception as e:
        logger.error(f"Error procesando email de error: {str(e)}", 
                    trace_id=trace_id, exc_info=True)
        raise


def _get_recipient_email(processing_uuid: str, trace_id: str) -> str:
    """
    Determina el email del destinatario para notificaciones
    """
    try:
        # Buscar en base de datos el email asociado al procesamiento
        record = database_service.get_processing_record(processing_uuid, trace_id=trace_id)
        
        if record and record.get('email_destinatario'):
            return record['email_destinatario']
        
        # Email por defecto desde configuración
        default_email = os.getenv('DEFAULT_RECIPIENT_EMAIL', config.FROM_EMAIL)
        
        logger.info(f"Usando email por defecto: {default_email}", 
                   context={'processing_uuid': processing_uuid}, trace_id=trace_id)
        
        return default_email
        
    except Exception as e:
        logger.warning(f"Error obteniendo email del destinatario, usando por defecto: {str(e)}", 
                      trace_id=trace_id)
        return config.FROM_EMAIL


def _get_error_notification_email(trace_id: str) -> str:
    """
    Obtiene email para notificaciones de error (normalmente administrador)
    """
    admin_email = os.getenv('ADMIN_EMAIL', config.FROM_EMAIL)
    logger.info(f"Enviando notificación de error a: {admin_email}", trace_id=trace_id)
    return admin_email


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8083))
    debug = config.DEBUG
    
    logger.info(
        f"🚀 Iniciando Email Service",
        context={
            'port': port,
            'debug': debug,
            'version': config.APP_VERSION,
            'smtp_host': config.SMTP_HOST,
            'from_email': config.FROM_EMAIL
        }
    )
    
    app.run(host='0.0.0.0', port=port, debug=debug)
