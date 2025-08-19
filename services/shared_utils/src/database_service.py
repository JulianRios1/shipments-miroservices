"""
Servicio de base de datos compartido para operaciones PostgreSQL
Implementa conexiones, consultas y operaciones siguiendo Clean Architecture
"""

import json
from typing import Dict, Any, List, Optional, Tuple
from contextlib import contextmanager
from datetime import datetime
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import RealDictCursor, execute_values
from .config import config
from .logger import setup_logger


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
    
    # ========== MÉTODOS DE CONSULTA DE IMÁGENES ==========
    
    def get_image_paths_by_shipment_ids(self, shipment_ids: List[str], 
                                      trace_id: Optional[str] = None) -> Dict[str, List[str]]:
        """
        Obtiene rutas de imágenes para una lista de IDs de envíos
        
        Args:
            shipment_ids: Lista de IDs de envíos
            trace_id: ID de trazabilidad opcional
            
        Returns:
            Dict[str, List[str]]: Diccionario {shipment_id: [lista_de_rutas]}
        """
        try:
            self.logger.processing(
                f"Consultando rutas de imágenes para {len(shipment_ids)} envíos",
                context={'shipment_ids_count': len(shipment_ids)},
                trace_id=trace_id
            )
            
            if not shipment_ids:
                return {}
            
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    # Query optimizada con batch processing
                    query = """
                    SELECT 
                        envio_id,
                        ruta_imagen,
                        tipo_imagen,
                        orden
                    FROM imagenes_envios 
                    WHERE envio_id = ANY(%s)
                    ORDER BY envio_id, orden ASC
                    """
                    
                    cursor.execute(query, (shipment_ids,))
                    results = cursor.fetchall()
                    
                    # Agrupar resultados por envío
                    image_paths = {}
                    for row in results:
                        envio_id = row['envio_id']
                        if envio_id not in image_paths:
                            image_paths[envio_id] = []
                        
                        image_paths[envio_id].append({
                            'ruta': row['ruta_imagen'],
                            'tipo': row['tipo_imagen'],
                            'orden': row['orden']
                        })
            
            total_images = sum(len(paths) for paths in image_paths.values())
            shipments_with_images = len(image_paths)
            
            self.logger.success(
                f"Rutas de imágenes obtenidas exitosamente",
                context={
                    'shipments_with_images': shipments_with_images,
                    'total_images': total_images,
                    'coverage_percentage': round(shipments_with_images / len(shipment_ids) * 100, 2)
                },
                trace_id=trace_id
            )
            
            return image_paths
            
        except Exception as e:
            self.logger.error(f"Error consultando rutas de imágenes: {str(e)}", trace_id=trace_id, exc_info=True)
            raise
    
    def get_image_coverage_stats(self, shipment_ids: List[str], 
                               trace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Obtiene estadísticas de cobertura de imágenes para envíos
        
        Args:
            shipment_ids: Lista de IDs de envíos
            trace_id: ID de trazabilidad opcional
            
        Returns:
            Dict con estadísticas de cobertura
        """
        try:
            self.logger.processing(
                f"Calculando estadísticas de cobertura para {len(shipment_ids)} envíos",
                trace_id=trace_id
            )
            
            if not shipment_ids:
                return {
                    'total_shipments': 0,
                    'shipments_with_images': 0,
                    'shipments_without_images': 0,
                    'coverage_percentage': 0.0,
                    'total_images': 0,
                    'images_by_type': {}
                }
            
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    # Query para estadísticas de cobertura
                    query = """
                    SELECT 
                        COUNT(DISTINCT CASE WHEN ie.envio_id IS NOT NULL THEN ie.envio_id END) as shipments_with_images,
                        COUNT(ie.ruta_imagen) as total_images,
                        ie.tipo_imagen,
                        COUNT(ie.tipo_imagen) as images_of_type
                    FROM unnest(%s) as envio_id
                    LEFT JOIN imagenes_envios ie ON ie.envio_id = envio_id::varchar
                    GROUP BY ie.tipo_imagen
                    """
                    
                    cursor.execute(query, (shipment_ids,))
                    results = cursor.fetchall()
                    
                    # Procesar resultados
                    total_shipments = len(shipment_ids)
                    shipments_with_images = 0
                    total_images = 0
                    images_by_type = {}
                    
                    for row in results:
                        if row['tipo_imagen']:  # Solo contar si tiene tipo (no es NULL)
                            images_by_type[row['tipo_imagen']] = row['images_of_type']
                            total_images += row['images_of_type']
                            shipments_with_images = max(shipments_with_images, row['shipments_with_images'])
            
            shipments_without_images = total_shipments - shipments_with_images
            coverage_percentage = (shipments_with_images / total_shipments * 100) if total_shipments > 0 else 0.0
            
            stats = {
                'total_shipments': total_shipments,
                'shipments_with_images': shipments_with_images,
                'shipments_without_images': shipments_without_images,
                'coverage_percentage': round(coverage_percentage, 2),
                'total_images': total_images,
                'images_by_type': images_by_type,
                'avg_images_per_shipment': round(total_images / total_shipments, 2) if total_shipments > 0 else 0.0
            }
            
            self.logger.success(
                f"Estadísticas de cobertura calculadas",
                context=stats,
                trace_id=trace_id
            )
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error calculando estadísticas de cobertura: {str(e)}", trace_id=trace_id, exc_info=True)
            raise
    
    # ========== MÉTODOS DE GESTIÓN DE ARCHIVOS ==========
    
    def create_file_processing_record(self, file_name: str, processing_uuid: str, 
                                    total_shipments: int, total_packages: int,
                                    trace_id: Optional[str] = None) -> int:
        """
        Crea registro de procesamiento de archivo
        
        Args:
            file_name: Nombre del archivo
            processing_uuid: UUID del procesamiento
            total_shipments: Total de envíos
            total_packages: Total de paquetes
            trace_id: ID de trazabilidad opcional
            
        Returns:
            int: ID del registro creado
        """
        try:
            self.logger.processing(
                f"Creando registro de procesamiento para archivo: {file_name}",
                context={'processing_uuid': processing_uuid, 'total_shipments': total_shipments},
                trace_id=trace_id
            )
            
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    query = """
                    INSERT INTO archivos_procesamiento (
                        nombre_archivo,
                        uuid_procesamiento,
                        total_envios,
                        total_paquetes,
                        estado,
                        fecha_inicio,
                        metadatos
                    ) VALUES (
                        %s, %s, %s, %s, 'processing', %s, %s
                    ) RETURNING id
                    """
                    
                    metadatos = {
                        'service_version': config.APP_VERSION,
                        'processing_timestamp': datetime.now().isoformat(),
                        'trace_id': trace_id
                    }
                    
                    cursor.execute(query, (
                        file_name,
                        processing_uuid,
                        total_shipments,
                        total_packages,
                        datetime.now(),
                        json.dumps(metadatos)
                    ))
                    
                    record_id = cursor.fetchone()['id']
                    conn.commit()
            
            self.logger.success(
                f"Registro de procesamiento creado",
                context={'record_id': record_id, 'processing_uuid': processing_uuid},
                trace_id=trace_id
            )
            
            return record_id
            
        except Exception as e:
            self.logger.error(f"Error creando registro de procesamiento: {str(e)}", trace_id=trace_id, exc_info=True)
            raise
    
    def update_file_processing_status(self, processing_uuid: str, status: str, 
                                    result_data: Optional[Dict[str, Any]] = None,
                                    trace_id: Optional[str] = None) -> bool:
        """
        Actualiza estado del procesamiento de archivo
        
        Args:
            processing_uuid: UUID del procesamiento
            status: Nuevo estado ('processing', 'completed', 'failed')
            result_data: Datos del resultado opcional
            trace_id: ID de trazabilidad opcional
            
        Returns:
            bool: True si se actualizó exitosamente
        """
        try:
            self.logger.processing(
                f"Actualizando estado de procesamiento: {processing_uuid} -> {status}",
                context={'status': status},
                trace_id=trace_id
            )
            
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # Construir query dinámicamente según el estado
                    if status == 'completed':
                        query = """
                        UPDATE archivos_procesamiento 
                        SET estado = %s, 
                            fecha_finalizacion = %s,
                            resultado = %s,
                            metadatos = metadatos || %s
                        WHERE uuid_procesamiento = %s
                        """
                        
                        update_metadata = {
                            'completion_timestamp': datetime.now().isoformat(),
                            'final_status': 'completed'
                        }
                        
                        cursor.execute(query, (
                            status,
                            datetime.now(),
                            json.dumps(result_data) if result_data else None,
                            json.dumps(update_metadata),
                            processing_uuid
                        ))
                        
                    elif status == 'failed':
                        query = """
                        UPDATE archivos_procesamiento 
                        SET estado = %s,
                            fecha_finalizacion = %s,
                            error_mensaje = %s,
                            metadatos = metadatos || %s
                        WHERE uuid_procesamiento = %s
                        """
                        
                        error_message = result_data.get('error', 'Unknown error') if result_data else 'Unknown error'
                        update_metadata = {
                            'failure_timestamp': datetime.now().isoformat(),
                            'final_status': 'failed'
                        }
                        
                        cursor.execute(query, (
                            status,
                            datetime.now(),
                            error_message,
                            json.dumps(update_metadata),
                            processing_uuid
                        ))
                        
                    else:  # status == 'processing' u otros
                        query = """
                        UPDATE archivos_procesamiento 
                        SET estado = %s,
                            metadatos = metadatos || %s
                        WHERE uuid_procesamiento = %s
                        """
                        
                        update_metadata = {
                            'status_update_timestamp': datetime.now().isoformat(),
                            'current_status': status
                        }
                        
                        cursor.execute(query, (
                            status,
                            json.dumps(update_metadata),
                            processing_uuid
                        ))
                    
                    rows_affected = cursor.rowcount
                    conn.commit()
            
            success = rows_affected > 0
            
            if success:
                self.logger.success(
                    f"Estado de procesamiento actualizado exitosamente",
                    context={'processing_uuid': processing_uuid, 'new_status': status},
                    trace_id=trace_id
                )
            else:
                self.logger.warning(
                    f"No se encontró registro para actualizar",
                    context={'processing_uuid': processing_uuid},
                    trace_id=trace_id
                )
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error actualizando estado de procesamiento: {str(e)}", trace_id=trace_id, exc_info=True)
            raise
    
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
