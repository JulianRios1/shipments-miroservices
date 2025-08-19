"""
Servicio de validación de imágenes para verificar URLs de envíos
Implementa validación HTTP y análisis de contenido siguiendo Clean Architecture
"""

import requests
import concurrent.futures
from typing import List, Dict, Any
from urllib.parse import urlparse
from utils.logger import setup_logger
from utils.config import Config


class ImageValidatorService:
    """
    Servicio para validar URLs de imágenes en envíos
    Verifica accesibilidad y tipo de contenido de las URLs
    """
    
    def __init__(self):
        self.logger = setup_logger(__name__)
        self.config = Config()
        
        # Configuración para requests
        self.timeout = 10  # Timeout en segundos
        self.max_workers = 5  # Máximo número de workers para validación concurrente
        
        # Headers para simular un navegador
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Tipos de contenido válidos para imágenes
        self.valid_content_types = {
            'image/jpeg', 'image/jpg', 'image/png', 'image/gif', 
            'image/webp', 'image/bmp', 'image/tiff', 'image/svg+xml'
        }
    
    def validar_rutas_imagenes(self, envios: List[Dict]) -> List[Dict]:
        """
        Valida todas las rutas de imágenes en una lista de envíos
        Utiliza procesamiento concurrente para mejorar rendimiento
        
        Args:
            envios: Lista de diccionarios con información de envíos
            
        Returns:
            List[Dict]: Lista de resultados de validación
        """
        try:
            self.logger.info(f"🔍 Iniciando validación de {len(envios)} URLs de imágenes")
            
            # Extraer URLs de imágenes
            urls_con_indices = []
            for i, envio in enumerate(envios):
                url_imagen = self._extraer_url_imagen(envio)
                urls_con_indices.append((i, url_imagen))
            
            # Validar URLs usando threading para mejorar rendimiento
            resultados = self._validar_urls_concurrentemente(urls_con_indices)
            
            # Calcular estadísticas
            validas = len([r for r in resultados if r['valida']])
            invalidas = len(resultados) - validas
            
            self.logger.info(f"✅ Validación completada: {validas} válidas, {invalidas} inválidas")
            
            return resultados
            
        except Exception as e:
            self.logger.error(f"❌ Error validando rutas de imágenes: {str(e)}")
            raise
    
    def validar_url_imagen(self, url: str) -> Dict[str, Any]:
        """
        Valida una URL individual de imagen
        
        Args:
            url: URL de la imagen a validar
            
        Returns:
            Dict con resultado de validación
        """
        try:
            if not url:
                return {
                    'url': None,
                    'valida': False,
                    'error': 'URL vacía o None',
                    'status_code': None,
                    'content_type': None,
                    'content_length': None
                }
            
            # Validar formato básico de URL
            if not self._es_url_valida(url):
                return {
                    'url': url,
                    'valida': False,
                    'error': 'Formato de URL inválido',
                    'status_code': None,
                    'content_type': None,
                    'content_length': None
                }
            
            # Realizar request HTTP HEAD para verificar accesibilidad
            response = requests.head(
                url, 
                headers=self.headers,
                timeout=self.timeout,
                allow_redirects=True
            )
            
            # Verificar status code
            if response.status_code != 200:
                return {
                    'url': url,
                    'valida': False,
                    'error': f'Status code inválido: {response.status_code}',
                    'status_code': response.status_code,
                    'content_type': response.headers.get('content-type'),
                    'content_length': response.headers.get('content-length')
                }
            
            # Verificar tipo de contenido
            content_type = response.headers.get('content-type', '').lower()
            es_imagen = any(ct in content_type for ct in self.valid_content_types)
            
            if not es_imagen:
                return {
                    'url': url,
                    'valida': False,
                    'error': f'Tipo de contenido no es imagen: {content_type}',
                    'status_code': response.status_code,
                    'content_type': content_type,
                    'content_length': response.headers.get('content-length')
                }
            
            # Validación exitosa
            return {
                'url': url,
                'valida': True,
                'error': None,
                'status_code': response.status_code,
                'content_type': content_type,
                'content_length': response.headers.get('content-length')
            }
            
        except requests.exceptions.Timeout:
            return {
                'url': url,
                'valida': False,
                'error': f'Timeout después de {self.timeout} segundos',
                'status_code': None,
                'content_type': None,
                'content_length': None
            }
        except requests.exceptions.ConnectionError:
            return {
                'url': url,
                'valida': False,
                'error': 'Error de conexión - URL no accesible',
                'status_code': None,
                'content_type': None,
                'content_length': None
            }
        except requests.exceptions.RequestException as e:
            return {
                'url': url,
                'valida': False,
                'error': f'Error de request: {str(e)}',
                'status_code': None,
                'content_type': None,
                'content_length': None
            }
        except Exception as e:
            return {
                'url': url,
                'valida': False,
                'error': f'Error inesperado: {str(e)}',
                'status_code': None,
                'content_type': None,
                'content_length': None
            }
    
    def _extraer_url_imagen(self, envio: Dict) -> str:
        """
        Extrae URL de imagen de un envío usando diferentes campos posibles
        
        Args:
            envio: Diccionario con datos del envío
            
        Returns:
            str: URL de imagen o None si no se encuentra
        """
        campos_posibles = [
            'imagen_url', 'url_imagen', 'imagen', 'image_url',
            'photo_url', 'picture_url', 'img_url', 'imageUrl'
        ]
        
        for campo in campos_posibles:
            if campo in envio and envio[campo]:
                return str(envio[campo]).strip()
        
        # Buscar en campos anidados
        if 'producto' in envio and isinstance(envio['producto'], dict):
            for campo in campos_posibles:
                if campo in envio['producto'] and envio['producto'][campo]:
                    return str(envio['producto'][campo]).strip()
        
        return None
    
    def _es_url_valida(self, url: str) -> bool:
        """
        Verifica si una URL tiene formato válido
        
        Args:
            url: URL a verificar
            
        Returns:
            bool: True si la URL tiene formato válido
        """
        try:
            resultado = urlparse(url)
            return all([resultado.scheme, resultado.netloc])
        except Exception:
            return False
    
    def _validar_urls_concurrentemente(self, urls_con_indices: List[tuple]) -> List[Dict]:
        """
        Valida múltiples URLs usando ThreadPoolExecutor para mejorar rendimiento
        
        Args:
            urls_con_indices: Lista de tuplas (índice, url)
            
        Returns:
            List[Dict]: Resultados de validación ordenados por índice original
        """
        try:
            resultados = [None] * len(urls_con_indices)
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Crear tareas de validación
                future_to_index = {
                    executor.submit(self.validar_url_imagen, url): i 
                    for i, url in urls_con_indices
                }
                
                # Procesar resultados a medida que se completan
                for future in concurrent.futures.as_completed(future_to_index):
                    indice = future_to_index[future]
                    try:
                        resultado = future.result()
                        resultado['indice'] = indice
                        resultados[indice] = resultado
                        
                        # Log progreso cada 10 validaciones
                        if (indice + 1) % 10 == 0:
                            self.logger.info(f"🔄 Progreso validación: {indice + 1}/{len(urls_con_indices)}")
                            
                    except Exception as e:
                        self.logger.error(f"❌ Error validando URL en índice {indice}: {str(e)}")
                        # Crear resultado de error para este índice
                        resultados[indice] = {
                            'indice': indice,
                            'url': urls_con_indices[indice][1],
                            'valida': False,
                            'error': f'Error de procesamiento: {str(e)}',
                            'status_code': None,
                            'content_type': None,
                            'content_length': None
                        }
            
            return resultados
            
        except Exception as e:
            self.logger.error(f"❌ Error en validación concurrente: {str(e)}")
            raise
    
    def obtener_estadisticas_validacion(self, validaciones: List[Dict]) -> Dict[str, Any]:
        """
        Calcula estadísticas detalladas de las validaciones realizadas
        
        Args:
            validaciones: Lista de resultados de validación
            
        Returns:
            Dict con estadísticas detalladas
        """
        try:
            total = len(validaciones)
            validas = len([v for v in validaciones if v.get('valida', False)])
            invalidas = total - validas
            
            # Agrupar errores por tipo
            errores_por_tipo = {}
            status_codes = {}
            content_types = {}
            
            for validacion in validaciones:
                if not validacion.get('valida', False):
                    error = validacion.get('error', 'Error desconocido')
                    errores_por_tipo[error] = errores_por_tipo.get(error, 0) + 1
                
                status_code = validacion.get('status_code')
                if status_code:
                    status_codes[status_code] = status_codes.get(status_code, 0) + 1
                
                content_type = validacion.get('content_type')
                if content_type:
                    # Extraer tipo principal (ej: 'image/jpeg' -> 'image')
                    tipo_principal = content_type.split('/')[0] if '/' in content_type else content_type
                    content_types[tipo_principal] = content_types.get(tipo_principal, 0) + 1
            
            return {
                'resumen': {
                    'total': total,
                    'validas': validas,
                    'invalidas': invalidas,
                    'porcentaje_exito': round((validas / total * 100), 2) if total > 0 else 0
                },
                'errores_por_tipo': errores_por_tipo,
                'status_codes': status_codes,
                'content_types': content_types,
                'recomendaciones': self._generar_recomendaciones(errores_por_tipo, invalidas, total)
            }
            
        except Exception as e:
            self.logger.error(f"❌ Error calculando estadísticas: {str(e)}")
            raise
    
    def _generar_recomendaciones(self, errores_por_tipo: Dict, invalidas: int, total: int) -> List[str]:
        """
        Genera recomendaciones basadas en los tipos de errores encontrados
        """
        recomendaciones = []
        
        if invalidas == 0:
            recomendaciones.append("¡Excelente! Todas las URLs de imágenes son válidas.")
            return recomendaciones
        
        porcentaje_error = (invalidas / total * 100) if total > 0 else 0
        
        if porcentaje_error > 50:
            recomendaciones.append("⚠️ Más del 50% de las URLs son inválidas. Revisar fuente de datos.")
        
        # Recomendaciones específicas por tipo de error
        if 'URL vacía o None' in errores_por_tipo:
            recomendaciones.append("🔍 Algunos envíos no tienen URL de imagen definida.")
        
        if any('Timeout' in error for error in errores_por_tipo.keys()):
            recomendaciones.append("⏱️ Considerar aumentar el timeout para URLs lentas.")
        
        if any('Status code inválido' in error for error in errores_por_tipo.keys()):
            recomendaciones.append("🔗 Verificar que las URLs de imágenes estén activas.")
        
        if any('Tipo de contenido no es imagen' in error for error in errores_por_tipo.keys()):
            recomendaciones.append("🖼️ Algunas URLs no apuntan a archivos de imagen válidos.")
        
        return recomendaciones
