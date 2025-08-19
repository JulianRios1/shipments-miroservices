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
from pubsub_service import pubsub_service

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
                'pubsub': 'healthy'  # Asumimos healthy si no hay errores
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
