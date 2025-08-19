"""
Unit tests for Email Service.
Tests all endpoints and core functionality for email processing.
"""
import pytest
import json
import uuid
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import sys
import os

# Add services to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'services', 'email_service', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'services', 'shared_utils', 'src'))

# Mock shared services before import
with patch.dict(sys.modules, {
    'config': MagicMock(),
    'logger': MagicMock(),
    'database_service': MagicMock(),
    'pubsub_service': MagicMock(),
    'services.email_sender': MagicMock(),
    'services.template_manager': MagicMock(),
    'services.notification_manager': MagicMock()
}):
    import main as email_main

@pytest.fixture
def app():
    """Create Flask test app."""
    email_main.app.config['TESTING'] = True
    return email_main.app.test_client()

@pytest.fixture
def valid_completion_request():
    """Valid completion email request."""
    return {
        'processing_uuid': 'test-uuid-123',
        'customer_email': 'customer@example.com',
        'customer_name': 'Test Customer',
        'signed_urls': [
            'https://signed-url.example.com/package1.zip',
            'https://signed-url.example.com/package2.zip'
        ],
        'expiration_time': (datetime.now() + timedelta(hours=2)).isoformat(),
        'total_shipments': 10,
        'total_packages': 2
    }

@pytest.fixture
def valid_error_notification():
    """Valid error notification request."""
    return {
        'processing_uuid': 'error-uuid-123',
        'error_type': 'image_processing_failed',
        'error_message': 'Failed to download images from bucket',
        'customer_email': 'customer@example.com',
        'customer_name': 'Test Customer'
    }

@pytest.fixture
def valid_custom_email():
    """Valid custom email request."""
    return {
        'to_email': 'recipient@example.com',
        'subject': 'Test Custom Email',
        'template_name': 'custom_notification',
        'template_data': {
            'customer_name': 'Custom Customer',
            'message': 'This is a custom message'
        }
    }


class TestHealthEndpoints:
    """Test health and status endpoints."""
    
    def test_health_check(self, app):
        """Test health check endpoint returns healthy status."""
        response = app.get('/health')
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['status'] == 'healthy'
        assert data['service'] == 'email-service'
        assert 'timestamp' in data

    @patch('main.database_service')
    @patch('main.email_sender')
    @patch('main.template_manager')
    def test_status_check_healthy(self, mock_template, mock_email, mock_db, app):
        """Test status endpoint when all dependencies are healthy."""
        mock_db.check_connectivity.return_value = True
        mock_email.check_smtp_connectivity.return_value = True
        mock_template.get_available_templates.return_value = ['completion', 'error', 'custom']
        
        response = app.get('/status')
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['status'] == 'ready'
        assert data['dependencies']['database'] == 'healthy'
        assert data['dependencies']['smtp_server'] == 'healthy'
        assert data['service'] == 'email-service'
        assert len(data['configuration']['templates_available']) == 3

    @patch('main.database_service')
    @patch('main.email_sender')
    def test_status_check_unhealthy_smtp(self, mock_email, mock_db, app):
        """Test status endpoint when SMTP is unhealthy."""
        mock_db.check_connectivity.return_value = True
        mock_email.check_smtp_connectivity.return_value = False
        
        response = app.get('/status')
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['dependencies']['smtp_server'] == 'unhealthy'
        assert data['dependencies']['database'] == 'healthy'

    @patch('main.database_service')
    def test_status_check_exception(self, mock_db, app):
        """Test status endpoint when exception occurs."""
        mock_db.check_connectivity.side_effect = Exception("DB connection failed")
        
        response = app.get('/status')
        data = json.loads(response.data)
        
        assert response.status_code == 500
        assert data['status'] == 'error'
        assert 'error' in data


class TestSendCompletionEmailEndpoint:
    """Test the main completion email sending endpoint."""
    
    @patch('main.notification_manager')
    def test_send_completion_email_success(self, mock_notification, app, valid_completion_request):
        """Test successful completion email sending."""
        expected_result = {
            'processing_uuid': 'test-uuid-123',
            'emails_sent': 1,
            'database_updated': True,
            'customer_email': 'customer@example.com',
            'sent_at': datetime.now().isoformat()
        }
        mock_notification.process_completion_notification.return_value = expected_result
        
        response = app.post('/send-completion-email', json=valid_completion_request)
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['processing_uuid'] == 'test-uuid-123'
        assert data['emails_sent'] == 1
        assert data['database_updated'] is True
        
        # Verify method was called with correct arguments
        mock_notification.process_completion_notification.assert_called_once_with(
            processing_uuid='test-uuid-123',
            notification_data=valid_completion_request,
            trace_id=unittest.mock.ANY
        )

    def test_send_completion_email_no_data(self, app):
        """Test sending completion email with no request data."""
        response = app.post('/send-completion-email')
        data = json.loads(response.data)
        
        assert response.status_code == 400
        assert 'error' in data

    def test_send_completion_email_missing_uuid(self, app):
        """Test sending completion email with missing processing_uuid."""
        invalid_request = {
            'customer_email': 'customer@example.com',
            'signed_urls': ['https://example.com/package.zip']
        }
        
        response = app.post('/send-completion-email', json=invalid_request)
        data = json.loads(response.data)
        
        assert response.status_code == 400
        assert 'processing_uuid requerido' in data['error']

    @patch('main.notification_manager')
    @patch('main.pubsub_service')
    def test_send_completion_email_exception_with_pubsub(self, mock_pubsub, mock_notification, 
                                                       app, valid_completion_request):
        """Test exception handling with Pub/Sub error publishing."""
        mock_notification.process_completion_notification.side_effect = Exception("Email sending failed")
        
        response = app.post('/send-completion-email', json=valid_completion_request)
        data = json.loads(response.data)
        
        assert response.status_code == 500
        assert 'error' in data
        
        # Verify error was published to Pub/Sub
        mock_pubsub.publish_error.assert_called_once()

    @patch('main.notification_manager')
    @patch('main.pubsub_service')
    def test_send_completion_email_pubsub_publish_fails(self, mock_pubsub, mock_notification, 
                                                       app, valid_completion_request):
        """Test when Pub/Sub error publishing also fails."""
        mock_notification.process_completion_notification.side_effect = Exception("Email sending failed")
        mock_pubsub.publish_error.side_effect = Exception("Pub/Sub failed")
        
        response = app.post('/send-completion-email', json=valid_completion_request)
        data = json.loads(response.data)
        
        assert response.status_code == 500
        assert 'error' in data


class TestSendErrorNotificationEndpoint:
    """Test error notification sending endpoint."""
    
    @patch('main.notification_manager')
    def test_send_error_notification_success(self, mock_notification, app, valid_error_notification):
        """Test successful error notification sending."""
        expected_result = {
            'processing_uuid': 'error-uuid-123',
            'error_notification_sent': True,
            'notification_type': 'image_processing_failed',
            'sent_at': datetime.now().isoformat()
        }
        mock_notification.send_error_notification.return_value = expected_result
        
        response = app.post('/send-error-notification', json=valid_error_notification)
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['error_notification_sent'] is True
        assert data['processing_uuid'] == 'error-uuid-123'
        
        mock_notification.send_error_notification.assert_called_once_with(
            error_type='image_processing_failed',
            error_message='Failed to download images from bucket',
            processing_uuid='error-uuid-123',
            additional_data=valid_error_notification,
            trace_id=unittest.mock.ANY
        )

    def test_send_error_notification_no_data(self, app):
        """Test sending error notification with no request data."""
        response = app.post('/send-error-notification')
        data = json.loads(response.data)
        
        assert response.status_code == 400
        assert 'error' in data

    @patch('main.notification_manager')
    def test_send_error_notification_default_values(self, mock_notification, app):
        """Test error notification with default values for optional fields."""
        minimal_request = {}
        
        expected_result = {
            'processing_uuid': 'unknown',
            'error_notification_sent': True,
            'notification_type': 'general_error'
        }
        mock_notification.send_error_notification.return_value = expected_result
        
        response = app.post('/send-error-notification', json=minimal_request)
        data = json.loads(response.data)
        
        assert response.status_code == 200
        
        mock_notification.send_error_notification.assert_called_once_with(
            error_type='general_error',
            error_message='Error no especificado',
            processing_uuid='unknown',
            additional_data=minimal_request,
            trace_id=unittest.mock.ANY
        )

    @patch('main.notification_manager')
    def test_send_error_notification_exception(self, mock_notification, app):
        """Test error notification when exception occurs."""
        mock_notification.send_error_notification.side_effect = Exception("Notification failed")
        
        response = app.post('/send-error-notification', json={'error_type': 'test'})
        data = json.loads(response.data)
        
        assert response.status_code == 500
        assert 'error' in data


class TestSendCustomEmailEndpoint:
    """Test custom email sending endpoint."""
    
    @patch('main.email_sender')
    def test_send_custom_email_success(self, mock_email_sender, app, valid_custom_email):
        """Test successful custom email sending."""
        expected_result = {
            'email_sent': True,
            'to_email': 'recipient@example.com',
            'template_used': 'custom_notification',
            'sent_at': datetime.now().isoformat()
        }
        mock_email_sender.send_templated_email.return_value = expected_result
        
        response = app.post('/send-custom-email', json=valid_custom_email)
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['email_sent'] is True
        assert data['to_email'] == 'recipient@example.com'
        
        mock_email_sender.send_templated_email.assert_called_once_with(
            to_email='recipient@example.com',
            subject='Test Custom Email',
            template_name='custom_notification',
            template_data=valid_custom_email['template_data'],
            trace_id=unittest.mock.ANY
        )

    def test_send_custom_email_missing_fields(self, app):
        """Test custom email with missing required fields."""
        incomplete_request = {
            'to_email': 'recipient@example.com'
            # Missing subject
        }
        
        response = app.post('/send-custom-email', json=incomplete_request)
        data = json.loads(response.data)
        
        assert response.status_code == 400
        assert 'campos requeridos' in data['error'].lower()

    @patch('main.email_sender')
    def test_send_custom_email_default_template(self, mock_email_sender, app):
        """Test custom email with default template name."""
        request_data = {
            'to_email': 'recipient@example.com',
            'subject': 'Test Email'
            # No template_name specified
        }
        
        expected_result = {
            'email_sent': True,
            'template_used': 'custom'
        }
        mock_email_sender.send_templated_email.return_value = expected_result
        
        response = app.post('/send-custom-email', json=request_data)
        data = json.loads(response.data)
        
        assert response.status_code == 200
        
        mock_email_sender.send_templated_email.assert_called_once_with(
            to_email='recipient@example.com',
            subject='Test Email',
            template_name='custom',
            template_data={},
            trace_id=unittest.mock.ANY
        )

    @patch('main.email_sender')
    def test_send_custom_email_exception(self, mock_email_sender, app):
        """Test custom email when exception occurs."""
        mock_email_sender.send_templated_email.side_effect = Exception("Email sending failed")
        
        request_data = {
            'to_email': 'recipient@example.com',
            'subject': 'Test Email'
        }
        
        response = app.post('/send-custom-email', json=request_data)
        data = json.loads(response.data)
        
        assert response.status_code == 500
        assert 'error' in data


class TestTemplateEndpoints:
    """Test template management endpoints."""
    
    @patch('main.template_manager')
    def test_list_templates(self, mock_template_manager, app):
        """Test listing available templates."""
        expected_templates = ['completion', 'error', 'custom', 'notification']
        mock_template_manager.get_available_templates.return_value = expected_templates
        
        response = app.get('/templates')
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['templates'] == expected_templates
        assert data['total_templates'] == 4
        assert 'timestamp' in data

    @patch('main.template_manager')
    def test_list_templates_exception(self, mock_template_manager, app):
        """Test listing templates when exception occurs."""
        mock_template_manager.get_available_templates.side_effect = Exception("Template error")
        
        response = app.get('/templates')
        data = json.loads(response.data)
        
        assert response.status_code == 500
        assert 'error' in data

    @patch('main.template_manager')
    def test_get_template_info_success(self, mock_template_manager, app):
        """Test getting specific template information."""
        template_info = {
            'name': 'completion',
            'description': 'Template for completion notifications',
            'variables': ['customer_name', 'signed_urls', 'expiration_time'],
            'last_modified': datetime.now().isoformat()
        }
        mock_template_manager.get_template_info.return_value = template_info
        
        response = app.get('/templates/completion')
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['name'] == 'completion'
        assert len(data['variables']) == 3

    @patch('main.template_manager')
    def test_get_template_info_not_found(self, mock_template_manager, app):
        """Test getting template info for non-existent template."""
        mock_template_manager.get_template_info.return_value = None
        
        response = app.get('/templates/nonexistent')
        data = json.loads(response.data)
        
        assert response.status_code == 404
        assert 'no encontrado' in data['error']

    @patch('main.template_manager')
    def test_get_template_info_exception(self, mock_template_manager, app):
        """Test getting template info when exception occurs."""
        mock_template_manager.get_template_info.side_effect = Exception("Template error")
        
        response = app.get('/templates/completion')
        data = json.loads(response.data)
        
        assert response.status_code == 500
        assert 'error' in data


class TestUtilityEndpoints:
    """Test utility endpoints like test email and statistics."""
    
    @patch('main.email_sender')
    @patch('main.config')
    def test_test_email_success(self, mock_config, mock_email_sender, app):
        """Test email configuration testing."""
        mock_config.FROM_EMAIL = 'test@example.com'
        expected_result = {
            'test_email_sent': True,
            'to_email': 'test@example.com',
            'sent_at': datetime.now().isoformat()
        }
        mock_email_sender.send_test_email.return_value = expected_result
        
        response = app.post('/test-email')
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['test_email_sent'] is True

    @patch('main.email_sender')
    def test_test_email_custom_recipient(self, mock_email_sender, app):
        """Test email configuration with custom recipient."""
        expected_result = {
            'test_email_sent': True,
            'to_email': 'custom@example.com'
        }
        mock_email_sender.send_test_email.return_value = expected_result
        
        response = app.post('/test-email', json={'to_email': 'custom@example.com'})
        data = json.loads(response.data)
        
        assert response.status_code == 200
        mock_email_sender.send_test_email.assert_called_once_with('custom@example.com', unittest.mock.ANY)

    @patch('main.email_sender')
    def test_test_email_exception(self, mock_email_sender, app):
        """Test email configuration when exception occurs."""
        mock_email_sender.send_test_email.side_effect = Exception("SMTP error")
        
        response = app.post('/test-email')
        data = json.loads(response.data)
        
        assert response.status_code == 500
        assert 'error' in data

    @patch('main.notification_manager')
    def test_get_email_statistics_success(self, mock_notification, app):
        """Test getting email statistics."""
        expected_stats = {
            'period_days': 7,
            'total_emails_sent': 150,
            'completion_emails': 120,
            'error_notifications': 25,
            'custom_emails': 5,
            'success_rate': 95.5,
            'last_updated': datetime.now().isoformat()
        }
        mock_notification.get_email_statistics.return_value = expected_stats
        
        response = app.get('/statistics')
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['total_emails_sent'] == 150
        assert data['period_days'] == 7
        
        mock_notification.get_email_statistics.assert_called_once_with(7)

    @patch('main.notification_manager')
    def test_get_email_statistics_custom_days(self, mock_notification, app):
        """Test getting email statistics with custom day range."""
        expected_stats = {
            'period_days': 30,
            'total_emails_sent': 500
        }
        mock_notification.get_email_statistics.return_value = expected_stats
        
        response = app.get('/statistics?days=30')
        data = json.loads(response.data)
        
        assert response.status_code == 200
        mock_notification.get_email_statistics.assert_called_once_with(30)

    @patch('main.notification_manager')
    def test_get_email_statistics_exception(self, mock_notification, app):
        """Test getting statistics when exception occurs."""
        mock_notification.get_email_statistics.side_effect = Exception("Stats error")
        
        response = app.get('/statistics')
        data = json.loads(response.data)
        
        assert response.status_code == 500
        assert 'error' in data


class TestPubSubHandler:
    """Test Pub/Sub message handling endpoint."""
    
    @patch('main.send_completion_email')
    def test_pubsub_handler_completion_email(self, mock_send_completion, app):
        """Test Pub/Sub handler for completion email action."""
        message_data = {
            'action': 'send_completion_email',
            'processing_uuid': 'test-uuid-123'
        }
        
        import base64
        envelope = {
            'message': {
                'data': base64.b64encode(json.dumps(message_data).encode()).decode(),
                'messageId': '123456789'
            }
        }
        
        mock_send_completion.return_value = ('{"success": true}', 200)
        
        response = app.post('/pubsub-handler', json=envelope)
        
        assert response.status_code == 200

    @patch('main.send_error_notification')
    def test_pubsub_handler_error_notification(self, mock_send_error, app):
        """Test Pub/Sub handler for error notification action."""
        message_data = {
            'action': 'send_error_notification',
            'error_type': 'processing_failed'
        }
        
        import base64
        envelope = {
            'message': {
                'data': base64.b64encode(json.dumps(message_data).encode()).decode(),
                'messageId': '123456789'
            }
        }
        
        mock_send_error.return_value = ('{"success": true}', 200)
        
        response = app.post('/pubsub-handler', json=envelope)
        
        assert response.status_code == 200

    def test_pubsub_handler_unknown_action(self, app):
        """Test Pub/Sub handler with unknown action."""
        message_data = {
            'action': 'unknown_action'
        }
        
        import base64
        envelope = {
            'message': {
                'data': base64.b64encode(json.dumps(message_data).encode()).decode(),
                'messageId': '123456789'
            }
        }
        
        response = app.post('/pubsub-handler', json=envelope)
        data = json.loads(response.data)
        
        assert response.status_code == 400
        assert 'no reconocida' in data['error']

    def test_pubsub_handler_invalid_message(self, app):
        """Test Pub/Sub handler with invalid message format."""
        response = app.post('/pubsub-handler', json={})
        data = json.loads(response.data)
        
        assert response.status_code == 400
        assert 'error' in data

    def test_pubsub_handler_exception(self, app):
        """Test Pub/Sub handler when exception occurs."""
        # Invalid base64 data
        envelope = {
            'message': {
                'data': 'invalid-base64-data',
                'messageId': '123456789'
            }
        }
        
        response = app.post('/pubsub-handler', json=envelope)
        data = json.loads(response.data)
        
        assert response.status_code == 500
        assert 'error' in data


@pytest.mark.integration
class TestEmailServiceIntegration:
    """Integration tests that test multiple components together."""
    
    @patch('main.notification_manager')
    @patch('main.template_manager')
    @patch('main.email_sender')
    def test_full_email_flow_completion(self, mock_email_sender, mock_template, mock_notification, app):
        """Test complete email sending flow for completion notification."""
        # Setup template manager
        mock_template.get_available_templates.return_value = ['completion', 'error']
        
        # Setup notification processing
        notification_result = {
            'processing_uuid': 'integration-uuid-123',
            'emails_sent': 1,
            'database_updated': True,
            'customer_email': 'customer@example.com'
        }
        mock_notification.process_completion_notification.return_value = notification_result
        
        # Send completion email
        request_data = {
            'processing_uuid': 'integration-uuid-123',
            'customer_email': 'customer@example.com',
            'signed_urls': ['https://signed-url.example.com/package.zip']
        }
        
        response = app.post('/send-completion-email', json=request_data)
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['emails_sent'] == 1
        
        # Verify template was available
        templates_response = app.get('/templates')
        templates_data = json.loads(templates_response.data)
        
        assert templates_response.status_code == 200
        assert 'completion' in templates_data['templates']

import unittest.mock
