"""
Unit tests for Image Processing Service.
Tests all endpoints and core functionality for image processing.
"""
import pytest
import json
import uuid
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import sys
import os

# Add services to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'services', 'image_processing_service', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'services', 'shared_utils', 'src'))

# Mock shared services before import
with patch.dict(sys.modules, {
    'config': MagicMock(),
    'logger': MagicMock(),
    'storage_service': MagicMock(),
    'database_service': MagicMock(),
    'pubsub_service': MagicMock(),
    'services.image_downloader': MagicMock(),
    'services.zip_creator': MagicMock(),
    'services.signed_url_generator': MagicMock(),
    'services.cleanup_scheduler': MagicMock(),
    'services.package_processor': MagicMock()
}):
    import main as image_main

@pytest.fixture
def app():
    """Create Flask test app."""
    image_main.app.config['TESTING'] = True
    return image_main.app.test_client()

@pytest.fixture
def valid_package_request():
    """Valid package processing request."""
    return {
        'processing_uuid': 'test-uuid-123',
        'package_uri': 'gs://test-bucket/package_001.json',
        'package_name': 'package_001.json'
    }

@pytest.fixture
def sample_package_data():
    """Sample package data with shipment information."""
    return {
        'processing_uuid': 'test-uuid-123',
        'package_name': 'package_001.json',
        'shipments': [
            {
                'shipment_id': 'SHIP_001',
                'customer': {
                    'name': 'Test Customer',
                    'email': 'test@example.com'
                },
                'images': [
                    {'url': 'gs://images/ship1_img1.jpg', 'filename': 'front.jpg'},
                    {'url': 'gs://images/ship1_img2.jpg', 'filename': 'back.jpg'}
                ]
            }
        ]
    }


class TestHealthEndpoints:
    """Test health and status endpoints."""
    
    def test_health_check(self, app):
        """Test health check endpoint returns healthy status."""
        response = app.get('/health')
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['status'] == 'healthy'
        assert data['service'] == 'image-processing-service'
        assert 'timestamp' in data

    @patch('main.database_service')
    @patch('main.storage_service')
    def test_status_check_healthy(self, mock_storage, mock_db, app):
        """Test status endpoint when all dependencies are healthy."""
        mock_db.check_connectivity.return_value = True
        mock_storage.check_bucket_access.return_value = True
        
        response = app.get('/status')
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['status'] == 'ready'
        assert data['dependencies']['database'] == 'healthy'
        assert data['dependencies']['storage'] == 'healthy'
        assert data['service'] == 'image-processing-service'

    @patch('main.database_service')
    @patch('main.storage_service')
    def test_status_check_unhealthy_storage(self, mock_storage, mock_db, app):
        """Test status endpoint when storage is unhealthy."""
        mock_db.check_connectivity.return_value = True
        mock_storage.check_bucket_access.return_value = False
        
        response = app.get('/status')
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['dependencies']['storage'] == 'unhealthy'
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


class TestProcessPackageEndpoint:
    """Test the main package processing endpoint."""
    
    @patch('main.package_processor')
    def test_process_package_success(self, mock_processor, app, valid_package_request):
        """Test successful package processing."""
        expected_result = {
            'processing_uuid': 'test-uuid-123',
            'package_name': 'package_001.json',
            'images_processed': 5,
            'zip_created': True,
            'signed_url_generated': True,
            'signed_url': 'https://signed-url.example.com/package.zip',
            'expiration_time': (datetime.now() + timedelta(hours=2)).isoformat()
        }
        mock_processor.process_complete_package.return_value = expected_result
        
        response = app.post('/process-package', json=valid_package_request)
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['processing_uuid'] == 'test-uuid-123'
        assert data['images_processed'] == 5
        assert data['zip_created'] is True
        assert data['signed_url_generated'] is True
        
        # Verify method was called with correct arguments
        mock_processor.process_complete_package.assert_called_once_with(
            processing_uuid='test-uuid-123',
            package_uri='gs://test-bucket/package_001.json',
            package_name='package_001.json',
            trace_id=unittest.mock.ANY
        )

    def test_process_package_no_data(self, app):
        """Test processing with no request data."""
        response = app.post('/process-package')
        data = json.loads(response.data)
        
        assert response.status_code == 400
        assert 'error' in data

    def test_process_package_missing_fields(self, app):
        """Test processing with missing required fields."""
        incomplete_request = {
            'processing_uuid': 'test-uuid-123'
            # Missing package_uri and package_name
        }
        
        response = app.post('/process-package', json=incomplete_request)
        data = json.loads(response.data)
        
        assert response.status_code == 400
        assert 'campos requeridos' in data['error'].lower()

    @patch('main.package_processor')
    @patch('main.pubsub_service')
    def test_process_package_exception_with_pubsub(self, mock_pubsub, mock_processor, app, valid_package_request):
        """Test exception handling with Pub/Sub error publishing."""
        mock_processor.process_complete_package.side_effect = Exception("Processing failed")
        
        response = app.post('/process-package', json=valid_package_request)
        data = json.loads(response.data)
        
        assert response.status_code == 500
        assert 'error' in data
        
        # Verify error was published to Pub/Sub
        mock_pubsub.publish_error.assert_called_once()

    @patch('main.package_processor')  
    @patch('main.pubsub_service')
    def test_process_package_pubsub_publish_fails(self, mock_pubsub, mock_processor, app, valid_package_request):
        """Test when Pub/Sub error publishing also fails."""
        mock_processor.process_complete_package.side_effect = Exception("Processing failed")
        mock_pubsub.publish_error.side_effect = Exception("Pub/Sub failed")
        
        response = app.post('/process-package', json=valid_package_request)
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
            'paquetes_completados': 3,
            'total_paquetes': 3,
            'imagenes_procesadas': 15,
            'archivos_zip_creados': 3,
            'urls_firmadas_generadas': 3,
            'fecha_inicio': datetime.now(),
            'fecha_finalizacion': datetime.now(),
            'metadatos': {'packages': ['pkg1', 'pkg2', 'pkg3']},
            'resultado': {'signed_urls': ['url1', 'url2', 'url3']},
            'error_mensaje': None
        }
        mock_db.get_image_processing_record.return_value = mock_record
        
        response = app.get('/processing-status/test-uuid-123')
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['processing_uuid'] == 'test-uuid-123'
        assert data['status'] == 'completed'
        assert data['packages_completed'] == 3
        assert data['total_packages'] == 3
        assert data['images_processed'] == 15

    @patch('main.database_service')
    def test_get_processing_status_not_found(self, mock_db, app):
        """Test status retrieval for non-existent processing."""
        mock_db.get_image_processing_record.return_value = None
        
        response = app.get('/processing-status/nonexistent-uuid')
        data = json.loads(response.data)
        
        assert response.status_code == 404
        assert 'no encontrado' in data['error']

    @patch('main.database_service')
    def test_get_processing_status_with_error(self, mock_db, app):
        """Test status retrieval when record has error message."""
        mock_record = {
            'estado': 'error',
            'paquetes_completados': 1,
            'total_paquetes': 3,
            'imagenes_procesadas': 5,
            'archivos_zip_creados': 1,
            'urls_firmadas_generadas': 1,
            'fecha_inicio': datetime.now(),
            'fecha_finalizacion': None,
            'metadatos': {},
            'resultado': None,
            'error_mensaje': 'Image download failed'
        }
        mock_db.get_image_processing_record.return_value = mock_record
        
        response = app.get('/processing-status/error-uuid')
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['status'] == 'error'
        assert data['error_message'] == 'Image download failed'

    @patch('main.database_service')
    def test_get_processing_status_exception(self, mock_db, app):
        """Test status retrieval when database exception occurs."""
        mock_db.get_image_processing_record.side_effect = Exception("Database error")
        
        response = app.get('/processing-status/test-uuid')
        data = json.loads(response.data)
        
        assert response.status_code == 500
        assert 'error' in data


class TestScheduleCleanupEndpoint:
    """Test cleanup scheduling endpoint."""
    
    @patch('main.cleanup_scheduler')
    def test_schedule_cleanup_success(self, mock_scheduler, app):
        """Test successful cleanup scheduling."""
        expected_result = {
            'processing_uuid': 'test-uuid-123',
            'cleanup_scheduled': True,
            'scheduled_for': (datetime.now() + timedelta(hours=24)).isoformat(),
            'cleanup_after_hours': 24
        }
        mock_scheduler.schedule_cleanup.return_value = expected_result
        
        request_data = {
            'processing_uuid': 'test-uuid-123',
            'cleanup_after_hours': 24
        }
        
        response = app.post('/schedule-cleanup', json=request_data)
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['cleanup_scheduled'] is True
        assert data['processing_uuid'] == 'test-uuid-123'
        
        mock_scheduler.schedule_cleanup.assert_called_once_with(
            processing_uuid='test-uuid-123',
            cleanup_after_hours=24,
            trace_id=unittest.mock.ANY
        )

    def test_schedule_cleanup_missing_uuid(self, app):
        """Test cleanup scheduling with missing processing_uuid."""
        response = app.post('/schedule-cleanup', json={})
        data = json.loads(response.data)
        
        assert response.status_code == 400
        assert 'requerido' in data['error'].lower()

    @patch('main.cleanup_scheduler')
    @patch('main.config')
    def test_schedule_cleanup_default_hours(self, mock_config, mock_scheduler, app):
        """Test cleanup scheduling with default hours from config."""
        mock_config.TEMP_FILES_CLEANUP_HOURS = 48
        expected_result = {
            'processing_uuid': 'test-uuid-123',
            'cleanup_scheduled': True,
            'scheduled_for': (datetime.now() + timedelta(hours=48)).isoformat(),
            'cleanup_after_hours': 48
        }
        mock_scheduler.schedule_cleanup.return_value = expected_result
        
        request_data = {'processing_uuid': 'test-uuid-123'}
        
        response = app.post('/schedule-cleanup', json=request_data)
        data = json.loads(response.data)
        
        assert response.status_code == 200
        mock_scheduler.schedule_cleanup.assert_called_once_with(
            processing_uuid='test-uuid-123',
            cleanup_after_hours=48,
            trace_id=unittest.mock.ANY
        )

    @patch('main.cleanup_scheduler')
    def test_schedule_cleanup_exception(self, mock_scheduler, app):
        """Test cleanup scheduling when exception occurs."""
        mock_scheduler.schedule_cleanup.side_effect = Exception("Scheduler error")
        
        request_data = {'processing_uuid': 'test-uuid-123'}
        
        response = app.post('/schedule-cleanup', json=request_data)
        data = json.loads(response.data)
        
        assert response.status_code == 500
        assert 'error' in data


class TestExecuteCleanupEndpoint:
    """Test immediate cleanup execution endpoint."""
    
    @patch('main.cleanup_scheduler')
    def test_execute_cleanup_success(self, mock_scheduler, app):
        """Test successful cleanup execution."""
        expected_result = {
            'processing_uuid': 'test-uuid-123',
            'cleanup_executed': True,
            'files_deleted': 15,
            'storage_freed_mb': 250.5,
            'execution_time': datetime.now().isoformat()
        }
        mock_scheduler.execute_cleanup_now.return_value = expected_result
        
        response = app.post('/cleanup/execute/test-uuid-123')
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['cleanup_executed'] is True
        assert data['files_deleted'] == 15
        assert data['storage_freed_mb'] == 250.5
        
        mock_scheduler.execute_cleanup_now.assert_called_once_with(
            processing_uuid='test-uuid-123',
            trace_id=unittest.mock.ANY
        )

    @patch('main.cleanup_scheduler')
    def test_execute_cleanup_exception(self, mock_scheduler, app):
        """Test cleanup execution when exception occurs."""
        mock_scheduler.execute_cleanup_now.side_effect = Exception("Cleanup failed")
        
        response = app.post('/cleanup/execute/test-uuid-123')
        data = json.loads(response.data)
        
        assert response.status_code == 500
        assert 'error' in data


@pytest.mark.integration
class TestImageProcessingServiceIntegration:
    """Integration tests that test multiple components together."""
    
    @patch('main.package_processor')
    @patch('main.cleanup_scheduler')
    @patch('main.database_service')
    def test_full_package_processing_with_cleanup_flow(self, mock_db, mock_scheduler, mock_processor, app):
        """Test complete package processing flow with cleanup scheduling."""
        # Setup package processing result
        processing_result = {
            'processing_uuid': 'integration-uuid-123',
            'package_name': 'integration_package.json',
            'images_processed': 8,
            'zip_created': True,
            'signed_url_generated': True,
            'signed_url': 'https://signed-url.example.com/package.zip',
            'expiration_time': (datetime.now() + timedelta(hours=2)).isoformat()
        }
        mock_processor.process_complete_package.return_value = processing_result
        
        # Setup cleanup scheduling result
        cleanup_result = {
            'processing_uuid': 'integration-uuid-123',
            'cleanup_scheduled': True,
            'scheduled_for': (datetime.now() + timedelta(hours=24)).isoformat(),
            'cleanup_after_hours': 24
        }
        mock_scheduler.schedule_cleanup.return_value = cleanup_result
        
        # Process package
        package_request = {
            'processing_uuid': 'integration-uuid-123',
            'package_uri': 'gs://test-bucket/integration_package.json',
            'package_name': 'integration_package.json'
        }
        
        response1 = app.post('/process-package', json=package_request)
        data1 = json.loads(response1.data)
        
        assert response1.status_code == 200
        assert data1['images_processed'] == 8
        assert data1['zip_created'] is True
        
        # Schedule cleanup
        cleanup_request = {
            'processing_uuid': 'integration-uuid-123',
            'cleanup_after_hours': 24
        }
        
        response2 = app.post('/schedule-cleanup', json=cleanup_request)
        data2 = json.loads(response2.data)
        
        assert response2.status_code == 200
        assert data2['cleanup_scheduled'] is True
        
        # Verify both services were called correctly
        mock_processor.process_complete_package.assert_called_once()
        mock_scheduler.schedule_cleanup.assert_called_once()

    @patch('main.package_processor')
    @patch('main.database_service')
    def test_package_processing_with_status_check(self, mock_db, mock_processor, app):
        """Test package processing followed by status check."""
        processing_uuid = 'status-test-uuid'
        
        # Setup processing result
        processing_result = {
            'processing_uuid': processing_uuid,
            'package_name': 'status_test.json',
            'images_processed': 3,
            'zip_created': True,
            'signed_url_generated': True
        }
        mock_processor.process_complete_package.return_value = processing_result
        
        # Setup database record for status check
        db_record = {
            'estado': 'completed',
            'paquetes_completados': 1,
            'total_paquetes': 1,
            'imagenes_procesadas': 3,
            'archivos_zip_creados': 1,
            'urls_firmadas_generadas': 1,
            'fecha_inicio': datetime.now(),
            'fecha_finalizacion': datetime.now(),
            'metadatos': {'package': 'status_test.json'},
            'resultado': processing_result,
            'error_mensaje': None
        }
        mock_db.get_image_processing_record.return_value = db_record
        
        # Process package
        package_request = {
            'processing_uuid': processing_uuid,
            'package_uri': 'gs://test-bucket/status_test.json',
            'package_name': 'status_test.json'
        }
        
        response1 = app.post('/process-package', json=package_request)
        assert response1.status_code == 200
        
        # Check status
        response2 = app.get(f'/processing-status/{processing_uuid}')
        data2 = json.loads(response2.data)
        
        assert response2.status_code == 200
        assert data2['processing_uuid'] == processing_uuid
        assert data2['status'] == 'completed'
        assert data2['images_processed'] == 3

import unittest.mock
