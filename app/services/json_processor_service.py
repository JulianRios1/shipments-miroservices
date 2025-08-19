"""
Servicio de procesamiento JSON para división de archivos de envíos
Implementa lógica de negocio para dividir archivos grandes siguiendo Clean Architecture
"""

import math
import copy
from datetime import datetime
from typing import Dict, Any, List
from utils.logger import setup_logger


class JsonProcessorService:
    """
    Servicio para procesar y dividir archivos JSON de envíos
    Maneja la lógica de división cuando el número de envíos excede el límite
    """
    
    def __init__(self):
        self.logger = setup_logger(__name__)
    
    def dividir_envios_con_imagenes(self, data: Dict[Any, Any], max_envios: int, 
                                  rutas_imagenes: Dict[str, List[str]]) -> List[Dict[Any, Any]]:
        """
        Divide el archivo JSON en múltiples archivos si excede el límite de envíos
        Incluye rutas de imágenes obtenidas desde la base de datos
        
        Args:
            data: Diccionario con los datos JSON originales
            max_envios: Número máximo de envíos por archivo
            rutas_imagenes: Diccionario con envio_id como clave y lista de rutas como valor
            
        Returns:
            List[Dict]: Lista de diccionarios JSON divididos
        """
        try:
            envios = data.get('envios', [])
            self.logger.info(f"🔄 Procesando {len(envios)} envíos con límite de {max_envios}")
            
            if len(envios) <= max_envios:
                # No necesita división - archivo único con toda la información
                return self._crear_archivo_unico(data, rutas_imagenes)
            else:
                # Necesita división - múltiples archivos
                return self._dividir_en_multiples_archivos(data, max_envios, rutas_imagenes)
                
        except Exception as e:
            self.logger.error(f"❌ Error dividiendo envíos: {str(e)}")
            raise
    
    def _crear_archivo_unico(self, data: Dict[Any, Any], 
                           rutas_imagenes: Dict[str, List[str]]) -> List[Dict[Any, Any]]:
        """
        Crea un archivo único cuando no se requiere división
        
        Args:
            data: Datos originales
            rutas_imagenes: Rutas de imágenes obtenidas de la BD
            
        Returns:
            List con un solo diccionario procesado
        """
        try:
            # Hacer copia profunda para no modificar el original
            archivo_procesado = copy.deepcopy(data)
            
            # Enriquecer envíos con rutas de imágenes
            archivo_procesado = self._enriquecer_envios_con_imagenes(archivo_procesado, rutas_imagenes)
            
            # Calcular estadísticas de imágenes
            stats_imagenes = self._calcular_stats_imagenes_desde_rutas(rutas_imagenes, data.get('envios', []))
            archivo_procesado['stats_imagenes'] = stats_imagenes
            
            # Agregar metadatos de procesamiento
            archivo_procesado['metadatos'] = {
                'procesamiento_completo': True,
                'division_requerida': False,
                'fecha_procesamiento': datetime.now().isoformat(),
                'archivo_original': data.get('nombre_archivo', 'unknown'),
                'total_envios': len(data.get('envios', [])),
                'version_procesador': '1.0.0'
            }
            
            self.logger.info(f"✅ Archivo único creado: {len(data.get('envios', []))} envíos")
            return [archivo_procesado]
            
        except Exception as e:
            self.logger.error(f"❌ Error creando archivo único: {str(e)}")
            raise
    
    def _dividir_en_multiples_archivos(self, data: Dict[Any, Any], max_envios: int,
                                     validaciones_imagenes: List[Dict]) -> List[Dict[Any, Any]]:
        """
        Divide los datos en múltiples archivos cuando excede el límite
        
        Args:
            data: Datos originales
            max_envios: Límite de envíos por archivo
            validaciones_imagenes: Validaciones de imágenes
            
        Returns:
            List de diccionarios JSON divididos
        """
        try:
            envios = data.get('envios', [])
            num_archivos = math.ceil(len(envios) / max_envios)
            archivos_divididos = []
            
            self.logger.info(f"📊 Dividiendo en {num_archivos} archivos de máximo {max_envios} envíos cada uno")
            
            for i in range(num_archivos):
                inicio = i * max_envios
                fin = min((i + 1) * max_envios, len(envios))
                
                # Crear archivo dividido
                archivo_dividido = self._crear_archivo_dividido(
                    data, envios[inicio:fin], validaciones_imagenes[inicio:fin],
                    i + 1, num_archivos, inicio, fin
                )
                
                archivos_divididos.append(archivo_dividido)
                
                self.logger.info(f"✅ Archivo {i+1}/{num_archivos} creado: envíos {inicio+1}-{fin}")
            
            return archivos_divididos
            
        except Exception as e:
            self.logger.error(f"❌ Error dividiendo en múltiples archivos: {str(e)}")
            raise
    
    def _crear_archivo_dividido(self, data_original: Dict[Any, Any], envios_parte: List[Dict],
                              validaciones_parte: List[Dict], parte_actual: int, total_partes: int,
                              inicio: int, fin: int) -> Dict[Any, Any]:
        """
        Crea un archivo dividido individual con sus metadatos correspondientes
        
        Args:
            data_original: Datos originales completos
            envios_parte: Envíos para esta parte
            validaciones_parte: Validaciones de imágenes para esta parte
            parte_actual: Número de parte actual (1-indexed)
            total_partes: Total de partes
            inicio: Índice de inicio (0-indexed)
            fin: Índice de fin (0-indexed)
            
        Returns:
            Dict con el archivo dividido
        """
        try:
            # Crear copia de la estructura original
            archivo_dividido = copy.deepcopy(data_original)
            
            # Reemplazar envíos con la parte correspondiente
            archivo_dividido['envios'] = envios_parte
            
            # Información de división en metadatos
            archivo_dividido['metadatos'] = {
                'procesamiento_completo': True,
                'division_requerida': True,
                'parte': parte_actual,
                'total_partes': total_partes,
                'archivo_original': data_original.get('nombre_archivo', 'unknown'),
                'fecha_procesamiento': datetime.now().isoformat(),
                'rango_envios': f"{inicio + 1}-{fin}",
                'total_envios_archivo': len(envios_parte),
                'total_envios_original': len(data_original.get('envios', [])),
                'version_procesador': '1.0.0'
            }
            
            # Validaciones de imágenes para esta parte
            archivo_dividido['validacion_imagenes'] = validaciones_parte
            archivo_dividido['stats_imagenes'] = self._calcular_stats_imagenes(validaciones_parte)
            
            return archivo_dividido
            
        except Exception as e:
            self.logger.error(f"❌ Error creando archivo dividido parte {parte_actual}: {str(e)}")
            raise
    
    def _calcular_stats_imagenes(self, validaciones_imagenes: List[Dict]) -> Dict[str, Any]:
        """
        Calcula estadísticas de validación de imágenes
        
        Args:
            validaciones_imagenes: Lista de validaciones
            
        Returns:
            Dict con estadísticas calculadas
        """
        try:
            total = len(validaciones_imagenes)
            validas = len([v for v in validaciones_imagenes if v.get('valida', False)])
            invalidas = total - validas
            
            # Calcular errores por tipo
            errores_por_tipo = {}
            for validacion in validaciones_imagenes:
                if not validacion.get('valida', False):
                    error = validacion.get('error', 'Error desconocido')
                    errores_por_tipo[error] = errores_por_tipo.get(error, 0) + 1
            
            stats = {
                'total': total,
                'validas': validas,
                'invalidas': invalidas,
                'porcentaje_validas': round((validas / total * 100), 2) if total > 0 else 0,
                'porcentaje_invalidas': round((invalidas / total * 100), 2) if total > 0 else 0,
                'errores_por_tipo': errores_por_tipo
            }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"❌ Error calculando estadísticas de imágenes: {str(e)}")
            raise
    
    def validar_estructura_json(self, data: Dict[Any, Any]) -> Dict[str, Any]:
        """
        Valida que el JSON tenga la estructura esperada para procesamiento
        
        Args:
            data: Diccionario con los datos JSON
            
        Returns:
            Dict con resultado de validación
        """
        try:
            validacion = {
                'es_valido': True,
                'errores': [],
                'advertencias': []
            }
            
            # Verificar existencia de campo 'envios'
            if 'envios' not in data:
                validacion['es_valido'] = False
                validacion['errores'].append("Campo 'envios' no encontrado en el JSON")
            elif not isinstance(data['envios'], list):
                validacion['es_valido'] = False
                validacion['errores'].append("Campo 'envios' debe ser una lista")
            elif len(data['envios']) == 0:
                validacion['advertencias'].append("Lista de envíos está vacía")
            
            # Verificar estructura de envíos individuales
            if validacion['es_valido'] and data.get('envios'):
                muestra_envios = data['envios'][:5]  # Revisar solo los primeros 5
                for i, envio in enumerate(muestra_envios):
                    if not isinstance(envio, dict):
                        validacion['errores'].append(f"Envío {i+1} no es un objeto válido")
                    else:
                        # Verificar campos comunes de imagen
                        campos_imagen = ['imagen_url', 'url_imagen', 'imagen', 'image_url']
                        tiene_imagen = any(campo in envio for campo in campos_imagen)
                        if not tiene_imagen:
                            validacion['advertencias'].append(f"Envío {i+1} no tiene campo de imagen identificable")
            
            self.logger.info(f"🔍 Validación de estructura: {'✅ Válido' if validacion['es_valido'] else '❌ Inválido'}")
            
            if validacion['errores']:
                self.logger.warning(f"⚠️ Errores: {validacion['errores']}")
            if validacion['advertencias']:
                self.logger.info(f"ℹ️ Advertencias: {validacion['advertencias']}")
            
            return validacion
            
        except Exception as e:
            self.logger.error(f"❌ Error validando estructura JSON: {str(e)}")
            return {
                'es_valido': False,
                'errores': [f"Error de validación: {str(e)}"],
                'advertencias': []
            }
    
    def _enriquecer_envios_con_imagenes(self, data: Dict[Any, Any], 
                                      rutas_imagenes: Dict[str, List[str]]) -> Dict[Any, Any]:
        """
        Enriquece el JSON de envíos con las rutas de imágenes obtenidas de la base de datos
        
        Args:
            data: Datos del JSON original
            rutas_imagenes: Diccionario con envio_id -> lista de rutas
            
        Returns:
            Dict: JSON enriquecido con rutas de imágenes
        """
        try:
            envios_enriquecidos = []
            
            for envio_id in data.get('envios', []):
                envio_str = str(envio_id)
                
                # Crear estructura enriquecida del envío
                envio_enriquecido = {
                    'id': envio_id,
                    'rutas_imagenes': rutas_imagenes.get(envio_str, []),
                    'tiene_imagenes': envio_str in rutas_imagenes and len(rutas_imagenes[envio_str]) > 0,
                    'total_imagenes': len(rutas_imagenes.get(envio_str, []))
                }
                
                envios_enriquecidos.append(envio_enriquecido)
            
            # Reemplazar la lista simple por la enriquecida
            data_enriquecida = copy.deepcopy(data)
            data_enriquecida['envios'] = envios_enriquecidos
            
            return data_enriquecida
            
        except Exception as e:
            self.logger.error(f"❌ Error enriqueciendo envíos: {str(e)}")
            raise
    
    def _calcular_stats_imagenes_desde_rutas(self, rutas_imagenes: Dict[str, List[str]], 
                                           envios_originales: List[str]) -> Dict[str, Any]:
        """
        Calcula estadísticas de imágenes basado en las rutas obtenidas de la BD
        
        Args:
            rutas_imagenes: Diccionario con envio_id -> lista de rutas
            envios_originales: Lista original de IDs de envíos
            
        Returns:
            Dict: Estadísticas de imágenes
        """
        try:
            total_envios = len(envios_originales)
            envios_con_imagenes = 0
            total_imagenes = 0
            
            distribucion_por_envio = {}
            
            for envio_id in envios_originales:
                envio_str = str(envio_id)
                rutas = rutas_imagenes.get(envio_str, [])
                num_imagenes = len(rutas)
                
                if num_imagenes > 0:
                    envios_con_imagenes += 1
                    total_imagenes += num_imagenes
                
                # Distribuir por cantidad de imágenes
                if num_imagenes not in distribucion_por_envio:
                    distribucion_por_envio[num_imagenes] = 0
                distribucion_por_envio[num_imagenes] += 1
            
            envios_sin_imagenes = total_envios - envios_con_imagenes
            
            stats = {
                'total_envios': total_envios,
                'envios_con_imagenes': envios_con_imagenes,
                'envios_sin_imagenes': envios_sin_imagenes,
                'total_imagenes': total_imagenes,
                'porcentaje_con_imagenes': round((envios_con_imagenes / total_envios * 100), 2) if total_envios > 0 else 0,
                'promedio_imagenes_por_envio': round((total_imagenes / envios_con_imagenes), 2) if envios_con_imagenes > 0 else 0,
                'distribucion_imagenes_por_envio': distribucion_por_envio
            }
            
            self.logger.info(
                f"📊 Stats calculadas: {envios_con_imagenes}/{total_envios} envíos con imágenes, "
                f"{total_imagenes} imágenes totales"
            )
            
            return stats
            
        except Exception as e:
            self.logger.error(f"❌ Error calculando estadísticas desde rutas: {str(e)}")
            raise
    
    def _dividir_en_multiples_archivos(self, data: Dict[Any, Any], max_envios: int,
                                     rutas_imagenes: Dict[str, List[str]]) -> List[Dict[Any, Any]]:
        """
        Divide los datos en múltiples archivos cuando excede el límite
        
        Args:
            data: Datos originales
            max_envios: Límite de envíos por archivo
            rutas_imagenes: Rutas de imágenes de la BD
            
        Returns:
            List de diccionarios JSON divididos
        """
        try:
            envios = data.get('envios', [])
            num_archivos = math.ceil(len(envios) / max_envios)
            archivos_divididos = []
            
            self.logger.info(f"📊 Dividiendo en {num_archivos} archivos de máximo {max_envios} envíos cada uno")
            
            for i in range(num_archivos):
                inicio = i * max_envios
                fin = min((i + 1) * max_envios, len(envios))
                
                # Obtener envíos y rutas para esta parte
                envios_parte = envios[inicio:fin]
                rutas_parte = {str(envio_id): rutas_imagenes.get(str(envio_id), []) for envio_id in envios_parte}
                
                # Crear archivo dividido
                archivo_dividido = self._crear_archivo_dividido_con_rutas(
                    data, envios_parte, rutas_parte,
                    i + 1, num_archivos, inicio, fin
                )
                
                archivos_divididos.append(archivo_dividido)
                
                self.logger.info(f"✅ Archivo {i+1}/{num_archivos} creado: envíos {inicio+1}-{fin}")
            
            return archivos_divididos
            
        except Exception as e:
            self.logger.error(f"❌ Error dividiendo en múltiples archivos: {str(e)}")
            raise
    
    def _crear_archivo_dividido_con_rutas(self, data_original: Dict[Any, Any], 
                                        envios_parte: List[str], rutas_parte: Dict[str, List[str]],
                                        parte_actual: int, total_partes: int,
                                        inicio: int, fin: int) -> Dict[Any, Any]:
        """
        Crea un archivo dividido individual con rutas de imágenes
        
        Args:
            data_original: Datos originales completos
            envios_parte: Envíos para esta parte
            rutas_parte: Rutas de imágenes para esta parte
            parte_actual: Número de parte actual (1-indexed)
            total_partes: Total de partes
            inicio: Índice de inicio (0-indexed)
            fin: Índice de fin (0-indexed)
            
        Returns:
            Dict con el archivo dividido
        """
        try:
            # Crear copia de la estructura original
            archivo_dividido = copy.deepcopy(data_original)
            
            # Crear datos temporales para enriquecimiento
            data_temp = {'envios': envios_parte}
            archivo_enriquecido = self._enriquecer_envios_con_imagenes(data_temp, rutas_parte)
            
            # Usar envíos enriquecidos
            archivo_dividido['envios'] = archivo_enriquecido['envios']
            
            # Calcular estadísticas para esta parte
            stats_imagenes = self._calcular_stats_imagenes_desde_rutas(rutas_parte, envios_parte)
            archivo_dividido['stats_imagenes'] = stats_imagenes
            
            # Información de división en metadatos
            archivo_dividido['metadatos'] = {
                'procesamiento_completo': True,
                'division_requerida': True,
                'parte': parte_actual,
                'total_partes': total_partes,
                'archivo_original': data_original.get('nombre_archivo', 'unknown'),
                'fecha_procesamiento': datetime.now().isoformat(),
                'rango_envios': f"{inicio + 1}-{fin}",
                'total_envios_archivo': len(envios_parte),
                'total_envios_original': len(data_original.get('envios', [])),
                'version_procesador': '1.0.0'
            }
            
            return archivo_dividido
            
        except Exception as e:
            self.logger.error(f"❌ Error creando archivo dividido parte {parte_actual}: {str(e)}")
            raise
