"""
Configuración de logging estructurado para la aplicación
Implementa logging con formato JSON para Cloud Logging siguiendo Clean Architecture
"""

import logging
import sys
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional


class JsonFormatter(logging.Formatter):
    """
    Formatter personalizado que convierte logs a formato JSON
    Compatible con Google Cloud Logging
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Formatea un registro de log como JSON
        
        Args:
            record: Registro de log a formatear
            
        Returns:
            str: Log formateado como JSON
        """
        # Datos básicos del log
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'severity': record.levelname,
            'message': record.getMessage(),
            'logger': record.name,
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'thread': record.thread,
            'service': os.getenv('APP_NAME', 'shipments-json-splitter'),
            'version': os.getenv('APP_VERSION', '1.0.0'),
            'environment': os.getenv('FLASK_ENV', 'development')
        }
        
        # Agregar información de excepción si existe
        if record.exc_info:
            log_entry['exception'] = {
                'type': record.exc_info[0].__name__ if record.exc_info[0] else None,
                'message': str(record.exc_info[1]) if record.exc_info[1] else None,
                'traceback': self.formatException(record.exc_info)
            }
        
        # Agregar campos personalizados si existen
        if hasattr(record, 'extra_fields'):
            log_entry.update(record.extra_fields)
        
        # Agregar contexto de request si está disponible (Flask)
        try:
            from flask import request, g
            if request:
                log_entry['request'] = {
                    'method': request.method,
                    'url': request.url,
                    'user_agent': request.headers.get('User-Agent'),
                    'remote_addr': request.remote_addr,
                    'request_id': getattr(g, 'request_id', None)
                }
        except (ImportError, RuntimeError):
            # Flask no está disponible o no estamos en contexto de request
            pass
        
        return json.dumps(log_entry, ensure_ascii=False)


class ContextFilter(logging.Filter):
    """
    Filtro que agrega contexto adicional a los logs
    """
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        Agrega contexto adicional al registro de log
        
        Args:
            record: Registro de log
            
        Returns:
            bool: True para permitir el log
        """
        # Agregar información de la aplicación
        record.app_name = os.getenv('APP_NAME', 'shipments-json-splitter')
        record.app_version = os.getenv('APP_VERSION', '1.0.0')
        record.environment = os.getenv('FLASK_ENV', 'development')
        
        return True


def setup_logger(name: str, level: Optional[str] = None, 
                extra_fields: Optional[Dict[str, Any]] = None) -> logging.Logger:
    """
    Configura y retorna un logger con formato estructurado
    
    Args:
        name: Nombre del logger (generalmente __name__)
        level: Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        extra_fields: Campos adicionales para incluir en todos los logs
        
    Returns:
        logging.Logger: Logger configurado
    """
    # Crear logger
    logger = logging.getLogger(name)
    
    # Evitar duplicar handlers si ya está configurado
    if logger.handlers:
        return logger
    
    # Configurar nivel
    log_level = level or os.getenv('LOG_LEVEL', 'INFO')
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Crear handler para stdout
    handler = logging.StreamHandler(sys.stdout)
    
    # Determinar formato basado en el entorno
    environment = os.getenv('FLASK_ENV', 'development').lower()
    
    if environment == 'production' or os.getenv('LOG_FORMAT', '').lower() == 'json':
        # Formato JSON para producción y Cloud Logging
        formatter = JsonFormatter()
    else:
        # Formato legible para desarrollo
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    handler.setFormatter(formatter)
    
    # Agregar filtro de contexto
    context_filter = ContextFilter()
    handler.addFilter(context_filter)
    
    logger.addHandler(handler)
    
    # Agregar campos extra si se proporcionan
    if extra_fields:
        logger = LoggerAdapter(logger, extra_fields)
    
    return logger


class LoggerAdapter(logging.LoggerAdapter):
    """
    Adaptador que permite agregar campos extra a todos los logs
    """
    
    def process(self, msg: str, kwargs: Dict) -> tuple:
        """
        Procesa el mensaje de log agregando campos extra
        
        Args:
            msg: Mensaje de log
            kwargs: Argumentos adicionales
            
        Returns:
            tuple: Mensaje procesado y kwargs actualizados
        """
        # Agregar campos extra al registro
        if 'extra' not in kwargs:
            kwargs['extra'] = {}
        
        kwargs['extra'].update(self.extra)
        kwargs['extra']['extra_fields'] = {**self.extra, **kwargs['extra']}
        
        return msg, kwargs


def log_execution_time(func):
    """
    Decorador para loggear tiempo de ejecución de funciones
    
    Args:
        func: Función a decorar
        
    Returns:
        Función decorada que loggea tiempo de ejecución
    """
    import functools
    import time
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = setup_logger(func.__module__)
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            
            logger.info(
                f"Función {func.__name__} ejecutada exitosamente",
                extra={
                    'function': func.__name__,
                    'execution_time_seconds': round(execution_time, 3),
                    'success': True
                }
            )
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            
            logger.error(
                f"Error ejecutando función {func.__name__}: {str(e)}",
                extra={
                    'function': func.__name__,
                    'execution_time_seconds': round(execution_time, 3),
                    'success': False,
                    'error': str(e)
                }
            )
            raise
    
    return wrapper


def log_api_call(endpoint: str, method: str = 'GET'):
    """
    Decorador para loggear llamadas a API
    
    Args:
        endpoint: Nombre del endpoint
        method: Método HTTP
        
    Returns:
        Decorador para funciones de API
    """
    def decorator(func):
        import functools
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger = setup_logger(func.__module__)
            
            logger.info(
                f"API call iniciada: {method} {endpoint}",
                extra={
                    'api_endpoint': endpoint,
                    'http_method': method,
                    'function': func.__name__
                }
            )
            
            try:
                result = func(*args, **kwargs)
                
                logger.info(
                    f"API call completada: {method} {endpoint}",
                    extra={
                        'api_endpoint': endpoint,
                        'http_method': method,
                        'function': func.__name__,
                        'success': True
                    }
                )
                
                return result
                
            except Exception as e:
                logger.error(
                    f"API call falló: {method} {endpoint} - {str(e)}",
                    extra={
                        'api_endpoint': endpoint,
                        'http_method': method,
                        'function': func.__name__,
                        'success': False,
                        'error': str(e)
                    }
                )
                raise
        
        return wrapper
    return decorator


def configure_root_logger():
    """
    Configura el logger raíz de la aplicación
    """
    root_logger = logging.getLogger()
    
    # Limpiar handlers existentes
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Configurar nivel base
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Configurar handler
    handler = logging.StreamHandler(sys.stdout)
    
    # Formato según el entorno
    environment = os.getenv('FLASK_ENV', 'development').lower()
    
    if environment == 'production' or os.getenv('LOG_FORMAT', '').lower() == 'json':
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    handler.setFormatter(formatter)
    handler.addFilter(ContextFilter())
    
    root_logger.addHandler(handler)
    
    # Configurar loggers de terceros
    logging.getLogger('google').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)


# Configurar logger raíz al importar el módulo
configure_root_logger()
