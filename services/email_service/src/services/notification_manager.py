"""
Notification Manager - Orquestador principal de notificaciones
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional

import sys
sys.path.insert(0, '/app/services/shared_utils/src')

from config import config
from logger import setup_logger
from database_service import database_service

from .email_sender import EmailSender
from .template_manager import TemplateManager


class NotificationManager:
    """
    Gestor principal de notificaciones y emails
    """
    
    def __init__(self):
        self.logger = setup_logger(__name__, 'notification-manager', config.APP_VERSION)
        self.email_sender = EmailSender()
        self.template_manager = TemplateManager()
        self.logger.info("✅ Notification Manager inicializado")
    
    def process_completion_notification(self, processing_uuid: str, 
                                      notification_data: Dict[str, Any],
                                      trace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Procesa notificación de procesamiento completado
        """
        try:
            # Obtener información del procesamiento desde BD
            processing_info = database_service.get_processing_record(processing_uuid, trace_id)
            
            if not processing_info:
                raise ValueError(f"Procesamiento no encontrado: {processing_uuid}")
            
            # Preparar datos para template
            template_data = {
                'processing_uuid': processing_uuid,
                'signed_url': notification_data.get('signed_url', '#'),
                'images_processed': notification_data.get('images_processed', 0),
                'file_size_mb': notification_data.get('file_size_mb', 0),
                'expiration_hours': notification_data.get('expiration_hours', 2),
                'expiration_datetime': notification_data.get('expiration_datetime', 'N/A')
            }
            
            # Enviar email
            # Para demo usamos una dirección por defecto
            to_email = config.FROM_EMAIL  # En producción se obtendría de BD
            
            email_result = self.email_sender.send_templated_email(
                to_email=to_email,
                subject=f"🎉 Procesamiento Completado - {processing_uuid[:8]}",
                template_name='completion',
                template_data=template_data,
                trace_id=trace_id
            )
            
            # Actualizar tabla archivos en BD
            database_result = database_service.update_file_completion_status(
                processing_uuid=processing_uuid,
                email_sent=email_result['success'],
                signed_url=notification_data.get('signed_url'),
                completion_data=notification_data,
                trace_id=trace_id
            )
            
            return {
                'success': True,
                'processing_uuid': processing_uuid,
                'emails_sent': 1 if email_result['success'] else 0,
                'database_updated': database_result,
                'email_result': email_result,
                'completed_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error en notification: {str(e)}", trace_id=trace_id, exc_info=True)
            raise
    
    def send_error_notification(self, error_type: str, error_message: str,
                               processing_uuid: str, additional_data: Dict[str, Any] = None,
                               trace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Envía notificación de error
        """
        try:
            template_data = {
                'error_type': error_type,
                'error_message': error_message,
                'processing_uuid': processing_uuid,
                **(additional_data if additional_data else {})
            }
            
            # Enviar a email de administración
            admin_email = config.FROM_EMAIL
            
            email_result = self.email_sender.send_templated_email(
                to_email=admin_email,
                subject=f"⚠️ Error en Procesamiento - {error_type}",
                template_name='error',
                template_data=template_data,
                trace_id=trace_id
            )
            
            return {
                'success': email_result['success'],
                'error_type': error_type,
                'notification_sent': email_result['success'],
                'sent_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error enviando error notification: {str(e)}", trace_id=trace_id)
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_email_statistics(self, days: int = 7) -> Dict[str, Any]:
        """
        Obtiene estadísticas de emails enviados
        """
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Obtener estadísticas desde BD
            stats = database_service.get_email_statistics(start_date, end_date)
            
            return {
                'period': {
                    'days': days,
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                },
                'statistics': stats,
                'generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error obteniendo estadísticas: {str(e)}")
            return {
                'error': str(e),
                'generated_at': datetime.now().isoformat()
            }
