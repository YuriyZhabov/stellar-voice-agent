"""Base resilient client with retry logic and circuit breaker pattern."""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional, TypeVar, Generic
from uuid import uuid4

import httpx


T = TypeVar('T')


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class RetryConfig:
    """Configuration for retry logic."""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    success_threshold: int = 3


@dataclass
class ClientMetrics:
    """Metrics for client operations."""
    request_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    total_latency: float = 0.0
    circuit_breaker_trips: int = 0
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.request_count == 0:
            return 0.0
        return self.success_count / self.request_count
    
    @property
    def average_latency(self) -> float:
        """Calculate average latency."""
        if self.success_count == 0:
            return 0.0
        return self.total_latency / self.success_count


class CircuitBreaker:
    """Circuit breaker implementation for handling service failures."""
    
    def __init__(self, config: CircuitBreakerConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
    
    def can_execute(self) -> bool:
        """Check if request can be executed."""
        if self.state == CircuitBreakerState.CLOSED:
            return True
        
        if self.state == CircuitBreakerState.OPEN:
            if self.last_failure_time and (
                time.time() - self.last_failure_time >= self.config.recovery_timeout
            ):
                self.logger.info("Circuit breaker transitioning to HALF_OPEN")
                self.state = CircuitBreakerState.HALF_OPEN
                self.success_count = 0
                return True
            return False
        
        # HALF_OPEN state
        return True
    
    def record_success(self) -> None:
        """Record successful operation."""
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.logger.info("Circuit breaker transitioning to CLOSED")
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
        elif self.state == CircuitBreakerState.CLOSED:
            self.failure_count = 0
    
    def record_failure(self) -> None:
        """Record failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitBreakerState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                self.logger.warning("Circuit breaker transitioning to OPEN")
                self.state = CircuitBreakerState.OPEN
        elif self.state == CircuitBreakerState.HALF_OPEN:
            self.logger.warning("Circuit breaker transitioning back to OPEN")
            self.state = CircuitBreakerState.OPEN
            self.success_count = 0


class BaseResilientClient(ABC, Generic[T]):
    """Base class for resilient API clients with retry logic and circuit breaker."""
    
    def __init__(
        self,
        service_name: str,
        retry_config: Optional[RetryConfig] = None,
        circuit_breaker_config: Optional[CircuitBreakerConfig] = None,
        timeout: float = 30.0
    ):
        self.service_name = service_name
        self.retry_config = retry_config or RetryConfig()
        self.circuit_breaker_config = circuit_breaker_config or CircuitBreakerConfig()
        self.timeout = timeout
        
        # Set up logging with correlation ID support
        self.logger = logging.getLogger(f"{__name__}.{service_name}")
        
        # Initialize circuit breaker and metrics
        self.circuit_breaker = CircuitBreaker(self.circuit_breaker_config, self.logger)
        self.metrics = ClientMetrics()
        
        # HTTP client for API calls
        self.http_client = httpx.AsyncClient(timeout=timeout)
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def close(self) -> None:
        """Close HTTP client."""
        await self.http_client.aclose()
    
    def _generate_correlation_id(self) -> str:
        """Generate correlation ID for request tracking."""
        return str(uuid4())
    
    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for exponential backoff."""
        delay = self.retry_config.base_delay * (
            self.retry_config.exponential_base ** (attempt - 1)
        )
        delay = min(delay, self.retry_config.max_delay)
        
        if self.retry_config.jitter:
            import random
            delay *= (0.5 + random.random() * 0.5)
        
        return delay
    
    async def execute_with_resilience(
        self,
        operation: Callable[[], Any],
        correlation_id: Optional[str] = None
    ) -> T:
        """Execute operation with retry logic and circuit breaker."""
        if correlation_id is None:
            correlation_id = self._generate_correlation_id()
        
        # Check circuit breaker
        if not self.circuit_breaker.can_execute():
            self.logger.error(
                "Circuit breaker is OPEN, rejecting request",
                extra={"correlation_id": correlation_id, "service": self.service_name}
            )
            raise Exception(f"Circuit breaker is OPEN for {self.service_name}")
        
        last_exception = None
        start_time = time.time()
        
        for attempt in range(1, self.retry_config.max_attempts + 1):
            try:
                self.logger.debug(
                    f"Executing {self.service_name} request (attempt {attempt})",
                    extra={"correlation_id": correlation_id, "attempt": attempt}
                )
                
                result = await operation()
                
                # Record success
                latency = time.time() - start_time
                self.metrics.request_count += 1
                self.metrics.success_count += 1
                self.metrics.total_latency += latency
                self.circuit_breaker.record_success()
                
                self.logger.info(
                    f"{self.service_name} request successful",
                    extra={
                        "correlation_id": correlation_id,
                        "attempt": attempt,
                        "latency": latency
                    }
                )
                
                return result
                
            except Exception as e:
                last_exception = e
                self.logger.warning(
                    f"{self.service_name} request failed (attempt {attempt}): {str(e)}",
                    extra={
                        "correlation_id": correlation_id,
                        "attempt": attempt,
                        "error": str(e)
                    }
                )
                
                # Don't retry on last attempt
                if attempt == self.retry_config.max_attempts:
                    break
                
                # Calculate delay and wait
                delay = self._calculate_delay(attempt)
                await asyncio.sleep(delay)
        
        # All attempts failed
        self.metrics.request_count += 1
        self.metrics.failure_count += 1
        self.circuit_breaker.record_failure()
        
        if self.circuit_breaker.state == CircuitBreakerState.OPEN:
            self.metrics.circuit_breaker_trips += 1
        
        self.logger.error(
            f"{self.service_name} request failed after {self.retry_config.max_attempts} attempts",
            extra={"correlation_id": correlation_id, "final_error": str(last_exception)}
        )
        
        raise last_exception
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the client."""
        return {
            "service": self.service_name,
            "circuit_breaker_state": self.circuit_breaker.state.value,
            "metrics": {
                "request_count": self.metrics.request_count,
                "success_rate": self.metrics.success_rate,
                "average_latency": self.metrics.average_latency,
                "circuit_breaker_trips": self.metrics.circuit_breaker_trips
            },
            "healthy": (
                self.circuit_breaker.state != CircuitBreakerState.OPEN and
                self.metrics.success_rate >= 0.8  # 80% success rate threshold
            )
        }
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Perform health check for the specific service."""
        pass