"""
Prometheus Auto-Recovery System

This module provides automatic recovery mechanisms for Prometheus service failures,
including service restart logic, fallback configuration generation, and retry mechanisms.
"""

import asyncio
import logging
import time
import yaml
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import subprocess
import requests
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class RecoveryAction:
    """Represents a recovery action taken by the system."""
    action_type: str
    timestamp: datetime
    success: bool
    details: str
    duration_seconds: float


@dataclass
class RecoveryResult:
    """Result of a recovery attempt."""
    success: bool
    actions_taken: List[RecoveryAction]
    final_status: str
    error_message: Optional[str] = None


class PrometheusRecovery:
    """Handles automatic recovery of Prometheus service failures."""
    
    def __init__(self, 
                 prometheus_url: str = "http://localhost:9091",
                 config_path: str = "monitoring/prometheus/prometheus.yml",
                 docker_compose_path: str = "docker-compose.yml",
                 max_retries: int = 5,
                 base_delay: float = 1.0):
        self.prometheus_url = prometheus_url
        self.config_path = Path(config_path)
        self.docker_compose_path = Path(docker_compose_path)
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.recovery_history: List[RecoveryAction] = []
    
    async def attempt_recovery(self) -> RecoveryResult:
        """
        Attempt to recover Prometheus service using various strategies.
        
        Returns:
            RecoveryResult with details of recovery attempt
        """
        logger.info("Starting Prometheus recovery process")
        actions_taken = []
        start_time = time.time()
        
        try:
            # Step 1: Check current status
            status_action = await self._check_service_status()
            actions_taken.append(status_action)
            
            if status_action.success:
                logger.info("Prometheus is already healthy, no recovery needed")
                return RecoveryResult(
                    success=True,
                    actions_taken=actions_taken,
                    final_status="healthy"
                )
            
            # Step 2: Validate and fix configuration
            config_action = await self._validate_and_fix_config()
            actions_taken.append(config_action)
            
            # Step 3: Restart service with dependencies
            restart_action = await self._restart_service_with_dependencies()
            actions_taken.append(restart_action)
            
            # Step 4: Wait for service to be ready with retry logic
            ready_action = await self._wait_for_service_ready()
            actions_taken.append(ready_action)
            
            # Step 5: Verify recovery
            verify_action = await self._verify_recovery()
            actions_taken.append(verify_action)
            
            success = verify_action.success
            final_status = "healthy" if success else "failed"
            
            total_duration = time.time() - start_time
            logger.info(f"Recovery process completed in {total_duration:.2f}s, success: {success}")
            
            return RecoveryResult(
                success=success,
                actions_taken=actions_taken,
                final_status=final_status
            )
            
        except Exception as e:
            error_msg = f"Recovery process failed with exception: {str(e)}"
            logger.error(error_msg)
            
            return RecoveryResult(
                success=False,
                actions_taken=actions_taken,
                final_status="error",
                error_message=error_msg
            )
    
    async def _check_service_status(self) -> RecoveryAction:
        """Check current Prometheus service status."""
        start_time = time.time()
        
        try:
            response = requests.get(f"{self.prometheus_url}/-/healthy", timeout=5)
            success = response.status_code == 200
            details = f"HTTP {response.status_code}" if not success else "Service healthy"
            
        except requests.exceptions.RequestException as e:
            success = False
            details = f"Connection failed: {str(e)}"
        
        duration = time.time() - start_time
        
        return RecoveryAction(
            action_type="status_check",
            timestamp=datetime.now(),
            success=success,
            details=details,
            duration_seconds=duration
        )
    
    async def _validate_and_fix_config(self) -> RecoveryAction:
        """Validate Prometheus configuration and create fallback if needed."""
        start_time = time.time()
        
        try:
            if not self.config_path.exists():
                # Create fallback configuration
                fallback_config = self._generate_fallback_config()
                self.config_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(self.config_path, 'w') as f:
                    yaml.dump(fallback_config, f, default_flow_style=False)
                
                details = "Created fallback configuration"
                success = True
            else:
                # Validate existing configuration
                with open(self.config_path, 'r') as f:
                    config = yaml.safe_load(f)
                
                # Basic validation
                if not config.get('scrape_configs'):
                    # Fix missing scrape configs
                    config['scrape_configs'] = self._get_default_scrape_configs()
                    
                    with open(self.config_path, 'w') as f:
                        yaml.dump(config, f, default_flow_style=False)
                    
                    details = "Fixed missing scrape_configs"
                else:
                    details = "Configuration is valid"
                
                success = True
                
        except Exception as e:
            success = False
            details = f"Configuration validation failed: {str(e)}"
        
        duration = time.time() - start_time
        
        return RecoveryAction(
            action_type="config_validation",
            timestamp=datetime.now(),
            success=success,
            details=details,
            duration_seconds=duration
        )
    
    async def _restart_service_with_dependencies(self) -> RecoveryAction:
        """Restart Prometheus service with proper dependency handling."""
        start_time = time.time()
        
        try:
            # Stop Prometheus service first
            stop_result = subprocess.run([
                "docker", "compose", "-f", str(self.docker_compose_path),
                "stop", "prometheus"
            ], capture_output=True, text=True, timeout=30)
            
            if stop_result.returncode != 0:
                logger.warning(f"Failed to stop Prometheus: {stop_result.stderr}")
            
            # Wait a moment for cleanup
            await asyncio.sleep(2)
            
            # Start dependencies first (Redis if needed)
            deps_result = subprocess.run([
                "docker", "compose", "-f", str(self.docker_compose_path),
                "up", "-d", "redis"
            ], capture_output=True, text=True, timeout=60)
            
            if deps_result.returncode != 0:
                logger.warning(f"Failed to start dependencies: {deps_result.stderr}")
            
            # Wait for dependencies to be ready
            await asyncio.sleep(5)
            
            # Start Prometheus
            start_result = subprocess.run([
                "docker", "compose", "-f", str(self.docker_compose_path),
                "up", "-d", "prometheus"
            ], capture_output=True, text=True, timeout=60)
            
            success = start_result.returncode == 0
            details = "Service restarted successfully" if success else f"Restart failed: {start_result.stderr}"
            
        except subprocess.TimeoutExpired:
            success = False
            details = "Service restart timed out"
        except Exception as e:
            success = False
            details = f"Restart failed with exception: {str(e)}"
        
        duration = time.time() - start_time
        
        return RecoveryAction(
            action_type="service_restart",
            timestamp=datetime.now(),
            success=success,
            details=details,
            duration_seconds=duration
        )
    
    async def _wait_for_service_ready(self) -> RecoveryAction:
        """Wait for Prometheus service to be ready with exponential backoff."""
        start_time = time.time()
        
        for attempt in range(self.max_retries):
            try:
                delay = self.base_delay * (2 ** attempt)
                logger.info(f"Waiting for Prometheus readiness, attempt {attempt + 1}/{self.max_retries}")
                
                await asyncio.sleep(delay)
                
                # Check if service is responding
                response = requests.get(f"{self.prometheus_url}/-/ready", timeout=10)
                
                if response.status_code == 200:
                    duration = time.time() - start_time
                    return RecoveryAction(
                        action_type="readiness_wait",
                        timestamp=datetime.now(),
                        success=True,
                        details=f"Service ready after {attempt + 1} attempts",
                        duration_seconds=duration
                    )
                
            except requests.exceptions.RequestException as e:
                logger.debug(f"Readiness check attempt {attempt + 1} failed: {str(e)}")
                continue
        
        duration = time.time() - start_time
        
        return RecoveryAction(
            action_type="readiness_wait",
            timestamp=datetime.now(),
            success=False,
            details=f"Service not ready after {self.max_retries} attempts",
            duration_seconds=duration
        )
    
    async def _verify_recovery(self) -> RecoveryAction:
        """Verify that Prometheus recovery was successful."""
        start_time = time.time()
        
        try:
            # Check health endpoint
            health_response = requests.get(f"{self.prometheus_url}/-/healthy", timeout=5)
            health_ok = health_response.status_code == 200
            
            # Check if we can query metrics
            query_response = requests.get(
                f"{self.prometheus_url}/api/v1/query",
                params={"query": "up"},
                timeout=5
            )
            query_ok = query_response.status_code == 200
            
            # Check configuration reload
            config_response = requests.get(f"{self.prometheus_url}/api/v1/status/config", timeout=5)
            config_ok = config_response.status_code == 200
            
            success = health_ok and query_ok and config_ok
            
            details_parts = []
            if not health_ok:
                details_parts.append(f"Health check failed: {health_response.status_code}")
            if not query_ok:
                details_parts.append(f"Query failed: {query_response.status_code}")
            if not config_ok:
                details_parts.append(f"Config check failed: {config_response.status_code}")
            
            details = "All checks passed" if success else "; ".join(details_parts)
            
        except Exception as e:
            success = False
            details = f"Verification failed: {str(e)}"
        
        duration = time.time() - start_time
        
        return RecoveryAction(
            action_type="recovery_verification",
            timestamp=datetime.now(),
            success=success,
            details=details,
            duration_seconds=duration
        )
    
    def _generate_fallback_config(self) -> Dict:
        """Generate a minimal working Prometheus configuration."""
        return {
            'global': {
                'scrape_interval': '15s',
                'evaluation_interval': '15s'
            },
            'scrape_configs': self._get_default_scrape_configs()
        }
    
    def _get_default_scrape_configs(self) -> List[Dict]:
        """Get default scrape configurations for essential services."""
        return [
            {
                'job_name': 'voice-ai-agent',
                'static_configs': [
                    {'targets': ['voice-ai-agent:8000']}
                ],
                'metrics_path': '/metrics',
                'scrape_interval': '15s'
            },
            {
                'job_name': 'voice-ai-agent-health',
                'static_configs': [
                    {'targets': ['voice-ai-agent:8000']}
                ],
                'metrics_path': '/health',
                'scrape_interval': '30s'
            },
            {
                'job_name': 'prometheus',
                'static_configs': [
                    {'targets': ['localhost:9090']}
                ],
                'metrics_path': '/metrics',
                'scrape_interval': '15s'
            }
        ]
    
    async def retry_with_exponential_backoff(self, 
                                           operation_func,
                                           max_attempts: int = None,
                                           base_delay: float = None) -> Tuple[bool, str]:
        """
        Retry an operation with exponential backoff.
        
        Args:
            operation_func: Async function to retry
            max_attempts: Maximum number of attempts (defaults to self.max_retries)
            base_delay: Base delay in seconds (defaults to self.base_delay)
            
        Returns:
            Tuple of (success, details)
        """
        max_attempts = max_attempts or self.max_retries
        base_delay = base_delay or self.base_delay
        
        for attempt in range(max_attempts):
            try:
                result = await operation_func()
                if result:
                    return True, f"Operation succeeded on attempt {attempt + 1}"
                    
            except Exception as e:
                logger.debug(f"Attempt {attempt + 1} failed: {str(e)}")
            
            if attempt < max_attempts - 1:  # Don't delay after the last attempt
                delay = base_delay * (2 ** attempt)
                await asyncio.sleep(delay)
        
        return False, f"Operation failed after {max_attempts} attempts"
    
    def get_recovery_history(self) -> List[RecoveryAction]:
        """Get the history of recovery actions."""
        return self.recovery_history.copy()
    
    def clear_recovery_history(self):
        """Clear the recovery history."""
        self.recovery_history.clear()
    
    async def schedule_periodic_recovery_check(self, interval_seconds: int = 300):
        """
        Schedule periodic recovery checks.
        
        Args:
            interval_seconds: Interval between checks in seconds
        """
        logger.info(f"Starting periodic recovery checks every {interval_seconds} seconds")
        
        while True:
            try:
                await asyncio.sleep(interval_seconds)
                
                # Quick health check
                status_action = await self._check_service_status()
                
                if not status_action.success:
                    logger.warning("Periodic check detected Prometheus failure, attempting recovery")
                    recovery_result = await self.attempt_recovery()
                    
                    if recovery_result.success:
                        logger.info("Automatic recovery successful")
                    else:
                        logger.error(f"Automatic recovery failed: {recovery_result.error_message}")
                
            except Exception as e:
                logger.error(f"Error in periodic recovery check: {str(e)}")


# Convenience functions for external use
async def recover_prometheus(prometheus_url: str = "http://localhost:9091",
                           config_path: str = "monitoring/prometheus/prometheus.yml") -> RecoveryResult:
    """
    Convenience function to attempt Prometheus recovery.
    
    Args:
        prometheus_url: URL of Prometheus service
        config_path: Path to Prometheus configuration file
        
    Returns:
        RecoveryResult with details of recovery attempt
    """
    recovery = PrometheusRecovery(prometheus_url=prometheus_url, config_path=config_path)
    return await recovery.attempt_recovery()


def create_fallback_prometheus_config(output_path: str = "monitoring/prometheus/prometheus.yml"):
    """
    Create a fallback Prometheus configuration file.
    
    Args:
        output_path: Path where to save the configuration
    """
    recovery = PrometheusRecovery()
    config = recovery._generate_fallback_config()
    
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)
    
    logger.info(f"Fallback configuration created at {output_path}")