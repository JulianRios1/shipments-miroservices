"""
Sistema de logging estructurado compartido para todos los servicios
Implementa logging consistente con contexto y trazabilidad
"""

import logging
import sys
import json
from typing import Any, Dict, Optional
from datetime import datetime
from pythonjsonlogger import jsonlogger


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """
    Formateador JSON personalizado para logs estructurados
    """
    
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]):
        """
        Añade campos personalizados al log record
        """
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        
        # Añadir timestamp ISO
        if not log_record.get('timestamp'):
            log_record['timestamp'] = datetime.utcnow().isoformat()
        
        # Añadir información del servicio
        log_record['service'] = getattr(record, 'service', 'unknown-service')
        log_record['version'] = getattr(record, 'version', '1.0.0')
        
        # Añadir información de contexto si existe
        if hasattr(record, 'context'):
            log_record['context'] = record.context
        
        # Añadir trace ID si existe (para trazabilidad)
        if hasattr(record, 'trace_id'):
            log_record['trace_id'] = record.trace_id
        
        # Añadir user ID si existe
        if hasattr(record, 'user_id'):
            log_record['user_id'] = record.user_id


class StructuredLogger:
    """
    Logger estructurado con contexto y trazabilidad
    """
    
    def __init__(self, name: str, service_name: str = 'unknown-service', version: str = '1.0.0'):
        self.logger = logging.getLogger(name)
        self.service_name = service_name
        self.version = version
        self._setup_logger()
    
    def _setup_logger(self):
        """
        Configura el logger con formateo estructurado
        """
        # Evitar configurar múltiples veces
        if self.logger.handlers:
            return
        
        # Configurar nivel de logging
        log_level = logging.INFO
        if hasattr(logging, 'INFO'):  # Verificar que INFO existe
            try:
                from config import config
                log_level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
            except ImportError:
                log_level = logging.INFO
        
        self.logger.setLevel(log_level)
        
        # Crear handler para stdout
        handler = logging.StreamHandler(sys.stdout)
        
        # Configurar formateador JSON
        formatter = CustomJsonFormatter(
            '%(timestamp)s %(level)s %(name)s %(message)s %(service)s %(version)s'
        )
        
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        
        # Prevenir propagación a loggers padre
        self.logger.propagate = False
    
    def _log_with_context(self, level: int, msg: str, context: Optional[Dict[str, Any]] = None, 
                         trace_id: Optional[str] = None, user_id: Optional[str] = None):
        """
        Registra mensaje con contexto estructurado
        """
        extra = {
            'service': self.service_name,
            'version': self.version
        }
        
        if context:
            extra['context'] = context
        
        if trace_id:
            extra['trace_id'] = trace_id
        
        if user_id:
            extra['user_id'] = user_id
        
        self.logger.log(level, msg, extra=extra)
    
    def debug(self, msg: str, context: Optional[Dict[str, Any]] = None, 
             trace_id: Optional[str] = None, user_id: Optional[str] = None):
        """Log debug message"""
        self._log_with_context(logging.DEBUG, f"🔍 {msg}", context, trace_id, user_id)
    
    def info(self, msg: str, context: Optional[Dict[str, Any]] = None,
            trace_id: Optional[str] = None, user_id: Optional[str] = None):
        """Log info message"""
        self._log_with_context(logging.INFO, f"ℹ️ {msg}", context, trace_id, user_id)
    
    def warning(self, msg: str, context: Optional[Dict[str, Any]] = None,
               trace_id: Optional[str] = None, user_id: Optional[str] = None):
        """Log warning message"""
        self._log_with_context(logging.WARNING, f"⚠️ {msg}", context, trace_id, user_id)
    
    def error(self, msg: str, context: Optional[Dict[str, Any]] = None,
             trace_id: Optional[str] = None, user_id: Optional[str] = None, exc_info: bool = False):
        """Log error message"""
        if exc_info:
            # Capturar información de excepción
            import traceback
            context = context or {}
            context['exception'] = traceback.format_exc()
        
        self._log_with_context(logging.ERROR, f"❌ {msg}", context, trace_id, user_id)
    
    def critical(self, msg: str, context: Optional[Dict[str, Any]] = None,
                trace_id: Optional[str] = None, user_id: Optional[str] = None):
        """Log critical message"""
        self._log_with_context(logging.CRITICAL, f"🚨 {msg}", context, trace_id, user_id)
    
    def success(self, msg: str, context: Optional[Dict[str, Any]] = None,
               trace_id: Optional[str] = None, user_id: Optional[str] = None):
        """Log success message (info level)"""
        self._log_with_context(logging.INFO, f"✅ {msg}", context, trace_id, user_id)
    
    def processing(self, msg: str, context: Optional[Dict[str, Any]] = None,
                  trace_id: Optional[str] = None, user_id: Optional[str] = None):
        """Log processing message (info level)"""
        self._log_with_context(logging.INFO, f"🔄 {msg}", context, trace_id, user_id)
    
    def performance(self, msg: str, duration: float, context: Optional[Dict[str, Any]] = None,
                   trace_id: Optional[str] = None, user_id: Optional[str] = None):
        """Log performance metrics"""
        perf_context = context or {}
        perf_context['duration_seconds'] = duration
        self._log_with_context(logging.INFO, f"⚡ {msg}", perf_context, trace_id, user_id)


def setup_logger(name: str, service_name: str = 'unknown-service', version: str = '2.0.0') -> StructuredLogger:
    """
    Factory function para crear logger estructurado
    
    Args:
        name: Nombre del logger (usualmente __name__)
        service_name: Nombre del servicio
        version: Versión del servicio
        
    Returns:
        StructuredLogger: Logger configurado
    """
    return StructuredLogger(name, service_name, version)


# Logger global para shared utils
logger = setup_logger(__name__, 'shared-utils', '2.0.0')
