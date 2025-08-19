"""
Template Manager
Gestiona templates de email para diferentes tipos de notificaciones
"""

from datetime import datetime
from typing import Dict, Any, List, Optional
from string import Template

import sys
sys.path.insert(0, '/app/services/shared_utils/src')

from logger import setup_logger
from config import config


class TemplateManager:
    """
    Gestor de templates de email
    """
    
    def __init__(self):
        self.logger = setup_logger(__name__, 'template-manager', config.APP_VERSION)
        self.templates = self._load_templates()
        self.logger.info("✅ Template Manager inicializado")
    
    def _load_templates(self) -> Dict[str, str]:
        """Carga templates de email"""
        return {
            'completion': """
            <html>
            <head>
                <style>
                    body { font-family: Arial, sans-serif; margin: 40px; }
                    .header { background: #4CAF50; color: white; padding: 20px; text-align: center; }
                    .content { padding: 20px; }
                    .download-btn { background: #2196F3; color: white; padding: 15px 30px; 
                                  text-decoration: none; border-radius: 5px; display: inline-block; margin: 20px 0; }
                    .stats { background: #f5f5f5; padding: 15px; border-left: 4px solid #4CAF50; }
                    .footer { color: #666; font-size: 12px; text-align: center; margin-top: 40px; }
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>🎉 Procesamiento de Imágenes Completado</h1>
                </div>
                <div class="content">
                    <p>Estimado usuario,</p>
                    
                    <p>Su procesamiento de imágenes ha sido completado exitosamente.</p>
                    
                    <div class="stats">
                        <h3>📊 Resumen del Procesamiento:</h3>
                        <ul>
                            <li><strong>UUID de Procesamiento:</strong> $processing_uuid</li>
                            <li><strong>Imágenes Procesadas:</strong> $images_processed</li>
                            <li><strong>Tamaño del Archivo:</strong> $file_size_mb MB</li>
                            <li><strong>Tiempo de Expiración:</strong> $expiration_hours horas</li>
                        </ul>
                    </div>
                    
                    <p><strong>⏰ IMPORTANTE:</strong> El enlace de descarga expira el $expiration_datetime</p>
                    
                    <div style="text-align: center;">
                        <a href="$signed_url" class="download-btn">
                            📥 DESCARGAR IMÁGENES
                        </a>
                    </div>
                    
                    <p>Gracias por utilizar nuestro servicio.</p>
                </div>
                <div class="footer">
                    <p>Shipments Processing Platform v$service_version</p>
                    <p>Generado automáticamente el $timestamp</p>
                </div>
            </body>
            </html>
            """,
            
            'error': """
            <html>
            <body style="font-family: Arial, sans-serif; margin: 40px;">
                <div style="background: #f44336; color: white; padding: 20px; text-align: center;">
                    <h1>⚠️ Error en Procesamiento</h1>
                </div>
                <div style="padding: 20px;">
                    <p>Ha ocurrido un error durante el procesamiento:</p>
                    <div style="background: #ffebee; padding: 15px; border-left: 4px solid #f44336;">
                        <p><strong>Error:</strong> $error_message</p>
                        <p><strong>UUID:</strong> $processing_uuid</p>
                        <p><strong>Tipo:</strong> $error_type</p>
                    </div>
                    <p>Nuestro equipo técnico ha sido notificado automáticamente.</p>
                </div>
            </body>
            </html>
            """
        }
    
    def render_template(self, template_name: str, data: Dict[str, Any]) -> str:
        """Renderiza template con datos"""
        try:
            if template_name not in self.templates:
                raise ValueError(f"Template {template_name} no encontrado")
            
            template = Template(self.templates[template_name])
            
            # Añadir datos por defecto
            render_data = {
                'service_version': config.APP_VERSION,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                **data
            }
            
            return template.safe_substitute(render_data)
            
        except Exception as e:
            self.logger.error(f"Error renderizando template: {str(e)}")
            raise
    
    def get_available_templates(self) -> List[str]:
        """Retorna lista de templates disponibles"""
        return list(self.templates.keys())
    
    def get_template_info(self, template_name: str) -> Optional[Dict[str, Any]]:
        """Obtiene información de un template"""
        if template_name not in self.templates:
            return None
        
        template_content = self.templates[template_name]
        
        # Extraer variables del template
        import re
        variables = re.findall(r'\$(\w+)', template_content)
        
        return {
            'name': template_name,
            'variables': list(set(variables)),
            'size': len(template_content),
            'description': self._get_template_description(template_name)
        }
    
    def _get_template_description(self, template_name: str) -> str:
        """Obtiene descripción del template"""
        descriptions = {
            'completion': 'Template para notificación de procesamiento completado',
            'error': 'Template para notificación de errores',
            'custom': 'Template personalizable'
        }
        return descriptions.get(template_name, 'Sin descripción')
