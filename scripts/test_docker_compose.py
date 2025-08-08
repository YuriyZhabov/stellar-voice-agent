#!/usr/bin/env python3
"""
Docker Compose Testing Script

This script tests the Docker Compose configuration by starting services
and verifying they are healthy and properly connected.
"""

import subprocess
import time
import requests
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DockerComposeTest:
    """Test Docker Compose configuration."""
    
    def __init__(self, compose_file: str = "docker-compose.yml"):
        self.compose_file = compose_file
        self.services_started = False
    
    def run_command(self, command: list, timeout: int = 30) -> tuple:
        """Run a command and return success status and output."""
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", "Command timed out"
        except Exception as e:
            return False, "", str(e)
    
    def start_services(self) -> bool:
        """Start Docker Compose services."""
        logger.info("Starting Docker Compose services...")
        
        # Stop any existing services first
        self.stop_services()
        
        success, stdout, stderr = self.run_command([
            "docker", "compose", "-f", self.compose_file, "up", "-d"
        ], timeout=120)
        
        if not success:
            logger.error(f"Failed to start services: {stderr}")
            return False
        
        self.services_started = True
        logger.info("Services started successfully")
        return True
    
    def stop_services(self) -> bool:
        """Stop Docker Compose services."""
        logger.info("Stopping Docker Compose services...")
        
        success, stdout, stderr = self.run_command([
            "docker", "compose", "-f", self.compose_file, "down", "-v"
        ])
        
        if not success:
            logger.warning(f"Failed to stop services cleanly: {stderr}")
        
        self.services_started = False
        return success
    
    def wait_for_service_health(self, service_name: str, max_wait: int = 120) -> bool:
        """Wait for a service to become healthy."""
        logger.info(f"Waiting for {service_name} to become healthy...")
        
        start_time = time.time()
        while time.time() - start_time < max_wait:
            success, stdout, stderr = self.run_command([
                "docker", "compose", "-f", self.compose_file, "ps", service_name
            ])
            
            if success and "healthy" in stdout:
                logger.info(f"✓ {service_name} is healthy")
                return True
            elif "unhealthy" in stdout:
                logger.error(f"✗ {service_name} is unhealthy")
                return False
            
            time.sleep(5)
        
        logger.error(f"✗ {service_name} did not become healthy within {max_wait}s")
        return False
    
    def test_prometheus_connectivity(self) -> bool:
        """Test Prometheus connectivity and configuration."""
        logger.info("Testing Prometheus connectivity...")
        
        try:
            # Test health endpoint
            response = requests.get("http://localhost:9091/-/healthy", timeout=10)
            if response.status_code != 200:
                logger.error(f"Prometheus health check failed: {response.status_code}")
                return False
            
            # Test ready endpoint
            response = requests.get("http://localhost:9091/-/ready", timeout=10)
            if response.status_code != 200:
                logger.error(f"Prometheus ready check failed: {response.status_code}")
                return False
            
            # Test configuration endpoint
            response = requests.get("http://localhost:9091/api/v1/status/config", timeout=10)
            if response.status_code != 200:
                logger.error(f"Prometheus config check failed: {response.status_code}")
                return False
            
            # Test targets endpoint
            response = requests.get("http://localhost:9091/api/v1/targets", timeout=10)
            if response.status_code != 200:
                logger.error(f"Prometheus targets check failed: {response.status_code}")
                return False
            
            targets_data = response.json()
            active_targets = targets_data.get('data', {}).get('activeTargets', [])
            
            # Check if we have expected targets
            expected_jobs = ['prometheus', 'voice-ai-agent']
            found_jobs = set()
            
            for target in active_targets:
                job = target.get('labels', {}).get('job')
                if job:
                    found_jobs.add(job)
            
            missing_jobs = set(expected_jobs) - found_jobs
            if missing_jobs:
                logger.warning(f"Missing expected scrape targets: {missing_jobs}")
            
            logger.info(f"✓ Prometheus is accessible and has {len(active_targets)} targets")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to connect to Prometheus: {str(e)}")
            return False
    
    def test_service_logs(self, service_name: str) -> bool:
        """Check service logs for errors."""
        logger.info(f"Checking {service_name} logs...")
        
        success, stdout, stderr = self.run_command([
            "docker", "compose", "-f", self.compose_file, "logs", "--tail=50", service_name
        ])
        
        if not success:
            logger.error(f"Failed to get logs for {service_name}: {stderr}")
            return False
        
        # Check for common error patterns
        error_patterns = [
            "error", "Error", "ERROR",
            "failed", "Failed", "FAILED",
            "exception", "Exception", "EXCEPTION"
        ]
        
        error_lines = []
        for line in stdout.split('\n'):
            if any(pattern in line for pattern in error_patterns):
                error_lines.append(line.strip())
        
        if error_lines:
            logger.warning(f"Found potential errors in {service_name} logs:")
            for line in error_lines[-5:]:  # Show last 5 error lines
                logger.warning(f"  {line}")
        else:
            logger.info(f"✓ No obvious errors in {service_name} logs")
        
        return True
    
    def test_network_connectivity(self) -> bool:
        """Test network connectivity between services."""
        logger.info("Testing network connectivity...")
        
        # Test if prometheus can reach voice-ai-agent
        success, stdout, stderr = self.run_command([
            "docker", "exec", "voice-ai-prometheus",
            "wget", "--spider", "--timeout=5", "http://voice-ai-agent:8000/health"
        ])
        
        if success:
            logger.info("✓ Prometheus can reach voice-ai-agent")
        else:
            logger.error("✗ Prometheus cannot reach voice-ai-agent")
            return False
        
        # Test if prometheus can reach redis
        success, stdout, stderr = self.run_command([
            "docker", "exec", "voice-ai-prometheus",
            "nc", "-z", "redis", "6379"
        ])
        
        if success:
            logger.info("✓ Prometheus can reach Redis")
        else:
            logger.warning("⚠ Prometheus cannot reach Redis (may be expected)")
        
        return True
    
    def run_full_test(self) -> bool:
        """Run the complete test suite."""
        logger.info("Starting Docker Compose configuration test...")
        
        try:
            # Start services
            if not self.start_services():
                return False
            
            # Wait for services to become healthy
            services_to_check = ['redis', 'prometheus']
            for service in services_to_check:
                if not self.wait_for_service_health(service):
                    return False
            
            # Test Prometheus connectivity
            if not self.test_prometheus_connectivity():
                return False
            
            # Test network connectivity
            if not self.test_network_connectivity():
                return False
            
            # Check service logs
            for service in ['prometheus', 'redis']:
                self.test_service_logs(service)
            
            logger.info("✓ All tests passed!")
            return True
            
        except Exception as e:
            logger.error(f"Test failed with exception: {str(e)}")
            return False
        
        finally:
            # Clean up
            if self.services_started:
                logger.info("Cleaning up test environment...")
                self.stop_services()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.services_started:
            self.stop_services()


def main():
    """Main test function."""
    compose_files = ['docker-compose.yml']
    
    # Only test production compose if it exists and we're in CI or explicitly requested
    if Path('docker-compose.prod.yml').exists() and (
        'DOCKER_COMPOSE_TEST_PROD' in os.environ or '--prod' in sys.argv
    ):
        compose_files.append('docker-compose.prod.yml')
    
    all_passed = True
    
    for compose_file in compose_files:
        if not Path(compose_file).exists():
            logger.warning(f"Compose file {compose_file} not found, skipping")
            continue
        
        logger.info(f"Testing {compose_file}...")
        
        with DockerComposeTest(compose_file) as test:
            if not test.run_full_test():
                all_passed = False
                logger.error(f"✗ Tests failed for {compose_file}")
            else:
                logger.info(f"✓ All tests passed for {compose_file}")
    
    if all_passed:
        logger.info("✓ All Docker Compose tests passed")
        sys.exit(0)
    else:
        logger.error("✗ Some Docker Compose tests failed")
        sys.exit(1)


if __name__ == "__main__":
    import os
    main()