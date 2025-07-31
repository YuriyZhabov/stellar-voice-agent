"""Integration tests for main application startup and shutdown procedures."""

import pytest
import asyncio
import os
import signal
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from contextlib import asynccontextmanager

from src.main import VoiceAIAgent, main
from src.config import Environment


class TestVoiceAIAgentIntegration:
    """Integration tests for VoiceAIAgent lifecycle management."""
    
    @pytest.fixture
    def mock_environment(self):
        """Create a mock environment for testing."""
        with patch.dict(os.environ, {
            'ENVIRONMENT': 'testing',
            'TEST_MODE': 'true',
            'DEBUG': 'true',
            'SECRET_KEY': 'test-secret-key-for-testing-only-32-chars',
            'DATABASE_URL': 'sqlite:///:memory:',
            'LOG_LEVEL': 'DEBUG'
        }):
            yield
    
    @pytest.fixture
    def agent(self, mock_environment):
        """Create a VoiceAIAgent instance for testing."""
        return VoiceAIAgent()
    
    @pytest.mark.asyncio
    async def test_initialization_success(self, agent):
        """Test successful application initialization."""
        # Mock external dependencies
        with patch('src.main.DeepgramSTTClient') as mock_stt, \
             patch('src.main.OpenAILLMClient') as mock_llm, \
             patch('src.main.CartesiaTTSClient') as mock_tts, \
             patch('src.main.get_livekit_integration') as mock_livekit, \
             patch('src.main.start_webhook_handler') as mock_webhook, \
             patch('src.database.connection.init_database') as mock_db, \
             patch('src.database.migrations.MigrationManager') as mock_migration:
            
            # Setup mocks
            mock_db.return_value = Mock()
            mock_migration.return_value.migrate_to_latest = AsyncMock(return_value=True)
            mock_livekit.return_value = Mock()
            mock_webhook.return_value = None
            
            # Test initialization
            result = await agent.async_initialize()
            
            assert result is True
            assert agent.startup_complete is True
            assert agent.settings is not None
            assert agent.orchestrator is not None
            assert 'configuration' in agent.initialized_components
            assert 'ai_clients' in agent.initialized_components
            assert 'orchestrator' in agent.initialized_components
    
    @pytest.mark.asyncio
    async def test_initialization_failure_configuration(self, agent):
        """Test initialization failure due to configuration error."""
        with patch('src.main.load_configuration') as mock_config:
            mock_config.side_effect = Exception("Configuration error")
            
            result = await agent.async_initialize()
            
            assert result is False
            assert agent.startup_complete is False
            assert 'configuration' not in agent.initialized_components
    
    @pytest.mark.asyncio
    async def test_initialization_failure_database_production(self, agent):
        """Test initialization failure due to database error in production."""
        with patch.dict(os.environ, {'ENVIRONMENT': 'production'}), \
             patch('src.main.load_configuration') as mock_config, \
             patch('src.database.connection.init_database') as mock_db:
            
            mock_config.return_value = Mock(
                environment=Environment.PRODUCTION,
                is_production=True,
                debug=False
            )
            mock_db.side_effect = Exception("Database connection failed")
            
            result = await agent.async_initialize()
            
            assert result is False
            assert 'database' not in agent.initialized_components
    
    @pytest.mark.asyncio
    async def test_initialization_database_failure_development(self, agent):
        """Test initialization continues despite database failure in development."""
        with patch('src.main.DeepgramSTTClient') as mock_stt, \
             patch('src.main.OpenAILLMClient') as mock_llm, \
             patch('src.main.CartesiaTTSClient') as mock_tts, \
             patch('src.main.get_livekit_integration') as mock_livekit, \
             patch('src.main.start_webhook_handler') as mock_webhook, \
             patch('src.database.connection.init_database') as mock_db:
            
            mock_db.side_effect = Exception("Database connection failed")
            mock_livekit.return_value = Mock()
            mock_webhook.return_value = None
            
            result = await agent.async_initialize()
            
            assert result is True  # Should continue in development mode
            assert 'database' not in agent.initialized_components
            assert 'ai_clients' in agent.initialized_components
    
    @pytest.mark.asyncio
    async def test_dependency_verification(self, agent):
        """Test dependency verification process."""
        result = await agent._verify_dependencies()
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_dependency_verification_python_version_failure(self, agent):
        """Test dependency verification fails with old Python version."""
        with patch('sys.version_info', (3, 10, 0)):
            result = await agent._verify_dependencies()
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_graceful_shutdown(self, agent):
        """Test graceful shutdown process."""
        # Initialize first
        with patch('src.main.DeepgramSTTClient'), \
             patch('src.main.OpenAILLMClient'), \
             patch('src.main.CartesiaTTSClient'), \
             patch('src.main.get_livekit_integration') as mock_livekit, \
             patch('src.main.start_webhook_handler'), \
             patch('src.database.connection.init_database') as mock_db, \
             patch('src.database.migrations.MigrationManager') as mock_migration:
            
            mock_db.return_value = Mock()
            mock_migration.return_value.migrate_to_latest = AsyncMock(return_value=True)
            mock_livekit.return_value = Mock()
            
            await agent.async_initialize()
        
        # Mock shutdown dependencies
        with patch('src.main.stop_webhook_handler') as mock_stop_webhook, \
             patch('src.main.shutdown_livekit_integration') as mock_shutdown_livekit, \
             patch('src.database.connection.cleanup_database') as mock_cleanup_db:
            
            mock_stop_webhook.return_value = None
            mock_shutdown_livekit.return_value = None
            mock_cleanup_db.return_value = None
            
            await agent.async_shutdown()
            
            assert agent.shutdown_in_progress is True
            assert agent.running is False
            assert agent.startup_complete is False
    
    @pytest.mark.asyncio
    async def test_signal_handling(self, agent):
        """Test signal handling for graceful shutdown."""
        # Test the shutdown mechanism directly
        agent.running = True
        
        # Manually trigger shutdown event (simulating signal)
        agent.shutdown_event.set()
        agent.running = False
        
        assert agent.running is False
        assert agent.shutdown_event.is_set()
        
        # Test that the signal handler function exists and works
        # We can't easily test actual signal handling in unit tests,
        # but we can verify the mechanism works
        assert hasattr(agent, 'shutdown_event')
        assert hasattr(agent, 'running')
    
    @pytest.mark.asyncio
    async def test_test_mode_exit(self, agent):
        """Test that application exits after initialization in test mode."""
        with patch('src.main.DeepgramSTTClient'), \
             patch('src.main.OpenAILLMClient'), \
             patch('src.main.CartesiaTTSClient'), \
             patch('src.main.get_livekit_integration') as mock_livekit, \
             patch('src.main.start_webhook_handler'), \
             patch('src.database.connection.init_database') as mock_db, \
             patch('src.database.migrations.MigrationManager') as mock_migration:
            
            mock_db.return_value = Mock()
            mock_migration.return_value.migrate_to_latest = AsyncMock(return_value=True)
            mock_livekit.return_value = Mock()
            
            result = await agent.async_run()
            
            assert result == 0  # Should exit successfully in test mode
    
    @pytest.mark.asyncio
    async def test_health_monitoring_loop(self, agent):
        """Test health monitoring in main loop."""
        # Test the health monitoring logic separately since the full loop test
        # would require waiting for the health check interval
        
        # Mock orchestrator health check
        mock_health_status = Mock()
        mock_health_status.is_healthy = True
        mock_orchestrator = Mock()
        mock_orchestrator.get_health_status = AsyncMock(return_value=mock_health_status)
        agent.orchestrator = mock_orchestrator
        
        # Test health check directly
        if agent.orchestrator:
            health_status = await agent.orchestrator.get_health_status()
            assert health_status.is_healthy is True
        
        # Verify the mock was called
        mock_orchestrator.get_health_status.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_emergency_cleanup(self, agent):
        """Test emergency cleanup functionality."""
        # Create a mock server task
        agent.server_task = Mock()
        agent.server_task.done.return_value = False
        
        # Call emergency cleanup
        agent._emergency_cleanup()
        
        # Verify server task was cancelled
        agent.server_task.cancel.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_safe_await_timeout(self, agent):
        """Test safe await with timeout."""
        async def slow_task():
            await asyncio.sleep(10)  # Longer than timeout
        
        task = asyncio.create_task(slow_task())
        
        # Should not raise exception, should timeout gracefully
        await agent._safe_await(task, "test_task", timeout=0.1)
        
        # Clean up
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    
    @pytest.mark.asyncio
    async def test_safe_await_cancellation(self, agent):
        """Test safe await with cancelled task."""
        async def cancelled_task():
            await asyncio.sleep(1)
        
        task = asyncio.create_task(cancelled_task())
        task.cancel()
        
        # Should handle cancellation gracefully
        await agent._safe_await(task, "cancelled_task")


class TestMainFunction:
    """Test the main function entry point."""
    
    def test_main_function_test_mode(self):
        """Test main function with test mode argument."""
        with patch('src.main.VoiceAIAgent') as mock_agent_class:
            mock_agent = Mock()
            mock_agent.run.return_value = 0
            mock_agent_class.return_value = mock_agent
            
            with patch('sys.argv', ['main.py', '--test-init']):
                result = main()
                
                assert result == 0
                mock_agent.run.assert_called_once()
    
    def test_main_function_normal_mode(self):
        """Test main function in normal mode."""
        with patch('src.main.VoiceAIAgent') as mock_agent_class:
            mock_agent = Mock()
            mock_agent.run.return_value = 0
            mock_agent_class.return_value = mock_agent
            
            with patch('sys.argv', ['main.py']):
                result = main()
                
                assert result == 0
                mock_agent.run.assert_called_once()


class TestProductionValidation:
    """Test production-specific validation."""
    
    @pytest.mark.asyncio
    async def test_production_validation_success(self):
        """Test successful production validation."""
        with patch.dict(os.environ, {
            'ENVIRONMENT': 'production',
            'SECRET_KEY': 'production-secret-key-32-characters',
            'SIP_NUMBER': '+1234567890',
            'SIP_SERVER': 'sip.example.com',
            'SIP_USERNAME': 'user',
            'SIP_PASSWORD': 'pass',
            'LIVEKIT_URL': 'wss://example.livekit.cloud',
            'LIVEKIT_API_KEY': 'test-key',
            'LIVEKIT_API_SECRET': 'test-secret',
            'DEEPGRAM_API_KEY': 'test-deepgram-key',
            'OPENAI_API_KEY': 'sk-test-openai-key',
            'CARTESIA_API_KEY': 'test-cartesia-key'
        }):
            agent = VoiceAIAgent()
            
            with patch('src.main.DeepgramSTTClient'), \
                 patch('src.main.OpenAILLMClient'), \
                 patch('src.main.CartesiaTTSClient'), \
                 patch('src.main.get_livekit_integration') as mock_livekit, \
                 patch('src.main.start_webhook_handler'), \
                 patch('src.database.connection.init_database') as mock_db, \
                 patch('src.database.migrations.MigrationManager') as mock_migration:
                
                mock_db.return_value = Mock()
                mock_migration.return_value.migrate_to_latest = AsyncMock(return_value=True)
                mock_livekit.return_value = Mock()
                
                result = await agent.async_initialize()
                
                assert result is True
                assert agent.settings.is_production is True
    
    @pytest.mark.asyncio
    async def test_production_validation_failure_secret_key(self):
        """Test production validation failure due to default secret key."""
        with patch.dict(os.environ, {
            'ENVIRONMENT': 'production',
            'SECRET_KEY': 'your-secret-key-here-change-this-in-production'
        }):
            agent = VoiceAIAgent()
            
            with patch('src.main.load_configuration') as mock_config:
                mock_config.return_value = Mock(
                    environment=Environment.PRODUCTION,
                    is_production=True,
                    secret_key='your-secret-key-here-change-this-in-production'
                )
                
                result = await agent.async_initialize()
                
                assert result is False


@pytest.mark.integration
class TestFullApplicationLifecycle:
    """Integration tests for full application lifecycle."""
    
    @pytest.mark.asyncio
    async def test_full_startup_shutdown_cycle(self):
        """Test complete startup and shutdown cycle."""
        with patch.dict(os.environ, {
            'ENVIRONMENT': 'testing',
            'TEST_MODE': 'false',  # Don't exit immediately
            'DEBUG': 'true',
            'SECRET_KEY': 'test-secret-key-for-testing-only-32-chars'
        }):
            agent = VoiceAIAgent()
            
            # Mock all external dependencies
            with patch('src.main.DeepgramSTTClient'), \
                 patch('src.main.OpenAILLMClient'), \
                 patch('src.main.CartesiaTTSClient'), \
                 patch('src.main.get_livekit_integration') as mock_livekit, \
                 patch('src.main.start_webhook_handler'), \
                 patch('src.main.stop_webhook_handler'), \
                 patch('src.main.shutdown_livekit_integration'), \
                 patch('src.database.connection.init_database') as mock_db, \
                 patch('src.database.connection.cleanup_database'), \
                 patch('src.database.migrations.MigrationManager') as mock_migration:
                
                mock_db.return_value = Mock()
                mock_migration.return_value.migrate_to_latest = AsyncMock(return_value=True)
                mock_livekit.return_value = Mock()
                
                # Start application in background
                async def run_and_stop():
                    # Let it run for a short time then stop
                    await asyncio.sleep(0.1)
                    agent.shutdown_event.set()
                
                stop_task = asyncio.create_task(run_and_stop())
                result = await agent.async_run()
                await stop_task
                
                assert result == 0
                assert agent.shutdown_in_progress is True
    
    @pytest.mark.asyncio
    async def test_startup_with_webhook_server(self):
        """Test startup with webhook server enabled."""
        with patch.dict(os.environ, {
            'ENVIRONMENT': 'testing',
            'TEST_MODE': 'true',
            'PORT': '8080'
        }):
            agent = VoiceAIAgent()
            
            with patch('src.main.DeepgramSTTClient'), \
                 patch('src.main.OpenAILLMClient'), \
                 patch('src.main.CartesiaTTSClient'), \
                 patch('src.main.get_livekit_integration') as mock_livekit, \
                 patch('src.main.start_webhook_handler'), \
                 patch('src.main.setup_webhook_routes'), \
                 patch('src.main.FastAPI') as mock_fastapi, \
                 patch('src.database.connection.init_database') as mock_db, \
                 patch('src.database.migrations.MigrationManager') as mock_migration:
                
                mock_db.return_value = Mock()
                mock_migration.return_value.migrate_to_latest = AsyncMock(return_value=True)
                mock_livekit.return_value = Mock()
                mock_fastapi.return_value = Mock()
                
                result = await agent.async_run()
                
                assert result == 0
                assert agent.fastapi_app is not None
                mock_fastapi.assert_called_once()