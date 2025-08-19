"""
Servicio de Pub/Sub para comunicación asíncrona con otros servicios GCP
Implementa publicación de mensajes siguiendo Clean Architecture
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, Optional
from google.cloud import pubsub_v1
from google.cloud.exceptions import GoogleCloudError
from utils.logger import setup_logger
from utils.config import Config


class PubSubService:
    """
    Servicio para publicar mensajes a Google Cloud Pub/Sub
    Maneja la comunicación con servicios downstream para procesamiento de imágenes
    """
    
    def __init__(self):
        self.logger = setup_logger(__name__)
        self.config = Config()
        
        # Cliente de Pub/Sub
        self.publisher = pubsub_v1.PublisherClient()
        
        # Configurar paths de tópicos
        self.project_id = self.config.GOOGLE_CLOUD_PROJECT
        self.topic_procesamiento = self.publisher.topic_path(
            self.project_id, 
            self.config.PUBSUB_TOPIC_PROCESAMIENTO
        )
    
    def publicar_mensaje_procesamiento(self, archivo_path: str, stats_imagenes: Dict[str, Any], 
                                     metadatos: Optional[Dict[str, Any]] = None) -> str:
        """
        Publica un mensaje para iniciar procesamiento de imágenes
        
        Args:
            archivo_path: URI del archivo procesado en GCS
            stats_imagenes: Estadísticas de validación de imágenes
            metadatos: Información adicional del procesamiento
            
        Returns:
            str: Message ID del mensaje publicado
            
        Raises:
            GoogleCloudError: Para errores de Pub/Sub
        """
        try:
            # Construir mensaje
            mensaje = self._construir_mensaje_procesamiento(
                archivo_path, stats_imagenes, metadatos
            )
            
            # Serializar mensaje
            data = json.dumps(mensaje, ensure_ascii=False).encode('utf-8')
            
            # Agregar atributos del mensaje
            attributes = {
                'message_type': 'procesamiento_imagenes',
                'source_service': 'shipments-json-splitter',
                'timestamp': datetime.now().isoformat(),
                'version': self.config.APP_VERSION
            }
            
            # Publicar mensaje
            future = self.publisher.publish(
                self.topic_procesamiento, 
                data=data, 
                **attributes
            )
            
            # Obtener ID del mensaje
            message_id = future.result(timeout=30)  # Timeout de 30 segundos
            
            self.logger.info(f"✅ Mensaje publicado exitosamente: {message_id}")
            self.logger.debug(f"📨 Contenido del mensaje: {json.dumps(mensaje, indent=2)}")
            
            return message_id
            
        except Exception as e:
            self.logger.error(f"❌ Error publicando mensaje: {str(e)}")
            self.logger.error(f"📄 Archivo: {archivo_path}")
            self.logger.error(f"📊 Stats: {stats_imagenes}")
            raise
    
    def publicar_error_procesamiento(self, archivo_original: str, error: str, 
                                   contexto: Optional[Dict[str, Any]] = None) -> str:
        """
        Publica un mensaje de error para notificar fallos en el procesamiento
        
        Args:
            archivo_original: Nombre del archivo que causó el error
            error: Descripción del error
            contexto: Información adicional sobre el contexto del error
            
        Returns:
            str: Message ID del mensaje de error
        """
        try:
            mensaje = {
                'tipo_evento': 'error_procesamiento',
                'archivo_original': archivo_original,
                'error': error,
                'contexto': contexto or {},
                'timestamp': datetime.now().isoformat(),
                'service': 'shipments-json-splitter',
                'severity': 'ERROR'
            }
            
            data = json.dumps(mensaje, ensure_ascii=False).encode('utf-8')
            
            attributes = {
                'message_type': 'error_procesamiento',
                'source_service': 'shipments-json-splitter',
                'severity': 'ERROR',
                'timestamp': datetime.now().isoformat()
            }
            
            # Usar tópico de errores si está configurado, sino usar el principal
            topic_path = self.publisher.topic_path(
                self.project_id,
                self.config.PUBSUB_TOPIC_ERRORES or self.config.PUBSUB_TOPIC_PROCESAMIENTO
            )
            
            future = self.publisher.publish(topic_path, data=data, **attributes)
            message_id = future.result(timeout=30)
            
            self.logger.warning(f"⚠️ Mensaje de error publicado: {message_id}")
            return message_id
            
        except Exception as e:
            self.logger.error(f"❌ Error publicando mensaje de error: {str(e)}")
            raise
    
    def publicar_metricas_procesamiento(self, metricas: Dict[str, Any]) -> str:
        """
        Publica métricas de procesamiento para monitoreo y análisis
        
        Args:
            metricas: Diccionario con métricas del procesamiento
            
        Returns:
            str: Message ID del mensaje de métricas
        """
        try:
            mensaje = {
                'tipo_evento': 'metricas_procesamiento',
                'metricas': metricas,
                'timestamp': datetime.now().isoformat(),
                'service': 'shipments-json-splitter'
            }
            
            data = json.dumps(mensaje, ensure_ascii=False).encode('utf-8')
            
            attributes = {
                'message_type': 'metricas',
                'source_service': 'shipments-json-splitter',
                'timestamp': datetime.now().isoformat()
            }
            
            # Usar tópico de métricas si está configurado
            topic_path = self.publisher.topic_path(
                self.project_id,
                self.config.PUBSUB_TOPIC_METRICAS or self.config.PUBSUB_TOPIC_PROCESAMIENTO
            )
            
            future = self.publisher.publish(topic_path, data=data, **attributes)
            message_id = future.result(timeout=30)
            
            self.logger.info(f"📊 Métricas publicadas: {message_id}")
            return message_id
            
        except Exception as e:
            self.logger.error(f"❌ Error publicando métricas: {str(e)}")
            raise
    
    def _construir_mensaje_procesamiento(self, archivo_path: str, stats_imagenes: Dict[str, Any],
                                       metadatos: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Construye el mensaje para procesamiento de imágenes
        
        Args:
            archivo_path: URI del archivo procesado
            stats_imagenes: Estadísticas de imágenes
            metadatos: Metadatos adicionales
            
        Returns:
            Dict con el mensaje estructurado
        """
        mensaje = {
            'tipo_evento': 'archivo_procesado',
            'archivo_path': archivo_path,
            'bucket_origen': self.config.BUCKET_ORIGEN,
            'bucket_procesado': self.config.BUCKET_PROCESADO,
            'stats_imagenes': stats_imagenes,
            'timestamp': datetime.now().isoformat(),
            'service_origen': 'shipments-json-splitter',
            'version': self.config.APP_VERSION
        }
        
        # Agregar metadatos si están disponibles
        if metadatos:
            mensaje['metadatos'] = metadatos
            
            # Información específica de división si está disponible
            if 'division_requerida' in metadatos:
                mensaje['requiere_procesamiento_paralelo'] = metadatos.get('division_requerida', False)
                mensaje['parte_actual'] = metadatos.get('parte', 1)
                mensaje['total_partes'] = metadatos.get('total_partes', 1)
        
        # Prioridad basada en estadísticas de imágenes
        porcentaje_validas = stats_imagenes.get('porcentaje_validas', 0)
        if porcentaje_validas >= 90:
            mensaje['prioridad'] = 'ALTA'
        elif porcentaje_validas >= 70:
            mensaje['prioridad'] = 'MEDIA'
        else:
            mensaje['prioridad'] = 'BAJA'
        
        # Configuración sugerida para procesamiento
        mensaje['configuracion_procesamiento'] = {
            'total_imagenes': stats_imagenes.get('total', 0),
            'imagenes_validas': stats_imagenes.get('validas', 0),
            'imagenes_invalidas': stats_imagenes.get('invalidas', 0),
            'requiere_validacion_adicional': porcentaje_validas < 95,
            'batch_size_sugerido': min(50, max(10, stats_imagenes.get('validas', 10)))
        }
        
        return mensaje
    
    def verificar_conectividad(self) -> bool:
        """
        Verifica la conectividad con Pub/Sub
        
        Returns:
            bool: True si la conexión es exitosa
        """
        try:
            # Intentar listar tópicos para verificar conectividad
            project_path = f"projects/{self.project_id}"
            topics = list(self.publisher.list_topics(request={"project": project_path}))
            
            self.logger.info(f"✅ Conectividad Pub/Sub verificada. Tópicos disponibles: {len(topics)}")
            return True
            
        except GoogleCloudError as e:
            self.logger.error(f"❌ Error de conectividad Pub/Sub: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"❌ Error inesperado verificando Pub/Sub: {str(e)}")
            return False
    
    def obtener_estadisticas_topicos(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas de los tópicos utilizados
        
        Returns:
            Dict con estadísticas de tópicos
        """
        try:
            estadisticas = {
                'project_id': self.project_id,
                'topicos_configurados': {
                    'procesamiento': self.config.PUBSUB_TOPIC_PROCESAMIENTO,
                    'errores': self.config.PUBSUB_TOPIC_ERRORES,
                    'metricas': self.config.PUBSUB_TOPIC_METRICAS
                },
                'timestamp': datetime.now().isoformat()
            }
            
            # Verificar existencia de tópicos
            project_path = f"projects/{self.project_id}"
            topics = list(self.publisher.list_topics(request={"project": project_path}))
            topic_names = [topic.name.split('/')[-1] for topic in topics]
            
            estadisticas['topicos_existentes'] = topic_names
            estadisticas['topicos_faltantes'] = [
                topic for topic in estadisticas['topicos_configurados'].values()
                if topic and topic not in topic_names
            ]
            
            return estadisticas
            
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo estadísticas de tópicos: {str(e)}")
            raise
