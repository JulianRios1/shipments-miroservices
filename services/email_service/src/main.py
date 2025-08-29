"""
Email Service Simplificado - Sin base de datos
Envía notificaciones por email de manera directa y eficiente
"""

import os
import json
from datetime import datetime
from flask import Flask, request, jsonify
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)

# Configuración simple
SMTP_HOST = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', '587'))
SMTP_USER = os.environ.get('SMTP_USER', 'noreply@example.com')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')
FROM_EMAIL = os.environ.get('FROM_EMAIL', 'noreply@example.com')
DEFAULT_TO_EMAIL = os.environ.get('DEFAULT_TO_EMAIL', 'admin@example.com')

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return {
        'status': 'healthy',
        'service': 'email-service-simple',
        'timestamp': datetime.now().isoformat()
    }, 200

@app.route('/send-completion-email', methods=['POST'])
def send_completion_email():
    """
    Envía email de notificación cuando se completa el procesamiento
    """
    try:
        data = request.get_json()
        
        # Extraer datos del request
        processing_uuid = data.get('processing_uuid', 'unknown')
        original_file = data.get('original_file', 'unknown')
        total_shipments = data.get('total_shipments', 0)
        packages_processed = data.get('packages_processed', 0)
        packages_failed = data.get('packages_failed', 0)
        
        # Datos adicionales opcionales
        signed_urls = data.get('signed_urls', [])
        user_email = data.get('user_email', DEFAULT_TO_EMAIL)
        
        # Crear el mensaje de email
        subject = f"✅ Procesamiento Completado - {processing_uuid}"
        
        if packages_failed > 0:
            subject = f"⚠️ Procesamiento con Errores - {processing_uuid}"
        
        # Crear contenido HTML del email
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2 style="color: {'#27ae60' if packages_failed == 0 else '#e74c3c'};">
                {'✅ Procesamiento Completado' if packages_failed == 0 else '⚠️ Procesamiento con Errores'}
            </h2>
            
            <div style="background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <h3>Resumen del Procesamiento</h3>
                <ul>
                    <li><strong>ID de Procesamiento:</strong> {processing_uuid}</li>
                    <li><strong>Archivo Original:</strong> {original_file}</li>
                    <li><strong>Total de Envíos:</strong> {total_shipments}</li>
                    <li><strong>Paquetes Procesados:</strong> {packages_processed}</li>
                    <li><strong>Paquetes con Error:</strong> {packages_failed}</li>
                    <li><strong>Fecha:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</li>
                </ul>
            </div>
        """
        
        # Agregar URLs de descarga si existen
        if signed_urls:
            html_content += """
            <div style="background: #e3f2fd; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <h3>📦 Enlaces de Descarga (válidos por 2 horas)</h3>
                <ul>
            """
            for i, url in enumerate(signed_urls, 1):
                html_content += f'<li><a href="{url}">Descargar Paquete {i}</a></li>'
            
            html_content += """
                </ul>
            </div>
            """
        
        html_content += """
            <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd;">
                <p style="color: #666; font-size: 12px;">
                    Este es un mensaje automático del sistema de procesamiento de envíos.<br>
                    Por favor, no responda a este correo.
                </p>
            </div>
        </body>
        </html>
        """
        
        # Enviar el email
        success = send_email(user_email, subject, html_content)
        
        if success:
            return {
                'success': True,
                'message': 'Email enviado exitosamente',
                'recipient': user_email,
                'processing_uuid': processing_uuid
            }, 200
        else:
            return {
                'success': False,
                'error': 'No se pudo enviar el email',
                'processing_uuid': processing_uuid
            }, 500
            
    except Exception as e:
        return {
            'success': False,
            'error': f'Error procesando solicitud: {str(e)}'
        }, 500

@app.route('/send-error-notification', methods=['POST'])
def send_error_notification():
    """
    Envía notificación cuando hay un error en el procesamiento
    """
    try:
        data = request.get_json()
        
        processing_uuid = data.get('processing_uuid', 'unknown')
        error_message = data.get('error_message', 'Error desconocido')
        package_name = data.get('package_name', 'unknown')
        user_email = data.get('user_email', DEFAULT_TO_EMAIL)
        
        subject = f"❌ Error en Procesamiento - {processing_uuid}"
        
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2 style="color: #e74c3c;">❌ Error en el Procesamiento</h2>
            
            <div style="background: #fee; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <h3>Detalles del Error</h3>
                <ul>
                    <li><strong>ID de Procesamiento:</strong> {processing_uuid}</li>
                    <li><strong>Paquete:</strong> {package_name}</li>
                    <li><strong>Error:</strong> {error_message}</li>
                    <li><strong>Fecha:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</li>
                </ul>
            </div>
            
            <p>Por favor, revise el sistema y vuelva a intentar el procesamiento.</p>
        </body>
        </html>
        """
        
        success = send_email(user_email, subject, html_content)
        
        return {
            'success': success,
            'message': 'Notificación de error enviada' if success else 'Error enviando notificación'
        }, 200 if success else 500
        
    except Exception as e:
        return {
            'success': False,
            'error': f'Error: {str(e)}'
        }, 500

def send_email(to_email: str, subject: str, html_content: str) -> bool:
    """
    Función auxiliar para enviar emails
    """
    try:
        # Crear mensaje
        msg = MIMEMultipart('alternative')
        msg['From'] = FROM_EMAIL
        msg['To'] = to_email
        msg['Subject'] = subject
        
        # Agregar contenido HTML
        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)
        
        # Para desarrollo local, solo imprimir
        if SMTP_HOST == 'localhost' or not SMTP_PASSWORD:
            print(f"📧 EMAIL SIMULADO:")
            print(f"  Para: {to_email}")
            print(f"  Asunto: {subject}")
            print(f"  Contenido: [HTML Email]")
            return True
        
        # Enviar email real
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            if SMTP_USER and SMTP_PASSWORD:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
            
        return True
        
    except Exception as e:
        print(f"Error enviando email: {str(e)}")
        return False

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8083))
    print(f"🚀 Email Service Simplificado iniciando en puerto {port}")
    app.run(host='0.0.0.0', port=port, debug=True)
