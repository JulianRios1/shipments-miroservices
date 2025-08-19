"""
Configuration and fixtures for pytest testing suite.
Provides shared fixtures and test configurations for all services.
"""
import pytest
import asyncio
import tempfile
import shutil
import json
import os
from unittest.mock import Mock, patch
from typing import Dict, Any, List
from datetime import datetime, timedelta

# Test data fixtures
@pytest.fixture
def sample_shipment_json():
    """Sample shipment JSON for testing."""
    return {
        "shipment_id": "SHIP_001",
        "customer": {
            "name": "Test Customer",
            "email": "test@example.com"
        },
        "images": [
            {
                "url": "https://storage.googleapis.com/test-bucket/image1.jpg",
                "filename": "package_front.jpg"
            },
            {
                "url": "https://storage.googleapis.com/test-bucket/image2.jpg", 
                "filename": "package_back.jpg"
            },
            {
                "url": "https://storage.googleapis.com/test-bucket/image3.jpg",
                "filename": "contents.jpg"
            }
        ]
    }

@pytest.fixture
def sample_batch_json():
    """Sample batch with multiple shipments for testing division service."""
    return {
        "batch_id": "BATCH_001",
        "shipments": [
            {
                "shipment_id": "SHIP_001",
                "customer": {
                    "name": "Customer 1",
                    "email": "customer1@example.com"
                },
                "images": [
                    {"url": "https://storage.googleapis.com/test-bucket/ship1_img1.jpg", "filename": "package.jpg"}
                ]
            },
            {
                "shipment_id": "SHIP_002", 
                "customer": {
                    "name": "Customer 2",
                    "email": "customer2@example.com"
                },
                "images": [
                    {"url": "https://storage.googleapis.com/test-bucket/ship2_img1.jpg", "filename": "package.jpg"}
                ]
            }
        ]
    }

@pytest.fixture
def temp_directory():
    """Create a temporary directory for tests."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)

@pytest.fixture
def mock_gcs_client():
    """Mock Google Cloud Storage client."""
    with patch('google.cloud.storage.Client') as mock_client:
        mock_bucket = Mock()
        mock_blob = Mock()
        mock_blob.generate_signed_url.return_value = "https://signed-url.example.com"
        mock_bucket.blob.return_value = mock_blob
        mock_client.return_value.bucket.return_value = mock_bucket
        yield mock_client

@pytest.fixture
def mock_pubsub_client():
    """Mock Google Cloud Pub/Sub client."""
    with patch('google.cloud.pubsub_v1.PublisherClient') as mock_publisher:
        mock_publisher.return_value.publish.return_value.result.return_value = "message-id"
        yield mock_publisher

@pytest.fixture
def mock_database():
    """Mock database connection."""
    with patch('psycopg2.connect') as mock_connect:
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        yield mock_conn

@pytest.fixture
def mock_smtp_server():
    """Mock SMTP server for email testing."""
    with patch('smtplib.SMTP') as mock_smtp:
        mock_server = Mock()
        mock_smtp.return_value = mock_server
        yield mock_server

@pytest.fixture
def test_config():
    """Test configuration settings."""
    return {
        "GCP_PROJECT_ID": "test-project",
        "GCS_BUCKET": "test-bucket",
        "PUBSUB_TOPIC": "test-topic",
        "DB_HOST": "localhost",
        "DB_NAME": "test_db",
        "DB_USER": "test_user",
        "DB_PASSWORD": "test_password",
        "SMTP_SERVER": "smtp.gmail.com",
        "SMTP_PORT": "587",
        "SMTP_USER": "test@gmail.com",
        "SMTP_PASSWORD": "test_password"
    }

@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch, test_config):
    """Setup test environment variables."""
    for key, value in test_config.items():
        monkeypatch.setenv(key, value)

# Event loop fixture for async tests
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

# Utility functions for tests
def create_mock_image_data(filename: str = "test.jpg", size: int = 1024) -> bytes:
    """Create mock image data for testing."""
    return b"mock_image_data" * (size // 15)  # Approximate size

def create_mock_zip_data(filenames: List[str]) -> bytes:
    """Create mock ZIP data for testing."""
    return b"mock_zip_data_for_files_" + str(len(filenames)).encode()

# Test markers
pytestmark = pytest.mark.asyncio
