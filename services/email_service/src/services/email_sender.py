"""
Email Sender Service
Responsable del envío de emails via SMTP
"""

import smtplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Dict, Any, Optional, List

import sys
sys.path.insert(0, '/app/services/shared_utils/src')

from config import config
from logger import setup_logger


class EmailSender:
    """
    Servicio para envío de emails via SMTP
    """
    
    def __init__(self):
        self.logger = setup_logger(__name__, 'email-sender', config.APP_VERSION)
        self.smtp_host = config.SMTP_HOST
        self.smtp_port = config.SMTP_PORT
        self.smtp_user = config.SMTP_USER
        self.smtp_password = config.SMTP_PASSWORD
        self.from_email = config.FROM_EMAIL
        
        self.logger.info("✅ Email Sender inicializado")
    
    def send_templated_email(self, to_email: str, subject: str, template_name: str,
                           template_data: Dict[str, Any], trace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Envía email usando template
        """
        try:
            from .template_manager import TemplateManager
            template_manager = TemplateManager()
            
            # Renderizar template
            html_content = template_manager.render_template(template_name, template_data)
            
            # Enviar email
            return self._send_email(
                to_email=to_email,
                subject=subject,
                html_content=html_content,
                trace_id=trace_id
            )
            
        except Exception as e:
            self.logger.error(f"Error enviando email templated: {str(e)}", trace_id=trace_id)
            return {
                'success': False,
                'error': str(e)
            }
    
    def _send_email(self, to_email: str, subject: str, html_content: str,
                   trace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Envía email via SMTP
        """
        try:
            # Crear mensaje
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.from_email
            msg['To'] = to_email
            
            # Añadir contenido HTML
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            # Enviar via SMTP
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                
                server.sendmail(self.from_email, [to_email], msg.as_string())
            
            self.logger.success(f"Email enviado exitosamente a {to_email}", trace_id=trace_id)
            
            return {
                'success': True,
                'to_email': to_email,
                'sent_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error enviando email: {str(e)}", trace_id=trace_id)
            return {
                'success': False,
                'error': str(e),
                'to_email': to_email
            }
    
    def check_smtp_connectivity(self) -> bool:
        """
        Verifica conectividad SMTP
        """
        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10) as server:
                server.starttls()
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                return True
        except Exception as e:
            self.logger.error(f"Error conectividad SMTP: {str(e)}")
            return False
    
    def send_test_email(self, to_email: str, trace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Envía email de prueba
        """
        test_content = f"""
        <html>
        <body>
            <h2>🎉 Email Service - Prueba de Conectividad</h2>
            <p>Este es un email de prueba del <strong>Shipments Processing Platform</strong>.</p>
            <p><strong>Servicio:</strong> Email Service v{config.APP_VERSION}</p>
            <p><strong>Timestamp:</strong> {datetime.now().isoformat()}</p>
            <p><strong>Trace ID:</strong> {trace_id}</p>
        </body>
        </html>
        """
        
        return self._send_email(
            to_email=to_email,
            subject="🧪 Email Service - Prueba de Conectividad",
            html_content=test_content,
            trace_id=trace_id
        )
