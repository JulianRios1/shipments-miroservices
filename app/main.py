"""
Aplicación principal Flask para procesamiento de archivos JSON de envíos
Implementa Clean Architecture con separación de responsabilidades
"""

import os
import json
import base64
import logging
from datetime import datetime
from flask import Flask, request
from flask_cors import CORS
from dotenv import load_dotenv

# Importar servicios
from services.storage_service import StorageService
from services.json_processor_service import JsonProcessorService
from services.database_service import DatabaseService
from services.pubsub_service import PubSubService
from utils.logger import setup_logger
from utils.config import Config

# Cargar variables de entorno
load_dotenv()

# Configurar aplicación Flask
app = Flask(__name__)
CORS(app)

# Configurar logging
logger = setup_logger(__name__)

# Inicializar configuración
config = Config()

# Inicializar servicios
storage_service = StorageService()
json_processor = JsonProcessorService()
database_service = DatabaseService()
pubsub_service = PubSubService()


@app.route('/', methods=['POST'])
def procesar_archivo_bucket():
    """
    Endpoint principal que recibe triggers directos de Cloud Storage via Eventarc
    Implementa el flujo: Bucket → Trigger → Validación → División → Movimiento → Pub/Sub
    """
    
    try:
        # Paso 1: Recibir notificación del bucket
        envelope = request.get_json()
        if not envelope:
            logger.warning("No se recibió notificación válida")
            return {'error': 'No se recibió notificación válida'}, 400
        
        # Extraer datos del evento (soporte para Eventarc y Pub/Sub)
        event_data = _extract_event_data(envelope)
        bucket_name = event_data.get('bucket')
        file_name = event_data.get('name')
        
        # Verificar que sea archivo JSON
        if not file_name or not file_name.endswith('.json'):
            logger.info(f"Archivo ignorado (no JSON): {file_name}")
            return {'message': f'Archivo {file_name} no es JSON'}, 200
        
        logger.info(f"🚀 INICIANDO PROCESAMIENTO: {file_name} en bucket {bucket_name}")
        
        # Paso 2: Leer archivo del bucket origen
        json_data = storage_service.read_json_file(bucket_name, file_name)
        envios = json_data.get('envios', [])
        
        logger.info(f"📊 Archivo cargado: {len(envios)} envíos encontrados")
        
        # Paso 3: Validación de parámetros y necesidad de división
        necesita_division = len(envios) > config.MAX_ENVIOS
        logger.info(f"🔍 División necesaria: {'SÍ' if necesita_division else 'NO'} (límite: {config.MAX_ENVIOS})")
        
        # Paso 3.1: Buscar rutas de imágenes en la base de datos
        logger.info("🗄️  Buscando rutas de imágenes en base de datos...")
        rutas_imagenes = database_service.obtener_rutas_imagenes_por_envios(envios)
        
        total_rutas = sum(len(rutas) for rutas in rutas_imagenes.values())
        envios_con_imagenes = len(rutas_imagenes)
        logger.info(f"✅ Búsqueda completada: {total_rutas} rutas encontradas para {envios_con_imagenes} envíos")
        
        # Procesar y dividir archivos si es necesario
        json_data['nombre_archivo'] = file_name
        archivos_procesados = json_processor.dividir_envios_con_imagenes(
            json_data, config.MAX_ENVIOS, rutas_imagenes
        )
        
        logger.info(f"📁 Archivos generados: {len(archivos_procesados)}")
        
        # Paso 4: Mover archivos procesados al bucket destino
        archivos_movidos = []
        
        for i, archivo_procesado in enumerate(archivos_procesados):
            # Generar nombre para archivo procesado
            nombre_destino = _generar_nombre_archivo_destino(file_name, i, len(archivos_procesados))
            
            # Mover archivo al bucket procesado
            archivo_path = storage_service.mover_archivo_procesado(
                file_name if i == 0 else None,  # Solo eliminar original en primera iteración
                archivo_procesado,
                nombre_destino
            )
            
            archivos_movidos.append(archivo_path)
            
            # Publicar mensaje para procesamiento de imágenes
            metadatos = archivo_procesado.get('metadatos', {})
            pubsub_service.publicar_mensaje_procesamiento(
                archivo_path,
                archivo_procesado['stats_imagenes'],
                metadatos
            )
            
            logger.info(f"✅ Procesado: {nombre_destino}")
        
        # Limpiar archivo original si no se eliminó antes
        if len(archivos_procesados) == 1:
            storage_service.eliminar_archivo_original(bucket_name, file_name)
        
        # Obtener estadísticas del primer archivo procesado
        stats_imagenes = archivos_procesados[0].get('stats_imagenes', {}) if archivos_procesados else {}
        
        resultado = {
            'status': 'success',
            'archivo_original': file_name,
            'archivos_generados': len(archivos_procesados),
            'archivos_procesados': archivos_movidos,
            'stats_imagenes': stats_imagenes,
            'necesito_division': necesita_division,
            'timestamp': datetime.now().isoformat()
        }
        
        logger.info(f"🎉 PROCESAMIENTO COMPLETADO: {file_name}")
        return resultado, 200
        
    except Exception as e:
        logger.error(f"❌ ERROR procesando archivo: {str(e)}")
        return {'error': str(e)}, 500


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint para Cloud Run"""
    return {
        'status': 'healthy',
        'service': 'shipments-json-splitter',
        'version': config.APP_VERSION,
        'timestamp': datetime.now().isoformat()
    }, 200


@app.route('/status', methods=['GET'])
def status():
    """Status endpoint con información de configuración"""
    return {
        'service': 'shipments-json-splitter',
        'version': config.APP_VERSION,
        'environment': config.FLASK_ENV,
        'max_envios': config.MAX_ENVIOS,
        'bucket_origen': config.BUCKET_ORIGEN,
        'bucket_procesado': config.BUCKET_PROCESADO,
        'timestamp': datetime.now().isoformat()
    }, 200


@app.route('/db/status', methods=['GET'])
def database_status():
    """Endpoint para verificar estado de la base de datos"""
    try:
        # Verificar conectividad
        conectividad = database_service.verificar_conectividad()
        
        # Validar estructura de tabla
        estructura = database_service.validar_estructura_tabla()
        
        # Obtener estadísticas básicas
        estadisticas = database_service.obtener_estadisticas_tabla() if conectividad else {}
        
        return {
            'conectividad': conectividad,
            'estructura_tabla': estructura,
            'estadisticas': estadisticas,
            'timestamp': datetime.now().isoformat()
        }, 200
        
    except Exception as e:
        logger.error(f"❌ Error verificando estado de BD: {str(e)}")
        return {
            'conectividad': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }, 500


def _extract_event_data(envelope):
    """Extrae datos del evento desde diferentes formatos"""
    # Formato Pub/Sub
    if 'message' in envelope:
        pubsub_message = envelope['message']
        event_data = json.loads(base64.b64decode(pubsub_message['data']).decode())
    # Formato directo Eventarc
    elif 'bucket' in envelope and 'name' in envelope:
        event_data = envelope
    # Formato CloudEvent (Eventarc v2)
    elif 'data' in envelope:
        event_data = envelope['data']
    else:
        # Fallback: usar el envelope completo
        event_data = envelope
    
    return event_data


def _calcular_stats_validacion(validaciones_imagenes):
    """Calcula estadísticas de validación de imágenes"""
    return {
        'total': len(validaciones_imagenes),
        'validas': len([v for v in validaciones_imagenes if v['valida']]),
        'invalidas': len([v for v in validaciones_imagenes if not v['valida']])
    }


def _generar_nombre_archivo_destino(file_name, indice, total):
    """Genera nombre para archivo de destino"""
    base_name = file_name.replace('.json', '')
    if total > 1:
        return f"{base_name}_parte_{indice+1}_de_{total}.json"
    else:
        return f"{base_name}_procesado.json"


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    logger.info(f"🚀 Iniciando aplicación en puerto {port}")
    logger.info(f"🔧 Modo debug: {debug}")
    logger.info(f"📁 Bucket origen: {config.BUCKET_ORIGEN}")
    logger.info(f"📁 Bucket procesado: {config.BUCKET_PROCESADO}")
    
    app.run(host='0.0.0.0', port=port, debug=debug)
