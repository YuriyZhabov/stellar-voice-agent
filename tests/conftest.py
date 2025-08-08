"""
Pytest configuration for LiveKit comprehensive testing.
Provides fixtures and configuration for all test suites.
"""

import pytest
import asyncio
import os
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, UTC

# Test configuration
pytest_plugins = ["pytest_asyncio"]


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_env_vars():
    """Mock environment variables for testing."""
    env_vars = {
        "LIVEKIT_URL": "wss://test.livekit.cloud",
        "LIVEKIT_API_KEY": "test_api_key",
        "LIVEKIT_API_SECRET": "test_api_secret",
        "SIP_NUMBER": "+1234567890",
        "SIP_SERVER": "sip.test.com",
        "SIP_PORT": "5060",
        "SIP_USERNAME": "test_user",
        "SIP_PASSWORD": "test_pass",
        "REDIS_URL": "redis://localhost:6379",
        "SECRET_KEY": "test_secret_key",
        "DOMAIN": "test.example.com",
        "PORT": "8000",
        "LOG_LEVEL": "INFO"
    }
    
    with patch.dict(os.environ, env_vars):
        yield env_vars


@pytest.fixture
def temp_config_dir():
    """Create temporary directory for test configuration files."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def mock_livekit_api():
    """Mock LiveKit API client."""
    with patch('livekit.api.LiveKitAPI') as mock_api:
        # Mock room service
        mock_room_service = Mock()
        mock_room_service.create_room = Mock()
        mock_room_service.list_rooms = Mock()
        mock_room_service.delete_room = Mock()
        mock_room_service.get_room = Mock()
        mock_room_service.list_participants = Mock()
        mock_room_service.get_participant = Mock()
        mock_room_service.remove_participant = Mock()
        mock_room_service.mute_published_track = Mock()
        mock_room_service.update_participant = Mock()
        mock_room_service.send_data = Mock()
        mock_room_service.update_subscriptions = Mock()
        
        # Mock egress service
        mock_egress_service = Mock()
        mock_egress_service.start_room_composite_egress = Mock()
        mock_egress_service.start_track_composite_egress = Mock()
        mock_egress_service.start_track_egress = Mock()
        mock_egress_service.list_egress = Mock()
        mock_egress_service.stop_egress = Mock()
        mock_egress_service.update_layout = Mock()
        mock_egress_service.update_stream = Mock()
        
        # Mock ingress service
        mock_ingress_service = Mock()
        mock_ingress_service.create_ingress = Mock()
        mock_ingress_service.list_ingress = Mock()
        mock_ingress_service.delete_ingress = Mock()
        mock_ingress_service.update_ingress = Mock()
        
        # Mock SIP service
        mock_sip_service = Mock()
        mock_sip_service.create_sip_inbound_trunk = Mock()
        mock_sip_service.create_sip_outbound_trunk = Mock()
        mock_sip_service.create_sip_dispatch_rule = Mock()
        mock_sip_service.create_sip_participant = Mock()
        mock_sip_service.list_sip_trunk = Mock()
        mock_sip_service.delete_sip_trunk = Mock()
        
        # Attach services to API
        mock_api_instance = Mock()
        mock_api_instance.room = mock_room_service
        mock_api_instance.egress = mock_egress_service
        mock_api_instance.ingress = mock_ingress_service
        mock_api_instance.sip = mock_sip_service
        
        mock_api.return_value = mock_api_instance
        yield mock_api_instance


@pytest.fixture
def mock_access_token():
    """Mock AccessToken for JWT testing."""
    with patch('livekit.api.AccessToken') as mock_token_class:
        mock_token = Mock()
        mock_token.with_identity = Mock(return_value=mock_token)
        mock_token.with_name = Mock(return_value=mock_token)
        mock_token.with_grants = Mock(return_value=mock_token)
        mock_token.with_ttl = Mock(return_value=mock_token)
        mock_token.to_jwt = Mock(return_value="mock_jwt_token")
        
        mock_token_class.return_value = mock_token
        yield mock_token


@pytest.fixture
def mock_video_grants():
    """Mock VideoGrants for permission testing."""
    with patch('livekit.api.VideoGrants') as mock_grants:
        yield mock_grants


@pytest.fixture
def sample_room_data():
    """Sample room data for testing."""
    return {
        "name": "test_room",
        "sid": "room_123",
        "creation_time": int(datetime.now(UTC).timestamp()),
        "empty_timeout": 300,
        "departure_timeout": 20,
        "max_participants": 10,
        "num_participants": 2,
        "metadata": '{"test": "data"}'
    }


@pytest.fixture
def sample_participant_data():
    """Sample participant data for testing."""
    return {
        "identity": "test_user",
        "sid": "participant_123",
        "name": "Test User",
        "state": "ACTIVE",
        "joined_at": int(datetime.now(UTC).timestamp()),
        "metadata": '{"role": "participant"}'
    }


@pytest.fixture
def sample_track_data():
    """Sample track data for testing."""
    return {
        "sid": "track_123",
        "name": "microphone",
        "type": "audio",
        "source": "microphone",
        "muted": False,
        "width": 0,
        "height": 0
    }


@pytest.fixture
def sample_egress_data():
    """Sample egress data for testing."""
    return {
        "egress_id": "egress_123",
        "room_name": "test_room",
        "status": "EGRESS_ACTIVE",
        "started_at": int(datetime.now(UTC).timestamp()),
        "ended_at": 0,
        "file_results": [],
        "stream_results": []
    }


@pytest.fixture
def sample_ingress_data():
    """Sample ingress data for testing."""
    return {
        "ingress_id": "ingress_123",
        "name": "test_ingress",
        "stream_key": "stream_key_123",
        "url": "rtmp://test.com/live",
        "input_type": 0,  # RTMP
        "state": "INGRESS_ACTIVE",
        "room_name": "test_room",
        "participant_identity": "streamer",
        "participant_name": "Test Streamer"
    }


@pytest.fixture
def mock_webhook_data():
    """Mock webhook event data."""
    return {
        "room_started": {
            "event": "room_started",
            "room": {
                "name": "test_room",
                "sid": "room_123",
                "creation_time": int(datetime.now(UTC).timestamp())
            }
        },
        "participant_joined": {
            "event": "participant_joined",
            "room": {"name": "test_room"},
            "participant": {
                "identity": "test_user",
                "sid": "participant_123",
                "name": "Test User"
            }
        },
        "track_published": {
            "event": "track_published",
            "room": {"name": "test_room"},
            "participant": {"identity": "test_user"},
            "track": {
                "sid": "track_123",
                "type": "audio",
                "source": "microphone"
            }
        },
        "participant_disconnected": {
            "event": "participant_disconnected",
            "room": {"name": "test_room"},
            "participant": {"identity": "test_user"}
        },
        "room_finished": {
            "event": "room_finished",
            "room": {
                "name": "test_room",
                "sid": "room_123"
            }
        }
    }


@pytest.fixture
def performance_test_config():
    """Configuration for performance tests."""
    return {
        "max_concurrent_requests": 100,
        "test_duration_seconds": 30,
        "requests_per_second": 10,
        "max_latency_ms": 1000,
        "min_success_rate": 0.95,
        "memory_limit_mb": 500,
        "cpu_limit_percent": 80
    }


@pytest.fixture
def security_test_config():
    """Configuration for security tests."""
    return {
        "max_failed_attempts": 5,
        "rate_limit_requests": 100,
        "rate_limit_window_seconds": 60,
        "token_expiry_seconds": 600,
        "admin_token_expiry_seconds": 3600,
        "suspicious_activity_threshold": 10
    }


# Pytest markers for test categorization
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "performance: mark test as a performance test"
    )
    config.addinivalue_line(
        "markers", "security: mark test as a security test"
    )
    config.addinivalue_line(
        "markers", "api: mark test as an API endpoint test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )


# Test collection hooks
def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on file names."""
    for item in items:
        # Add markers based on test file names
        if "comprehensive" in item.fspath.basename:
            item.add_marker(pytest.mark.unit)
        elif "integration_flow" in item.fspath.basename:
            item.add_marker(pytest.mark.integration)
        elif "performance_load" in item.fspath.basename:
            item.add_marker(pytest.mark.performance)
            item.add_marker(pytest.mark.slow)
        elif "security_validation" in item.fspath.basename:
            item.add_marker(pytest.mark.security)
        elif "api_endpoints" in item.fspath.basename:
            item.add_marker(pytest.mark.api)


# Async test utilities
@pytest.fixture
def async_test_timeout():
    """Default timeout for async tests."""
    return 30  # seconds


# Mock utilities
class MockAsyncContextManager:
    """Mock async context manager for testing."""
    
    def __init__(self, return_value=None):
        self.return_value = return_value
    
    async def __aenter__(self):
        return self.return_value
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.fixture
def mock_async_context_manager():
    """Factory for creating mock async context managers."""
    return MockAsyncContextManager


# Database mocking
@pytest.fixture
def mock_database():
    """Mock database connection for testing."""
    with patch('src.database.connection.DatabaseConnection') as mock_db:
        mock_instance = Mock()
        mock_instance.execute = Mock()
        mock_instance.fetch_one = Mock()
        mock_instance.fetch_all = Mock()
        mock_instance.close = Mock()
        
        mock_db.return_value = mock_instance
        yield mock_instance


# Redis mocking
@pytest.fixture
def mock_redis():
    """Mock Redis connection for testing."""
    with patch('redis.Redis') as mock_redis_class:
        mock_redis_instance = Mock()
        mock_redis_instance.get = Mock()
        mock_redis_instance.set = Mock()
        mock_redis_instance.delete = Mock()
        mock_redis_instance.exists = Mock()
        mock_redis_instance.expire = Mock()
        
        mock_redis_class.return_value = mock_redis_instance
        yield mock_redis_instance


# Logging mocking
@pytest.fixture
def mock_logger():
    """Mock logger for testing."""
    with patch('logging.getLogger') as mock_get_logger:
        mock_logger_instance = Mock()
        mock_logger_instance.debug = Mock()
        mock_logger_instance.info = Mock()
        mock_logger_instance.warning = Mock()
        mock_logger_instance.error = Mock()
        mock_logger_instance.critical = Mock()
        
        mock_get_logger.return_value = mock_logger_instance
        yield mock_logger_instance


# Test data cleanup
@pytest.fixture(autouse=True)
def cleanup_test_data():
    """Automatically cleanup test data after each test."""
    yield
    # Cleanup code would go here if needed
    pass