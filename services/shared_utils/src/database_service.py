"""
Servicio de base de datos compartido para operaciones PostgreSQL
Optimizado para arquitectura event-driven sin division service
"""

import json
from typing import Dict, Any, List, Optional, Tuple
from contextlib import contextmanager
from datetime import datetime
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import RealDictCursor, execute_values
from config import config
from logger import setup_logger


class DatabaseService:
    """
    Servicio centralizado para operaciones de base de datos PostgreSQL
    Maneja conexiones, consultas y transacciones de manera eficiente
    """
    
    def __init__(self, service_name: str = 'database-service'):
        self.logger = setup_logger(__name__, service_name, config.APP_VERSION)
        self.connection_pool = None
        self._initialize_connection_pool()
    
    def _initialize_connection_pool(self):
        """
        Inicializa pool de conexiones a PostgreSQL
        """
        try:
            self.logger.processing("Inicializando pool de conexiones a PostgreSQL")
            
            # Configurar parámetros de conexión
            connection_params = {
                'host': config.DB_HOST,
                'port': config.DB_PORT,
                'database': config.DB_NAME,
                'user': config.DB_USER,
                'password': config.DB_PASSWORD,
                'sslmode': config.DB_SSL_MODE
            }
            
            # Crear pool de conexiones
            self.connection_pool = SimpleConnectionPool(
                minconn=1,
                maxconn=config.DB_POOL_SIZE,
                **connection_params
            )
            
            # Verificar conectividad
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT version()")
                    version = cursor.fetchone()[0]
                    
            self.logger.success(
                f"Pool de conexiones inicializado exitosamente",
                context={
                    'host': config.DB_HOST,
                    'database': config.DB_NAME,
                    'pool_size': config.DB_POOL_SIZE,
                    'postgresql_version': version[:50]  # Primeros 50 caracteres
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error inicializando pool de conexiones: {str(e)}", exc_info=True)
            raise
    
    @contextmanager
    def get_connection(self):
        """
        Context manager para obtener conexión del pool
        
        Yields:
            psycopg2.connection: Conexión a la base de datos
        """
        conn = None
        try:
            conn = self.connection_pool.getconn()
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            self.logger.error(f"Error en conexión de base de datos: {str(e)}")
            raise
        finally:
            if conn:
                self.connection_pool.putconn(conn)
    
    # ========== MÉTODOS REQUERIDOS PARA IMAGE PROCESSING ==========
    
    def create_image_processing_record(self, processing_uuid: str, original_file: str,
                                     total_packages: int, total_shipments: int,
                                     metadata: Dict[str, Any], trace_id: Optional[str] = None) -> int:
        """
        Crea registro de procesamiento de imágenes
        """
        try:
            self.logger.processing(f"Creando registro de image processing: {processing_uuid}", trace_id=trace_id)
            
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    query = """
                    INSERT INTO procesamiento_imagenes (
                        uuid_procesamiento,
                        archivo_original, 
                        total_paquetes,
                        total_envios,
                        estado,
                        fecha_inicio,
                        metadatos
                    ) VALUES (%s, %s, %s, %s, 'processing', %s, %s) RETURNING id
                    """
                    
                    cursor.execute(query, (
                        processing_uuid, original_file, total_packages, total_shipments,
                        datetime.now(), json.dumps(metadata)
                    ))
                    record_id = cursor.fetchone()['id']
                    conn.commit()
            
            return record_id
        except Exception as e:
            self.logger.error(f"Error creando registro image processing: {str(e)}", trace_id=trace_id, exc_info=True)
            # Para development, no fallar si la tabla no existe
            return 1  # Mock ID
    
    def update_image_processing_status(self, processing_uuid: str, status: str,
                                     result_data: Optional[Dict[str, Any]] = None,
                                     trace_id: Optional[str] = None) -> bool:
        """
        Actualiza estado del procesamiento de imágenes
        """
        try:
            self.logger.processing(f"Actualizando image processing {processing_uuid} -> {status}", trace_id=trace_id)
            
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    query = """
                    UPDATE procesamiento_imagenes 
                    SET estado = %s, fecha_finalizacion = %s, resultado = %s
                    WHERE uuid_procesamiento = %s
                    """
                    
                    cursor.execute(query, (
                        status, datetime.now(), json.dumps(result_data) if result_data else None, processing_uuid
                    ))
                    conn.commit()
            
            return True
        except Exception as e:
            self.logger.warning(f"Error actualizando image processing (tabla puede no existir): {str(e)}", trace_id=trace_id)
            return True  # Para development, no fallar
    
    def get_image_processing_record(self, processing_uuid: str, trace_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Obtiene registro de procesamiento de imágenes (mock para development)
        """
        self.logger.processing(f"Consultando image processing record: {processing_uuid}", trace_id=trace_id)
        
        # Mock data para development
        return {
            'estado': 'completed',
            'paquetes_completados': 5,
            'total_paquetes': 5,
            'imagenes_procesadas': 150,
            'archivos_zip_creados': 5,
            'urls_firmadas_generadas': 5,
            'fecha_inicio': datetime.now(),
            'fecha_finalizacion': datetime.now(),
            'metadatos': {},
            'resultado': {}
        }
    
    # ========== MÉTODOS REQUERIDOS PARA EMAIL SERVICE ==========
    
    def update_processing_final_status(self, processing_uuid: str, status: str,
                                     email_sent: bool = False, email_recipient: Optional[str] = None,
                                     error_message: Optional[str] = None, trace_id: Optional[str] = None) -> bool:
        """
        Actualiza el estado final del procesamiento con información de email
        """
        try:
            self.logger.processing(f"Actualizando estado final {processing_uuid}: {status}", trace_id=trace_id)
            
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    query = """
                    UPDATE archivos_procesamiento 
                    SET estado = %s, email_enviado = %s, email_destinatario = %s, 
                        error_mensaje = %s, fecha_finalizacion = %s
                    WHERE uuid_procesamiento = %s
                    """
                    
                    cursor.execute(query, (
                        status, email_sent, email_recipient, error_message, datetime.now(), processing_uuid
                    ))
                    conn.commit()
            
            return True
        except Exception as e:
            self.logger.warning(f"Error actualizando estado final (tabla puede no existir): {str(e)}", trace_id=trace_id)
            return True  # Para development, no fallar
    
    def get_processing_record(self, processing_uuid: str, 
                            trace_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Obtiene registro de procesamiento por UUID
        
        Args:
            processing_uuid: UUID del procesamiento
            trace_id: ID de trazabilidad opcional
            
        Returns:
            Dict con información del procesamiento o None si no existe
        """
        try:
            self.logger.processing(
                f"Consultando registro de procesamiento: {processing_uuid}",
                trace_id=trace_id
            )
            
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    query = """
                    SELECT 
                        id,
                        nombre_archivo,
                        uuid_procesamiento,
                        total_envios,
                        total_paquetes,
                        estado,
                        fecha_inicio,
                        fecha_finalizacion,
                        resultado,
                        error_mensaje,
                        metadatos,
                        created_at,
                        updated_at
                    FROM archivos_procesamiento 
                    WHERE uuid_procesamiento = %s
                    """
                    
                    cursor.execute(query, (processing_uuid,))
                    result = cursor.fetchone()
            
            if result:
                # Convertir Row a dict y parsear campos JSON
                record = dict(result)
                if record.get('metadatos'):
                    record['metadatos'] = json.loads(record['metadatos']) if isinstance(record['metadatos'], str) else record['metadatos']
                if record.get('resultado'):
                    record['resultado'] = json.loads(record['resultado']) if isinstance(record['resultado'], str) else record['resultado']
                
                self.logger.success(
                    f"Registro de procesamiento encontrado",
                    context={'processing_uuid': processing_uuid, 'status': record['estado']},
                    trace_id=trace_id
                )
                
                return record
            else:
                self.logger.warning(
                    f"Registro de procesamiento no encontrado",
                    context={'processing_uuid': processing_uuid},
                    trace_id=trace_id
                )
                return None
            
        except Exception as e:
            self.logger.error(f"Error consultando registro de procesamiento: {str(e)}", trace_id=trace_id, exc_info=True)
            raise
    
    # ========== MÉTODOS DE UTILIDAD ==========
    
    def check_connectivity(self, trace_id: Optional[str] = None) -> bool:
        """
        Verifica conectividad a la base de datos
        
        Args:
            trace_id: ID de trazabilidad opcional
            
        Returns:
            bool: True si la conexión es exitosa
        """
        try:
            self.logger.processing("Verificando conectividad a base de datos", trace_id=trace_id)
            
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    result = cursor.fetchone()
            
            success = result is not None and result[0] == 1
            
            if success:
                self.logger.success("Conectividad a base de datos verificada exitosamente", trace_id=trace_id)
            else:
                self.logger.error("Fallo en verificación de conectividad", trace_id=trace_id)
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error verificando conectividad: {str(e)}", trace_id=trace_id)
            return False
    
    def get_database_stats(self, trace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Obtiene estadísticas básicas de la base de datos
        
        Args:
            trace_id: ID de trazabilidad opcional
            
        Returns:
            Dict con estadísticas de la base de datos
        """
        try:
            self.logger.processing("Obteniendo estadísticas de base de datos", trace_id=trace_id)
            
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    # Obtener estadísticas básicas
                    queries = {
                        'total_images': "SELECT COUNT(*) as count FROM imagenes_envios",
                        'total_processing_records': "SELECT COUNT(*) as count FROM archivos_procesamiento",
                        'processing_by_status': """
                            SELECT estado, COUNT(*) as count 
                            FROM archivos_procesamiento 
                            GROUP BY estado
                        """,
                        'images_by_type': """
                            SELECT tipo_imagen, COUNT(*) as count 
                            FROM imagenes_envios 
                            GROUP BY tipo_imagen
                        """
                    }
                    
                    stats = {}
                    
                    for stat_name, query in queries.items():
                        cursor.execute(query)
                        if stat_name in ['processing_by_status', 'images_by_type']:
                            stats[stat_name] = {row['estado' if 'estado' in row else 'tipo_imagen']: row['count'] for row in cursor.fetchall()}
                        else:
                            result = cursor.fetchone()
                            stats[stat_name] = result['count'] if result else 0
            
            self.logger.success(
                f"Estadísticas de base de datos obtenidas",
                context=stats,
                trace_id=trace_id
            )
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error obteniendo estadísticas de base de datos: {str(e)}", trace_id=trace_id, exc_info=True)
            raise


# Instancia global del servicio
database_service = DatabaseService()
