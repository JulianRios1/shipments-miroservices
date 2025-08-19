"""
Servicio de base de datos para consultas a PostgreSQL
Maneja conexiones y consultas a la tabla envios_imagenes siguiendo Clean Architecture
"""

import asyncpg
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Any, Optional
from contextlib import contextmanager
from utils.logger import setup_logger
from utils.config import Config


class DatabaseService:
    """
    Servicio para operaciones de base de datos PostgreSQL
    Maneja consultas a la tabla envios_imagenes para obtener rutas de imágenes
    """
    
    def __init__(self):
        self.logger = setup_logger(__name__)
        self.config = Config()
        self._connection_pool = None
    
    @contextmanager
    def get_connection(self):
        """
        Context manager para obtener una conexión a la base de datos
        
        Yields:
            psycopg2.connection: Conexión a PostgreSQL
        """
        connection = None
        try:
            connection = psycopg2.connect(
                host=self.config.DB_HOST,
                port=self.config.DB_PORT,
                database=self.config.DB_NAME,
                user=self.config.DB_USER,
                password=self.config.DB_PASSWORD,
                sslmode=self.config.DB_SSL_MODE
            )
            
            self.logger.debug("✅ Conexión a PostgreSQL establecida")
            yield connection
            
        except psycopg2.Error as e:
            self.logger.error(f"❌ Error conectando a PostgreSQL: {str(e)}")
            if connection:
                connection.rollback()
            raise
        finally:
            if connection:
                connection.close()
                self.logger.debug("🔒 Conexión a PostgreSQL cerrada")
    
    def buscar_imagenes_por_envios(self, envios_ids: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Busca todas las imágenes asociadas a una lista de IDs de envíos
        
        Args:
            envios_ids: Lista de IDs de envíos a buscar
            
        Returns:
            Dict: Diccionario con envio_id como clave y lista de imágenes como valor
            
        Raises:
            psycopg2.Error: Para errores de base de datos
        """
        try:
            self.logger.info(f"🔍 Buscando imágenes para {len(envios_ids)} envíos")
            
            if not envios_ids:
                self.logger.warning("⚠️ Lista de envíos vacía")
                return {}
            
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    # Query para buscar imágenes por IDs de envíos
                    query = """
                        SELECT 
                            id,
                            usuario_id,
                            idenvio,
                            ruta,
                            deleted_at,
                            created_at,
                            updated_at,
                            modulo,
                            img_despacho
                        FROM envios_imagenes 
                        WHERE idenvio = ANY(%s)
                        AND deleted_at IS NULL
                        ORDER BY idenvio, created_at
                    """
                    
                    cursor.execute(query, (envios_ids,))
                    resultados = cursor.fetchall()
                    
                    # Organizar resultados por envío
                    imagenes_por_envio = {}
                    for row in resultados:
                        envio_id = str(row['idenvio'])
                        if envio_id not in imagenes_por_envio:
                            imagenes_por_envio[envio_id] = []
                        
                        # Convertir RealDictRow a diccionario regular
                        imagen_dict = dict(row)
                        
                        # Convertir timestamps a string para serialización JSON
                        if imagen_dict['created_at']:
                            imagen_dict['created_at'] = imagen_dict['created_at'].isoformat()
                        if imagen_dict['updated_at']:
                            imagen_dict['updated_at'] = imagen_dict['updated_at'].isoformat()
                        if imagen_dict['deleted_at']:
                            imagen_dict['deleted_at'] = imagen_dict['deleted_at'].isoformat()
                        
                        imagenes_por_envio[envio_id].append(imagen_dict)
                    
                    total_imagenes = sum(len(imgs) for imgs in imagenes_por_envio.values())
                    envios_con_imagenes = len(imagenes_por_envio)
                    envios_sin_imagenes = len(envios_ids) - envios_con_imagenes
                    
                    self.logger.info(
                        f"✅ Búsqueda completada: {total_imagenes} imágenes encontradas para "
                        f"{envios_con_imagenes} envíos ({envios_sin_imagenes} sin imágenes)"
                    )
                    
                    return imagenes_por_envio
                    
        except psycopg2.Error as e:
            self.logger.error(f"❌ Error en consulta de base de datos: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"❌ Error inesperado buscando imágenes: {str(e)}")
            raise
    
    def obtener_rutas_imagenes_por_envios(self, envios_ids: List[str]) -> Dict[str, List[str]]:
        """
        Obtiene solo las rutas de imágenes para los envíos especificados
        
        Args:
            envios_ids: Lista de IDs de envíos
            
        Returns:
            Dict: Diccionario con envio_id como clave y lista de rutas como valor
        """
        try:
            imagenes_por_envio = self.buscar_imagenes_por_envios(envios_ids)
            
            # Extraer solo las rutas
            rutas_por_envio = {}
            for envio_id, imagenes in imagenes_por_envio.items():
                rutas_por_envio[envio_id] = [img['ruta'] for img in imagenes if img.get('ruta')]
            
            return rutas_por_envio
            
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo rutas de imágenes: {str(e)}")
            raise
    
    def verificar_conectividad(self) -> bool:
        """
        Verifica la conectividad con la base de datos
        
        Returns:
            bool: True si la conexión es exitosa
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    result = cursor.fetchone()
                    
                    if result and result[0] == 1:
                        self.logger.info("✅ Conectividad de base de datos verificada")
                        return True
                        
            return False
            
        except Exception as e:
            self.logger.error(f"❌ Error verificando conectividad: {str(e)}")
            return False
    
    def obtener_estadisticas_tabla(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas básicas de la tabla envios_imagenes
        
        Returns:
            Dict: Estadísticas de la tabla
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    # Contar registros totales
                    cursor.execute("SELECT COUNT(*) as total FROM envios_imagenes")
                    total = cursor.fetchone()['total']
                    
                    # Contar registros activos (no eliminados)
                    cursor.execute("SELECT COUNT(*) as activos FROM envios_imagenes WHERE deleted_at IS NULL")
                    activos = cursor.fetchone()['activos']
                    
                    # Contar por módulo
                    cursor.execute("""
                        SELECT modulo, COUNT(*) as cantidad 
                        FROM envios_imagenes 
                        WHERE deleted_at IS NULL 
                        GROUP BY modulo 
                        ORDER BY cantidad DESC
                    """)
                    por_modulo = {row['modulo']: row['cantidad'] for row in cursor.fetchall()}
                    
                    # Rango de fechas
                    cursor.execute("""
                        SELECT 
                            MIN(created_at) as fecha_min,
                            MAX(created_at) as fecha_max
                        FROM envios_imagenes 
                        WHERE deleted_at IS NULL
                    """)
                    fechas = cursor.fetchone()
                    
                    estadisticas = {
                        'total_registros': total,
                        'registros_activos': activos,
                        'registros_eliminados': total - activos,
                        'porcentaje_activos': round((activos / total * 100), 2) if total > 0 else 0,
                        'distribucion_por_modulo': por_modulo,
                        'fecha_registro_min': fechas['fecha_min'].isoformat() if fechas['fecha_min'] else None,
                        'fecha_registro_max': fechas['fecha_max'].isoformat() if fechas['fecha_max'] else None
                    }
                    
                    self.logger.info(f"📊 Estadísticas obtenidas: {activos}/{total} registros activos")
                    return estadisticas
                    
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo estadísticas: {str(e)}")
            raise
    
    def validar_estructura_tabla(self) -> Dict[str, Any]:
        """
        Valida que la tabla envios_imagenes tenga la estructura esperada
        
        Returns:
            Dict: Resultado de la validación
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    # Obtener información de las columnas
                    cursor.execute("""
                        SELECT column_name, data_type, is_nullable
                        FROM information_schema.columns 
                        WHERE table_name = 'envios_imagenes'
                        ORDER BY ordinal_position
                    """)
                    columnas = cursor.fetchall()
                    
                    # Columnas esperadas según el ejemplo
                    columnas_esperadas = {
                        'id', 'usuario_id', 'idenvio', 'ruta', 'deleted_at', 
                        'created_at', 'updated_at', 'modulo', 'img_despacho'
                    }
                    
                    columnas_encontradas = {col['column_name'] for col in columnas}
                    columnas_faltantes = columnas_esperadas - columnas_encontradas
                    columnas_extra = columnas_encontradas - columnas_esperadas
                    
                    validacion = {
                        'tabla_existe': len(columnas) > 0,
                        'columnas_esperadas': list(columnas_esperadas),
                        'columnas_encontradas': list(columnas_encontradas),
                        'columnas_faltantes': list(columnas_faltantes),
                        'columnas_extra': list(columnas_extra),
                        'estructura_valida': len(columnas_faltantes) == 0,
                        'detalles_columnas': [dict(col) for col in columnas]
                    }
                    
                    if validacion['estructura_valida']:
                        self.logger.info("✅ Estructura de tabla validada correctamente")
                    else:
                        self.logger.warning(f"⚠️ Columnas faltantes: {columnas_faltantes}")
                    
                    return validacion
                    
        except Exception as e:
            self.logger.error(f"❌ Error validando estructura de tabla: {str(e)}")
            raise
