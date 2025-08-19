# 🧪 Test Suite - Shipments Processing Platform

Esta suite de tests proporciona cobertura completa para validar todo el flujo desde la carga del JSON hasta el envío del email con URLs firmadas.

## 📋 Estructura de Tests

```
tests/
├── conftest.py                     # Configuración global y fixtures
├── unit/                          # Tests unitarios por servicio
│   ├── test_division_service.py   # Tests del Division Service
│   ├── test_image_processing_service.py # Tests del Image Processing Service
│   └── test_email_service.py      # Tests del Email Service
├── integration/                   # Tests de integración
│   └── test_end_to_end_flow.py   # Tests end-to-end completos
└── README.md                     # Esta documentación
```

## 🎯 Tipos de Tests

### Unit Tests (Pruebas Unitarias)
- **Division Service**: Valida división de JSON, validación de archivos, manejo de eventos
- **Image Processing Service**: Valida procesamiento de imágenes, creación de ZIPs, URLs firmadas
- **Email Service**: Valida envío de emails, templates, notificaciones

### Integration Tests (Pruebas de Integración)
- **End-to-End Flow**: Valida el flujo completo desde JSON hasta email
- **Error Scenarios**: Manejo de errores y recuperación
- **Performance Tests**: Verificación de tiempos de respuesta

## 🚀 Ejecución de Tests

### Usando el script de automatización:

```bash
# Hacer ejecutable el script
chmod +x run-tests.sh

# Ejecutar todos los tests
./run-tests.sh all

# Ejecutar tests unitarios únicamente
./run-tests.sh unit

# Ejecutar tests de integración
./run-tests.sh integration

# Ejecutar tests end-to-end
./run-tests.sh e2e

# Ejecutar con cobertura y en paralelo
./run-tests.sh all --coverage --parallel

# Ejecutar tests específicos con marcadores
./run-tests.sh --marker "email"
```

### Usando pytest directamente:

```bash
# Todos los tests
pytest tests/ -v

# Tests unitarios solamente
pytest tests/unit/ -v

# Tests end-to-end con output detallado
pytest tests/integration/test_end_to_end_flow.py -v -s

# Tests con cobertura
pytest tests/ --cov=services --cov-report=html

# Tests en paralelo
pytest tests/ -n auto
```

## 🏷️ Marcadores de Tests

Los tests están categorizados con marcadores para facilitar la ejecución selectiva:

- `unit`: Tests unitarios
- `integration`: Tests de integración  
- `e2e`: Tests end-to-end
- `smoke`: Tests de smoke rápidos
- `slow`: Tests que tardan más de 5 segundos
- `performance`: Tests de rendimiento
- `database`: Tests que requieren base de datos
- `storage`: Tests que requieren cloud storage
- `email`: Tests que requieren funcionalidad de email

## 📊 Cobertura de Tests

### Division Service
- ✅ Health check endpoints
- ✅ Procesamiento de archivos JSON
- ✅ Validación de estructura de archivos
- ✅ División en paquetes
- ✅ Manejo de errores y Pub/Sub
- ✅ Consulta de estado de procesamiento

### Image Processing Service
- ✅ Health check endpoints
- ✅ Procesamiento de paquetes de imágenes
- ✅ Descarga y agrupación de imágenes
- ✅ Creación de archivos ZIP
- ✅ Generación de URLs firmadas
- ✅ Programación y ejecución de limpieza
- ✅ Manejo de errores

### Email Service
- ✅ Health check endpoints
- ✅ Envío de emails de completitud
- ✅ Notificaciones de error
- ✅ Emails personalizados
- ✅ Gestión de templates
- ✅ Estadísticas de envío
- ✅ Manejo de mensajes Pub/Sub

### End-to-End Flow
- ✅ Flujo completo de procesamiento
- ✅ Procesamiento en paralelo
- ✅ Manejo de errores y recuperación
- ✅ Escenarios de éxito parcial
- ✅ Orquestación con Cloud Workflows
- ✅ Verificación de URLs firmadas
- ✅ Validación de emails enviados

## 🔧 Configuración de Testing

### Variables de Entorno
Los tests utilizan las siguientes variables de entorno:

```bash
TESTING=true
GCP_PROJECT_ID=test-project
GCS_BUCKET=test-bucket
DB_HOST=localhost
DB_NAME=test_db
SMTP_HOST=smtp.test.com
```

### Mocks y Fixtures
- **Storage Mock**: Simula operaciones de Google Cloud Storage
- **Database Mock**: Simula conexiones y operaciones de PostgreSQL
- **SMTP Mock**: Simula servidor de email
- **Pub/Sub Mock**: Simula mensajería
- **Workflow Mock**: Simula ejecuciones de Cloud Workflows

## 📈 Métricas y Reportes

### Coverage Report
Después de ejecutar tests con cobertura, se genera:
- **HTML Report**: `htmlcov/index.html`
- **Terminal Report**: Mostrado en consola
- **Objetivo**: Mínimo 85% de cobertura

### Performance Metrics
Los tests de rendimiento validan:
- **División**: < 5 segundos
- **Procesamiento de imágenes**: < 30 segundos  
- **Envío de email**: < 5 segundos
- **Flujo completo**: < 45 segundos

## 🛠️ Troubleshooting

### Errores Comunes

**ImportError en módulos de servicios:**
```bash
# Asegurar que PYTHONPATH incluye shared_utils
export PYTHONPATH="${PYTHONPATH}:$(pwd)/services/shared_utils/src"
```

**Tests fallan por dependencias:**
```bash
# Instalar dependencias de testing
pip install pytest pytest-cov pytest-xdist pytest-asyncio
```

**Problemas con tests async:**
```bash
# Verificar configuración en pytest.ini
asyncio_mode = auto
```

### Debug de Tests

Para debuggear tests específicos:
```bash
# Ejecutar test individual con output completo
pytest tests/unit/test_division_service.py::TestProcessFileEndpoint::test_process_file_success -v -s

# Ejecutar con breakpoints
pytest tests/unit/test_division_service.py -v -s --pdb

# Ver logs detallados
pytest tests/ -v -s --log-cli-level=DEBUG
```

## 📝 Mejores Prácticas

### Escritura de Tests
1. **Nombres descriptivos**: `test_process_file_with_valid_json_succeeds`
2. **Arrange-Act-Assert**: Estructura clara en 3 secciones
3. **Un concepto por test**: Cada test valida un escenario específico
4. **Mocks apropiados**: Mock solo dependencias externas
5. **Fixtures reutilizables**: Compartir setup común

### Organización
1. **Agrupar por funcionalidad**: Usar clases para agrupar tests relacionados
2. **Marcadores consistentes**: Usar markers para categorizar
3. **Fixtures específicas**: Crear fixtures por contexto de uso
4. **Documentación**: Docstrings explicando qué valida cada test

### Performance
1. **Paralelo para suites grandes**: Usar `pytest-xdist` para tests independientes
2. **Fixtures con scope**: `session`, `module`, `class` para setup costoso
3. **Mocks ligeros**: Evitar lógica compleja en mocks
4. **Cleanup apropiado**: Limpiar recursos después de tests

## 🔄 CI/CD Integration

Los tests están diseñados para integrarse con pipelines de CI/CD:

```yaml
# Ejemplo para GitHub Actions
- name: Run Tests
  run: |
    ./run-tests.sh all --coverage --parallel
    
- name: Upload Coverage
  uses: codecov/codecov-action@v1
  with:
    file: ./coverage.xml
```

## 📚 Recursos Adicionales

- [Pytest Documentation](https://docs.pytest.org/)
- [Google Cloud Testing](https://cloud.google.com/docs/testing)
- [Python Mock Library](https://docs.python.org/3/library/unittest.mock.html)
- [Async Testing](https://pytest-asyncio.readthedocs.io/)

---

**Nota**: Esta suite de tests asegura que el Shipments Processing Platform funciona correctamente desde la carga del JSON hasta la entrega del email con URLs firmadas, cubriendo todos los escenarios de éxito y error en una arquitectura empresarial robusta.
