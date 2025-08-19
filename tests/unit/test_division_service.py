"""
Unit tests for Division Service.
Tests all endpoints and core functionality independently.
"""
import pytest
import json
import uuid
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import sys
import os

# Add services to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'services', 'division_service', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'services', 'shared_utils', 'src'))

# Mock shared services before import
with patch.dict(sys.modules, {
    'config': MagicMock(),
    'logger': MagicMock(),
    'storage_service': MagicMock(),
    'database_service': MagicMock(),
    'pubsub_service': MagicMock(),
    'services.division_processor': MagicMock(),
    'services.uuid_generator': MagicMock(),
    'services.file_validator': MagicMock()
}):
    import main as division_main

@pytest.fixture
def app():
    """Create Flask test app."""
    division_main.app.config['TESTING'] = True
    return division_main.app.test_client()

@pytest.fixture
def valid_storage_event():
    """Valid Cloud Storage event data."""
    return {
        'bucket': 'test-bucket-pendientes',
        'name': 'shipments_batch_001.json',
        'eventType': 'google.storage.object.finalize',
        'timeCreated': datetime.now().isoformat()
    }

@pytest.fixture
def valid_pubsub_envelope(valid_storage_event):
    """Valid Pub/Sub envelope with Cloud Storage event."""
    import base64
    return {
        'message': {
            'data': base64.b64encode(json.dumps(valid_storage_event).encode()).decode(),
            'messageId': '123456789',
            'publishTime': datetime.now().isoformat()
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
        assert data['service'] == 'division-service'
        assert 'timestamp' in data

    @patch('main.database_service')
    def test_status_check_healthy(self, mock_db, app):
        """Test status endpoint when all dependencies are healthy."""
        mock_db.check_connectivity.return_value = True
        
        response = app.get('/status')
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['status'] == 'ready'
        assert data['dependencies']['database'] == 'healthy'
        assert data['service'] == 'division-service'

    @patch('main.database_service')
    def test_status_check_unhealthy_db(self, mock_db, app):
        """Test status endpoint when database is unhealthy."""
        mock_db.check_connectivity.return_value = False
        
        response = app.get('/status')
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['dependencies']['database'] == 'unhealthy'

    @patch('main.database_service')
    def test_status_check_exception(self, mock_db, app):
        """Test status endpoint when exception occurs."""
        mock_db.check_connectivity.side_effect = Exception("DB connection failed")
        
        response = app.get('/status')
        data = json.loads(response.data)
        
        assert response.status_code == 500
        assert data['status'] == 'error'
        assert 'error' in data


class TestProcessFileEndpoint:
    """Test the main file processing endpoint."""
    
    @patch('main.division_processor')
    @patch('main.file_validator')
    @patch('main.storage_service')
    @patch('main.config')
    def test_process_file_success(self, mock_config, mock_storage, mock_validator, mock_processor, app, valid_pubsub_envelope):
        """Test successful file processing."""
        # Setup mocks
        mock_config.BUCKET_JSON_PENDIENTES = 'test-bucket-pendientes'
        mock_storage.wait_for_file_completion.return_value = True
        mock_validator.validate_file_structure.return_value = True
        
        mock_processor.process_file_with_division.return_value = {
            'processing_uuid': 'test-uuid-123',
            'packages_created': 3,
            'total_shipments': 15,
            'status': 'completed'
        }
        
        # Make request
        response = app.post('/process-file', json=valid_pubsub_envelope)
        data = json.loads(response.data)
        
        # Assertions
        assert response.status_code == 200
        assert data['processing_uuid'] == 'test-uuid-123'
        assert data['packages_created'] == 3
        assert data['total_shipments'] == 15
        
        # Verify method calls
        mock_storage.wait_for_file_completion.assert_called_once()
        mock_validator.validate_file_structure.assert_called_once()
        mock_processor.process_file_with_division.assert_called_once()

    def test_process_file_no_data(self, app):
        """Test processing with no request data."""
        response = app.post('/process-file')
        data = json.loads(response.data)
        
        assert response.status_code == 400
        assert 'error' in data

    @patch('main.config')
    def test_process_file_wrong_bucket(self, mock_config, app, valid_pubsub_envelope):
        """Test processing file from wrong bucket."""
        mock_config.BUCKET_JSON_PENDIENTES = 'correct-bucket'
        
        # Modify envelope to have wrong bucket
        event_data = json.loads(json.loads(valid_pubsub_envelope['message']['data']))
        event_data['bucket'] = 'wrong-bucket'
        
        import base64
        valid_pubsub_envelope['message']['data'] = base64.b64encode(
            json.dumps(event_data).encode()
        ).decode()
        
        response = app.post('/process-file', json=valid_pubsub_envelope)
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert 'ignorado' in data['message']

    @patch('main.storage_service')
    @patch('main.config')
    def test_process_file_not_completed(self, mock_config, mock_storage, app, valid_pubsub_envelope):
        """Test processing when file is not completed."""
        mock_config.BUCKET_JSON_PENDIENTES = 'test-bucket-pendientes'
        mock_storage.wait_for_file_completion.return_value = False
        
        response = app.post('/process-file', json=valid_pubsub_envelope)
        data = json.loads(response.data)
        
        assert response.status_code == 408
        assert 'no completado' in data['error']

    @patch('main.file_validator')
    @patch('main.storage_service')
    @patch('main.config')
    def test_process_file_invalid_structure(self, mock_config, mock_storage, mock_validator, app, valid_pubsub_envelope):
        """Test processing when file has invalid structure."""
        mock_config.BUCKET_JSON_PENDIENTES = 'test-bucket-pendientes'
        mock_storage.wait_for_file_completion.return_value = True
        mock_validator.validate_file_structure.return_value = False
        
        response = app.post('/process-file', json=valid_pubsub_envelope)
        data = json.loads(response.data)
        
        assert response.status_code == 400
        assert 'estructura' in data['error'].lower()

    @patch('main.division_processor')
    @patch('main.file_validator')
    @patch('main.storage_service')
    @patch('main.config')
    @patch('main.pubsub_service')
    def test_process_file_exception_with_pubsub_error(self, mock_pubsub, mock_config, mock_storage, 
                                                     mock_validator, mock_processor, app, valid_pubsub_envelope):
        """Test exception handling with Pub/Sub error publishing."""
        mock_config.BUCKET_JSON_PENDIENTES = 'test-bucket-pendientes'
        mock_storage.wait_for_file_completion.return_value = True
        mock_validator.validate_file_structure.return_value = True
        mock_processor.process_file_with_division.side_effect = Exception("Processing failed")
        mock_pubsub.publish_error.side_effect = Exception("Pub/Sub failed")
        
        response = app.post('/process-file', json=valid_pubsub_envelope)
        data = json.loads(response.data)
        
        assert response.status_code == 500
        assert 'error' in data


class TestProcessingStatusEndpoint:
    """Test processing status lookup endpoint."""
    
    @patch('main.database_service')
    def test_get_processing_status_success(self, mock_db, app):
        """Test successful status retrieval."""
        mock_record = {
            'estado': 'completed',
            'nombre_archivo': 'test.json',
            'total_envios': 10,
            'total_paquetes': 3,
            'fecha_inicio': datetime.now(),
            'fecha_finalizacion': datetime.now(),
            'metadatos': {'key': 'value'},
            'resultado': {'success': True},
            'error_mensaje': None
        }
        mock_db.get_processing_record.return_value = mock_record
        
        response = app.get('/process-by-uuid/test-uuid-123')
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['processing_uuid'] == 'test-uuid-123'
        assert data['status'] == 'completed'
        assert data['total_shipments'] == 10
        assert data['total_packages'] == 3

    @patch('main.database_service')
    def test_get_processing_status_not_found(self, mock_db, app):
        """Test status retrieval for non-existent processing."""
        mock_db.get_processing_record.return_value = None
        
        response = app.get('/process-by-uuid/nonexistent-uuid')
        data = json.loads(response.data)
        
        assert response.status_code == 404
        assert 'no encontrado' in data['error']

    @patch('main.database_service')
    def test_get_processing_status_with_error(self, mock_db, app):
        """Test status retrieval when record has error message."""
        mock_record = {
            'estado': 'error',
            'nombre_archivo': 'test.json',
            'total_envios': 0,
            'total_paquetes': 0,
            'fecha_inicio': datetime.now(),
            'fecha_finalizacion': None,
            'metadatos': {},
            'resultado': None,
            'error_mensaje': 'Processing failed'
        }
        mock_db.get_processing_record.return_value = mock_record
        
        response = app.get('/process-by-uuid/error-uuid')
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['status'] == 'error'
        assert data['error_message'] == 'Processing failed'

    @patch('main.database_service')
    def test_get_processing_status_exception(self, mock_db, app):
        """Test status retrieval when database exception occurs."""
        mock_db.get_processing_record.side_effect = Exception("Database error")
        
        response = app.get('/process-by-uuid/test-uuid')
        data = json.loads(response.data)
        
        assert response.status_code == 500
        assert 'error' in data


class TestEventDataExtraction:
    """Test event data extraction utility function."""
    
    def test_extract_pubsub_event(self, valid_pubsub_envelope):
        """Test extraction from Pub/Sub envelope."""
        result = division_main._extract_event_data(valid_pubsub_envelope)
        
        assert result['bucket'] == 'test-bucket-pendientes'
        assert result['name'] == 'shipments_batch_001.json'
        assert result['eventType'] == 'google.storage.object.finalize'

    def test_extract_eventarc_direct(self):
        """Test extraction from direct Eventarc event."""
        event = {
            'bucket': 'direct-bucket',
            'name': 'direct-file.json',
            'eventType': 'storage.object.create'
        }
        
        result = division_main._extract_event_data(event)
        
        assert result['bucket'] == 'direct-bucket'
        assert result['name'] == 'direct-file.json'

    def test_extract_cloudevent_format(self):
        """Test extraction from CloudEvent format."""
        event = {
            'data': {
                'bucket': 'cloud-event-bucket',
                'name': 'cloud-event-file.json'
            },
            'type': 'storage.object.create'
        }
        
        result = division_main._extract_event_data(event)
        
        assert result['bucket'] == 'cloud-event-bucket'
        assert result['name'] == 'cloud-event-file.json'


class TestFileRequestValidation:
    """Test file request validation utility function."""
    
    @patch('main.config')
    def test_validate_file_request_valid(self, mock_config):
        """Test validation of valid file request."""
        mock_config.BUCKET_JSON_PENDIENTES = 'correct-bucket'
        
        result = division_main._validate_file_request('correct-bucket', 'file.json', 'trace-123')
        
        assert result is True

    @patch('main.config')
    def test_validate_file_request_wrong_bucket(self, mock_config):
        """Test validation with wrong bucket."""
        mock_config.BUCKET_JSON_PENDIENTES = 'correct-bucket'
        
        result = division_main._validate_file_request('wrong-bucket', 'file.json', 'trace-123')
        
        assert result is False

    @patch('main.config')
    def test_validate_file_request_not_json(self, mock_config):
        """Test validation with non-JSON file."""
        mock_config.BUCKET_JSON_PENDIENTES = 'correct-bucket'
        
        result = division_main._validate_file_request('correct-bucket', 'file.txt', 'trace-123')
        
        assert result is False

    @patch('main.config')
    def test_validate_file_request_temporary_file(self, mock_config):
        """Test validation with temporary file."""
        mock_config.BUCKET_JSON_PENDIENTES = 'correct-bucket'
        
        result = division_main._validate_file_request('correct-bucket', '.temp_file.json', 'trace-123')
        
        assert result is False

    @patch('main.config')
    def test_validate_file_request_tmp_path(self, mock_config):
        """Test validation with file in tmp path."""
        mock_config.BUCKET_JSON_PENDIENTES = 'correct-bucket'
        
        result = division_main._validate_file_request('correct-bucket', 'path/tmp/file.json', 'trace-123')
        
        assert result is False

    @patch('main.config')
    def test_validate_file_request_empty_filename(self, mock_config):
        """Test validation with empty filename."""
        mock_config.BUCKET_JSON_PENDIENTES = 'correct-bucket'
        
        result = division_main._validate_file_request('correct-bucket', '', 'trace-123')
        
        assert result is False


@pytest.mark.integration
class TestDivisionServiceIntegration:
    """Integration tests that test multiple components together."""
    
    @patch('main.division_processor')
    @patch('main.file_validator')  
    @patch('main.storage_service')
    @patch('main.database_service')
    @patch('main.config')
    def test_full_processing_flow(self, mock_config, mock_db, mock_storage, mock_validator, mock_processor, app):
        """Test complete file processing flow."""
        # Setup all mocks
        mock_config.BUCKET_JSON_PENDIENTES = 'test-bucket-pendientes'
        mock_storage.wait_for_file_completion.return_value = True
        mock_validator.validate_file_structure.return_value = True
        
        expected_result = {
            'processing_uuid': 'integration-test-uuid',
            'packages_created': 5,
            'total_shipments': 25,
            'status': 'completed'
        }
        mock_processor.process_file_with_division.return_value = expected_result
        
        # Create event
        event_data = {
            'bucket': 'test-bucket-pendientes',
            'name': 'integration_test.json',
            'eventType': 'google.storage.object.finalize'
        }
        
        import base64
        envelope = {
            'message': {
                'data': base64.b64encode(json.dumps(event_data).encode()).decode()
            }
        }
        
        # Make request
        response = app.post('/process-file', json=envelope)
        data = json.loads(response.data)
        
        # Verify complete flow
        assert response.status_code == 200
        assert data == expected_result
        
        # Verify all steps were called
        mock_storage.wait_for_file_completion.assert_called_once_with(
            'test-bucket-pendientes', 'integration_test.json', trace_id=unittest.mock.ANY
        )
        mock_validator.validate_file_structure.assert_called_once_with(
            'test-bucket-pendientes', 'integration_test.json', trace_id=unittest.mock.ANY
        )
        mock_processor.process_file_with_division.assert_called_once_with(
            bucket_name='test-bucket-pendientes',
            file_name='integration_test.json', 
            trace_id=unittest.mock.ANY
        )

import unittest.mock
