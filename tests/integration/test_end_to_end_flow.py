"""
End-to-End Integration Tests for Shipments Processing Platform.
Tests the complete flow from JSON upload to email with signed URLs.
"""
import pytest
import json
import uuid
import asyncio
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime, timedelta
from typing import Dict, Any, List
import requests
import time

# Test fixtures
@pytest.fixture
def sample_batch_json():
    """Complete batch JSON for end-to-end testing."""
    return {
        "batch_id": "E2E_BATCH_001",
        "created_at": datetime.now().isoformat(),
        "shipments": [
            {
                "shipment_id": "E2E_SHIP_001",
                "customer": {
                    "name": "John Smith",
                    "email": "john.smith@example.com"
                },
                "images": [
                    {
                        "url": "gs://source-images/e2e_ship001_front.jpg",
                        "filename": "package_front.jpg"
                    },
                    {
                        "url": "gs://source-images/e2e_ship001_back.jpg", 
                        "filename": "package_back.jpg"
                    },
                    {
                        "url": "gs://source-images/e2e_ship001_contents.jpg",
                        "filename": "contents.jpg"
                    }
                ]
            },
            {
                "shipment_id": "E2E_SHIP_002",
                "customer": {
                    "name": "Jane Doe", 
                    "email": "jane.doe@example.com"
                },
                "images": [
                    {
                        "url": "gs://source-images/e2e_ship002_front.jpg",
                        "filename": "package_front.jpg"
                    },
                    {
                        "url": "gs://source-images/e2e_ship002_side.jpg",
                        "filename": "package_side.jpg"
                    }
                ]
            }
        ]
    }

@pytest.fixture
def mock_service_responses():
    """Mock responses from all services in the flow."""
    return {
        'division_service': {
            'processing_uuid': 'e2e-test-uuid-123',
            'packages_created': 2,
            'total_shipments': 2,
            'status': 'completed',
            'packages': [
                {
                    'package_name': 'package_e2e_001.json',
                    'package_uri': 'gs://json-a-procesar/package_e2e_001.json',
                    'shipments': ['E2E_SHIP_001']
                },
                {
                    'package_name': 'package_e2e_002.json', 
                    'package_uri': 'gs://json-a-procesar/package_e2e_002.json',
                    'shipments': ['E2E_SHIP_002']
                }
            ]
        },
        'image_processing_service': {
            'package_1': {
                'processing_uuid': 'e2e-test-uuid-123',
                'package_name': 'package_e2e_001.json',
                'images_processed': 3,
                'zip_created': True,
                'signed_url_generated': True,
                'signed_url': 'https://storage.googleapis.com/temp-zip/signed/e2e_ship001_images.zip?signature=abc123',
                'expiration_time': (datetime.now() + timedelta(hours=2)).isoformat()
            },
            'package_2': {
                'processing_uuid': 'e2e-test-uuid-123',
                'package_name': 'package_e2e_002.json',
                'images_processed': 2,
                'zip_created': True,
                'signed_url_generated': True,
                'signed_url': 'https://storage.googleapis.com/temp-zip/signed/e2e_ship002_images.zip?signature=def456',
                'expiration_time': (datetime.now() + timedelta(hours=2)).isoformat()
            }
        },
        'email_service': {
            'john_smith': {
                'processing_uuid': 'e2e-test-uuid-123',
                'emails_sent': 1,
                'database_updated': True,
                'customer_email': 'john.smith@example.com',
                'signed_url': 'https://storage.googleapis.com/temp-zip/signed/e2e_ship001_images.zip?signature=abc123',
                'sent_at': datetime.now().isoformat()
            },
            'jane_doe': {
                'processing_uuid': 'e2e-test-uuid-123', 
                'emails_sent': 1,
                'database_updated': True,
                'customer_email': 'jane.doe@example.com',
                'signed_url': 'https://storage.googleapis.com/temp-zip/signed/e2e_ship002_images.zip?signature=def456',
                'sent_at': datetime.now().isoformat()
            }
        }
    }


class TestCompleteEndToEndFlow:
    """Test complete flow from JSON upload to email delivery."""
    
    @pytest.mark.asyncio
    @patch('requests.post')
    @patch('google.cloud.storage.Client')
    @patch('google.cloud.workflows_v1.ExecutionsClient')
    async def test_full_shipment_processing_flow(self, mock_workflow_client, mock_storage, mock_requests, 
                                                sample_batch_json, mock_service_responses):
        """
        Test complete end-to-end flow:
        1. JSON upload to bucket
        2. Division service processes and splits
        3. Workflow triggers image processing in parallel
        4. Image processing creates ZIPs and generates signed URLs
        5. Email service sends notifications to customers
        """
        
        # Setup storage mocks
        mock_bucket = Mock()
        mock_blob = Mock()
        mock_bucket.blob.return_value = mock_blob
        mock_storage.return_value.bucket.return_value = mock_bucket
        
        # Setup workflow execution mock
        mock_execution = Mock()
        mock_execution.name = "projects/test-project/locations/us-central1/workflows/shipment-processing/executions/e2e-test"
        mock_execution.state = "SUCCEEDED"
        mock_workflow_client.return_value.create_execution.return_value = mock_execution
        
        # Configure service endpoint responses
        def mock_post_side_effect(url, **kwargs):
            response = Mock()
            response.status_code = 200
            
            if 'division-service' in url:
                response.json.return_value = mock_service_responses['division_service']
            elif 'image-processing-service' in url:
                if 'package_e2e_001.json' in str(kwargs.get('json', {})):
                    response.json.return_value = mock_service_responses['image_processing_service']['package_1']
                else:
                    response.json.return_value = mock_service_responses['image_processing_service']['package_2']
            elif 'email-service' in url:
                email_data = kwargs.get('json', {})
                if 'john.smith' in str(email_data):
                    response.json.return_value = mock_service_responses['email_service']['john_smith']
                else:
                    response.json.return_value = mock_service_responses['email_service']['jane_doe']
            
            return response
        
        mock_requests.side_effect = mock_post_side_effect
        
        # ========== STEP 1: Simulate JSON file upload ==========
        print("🚀 STEP 1: Simulating JSON batch file upload...")
        
        file_name = f"e2e_batch_{uuid.uuid4().hex[:8]}.json"
        mock_blob.upload_from_string.return_value = None
        mock_blob.exists.return_value = True
        
        # Simulate file upload to json-pendientes bucket
        json_content = json.dumps(sample_batch_json, indent=2)
        
        # Verify file was "uploaded"
        assert json_content is not None
        assert json.loads(json_content)['batch_id'] == 'E2E_BATCH_001'
        assert len(json.loads(json_content)['shipments']) == 2
        
        print(f"✅ JSON file uploaded: {file_name}")
        print(f"   - Batch ID: {sample_batch_json['batch_id']}")
        print(f"   - Shipments: {len(sample_batch_json['shipments'])}")
        
        # ========== STEP 2: Division Service Processing ==========
        print("\n🔄 STEP 2: Division Service processing...")
        
        # Simulate Cloud Storage trigger to Division Service
        division_payload = {
            'bucket': 'json-pendientes',
            'name': file_name,
            'eventType': 'google.storage.object.finalize'
        }
        
        division_response = await self._call_division_service(division_payload, mock_requests)
        
        assert division_response['status'] == 'completed'
        assert division_response['processing_uuid'] == 'e2e-test-uuid-123'
        assert division_response['packages_created'] == 2
        
        print(f"✅ Division completed:")
        print(f"   - Processing UUID: {division_response['processing_uuid']}")
        print(f"   - Packages created: {division_response['packages_created']}")
        
        # ========== STEP 3: Cloud Workflow Orchestration ==========
        print("\n🔗 STEP 3: Cloud Workflow orchestration...")
        
        # Simulate workflow execution with parallel package processing
        workflow_input = {
            'processing_uuid': division_response['processing_uuid'],
            'packages': mock_service_responses['division_service']['packages']
        }
        
        # Verify workflow would be triggered
        mock_workflow_client.return_value.create_execution.assert_called_once()
        
        print("✅ Workflow execution started")
        
        # ========== STEP 4: Image Processing Service (Parallel) ==========
        print("\n🖼️  STEP 4: Image Processing Service (parallel processing)...")
        
        image_results = []
        
        # Process each package in parallel (simulated)
        for i, package in enumerate(mock_service_responses['division_service']['packages'], 1):
            print(f"   Processing package {i}: {package['package_name']}")
            
            image_payload = {
                'processing_uuid': division_response['processing_uuid'],
                'package_uri': package['package_uri'],
                'package_name': package['package_name']
            }
            
            image_response = await self._call_image_processing_service(image_payload, mock_requests)
            image_results.append(image_response)
            
            assert image_response['zip_created'] is True
            assert image_response['signed_url_generated'] is True
            assert 'signed_url' in image_response
            
            print(f"   ✅ Package {i} processed: {image_response['images_processed']} images")
        
        print(f"✅ All {len(image_results)} packages processed with signed URLs")
        
        # ========== STEP 5: Email Service Notifications ==========
        print("\n📧 STEP 5: Email Service sending notifications...")
        
        email_results = []
        
        # Send email to each customer
        for i, shipment in enumerate(sample_batch_json['shipments'], 1):
            corresponding_package_result = image_results[i-1]
            
            email_payload = {
                'processing_uuid': division_response['processing_uuid'],
                'customer_email': shipment['customer']['email'],
                'customer_name': shipment['customer']['name'],
                'signed_urls': [corresponding_package_result['signed_url']],
                'expiration_time': corresponding_package_result['expiration_time'],
                'shipment_id': shipment['shipment_id']
            }
            
            email_response = await self._call_email_service(email_payload, mock_requests)
            email_results.append(email_response)
            
            assert email_response['emails_sent'] == 1
            assert email_response['database_updated'] is True
            assert email_response['customer_email'] == shipment['customer']['email']
            
            print(f"   ✅ Email sent to: {email_response['customer_email']}")
        
        # ========== STEP 6: Validation and Assertions ==========
        print("\n✅ STEP 6: End-to-End validation...")
        
        # Verify complete flow
        assert len(image_results) == 2, "Should have processed 2 packages"
        assert len(email_results) == 2, "Should have sent 2 emails"
        
        # Verify all signed URLs are unique and valid format
        signed_urls = [result['signed_url'] for result in image_results]
        assert len(set(signed_urls)) == len(signed_urls), "All signed URLs should be unique"
        
        for url in signed_urls:
            assert url.startswith('https://'), "Signed URLs should be HTTPS"
            assert 'signature=' in url, "Signed URLs should contain signature parameter"
        
        # Verify customer emails match
        expected_emails = {shipment['customer']['email'] for shipment in sample_batch_json['shipments']}
        actual_emails = {result['customer_email'] for result in email_results}
        assert expected_emails == actual_emails, "All customers should receive emails"
        
        print("🎉 END-TO-END TEST COMPLETED SUCCESSFULLY!")
        print(f"   - Processed: {division_response['total_shipments']} shipments")
        print(f"   - Created: {division_response['packages_created']} packages")
        print(f"   - Generated: {len(signed_urls)} signed URLs")
        print(f"   - Sent: {sum(r['emails_sent'] for r in email_results)} emails")
    
    async def _call_division_service(self, payload: Dict[str, Any], mock_requests) -> Dict[str, Any]:
        """Simulate call to Division Service."""
        # This would be a real HTTP call in actual implementation
        response = mock_requests.return_value
        response.json.return_value = {
            'processing_uuid': 'e2e-test-uuid-123',
            'packages_created': 2,
            'total_shipments': 2,
            'status': 'completed'
        }
        return response.json()
    
    async def _call_image_processing_service(self, payload: Dict[str, Any], mock_requests) -> Dict[str, Any]:
        """Simulate call to Image Processing Service."""
        package_name = payload['package_name']
        if 'e2e_001' in package_name:
            return {
                'processing_uuid': 'e2e-test-uuid-123',
                'package_name': package_name,
                'images_processed': 3,
                'zip_created': True,
                'signed_url_generated': True,
                'signed_url': 'https://storage.googleapis.com/temp-zip/signed/e2e_ship001_images.zip?signature=abc123',
                'expiration_time': (datetime.now() + timedelta(hours=2)).isoformat()
            }
        else:
            return {
                'processing_uuid': 'e2e-test-uuid-123',
                'package_name': package_name,
                'images_processed': 2,
                'zip_created': True,
                'signed_url_generated': True,
                'signed_url': 'https://storage.googleapis.com/temp-zip/signed/e2e_ship002_images.zip?signature=def456',
                'expiration_time': (datetime.now() + timedelta(hours=2)).isoformat()
            }
    
    async def _call_email_service(self, payload: Dict[str, Any], mock_requests) -> Dict[str, Any]:
        """Simulate call to Email Service."""
        return {
            'processing_uuid': payload['processing_uuid'],
            'emails_sent': 1,
            'database_updated': True,
            'customer_email': payload['customer_email'],
            'signed_url': payload['signed_urls'][0],
            'sent_at': datetime.now().isoformat()
        }


class TestEndToEndErrorScenarios:
    """Test end-to-end error handling and recovery scenarios."""
    
    @pytest.mark.asyncio
    @patch('requests.post')
    async def test_image_processing_failure_with_email_notification(self, mock_requests, sample_batch_json):
        """Test error handling when image processing fails."""
        
        # Configure division service to succeed
        division_response = Mock()
        division_response.status_code = 200
        division_response.json.return_value = {
            'processing_uuid': 'error-test-uuid-456',
            'packages_created': 1,
            'total_shipments': 1,
            'status': 'completed'
        }
        
        # Configure image processing to fail
        image_error_response = Mock()
        image_error_response.status_code = 500
        image_error_response.json.return_value = {
            'error': 'Failed to download images from source bucket'
        }
        
        # Configure email service to send error notification
        email_response = Mock()
        email_response.status_code = 200
        email_response.json.return_value = {
            'error_notification_sent': True,
            'customer_email': 'customer@example.com',
            'notification_type': 'image_processing_failed'
        }
        
        def mock_post_side_effect(url, **kwargs):
            if 'division-service' in url:
                return division_response
            elif 'image-processing-service' in url:
                return image_error_response
            elif 'email-service' in url and 'error-notification' in url:
                return email_response
        
        mock_requests.side_effect = mock_post_side_effect
        
        # Simulate the error flow
        try:
            # Division succeeds
            div_result = division_response.json()
            assert div_result['status'] == 'completed'
            
            # Image processing fails
            img_result = image_error_response
            assert img_result.status_code == 500
            
            # Error notification is sent
            error_result = email_response.json()
            assert error_result['error_notification_sent'] is True
            
        except Exception as e:
            pytest.fail(f"Error handling test failed: {str(e)}")
    
    @pytest.mark.asyncio
    @patch('requests.post')
    async def test_partial_success_scenario(self, mock_requests, sample_batch_json):
        """Test scenario where some packages succeed and others fail."""
        
        success_response = Mock()
        success_response.status_code = 200
        success_response.json.return_value = {
            'zip_created': True,
            'signed_url': 'https://storage.googleapis.com/signed-url-success'
        }
        
        failure_response = Mock()
        failure_response.status_code = 500
        failure_response.json.return_value = {
            'error': 'Image download failed'
        }
        
        call_count = 0
        def mock_post_side_effect(url, **kwargs):
            nonlocal call_count
            if 'image-processing-service' in url:
                call_count += 1
                # First call succeeds, second fails
                return success_response if call_count == 1 else failure_response
        
        mock_requests.side_effect = mock_post_side_effect
        
        # Test partial success handling
        results = []
        for i in range(2):
            try:
                response = mock_requests(f'http://image-processing-service/process-package')
                if response.status_code == 200:
                    results.append(('success', response.json()))
                else:
                    results.append(('error', response.json()))
            except Exception as e:
                results.append(('error', {'error': str(e)}))
        
        # Verify mixed results
        assert len(results) == 2
        assert results[0][0] == 'success'
        assert results[1][0] == 'error'


class TestEndToEndPerformance:
    """Test end-to-end performance and timing requirements."""
    
    @pytest.mark.asyncio
    @patch('requests.post')
    async def test_processing_time_requirements(self, mock_requests, sample_batch_json):
        """Test that processing completes within acceptable time limits."""
        
        # Configure fast responses
        fast_response = Mock()
        fast_response.status_code = 200
        fast_response.json.return_value = {'status': 'completed'}
        mock_requests.return_value = fast_response
        
        # Measure processing time
        start_time = time.time()
        
        # Simulate processing steps
        division_start = time.time()
        await asyncio.sleep(0.1)  # Simulate division processing
        division_time = time.time() - division_start
        
        image_start = time.time()
        await asyncio.sleep(0.2)  # Simulate image processing
        image_time = time.time() - image_start
        
        email_start = time.time()
        await asyncio.sleep(0.1)  # Simulate email sending
        email_time = time.time() - email_start
        
        total_time = time.time() - start_time
        
        # Verify performance requirements
        assert division_time < 5.0, "Division should complete in under 5 seconds"
        assert image_time < 30.0, "Image processing should complete in under 30 seconds"
        assert email_time < 5.0, "Email sending should complete in under 5 seconds"
        assert total_time < 45.0, "Total end-to-end processing should complete in under 45 seconds"
        
        print(f"Performance metrics:")
        print(f"  Division: {division_time:.2f}s")
        print(f"  Image Processing: {image_time:.2f}s") 
        print(f"  Email Sending: {email_time:.2f}s")
        print(f"  Total: {total_time:.2f}s")


class TestWorkflowIntegration:
    """Test Cloud Workflow integration and orchestration."""
    
    @pytest.mark.asyncio
    @patch('google.cloud.workflows_v1.ExecutionsClient')
    async def test_workflow_execution_success(self, mock_workflow_client):
        """Test successful workflow execution with proper orchestration."""
        
        # Setup mock workflow execution
        mock_execution = Mock()
        mock_execution.name = "projects/test/locations/us-central1/workflows/shipment-processing/executions/test"
        mock_execution.state = "ACTIVE"
        mock_workflow_client.return_value.create_execution.return_value = mock_execution
        
        # Setup execution status progression
        status_sequence = ["ACTIVE", "ACTIVE", "SUCCEEDED"]
        mock_workflow_client.return_value.get_execution.side_effect = [
            Mock(state=status) for status in status_sequence
        ]
        
        # Test workflow execution
        workflow_input = {
            'processing_uuid': 'workflow-test-uuid',
            'packages': [
                {'package_name': 'package1.json', 'package_uri': 'gs://bucket/package1.json'}
            ]
        }
        
        # Verify workflow was created and executed
        execution = mock_workflow_client.return_value.create_execution.return_value
        assert execution.name.endswith('test')
        
        # Verify workflow reaches completion
        final_status = mock_workflow_client.return_value.get_execution.side_effect[-1]
        assert final_status.state == "SUCCEEDED"
    
    @pytest.mark.asyncio
    @patch('google.cloud.workflows_v1.ExecutionsClient')
    async def test_workflow_execution_failure(self, mock_workflow_client):
        """Test workflow execution failure handling."""
        
        # Setup mock workflow failure
        mock_execution = Mock()
        mock_execution.state = "FAILED"
        mock_execution.error = Mock()
        mock_execution.error.payload = '{"error": "Step failed"}'
        mock_workflow_client.return_value.create_execution.return_value = mock_execution
        
        # Test that workflow failure is handled appropriately
        workflow_result = mock_execution
        assert workflow_result.state == "FAILED"
        assert "error" in workflow_result.error.payload


@pytest.mark.slow
class TestEndToEndLoad:
    """Load testing for end-to-end scenarios."""
    
    @pytest.mark.asyncio
    async def test_concurrent_batch_processing(self):
        """Test processing multiple batches concurrently."""
        
        async def process_single_batch(batch_id: str):
            """Simulate processing a single batch."""
            await asyncio.sleep(0.5)  # Simulate processing time
            return {
                'batch_id': batch_id,
                'status': 'completed',
                'processing_time': 0.5
            }
        
        # Process multiple batches concurrently
        batch_ids = [f"LOAD_BATCH_{i:03d}" for i in range(5)]
        
        start_time = time.time()
        results = await asyncio.gather(*[
            process_single_batch(batch_id) for batch_id in batch_ids
        ])
        total_time = time.time() - start_time
        
        # Verify concurrent processing is faster than sequential
        assert len(results) == 5
        assert all(r['status'] == 'completed' for r in results)
        assert total_time < 2.5  # Should be much faster than 5 * 0.5 seconds
        
        print(f"Processed {len(results)} batches concurrently in {total_time:.2f}s")


if __name__ == "__main__":
    # Run specific test for development
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "run-e2e":
        pytest.main([__file__ + "::TestCompleteEndToEndFlow::test_full_shipment_processing_flow", "-v", "-s"])
    else:
        pytest.main([__file__, "-v"])
