"""
Email Service - Services Module
"""

from .email_sender import EmailSender
from .template_manager import TemplateManager
from .notification_manager import NotificationManager

__all__ = [
    'EmailSender',
    'TemplateManager',
    'NotificationManager'
]
