# Cloud Run con Python para Monitorear Bucket GCP

## Análisis de Arquitectura y Decisiones de Diseño

### ¿Por qué Cloud Run y no Cloud Functions?

**Ventajas de Cloud Run:**
- **Flexibilidad**: Puedes manejar múltiples endpoints y lógica compleja
- **Timeout**: Hasta 60 minutos vs 9 minutos en Cloud Functions
- **Memoria**: Hasta 8GB vs 8GB (similar, pero más control)
- **Concurrencia**: Mejor manejo de múltiples requests simultáneos
- **Debugging**: Más fácil para desarrollo y testing

**Cuándo usar Cloud Functions:**
- Procesamiento simple y rápido
- Eventos específicos (Pub/Sub, HTTP trigger)
- Funciones stateless pequeñas

### Evaluación de tu Flujo Propuesto

Tu flujo es **MÁS EFICIENTE** que mi propuesta inicial. Analicemos:

## 1. Estructura del Proyecto

```
proyecto/
├── main.py
├── requirements.txt
├── Dockerfile
├── config.py
└── utils/
    ├── bucket_manager.py
    ├── image_validator.py
    └── file_processor.py
```

## 2. Tu Flujo Optimizado - Implementación

### Ventajas de tu enfoque:
1. **Trigger directo**: Más eficiente que webhook Pub/Sub
2. **Validación previa de imágenes**: Evita procesar archivos inválidos
3. **Gestión de buckets**: Organización clara y limpieza automática
4. **Menos componentes**: Reduce latencia y puntos de falla

### Código Python Optimizado (main.py)

```python
import json
import os
import base64
from flask import Flask, request
from google.cloud import storage
from google.cloud import pubsub_v1
import requests
import math
import logging
from datetime import datetime

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuración
BUCKET_ORIGEN = os.environ.get('BUCKET_ORIGEN', 'archivos-json-origen')
BUCKET_PROCESADO = os.environ.get('BUCKET_PROCESADO', 'archivos-procesados')
MAX_ENVIOS = int(os.environ.get('MAX_ENVIOS', 100))
PUBSUB_TOPIC = os.environ.get('PUBSUB_TOPIC', 'procesar-imagenes')

# Clientes GCP
storage_client = storage.Client()
publisher = pubsub_v1.PublisherClient()

class ImageValidator:
    """Clase para validar existencia y accesibilidad de imágenes"""
    
    @staticmethod
    def validar_url_imagen(url):
        """Valida si la URL de imagen es accesible"""
        try:
            response = requests.head(url, timeout=5)
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '')
                return content_type.startswith('image/')
            return False
        except:
            return False
    
    @staticmethod
    def validar_rutas_imagenes(envios):
        """Valida todas las rutas de imágenes en los envíos"""
        resultados = []
        
        for i, envio in enumerate(envios):
            ruta_imagen = envio.get('imagen_url') or envio.get('url_imagen') or envio.get('imagen')
            
            if not ruta_imagen:
                logger.warning(f"Envío {i+1} sin URL de imagen")
                resultados.append({
                    'indice': i,
                    'url': None,
                    'valida': False,
                    'error': 'URL no encontrada'
                })
                continue
            
            # Validar URL
            es_valida = ImageValidator.validar_url_imagen(ruta_imagen)
            resultados.append({
                'indice': i,
                'url': ruta_imagen,
                'valida': es_valida,
                'error': None if es_valida else 'URL no accesible'
            })
        
        return resultados

class FileProcessor:
    """Clase para procesar y dividir archivos JSON"""
    
    @staticmethod
    def dividir_envios_con_imagenes(data, max_envios, validaciones_imagenes):
        """Divide el JSON incluyendo información de validación de imágenes"""
        envios = data.get('envios', [])
        
        if len(envios) <= max_envios:
            # Agregar info de imágenes al archivo único
            data['validacion_imagenes'] = validaciones_imagenes
            data['stats_imagenes'] = {
                'total': len(validaciones_imagenes),
                'validas': len([v for v in validaciones_imagenes if v['valida']]),
                'invalidas': len([v for v in validaciones_imagenes if not v['valida']])
            }
            return [data]
        
        # Dividir en múltiples archivos
        num_archivos = math.ceil(len(envios) / max_envios)
        archivos_divididos = []
        
        for i in range(num_archivos):
            inicio = i * max_envios
            fin = min((i + 1) * max_envios, len(envios))
            
            # Crear nuevo archivo
            nuevo_archivo = data.copy()
            nuevo_archivo['envios'] = envios[inicio:fin]
            
            # Información de división
            nuevo_archivo['metadatos'] = {
                'parte': i + 1,
                'total_partes': num_archivos,
                'archivo_original': data.get('nombre_archivo', 'original'),
                'fecha_procesamiento': datetime.now().isoformat(),
                'rango_envios': f"{inicio + 1}-{fin}"
            }
            
            # Validaciones de imágenes para esta parte
            validaciones_parte = validaciones_imagenes[inicio:fin]
            nuevo_archivo['validacion_imagenes'] = validaciones_parte
            nuevo_archivo['stats_imagenes'] = {
                'total': len(validaciones_parte),
                'validas': len([v for v in validaciones_parte if v['valida']]),
                'invalidas': len([v for v in validaciones_parte if not v['valida']])
            }
            
            archivos_divididos.append(nuevo_archivo)
        
        return archivos_divididos

class BucketManager:
    """Clase para gestión de buckets"""
    
    @staticmethod
    def mover_archivo_procesado(archivo_original, contenido_procesado, nombre_destino):
        """Mueve archivo procesado al bucket destino y elimina original"""
        try:
            # Subir archivo procesado
            bucket_destino = storage_client.bucket(BUCKET_PROCESADO)
            blob_destino = bucket_destino.blob(f"procesados/{nombre_destino}")
            blob_destino.upload_from_string(
                json.dumps(contenido_procesado, indent=2, ensure_ascii=False)
            )
            
            # Eliminar archivo original
            bucket_origen = storage_client.bucket(BUCKET_ORIGEN)
            blob_original = bucket_origen.blob(archivo_original)
            blob_original.delete()
            
            logger.info(f"Archivo movido: {archivo_original} → procesados/{nombre_destino}")
            return f"gs://{BUCKET_PROCESADO}/procesados/{nombre_destino}"
            
        except Exception as e:
            logger.error(f"Error moviendo archivo: {str(e)}")
            raise

def publicar_mensaje_procesamiento(archivo_path, stats_imagenes, metadatos=None):
    """Publica mensaje a Pub/Sub para procesamiento de imágenes"""
    try:
        topic_path = publisher.topic_path(os.environ.get('PROJECT_ID'), PUBSUB_TOPIC)
        
        mensaje = {
            'archivo_path': archivo_path,
            'stats_imagenes': stats_imagenes,
            'metadatos': metadatos,
            'timestamp': datetime.now().isoformat(),
            'accion': 'procesar_imagenes'
        }
        
        data = json.dumps(mensaje).encode('utf-8')
        future = publisher.publish(topic_path, data)
        message_id = future.result()
        
        logger.info(f"Mensaje publicado: {message_id}")
        return message_id
        
    except Exception as e:
        logger.error(f"Error publicando mensaje: {str(e)}")
        raise

# ESTE ES EL FLUJO QUE PROPONES - TRIGGER DIRECTO
@app.route('/', methods=['POST'])
def procesar_archivo_bucket():
    """
    Endpoint principal que recibe triggers directos de Cloud Storage
    Implementa tu flujo: Bucket → Trigger → Validación → División → Movimiento
    """
    
    try:
        # Paso 1: Recibir notificación del bucket
        envelope = request.get_json()
        if not envelope:
            return 'No se recibió notificación válida', 400
        
        # Extraer datos del evento
        if 'message' in envelope:  # Pub/Sub format
            pubsub_message = envelope['message']
            event_data = json.loads(base64.b64decode(pubsub_message['data']).decode())
        else:  # Direct HTTP trigger format
            event_data = envelope
        
        bucket_name = event_data.get('bucketId') or event_data.get('bucket')
        file_name = event_data.get('name') or event_data.get('object')
        
        # Verificar que sea archivo JSON
        if not file_name or not file_name.endswith('.json'):
            logger.info(f"Archivo ignorado (no JSON): {file_name}")
            return f'Archivo {file_name} no es JSON', 200
        
        logger.info(f"🚀 INICIANDO PROCESAMIENTO: {file_name}")
        
        # Paso 2: Leer archivo del bucket origen
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_name)
        contenido = blob.download_as_text()
        json_data = json.loads(contenido)
        
        envios = json_data.get('envios', [])
        logger.info(f"📊 Archivo cargado: {len(envios)} envíos encontrados")
        
        # Paso 3: Validación de parámetros y necesidad de división
        necesita_division = len(envios) > MAX_ENVIOS
        logger.info(f"🔍 División necesaria: {'SÍ' if necesita_division else 'NO'} (límite: {MAX_ENVIOS})")
        
        # Paso 3.1: Validar rutas de imágenes
        logger.info("🖼️  Validando URLs de imágenes...")
        validaciones_imagenes = ImageValidator.validar_rutas_imagenes(envios)
        
        stats_validacion = {
            'total': len(validaciones_imagenes),
            'validas': len([v for v in validaciones_imagenes if v['valida']]),
            'invalidas': len([v for v in validaciones_imagenes if not v['valida']])
        }
        
        logger.info(f"✅ Validación completada: {stats_validacion['validas']}/{stats_validacion['total']} imágenes válidas")
        
        # Procesar y dividir archivos si es necesario
        json_data['nombre_archivo'] = file_name
        archivos_procesados = FileProcessor.dividir_envios_con_imagenes(
            json_data, MAX_ENVIOS, validaciones_imagenes
        )
        
        logger.info(f"📁 Archivos generados: {len(archivos_procesados)}")
        
        # Paso 4: Mover archivos procesados al bucket destino
        archivos_movidos = []
        
        for i, archivo_procesado in enumerate(archivos_procesados):
            # Generar nombre para archivo procesado
            base_name = file_name.replace('.json', '')
            if len(archivos_procesados) > 1:
                nombre_destino = f"{base_name}_parte_{i+1}_de_{len(archivos_procesados)}.json"
            else:
                nombre_destino = f"{base_name}_procesado.json"
            
            # Mover archivo al bucket procesado
            archivo_path = BucketManager.mover_archivo_procesado(
                file_name if i == 0 else None,  # Solo eliminar original en primera iteración
                archivo_procesado,
                nombre_destino
            )
            
            archivos_movidos.append(archivo_path)
            
            # Publicar mensaje para procesamiento de imágenes
            metadatos = archivo_procesado.get('metadatos', {})
            publicar_mensaje_procesamiento(
                archivo_path,
                archivo_procesado['stats_imagenes'],
                metadatos
            )
            
            logger.info(f"✅ Procesado: {nombre_destino}")
        
        # Eliminar archivo original (si no se eliminó antes)
        if len(archivos_procesados) == 1:
            try:
                blob.delete()
                logger.info(f"🗑️  Archivo original eliminado: {file_name}")
            except:
                logger.warning("Archivo original ya fue eliminado")
        
        resultado = {
            'status': 'success',
            'archivo_original': file_name,
            'archivos_generados': len(archivos_procesados),
            'archivos_procesados': archivos_movidos,
            'stats_imagenes': stats_validacion,
            'necesito_division': necesita_division
        }
        
        logger.info(f"🎉 PROCESAMIENTO COMPLETADO: {file_name}")
        return resultado, 200
        
    except Exception as e:
        logger.error(f"❌ ERROR procesando archivo: {str(e)}")
        return {'error': str(e)}, 500

@app.route('/health', methods=['GET'])
def health_check():
    return {'status': 'healthy', 'service': 'bucket-processor'}, 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
```
```

## 3. Requirements.txt Actualizado

```
flask==2.3.3
google-cloud-storage==2.10.0
google-cloud-pubsub==2.18.4
requests==2.31.0
Pillow==10.0.1
```

## 4. Análisis de tu Flujo vs Mi Propuesta Original

### 🎯 Tu Flujo (RECOMENDADO)
```
Bucket → Trigger Directo → Cloud Run → Validación → División → Bucket Destino → Pub/Sub
```

**✅ Ventajas:**
- **Más eficiente**: Menos saltos entre servicios
- **Validación previa**: Evita procesar imágenes inexistentes
- **Gestión limpia**: Buckets separados + eliminación automática
- **Mejor trazabilidad**: Metadatos de procesamiento
- **Menos latencia**: Trigger directo vs webhook

### 🔄 Mi Propuesta Original
```
Bucket → Pub/Sub → Webhook → Cloud Run → Pub/Sub → Cloud Function
```

**❌ Desventajas:**
- **Más complejo**: Doble Pub/Sub innecesario
- **Mayor latencia**: Múltiples saltos
- **Sin validación previa**: Procesa archivos que pueden fallar
- **Menos organizado**: Todo en el mismo bucket

## 5. Configuración del Trigger Directo (Tu Flujo)

### Opción 1: Eventarc (Recomendado)
```bash
# Crear trigger directo desde Cloud Storage
gcloud eventarc triggers create bucket-processor-trigger \
  --location=us-central1 \
  --destination-run-service=bucket-processor \
  --destination-run-region=us-central1 \
  --event-filters="type=google.cloud.storage.object.v1.finalized" \
  --event-filters="bucket=${BUCKET_ORIGEN}" \
  --service-account=bucket-processor@${PROJECT_ID}.iam.gserviceaccount.com
```

### Opción 2: Cloud Storage Notification (Alternativa)
```bash
# Si prefieres Pub/Sub pero más directo
gcloud pubsub topics create storage-notifications

gcloud eventarc triggers create storage-direct \
  --location=us-central1 \
  --destination-run-service=bucket-processor \
  --destination-run-region=us-central1 \
  --transport-topic=storage-notifications \
  --event-filters="type=google.cloud.storage.object.v1.finalized"
```

## 4. Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["python", "main.py"]
```

## 5. Deploy a Cloud Run

### Paso 1: Construir imagen
```bash
# Configurar proyecto
gcloud config set project TU-PROJECT-ID

# Construir imagen
gcloud builds submit --tag gcr.io/TU-PROJECT-ID/bucket-processor

# O usando Cloud Build
docker build -t gcr.io/TU-PROJECT-ID/bucket-processor .
docker push gcr.io/TU-PROJECT-ID/bucket-processor
```

### Paso 2: Deploy Cloud Run
```bash
gcloud run deploy bucket-processor \
  --image gcr.io/TU-PROJECT-ID/bucket-processor \
  --platform managed \
  --region us-central1 \
  --set-env-vars BUCKET_NAME=tu-bucket-name,MAX_ENVIOS=50,PUBSUB_TOPIC=procesar-imagenes \
  --allow-unauthenticated
```

## 6. Configurar Notificaciones del Bucket

### Crear notificación Pub/Sub
```bash
# Crear tópico
gcloud pubsub topics create bucket-notifications

# Crear suscripción push hacia Cloud Run
gcloud pubsub subscriptions create bucket-processor-sub \
  --topic=bucket-notifications \
  --push-endpoint=https://TU-CLOUD-RUN-URL/webhook

# Configurar notificaciones del bucket
gsutil notification create -t bucket-notifications -f json gs://tu-bucket-name
```

## 7. Permisos Necesarios

### Service Account para Cloud Run
```bash
# Crear service account
gcloud iam service-accounts create bucket-processor

# Asignar permisos
gcloud projects add-iam-policy-binding TU-PROJECT-ID \
  --member="serviceAccount:bucket-processor@TU-PROJECT-ID.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"

gcloud projects add-iam-policy-binding TU-PROJECT-ID \
  --member="serviceAccount:bucket-processor@TU-PROJECT-ID.iam.gserviceaccount.com" \
  --role="roles/pubsub.publisher"
```

## 8. Configuración Cloud Function (Contexto)

Para complementar tu flujo con la Cloud Function que procese las imágenes:

```python
# cloud_function_main.py
import base64
import json
from google.cloud import storage
import zipfile
from PIL import Image
import io

def procesar_imagenes(event, context):
    """Cloud Function triggered por Pub/Sub"""
    
    # Decodificar mensaje
    pubsub_message = base64.b64decode(event['data']).decode('utf-8')
    mensaje = json.loads(pubsub_message)
    
    archivo_path = mensaje['archivo_path']
    num_envios = mensaje['num_envios']
    
    # Leer archivo JSON dividido
    # Procesar imágenes según los envíos
    # Comprimir y guardar resultado
    
    print(f"Procesando {num_envios} envíos desde {archivo_path}")
```

## 9. Variables de Entorno Importantes

- `BUCKET_NAME`: Nombre del bucket a monitorear
- `MAX_ENVIOS`: Número máximo de envíos por archivo (N parámetro)
- `PUBSUB_TOPIC`: Tópico donde publicar para procesamiento posterior
- `PORT`: Puerto donde corre la aplicación (8080 por defecto)

## 10. Testing Local

```bash
# Instalar dependencias
pip install -r requirements.txt

# Configurar autenticación
export GOOGLE_APPLICATION_CREDENTIALS="path/to/service-account.json"

# Variables de entorno
export BUCKET_NAME="tu-bucket"
export MAX_ENVIOS="100"
export PUBSUB_TOPIC="procesar-imagenes"

# Ejecutar
python main.py
```

## Flujo Completo

1. **Archivo JSON llega al bucket** → Trigger notificación
2. **Cloud Run recibe webhook** → Procesa archivo JSON
3. **Si envíos > N** → Divide en múltiples archivos
4. **Publica mensaje Pub/Sub** → Para cada archivo procesado
5. **Cloud Function recibe mensaje** → Descarga y comprime imágenes