"""
Servicio de Pub/Sub compartido para comunicación asíncrona entre servicios
Implementa publicación y suscripción siguiendo Clean Architecture
"""

import json
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, Callable
from google.cloud import pubsub_v1
from google.cloud.exceptions import GoogleCloudError
from .config import config
from .logger import setup_logger


class PubSubService:
    """
    Servicio centralizado para operaciones de Google Cloud Pub/Sub
    Maneja comunicación asíncrona entre servicios siguiendo patrones empresariales
    """
    
    def __init__(self, service_name: str = 'pubsub-service'):
        self.logger = setup_logger(__name__, service_name, config.APP_VERSION)
        
        # Clientes de Pub/Sub
        self.publisher = pubsub_v1.PublisherClient()
        self.subscriber = pubsub_v1.SubscriberClient()
        
        # Configurar paths de tópicos
        self.project_id = config.GOOGLE_CLOUD_PROJECT
        self._setup_topic_paths()
    
    def _setup_topic_paths(self):
        """
        Configura paths completos de los tópicos
        """
        self.topics = {
            'file_processed': self.publisher.topic_path(
                self.project_id, config.PUBSUB_TOPIC_FILE_PROCESSED
            ),
            'images_ready': self.publisher.topic_path(
                self.project_id, config.PUBSUB_TOPIC_IMAGES_READY
            ),
            'email_send': self.publisher.topic_path(
                self.project_id, config.PUBSUB_TOPIC_EMAIL_SEND
            ),
            'errors': self.publisher.topic_path(
                self.project_id, config.PUBSUB_TOPIC_ERRORS
            )
        }
        
        self.logger.debug(
            f"Topic paths configurados",
            context={'topics_count': len(self.topics), 'project_id': self.project_id}
        )
    
    # ========== MÉTODOS DE PUBLICACIÓN ==========
    
    def publish_file_processed(self, processing_uuid: str, file_data: Dict[str, Any], 
                             trace_id: Optional[str] = None) -> str:
        """
        Publica mensaje de archivo procesado (División completada)
        
        Args:
            processing_uuid: UUID del procesamiento
            file_data: Datos del archivo procesado
            trace_id: ID de trazabilidad opcional
            
        Returns:
            str: ID del mensaje publicado
        """
        try:
            message_data = {
                'event_type': 'file_processed',
                'processing_uuid': processing_uuid,
                'file_data': file_data,
                'timestamp': datetime.now().isoformat(),
                'trace_id': trace_id or str(uuid.uuid4()),
                'service_origin': 'division-service'
            }
            
            return self._publish_message(
                topic_name='file_processed',
                message_data=message_data,
                message_type='file_processed',
                trace_id=trace_id
            )
            
        except Exception as e:
            self.logger.error(f"Error publicando mensaje de archivo procesado: {str(e)}", trace_id=trace_id, exc_info=True)
            raise
    
    def publish_images_ready(self, processing_uuid: str, zip_data: Dict[str, Any], 
                           signed_url: str, trace_id: Optional[str] = None) -> str:
        """
        Publica mensaje de imágenes listas (ZIP creado con URL firmada)
        
        Args:
            processing_uuid: UUID del procesamiento
            zip_data: Datos del archivo ZIP
            signed_url: URL firmada del ZIP
            trace_id: ID de trazabilidad opcional
            
        Returns:
            str: ID del mensaje publicado
        """
        try:
            message_data = {
                'event_type': 'images_ready',
                'processing_uuid': processing_uuid,
                'zip_data': zip_data,
                'signed_url': signed_url,
                'expiration_hours': config.SIGNED_URL_EXPIRATION_HOURS,
                'timestamp': datetime.now().isoformat(),
                'trace_id': trace_id or str(uuid.uuid4()),
                'service_origin': 'image-processing-service'
            }
            
            return self._publish_message(
                topic_name='images_ready',
                message_data=message_data,
                message_type='images_ready',
                trace_id=trace_id
            )
            
        except Exception as e:
            self.logger.error(f"Error publicando mensaje de imágenes listas: {str(e)}", trace_id=trace_id, exc_info=True)
            raise
    
    def publish_email_request(self, processing_uuid: str, email_data: Dict[str, Any], 
                            trace_id: Optional[str] = None) -> str:
        """
        Publica solicitud de envío de email
        
        Args:
            processing_uuid: UUID del procesamiento
            email_data: Datos para el email
            trace_id: ID de trazabilidad opcional
            
        Returns:
            str: ID del mensaje publicado
        """
        try:
            message_data = {
                'event_type': 'email_send_request',
                'processing_uuid': processing_uuid,
                'email_data': email_data,
                'timestamp': datetime.now().isoformat(),
                'trace_id': trace_id or str(uuid.uuid4()),
                'service_origin': 'image-processing-service'
            }
            
            return self._publish_message(
                topic_name='email_send',
                message_data=message_data,
                message_type='email_send',
                trace_id=trace_id
            )
            
        except Exception as e:
            self.logger.error(f"Error publicando solicitud de email: {str(e)}", trace_id=trace_id, exc_info=True)
            raise
    
    def publish_error(self, processing_uuid: str, error_data: Dict[str, Any], 
                     severity: str = 'ERROR', trace_id: Optional[str] = None) -> str:
        """
        Publica mensaje de error
        
        Args:
            processing_uuid: UUID del procesamiento donde ocurrió el error
            error_data: Datos del error
            severity: Severidad del error ('ERROR', 'CRITICAL', 'WARNING')
            trace_id: ID de trazabilidad opcional
            
        Returns:
            str: ID del mensaje publicado
        """
        try:
            message_data = {
                'event_type': 'processing_error',
                'processing_uuid': processing_uuid,
                'error_data': error_data,
                'severity': severity,
                'timestamp': datetime.now().isoformat(),
                'trace_id': trace_id or str(uuid.uuid4()),
                'service_origin': error_data.get('service_origin', 'unknown-service')
            }
            
            return self._publish_message(
                topic_name='errors',
                message_data=message_data,
                message_type='error',
                trace_id=trace_id
            )
            
        except Exception as e:
            self.logger.error(f"Error publicando mensaje de error: {str(e)}", trace_id=trace_id, exc_info=True)
            raise
    
    def publish_workflow_trigger(self, processing_uuid: str, workflow_data: Dict[str, Any],
                               trace_id: Optional[str] = None) -> str:
        """
        Publica mensaje para activar Cloud Workflow
        
        Args:
            processing_uuid: UUID del procesamiento
            workflow_data: Datos para el workflow
            trace_id: ID de trazabilidad opcional
            
        Returns:
            str: ID del mensaje publicado
        """
        try:
            message_data = {
                'event_type': 'workflow_trigger',
                'processing_uuid': processing_uuid,
                'workflow_data': workflow_data,
                'timestamp': datetime.now().isoformat(),
                'trace_id': trace_id or str(uuid.uuid4()),
                'service_origin': 'division-service'
            }
            
            # Usar el tópico de archivos procesados para activar workflow
            return self._publish_message(
                topic_name='file_processed',
                message_data=message_data,
                message_type='workflow_trigger',
                trace_id=trace_id
            )
            
        except Exception as e:
            self.logger.error(f"Error publicando trigger de workflow: {str(e)}", trace_id=trace_id, exc_info=True)
            raise
    
    # ========== MÉTODOS PRIVADOS ==========
    
    def _publish_message(self, topic_name: str, message_data: Dict[str, Any], 
                        message_type: str, trace_id: Optional[str] = None) -> str:
        """
        Método privado para publicar mensaje con formato estándar
        
        Args:
            topic_name: Nombre del tópico (key en self.topics)
            message_data: Datos del mensaje
            message_type: Tipo de mensaje para atributos
            trace_id: ID de trazabilidad opcional
            
        Returns:
            str: ID del mensaje publicado
        """
        try:
            if topic_name not in self.topics:
                raise ValueError(f"Topic desconocido: {topic_name}")
            
            topic_path = self.topics[topic_name]
            
            self.logger.processing(
                f"Publicando mensaje en tópico: {topic_name}",
                context={'message_type': message_type, 'topic_path': topic_path},
                trace_id=trace_id
            )
            
            # Serializar mensaje
            data = json.dumps(message_data, ensure_ascii=False).encode('utf-8')
            
            # Atributos del mensaje
            attributes = {
                'message_type': message_type,
                'source_service': message_data.get('service_origin', 'unknown-service'),
                'processing_uuid': message_data.get('processing_uuid', ''),
                'timestamp': message_data.get('timestamp', datetime.now().isoformat()),
                'trace_id': trace_id or str(uuid.uuid4()),
                'version': config.APP_VERSION
            }
            
            # Publicar mensaje
            future = self.publisher.publish(
                topic_path,
                data=data,
                **attributes
            )
            
            # Obtener ID del mensaje con timeout
            message_id = future.result(timeout=30)
            
            self.logger.success(
                f"Mensaje publicado exitosamente",
                context={
                    'message_id': message_id,
                    'topic': topic_name,
                    'message_type': message_type,
                    'data_size_bytes': len(data)
                },
                trace_id=trace_id
            )
            
            return message_id
            
        except Exception as e:
            self.logger.error(
                f"Error publicando mensaje en tópico {topic_name}: {str(e)}",
                context={'topic_name': topic_name, 'message_type': message_type},
                trace_id=trace_id,
                exc_info=True
            )
            raise
    
    # ========== MÉTODOS DE SUSCRIPCIÓN (Para desarrollo/testing) ==========
    
    def create_subscription_if_not_exists(self, topic_name: str, subscription_name: str,
                                        trace_id: Optional[str] = None) -> str:
        """
        Crea suscripción si no existe (útil para desarrollo)
        
        Args:
            topic_name: Nombre del tópico
            subscription_name: Nombre de la suscripción
            trace_id: ID de trazabilidad opcional
            
        Returns:
            str: Path completo de la suscripción
        """
        try:
            if topic_name not in self.topics:
                raise ValueError(f"Topic desconocido: {topic_name}")
            
            topic_path = self.topics[topic_name]
            subscription_path = self.subscriber.subscription_path(self.project_id, subscription_name)
            
            self.logger.processing(
                f"Verificando/creando suscripción: {subscription_name}",
                context={'topic': topic_name},
                trace_id=trace_id
            )
            
            try:
                # Intentar obtener la suscripción
                self.subscriber.get_subscription(request={'subscription': subscription_path})
                self.logger.debug(f"Suscripción ya existe: {subscription_name}", trace_id=trace_id)
                
            except Exception:
                # La suscripción no existe, crearla
                self.subscriber.create_subscription(
                    request={
                        'name': subscription_path,
                        'topic': topic_path,
                        'ack_deadline_seconds': 60  # 60 segundos para ACK
                    }
                )
                self.logger.success(f"Suscripción creada: {subscription_name}", trace_id=trace_id)
            
            return subscription_path
            
        except Exception as e:
            self.logger.error(f"Error manejando suscripción: {str(e)}", trace_id=trace_id, exc_info=True)
            raise
    
    def listen_to_subscription(self, subscription_name: str, callback: Callable,
                             max_messages: int = 100, trace_id: Optional[str] = None):
        """
        Escucha mensajes de una suscripción (para desarrollo/testing)
        
        Args:
            subscription_name: Nombre de la suscripción
            callback: Función callback para procesar mensajes
            max_messages: Máximo número de mensajes concurrentes
            trace_id: ID de trazabilidad opcional
        """
        try:
            subscription_path = self.subscriber.subscription_path(self.project_id, subscription_name)
            
            self.logger.processing(
                f"Iniciando listener para suscripción: {subscription_name}",
                context={'max_messages': max_messages},
                trace_id=trace_id
            )
            
            # Configurar flow control
            flow_control = pubsub_v1.types.FlowControl(max_messages=max_messages)
            
            # Iniciar streaming pull
            streaming_pull_future = self.subscriber.pull(
                request={'subscription': subscription_path, 'max_messages': max_messages},
                flow_control=flow_control
            )
            
            self.logger.success(
                f"Listener activo para suscripción: {subscription_name}",
                trace_id=trace_id
            )
            
            # Procesar mensajes
            with self.subscriber:
                try:
                    streaming_pull_future.result()
                except KeyboardInterrupt:
                    self.logger.info(f"Deteniendo listener para {subscription_name}", trace_id=trace_id)
                    streaming_pull_future.cancel()
            
        except Exception as e:
            self.logger.error(f"Error en listener de suscripción: {str(e)}", trace_id=trace_id, exc_info=True)
            raise
    
    # ========== MÉTODOS DE UTILIDAD ==========
    
    def get_service_info(self) -> Dict[str, Any]:
        """
        Obtiene información del servicio
        
        Returns:
            Dict con información del servicio
        """
        return {
            'service_name': 'pubsub-service',
            'version': config.APP_VERSION,
            'project_id': self.project_id,
            'configured_topics': list(self.topics.keys()),
            'topic_paths': self.topics
        }


# Instancia global del servicio
pubsub_service = PubSubService()
