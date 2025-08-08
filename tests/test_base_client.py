"""Tests for base resilient client infrastructure."""

import asyncio
import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch

from src.clients.base import (
    BaseResilientClient,
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerState,
    RetryConfig,
    ClientMetrics
)


class TestCircuitBreaker:
    """Test circuit breaker functionality."""
    
    def test_initial_state(self):
        """Test circuit breaker initial state."""
        config = CircuitBreakerConfig()
        logger = MagicMock()
        cb = CircuitBreaker(config, logger)
        
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0
        assert cb.success_count == 0
        assert cb.can_execute() is True
    
    def test_failure_threshold_triggers_open(self):
        """Test that failure threshold triggers OPEN state."""
        config = CircuitBreakerConfig(failure_threshold=3)
        logger = MagicMock()
        cb = CircuitBreaker(config, logger)
        
        # Record failures up to threshold
        for i in range(3):
            cb.record_failure()
            if i < 2:
                assert cb.state == CircuitBreakerState.CLOSED
            else:
                assert cb.state == CircuitBreakerState.OPEN
        
        assert cb.can_execute() is False
    
    def test_recovery_timeout_enables_half_open(self):
        """Test recovery timeout enables HALF_OPEN state."""
        config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=0.1)
        logger = MagicMock()
        cb = CircuitBreaker(config, logger)
        
        # Trigger OPEN state
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN
        
        # Wait for recovery timeout
        time.sleep(0.2)
        
        # Should transition to HALF_OPEN
        assert cb.can_execute() is True
        assert cb.state == CircuitBreakerState.HALF_OPEN
    
    def test_half_open_success_threshold_closes_circuit(self):
        """Test that success threshold in HALF_OPEN closes circuit."""
        config = CircuitBreakerConfig(failure_threshold=2, success_threshold=2)
        logger = MagicMock()
        cb = CircuitBreaker(config, logger)
        
        # Force HALF_OPEN state
        cb.state = CircuitBreakerState.HALF_OPEN
        
        # Record successes up to threshold
        cb.record_success()
        assert cb.state == CircuitBreakerState.HALF_OPEN
        
        cb.record_success()
        assert cb.state == CircuitBreakerState.CLOSED
    
    def test_half_open_failure_returns_to_open(self):
        """Test that failure in HALF_OPEN returns to OPEN."""
        config = CircuitBreakerConfig()
        logger = MagicMock()
        cb = CircuitBreaker(config, logger)
        
        # Force HALF_OPEN state
        cb.state = CircuitBreakerState.HALF_OPEN
        
        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN


class TestClientMetrics:
    """Test client metrics functionality."""
    
    def test_initial_metrics(self):
        """Test initial metrics state."""
        metrics = ClientMetrics()
        
        assert metrics.request_count == 0
        assert metrics.success_count == 0
        assert metrics.failure_count == 0
        assert metrics.total_latency == 0.0
        assert metrics.circuit_breaker_trips == 0
        assert metrics.success_rate == 0.0
        assert metrics.average_latency == 0.0
    
    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        metrics = ClientMetrics()
        metrics.request_count = 10
        metrics.success_count = 8
        
        assert metrics.success_rate == 0.8
    
    def test_average_latency_calculation(self):
        """Test average latency calculation."""
        metrics = ClientMetrics()
        metrics.success_count = 5
        metrics.total_latency = 10.0
        
        assert metrics.average_latency == 2.0


class MockResilientClient(BaseResilientClient):
    """Mock implementation for testing."""
    
    async def health_check(self) -> bool:
        """Mock health check."""
        return True


class TestBaseResilientClient:
    """Test base resilient client functionality."""
    
    @pytest.fixture
    async def client(self):
        """Create test client."""
        client = MockResilientClient("test-service")
        yield client
        await client.close()
    
    def test_initialization(self):
        """Test client initialization."""
        client = MockResilientClient("test-service")
        
        assert client.service_name == "test-service"
        assert client.retry_config.max_attempts == 3
        assert client.circuit_breaker_config.failure_threshold == 5
        assert client.metrics.request_count == 0
    
    def test_custom_configuration(self):
        """Test client with custom configuration."""
        retry_config = RetryConfig(max_attempts=5, base_delay=2.0)
        cb_config = CircuitBreakerConfig(failure_threshold=10)
        
        client = MockResilientClient(
            "test-service",
            retry_config=retry_config,
            circuit_breaker_config=cb_config
        )
        
        assert client.retry_config.max_attempts == 5
        assert client.retry_config.base_delay == 2.0
        assert client.circuit_breaker_config.failure_threshold == 10
    
    def test_correlation_id_generation(self):
        """Test correlation ID generation."""
        client = MockResilientClient("test-service")
        
        correlation_id = client._generate_correlation_id()
        assert isinstance(correlation_id, str)
        assert len(correlation_id) > 0
        
        # Should generate unique IDs
        correlation_id2 = client._generate_correlation_id()
        assert correlation_id != correlation_id2
    
    def test_delay_calculation(self):
        """Test exponential backoff delay calculation."""
        # Disable jitter for predictable results
        retry_config = RetryConfig(jitter=False)
        client = MockResilientClient("test-service", retry_config=retry_config)
        
        # Test exponential backoff
        delay1 = client._calculate_delay(1)
        delay2 = client._calculate_delay(2)
        delay3 = client._calculate_delay(3)
        
        assert delay1 == 1.0  # base_delay * 2^0
        assert delay2 == 2.0  # base_delay * 2^1
        assert delay3 == 4.0  # base_delay * 2^2
    
    def test_delay_calculation_with_max_delay(self):
        """Test delay calculation respects max_delay."""
        retry_config = RetryConfig(base_delay=10.0, max_delay=15.0)
        client = MockResilientClient("test-service", retry_config=retry_config)
        
        delay = client._calculate_delay(5)  # Would be 160.0 without max
        assert delay <= 15.0
    
    @pytest.mark.asyncio
    async def test_successful_operation(self, client):
        """Test successful operation execution."""
        async def mock_operation():
            return "success"
        
        result = await client.execute_with_resilience(mock_operation)
        
        assert result == "success"
        assert client.metrics.request_count == 1
        assert client.metrics.success_count == 1
        assert client.metrics.failure_count == 0
        assert client.circuit_breaker.state == CircuitBreakerState.CLOSED
    
    @pytest.mark.asyncio
    async def test_operation_with_retries(self, client):
        """Test operation that fails then succeeds."""
        call_count = 0
        
        async def mock_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"
        
        with patch('asyncio.sleep', new_callable=AsyncMock):
            result = await client.execute_with_resilience(mock_operation)
        
        assert result == "success"
        assert call_count == 3
        assert client.metrics.request_count == 1
        assert client.metrics.success_count == 1
        assert client.metrics.failure_count == 0
    
    @pytest.mark.asyncio
    async def test_operation_exhausts_retries(self, client):
        """Test operation that exhausts all retry attempts."""
        async def mock_operation():
            raise Exception("Persistent failure")
        
        with patch('asyncio.sleep', new_callable=AsyncMock):
            with pytest.raises(Exception, match="Persistent failure"):
                await client.execute_with_resilience(mock_operation)
        
        assert client.metrics.request_count == 1
        assert client.metrics.success_count == 0
        assert client.metrics.failure_count == 1
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_blocks_requests(self):
        """Test circuit breaker blocks requests when open."""
        # Use low failure threshold for testing
        cb_config = CircuitBreakerConfig(failure_threshold=2)
        client = MockResilientClient("test-service", circuit_breaker_config=cb_config)
        
        async def failing_operation():
            raise Exception("Always fails")
        
        # Trigger circuit breaker
        with patch('asyncio.sleep', new_callable=AsyncMock):
            for _ in range(2):
                with pytest.raises(Exception):
                    await client.execute_with_resilience(failing_operation)
        
        assert client.circuit_breaker.state == CircuitBreakerState.OPEN
        
        # Next request should be blocked
        with pytest.raises(Exception, match="Circuit breaker is OPEN"):
            await client.execute_with_resilience(failing_operation)
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_health_status(self, client):
        """Test health status reporting."""
        # Execute some operations to populate metrics
        async def mock_operation():
            return "success"
        
        await client.execute_with_resilience(mock_operation)
        
        health_status = client.get_health_status()
        
        assert health_status["service"] == "test-service"
        assert health_status["circuit_breaker_state"] == "closed"
        assert health_status["metrics"]["request_count"] == 1
        assert health_status["metrics"]["success_rate"] == 1.0
        assert health_status["healthy"] is True
    
    @pytest.mark.asyncio
    async def test_health_status_unhealthy(self):
        """Test health status when unhealthy."""
        cb_config = CircuitBreakerConfig(failure_threshold=1)
        client = MockResilientClient("test-service", circuit_breaker_config=cb_config)
        
        async def failing_operation():
            raise Exception("Failure")
        
        # Trigger circuit breaker
        with patch('asyncio.sleep', new_callable=AsyncMock):
            with pytest.raises(Exception):
                await client.execute_with_resilience(failing_operation)
        
        health_status = client.get_health_status()
        
        assert health_status["circuit_breaker_state"] == "open"
        assert health_status["healthy"] is False
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test client as async context manager."""
        async with MockResilientClient("test-service") as client:
            assert client.service_name == "test-service"
            
            async def mock_operation():
                return "success"
            
            result = await client.execute_with_resilience(mock_operation)
            assert result == "success"
        
        # Client should be closed after context exit
        assert client.http_client.is_closed
    
    @pytest.mark.asyncio
    async def test_correlation_id_propagation(self, client):
        """Test correlation ID propagation."""
        correlation_id = "test-correlation-123"
        
        async def mock_operation():
            return "success"
        
        with patch.object(client.logger, 'debug') as mock_debug:
            await client.execute_with_resilience(mock_operation, correlation_id)
            
            # Verify correlation ID was used in logging
            mock_debug.assert_called()
            call_args = mock_debug.call_args
            assert call_args[1]['extra']['correlation_id'] == correlation_id
    
    def test_retry_config_validation(self):
        """Test retry configuration validation."""
        # Test valid configuration
        config = RetryConfig(
            max_attempts=5,
            base_delay=1.0,
            max_delay=60.0,
            exponential_base=2.0,
            jitter=True
        )
        
        assert config.max_attempts == 5
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert config.jitter is True
    
    def test_circuit_breaker_config_validation(self):
        """Test circuit breaker configuration validation."""
        config = CircuitBreakerConfig(
            failure_threshold=10,
            recovery_timeout=30.0,
            success_threshold=5
        )
        
        assert config.failure_threshold == 10
        assert config.recovery_timeout == 30.0
        assert config.success_threshold == 5
    
    @pytest.mark.asyncio
    async def test_concurrent_operations(self):
        """Test concurrent operations with circuit breaker."""
        client = MockResilientClient("test-service")
        
        async def mock_operation(delay=0.1):
            await asyncio.sleep(delay)
            return "success"
        
        # Execute multiple concurrent operations
        tasks = [
            client.execute_with_resilience(lambda: mock_operation(0.1))
            for _ in range(5)
        ]
        
        results = await asyncio.gather(*tasks)
        
        assert all(result == "success" for result in results)
        assert client.metrics.request_count == 5
        assert client.metrics.success_count == 5
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_jitter_in_delay_calculation(self):
        """Test jitter in delay calculation."""
        retry_config = RetryConfig(jitter=True)
        client = MockResilientClient("test-service", retry_config=retry_config)
        
        # Calculate multiple delays for the same attempt
        delays = [client._calculate_delay(2) for _ in range(10)]
        
        # With jitter, delays should vary
        assert len(set(delays)) > 1  # Should have different values
        
        # All delays should be within expected range (1.0 to 2.0 for attempt 2)
        for delay in delays:
            assert 1.0 <= delay <= 2.0
    
    @pytest.mark.asyncio
    async def test_no_jitter_in_delay_calculation(self):
        """Test consistent delay without jitter."""
        retry_config = RetryConfig(jitter=False)
        client = MockResilientClient("test-service", retry_config=retry_config)
        
        # Calculate multiple delays for the same attempt
        delays = [client._calculate_delay(2) for _ in range(10)]
        
        # Without jitter, all delays should be the same
        assert all(delay == 2.0 for delay in delays)