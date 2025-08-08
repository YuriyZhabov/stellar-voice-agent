#!/usr/bin/env python3
"""
Docker Compose Configuration Validator

This script validates Docker Compose configurations for the Voice AI Agent
monitoring stack, ensuring proper service dependencies, health checks,
and network configurations.
"""

import yaml
import sys
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DockerComposeValidator:
    """Validates Docker Compose configurations."""
    
    def __init__(self, compose_file: str):
        self.compose_file = Path(compose_file)
        self.config = None
        self.errors = []
        self.warnings = []
    
    def load_config(self) -> bool:
        """Load and parse the Docker Compose configuration."""
        try:
            with open(self.compose_file, 'r') as f:
                self.config = yaml.safe_load(f)
            return True
        except Exception as e:
            self.errors.append(f"Failed to load {self.compose_file}: {str(e)}")
            return False
    
    def validate_prometheus_service(self) -> bool:
        """Validate Prometheus service configuration."""
        if 'services' not in self.config:
            self.errors.append("No services section found")
            return False
        
        services = self.config['services']
        if 'prometheus' not in services:
            self.errors.append("Prometheus service not found")
            return False
        
        prometheus = services['prometheus']
        valid = True
        
        # Check required fields
        required_fields = ['image', 'ports', 'volumes', 'healthcheck']
        for field in required_fields:
            if field not in prometheus:
                self.errors.append(f"Prometheus service missing required field: {field}")
                valid = False
        
        # Validate health check
        if 'healthcheck' in prometheus:
            healthcheck = prometheus['healthcheck']
            required_hc_fields = ['test', 'interval', 'timeout', 'retries']
            for field in required_hc_fields:
                if field not in healthcheck:
                    self.errors.append(f"Prometheus healthcheck missing field: {field}")
                    valid = False
        
        # Validate ports
        if 'ports' in prometheus:
            ports = prometheus['ports']
            if not any('9091:9090' in str(port) for port in ports):
                self.warnings.append("Prometheus port mapping should use 9091:9090 to avoid conflicts")
        
        # Validate volumes
        if 'volumes' in prometheus:
            volumes = prometheus['volumes']
            required_volumes = [
                'prometheus.yml:/etc/prometheus/prometheus.yml',
                'prometheus_data:/prometheus'
            ]
            for req_vol in required_volumes:
                if not any(req_vol in str(vol) for vol in volumes):
                    self.errors.append(f"Prometheus missing required volume: {req_vol}")
                    valid = False
        
        # Validate command arguments
        if 'command' in prometheus:
            command = prometheus['command']
            required_args = [
                '--config.file=/etc/prometheus/prometheus.yml',
                '--storage.tsdb.path=/prometheus'
            ]
            for arg in required_args:
                if arg not in command:
                    self.errors.append(f"Prometheus missing required command argument: {arg}")
                    valid = False
        
        return valid
    
    def validate_service_dependencies(self) -> bool:
        """Validate service dependencies and startup order."""
        if 'services' not in self.config:
            return False
        
        services = self.config['services']
        valid = True
        
        # Check if voice-ai-agent depends on prometheus
        if 'voice-ai-agent' in services:
            agent = services['voice-ai-agent']
            if 'depends_on' in agent:
                depends_on = agent['depends_on']
                if isinstance(depends_on, dict):
                    if 'prometheus' not in depends_on:
                        self.warnings.append("voice-ai-agent should depend on prometheus")
                    elif depends_on.get('prometheus', {}).get('condition') != 'service_healthy':
                        self.warnings.append("voice-ai-agent should wait for prometheus to be healthy")
                elif isinstance(depends_on, list):
                    if 'prometheus' not in depends_on:
                        self.warnings.append("voice-ai-agent should depend on prometheus")
        
        # Check if prometheus depends on redis
        if 'prometheus' in services:
            prometheus = services['prometheus']
            if 'depends_on' in prometheus:
                depends_on = prometheus['depends_on']
                if isinstance(depends_on, dict):
                    if 'redis' not in depends_on:
                        self.warnings.append("prometheus should depend on redis")
                    elif depends_on.get('redis', {}).get('condition') != 'service_healthy':
                        self.warnings.append("prometheus should wait for redis to be healthy")
        
        return valid
    
    def validate_networks(self) -> bool:
        """Validate network configuration."""
        if 'networks' not in self.config:
            self.errors.append("No networks section found")
            return False
        
        networks = self.config['networks']
        if 'voice-ai-network' not in networks:
            self.errors.append("voice-ai-network not defined")
            return False
        
        # Check if all services are on the network
        if 'services' in self.config:
            for service_name, service_config in self.config['services'].items():
                if 'networks' not in service_config:
                    self.warnings.append(f"Service {service_name} not explicitly assigned to network")
                elif 'voice-ai-network' not in service_config['networks']:
                    self.errors.append(f"Service {service_name} not on voice-ai-network")
        
        return True
    
    def validate_volumes(self) -> bool:
        """Validate volume configuration."""
        if 'volumes' not in self.config:
            self.errors.append("No volumes section found")
            return False
        
        volumes = self.config['volumes']
        required_volumes = ['prometheus_data', 'redis_data']
        
        for vol in required_volumes:
            if vol not in volumes:
                self.errors.append(f"Required volume {vol} not defined")
        
        return len([e for e in self.errors if 'volume' in e.lower()]) == 0
    
    def validate_security(self) -> bool:
        """Validate security configurations."""
        if 'services' not in self.config:
            return False
        
        services = self.config['services']
        
        # Check if prometheus runs as non-root user
        if 'prometheus' in services:
            prometheus = services['prometheus']
            if 'user' not in prometheus:
                self.warnings.append("Prometheus should run as non-root user for security")
            elif prometheus['user'] != '65534:65534':
                self.warnings.append("Prometheus should run as nobody user (65534:65534)")
        
        return True
    
    def validate_all(self) -> Tuple[bool, List[str], List[str]]:
        """Run all validations."""
        if not self.load_config():
            return False, self.errors, self.warnings
        
        validations = [
            self.validate_prometheus_service,
            self.validate_service_dependencies,
            self.validate_networks,
            self.validate_volumes,
            self.validate_security
        ]
        
        all_valid = True
        for validation in validations:
            if not validation():
                all_valid = False
        
        return all_valid, self.errors, self.warnings


def validate_prometheus_config(config_path: str = "monitoring/prometheus/prometheus.yml") -> bool:
    """Validate Prometheus configuration file."""
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        errors = []
        warnings = []
        
        # Check required sections
        required_sections = ['global', 'scrape_configs']
        for section in required_sections:
            if section not in config:
                errors.append(f"Missing required section: {section}")
        
        # Validate scrape configs
        if 'scrape_configs' in config:
            scrape_configs = config['scrape_configs']
            required_jobs = ['prometheus', 'voice-ai-agent']
            
            existing_jobs = [job.get('job_name') for job in scrape_configs]
            for job in required_jobs:
                if job not in existing_jobs:
                    errors.append(f"Missing required scrape job: {job}")
        
        # Check for proper target addressing
        if 'scrape_configs' in config:
            for job in config['scrape_configs']:
                if 'static_configs' in job:
                    for static_config in job['static_configs']:
                        if 'targets' in static_config:
                            for target in static_config['targets']:
                                if 'localhost' in target and job['job_name'] != 'prometheus':
                                    warnings.append(f"Job {job['job_name']} uses localhost, should use service name")
        
        if errors:
            logger.error("Prometheus configuration errors:")
            for error in errors:
                logger.error(f"  - {error}")
            return False
        
        if warnings:
            logger.warning("Prometheus configuration warnings:")
            for warning in warnings:
                logger.warning(f"  - {warning}")
        
        logger.info("Prometheus configuration is valid")
        return True
        
    except Exception as e:
        logger.error(f"Failed to validate Prometheus config: {str(e)}")
        return False


def main():
    """Main validation function."""
    compose_files = ['docker-compose.yml', 'docker-compose.prod.yml']
    all_valid = True
    
    for compose_file in compose_files:
        if not Path(compose_file).exists():
            logger.warning(f"Compose file {compose_file} not found, skipping")
            continue
        
        logger.info(f"Validating {compose_file}...")
        validator = DockerComposeValidator(compose_file)
        valid, errors, warnings = validator.validate_all()
        
        if not valid:
            all_valid = False
            logger.error(f"Validation failed for {compose_file}")
            for error in errors:
                logger.error(f"  ERROR: {error}")
        
        if warnings:
            for warning in warnings:
                logger.warning(f"  WARNING: {warning}")
        
        if valid and not warnings:
            logger.info(f"✓ {compose_file} is valid")
        elif valid:
            logger.info(f"✓ {compose_file} is valid (with warnings)")
    
    # Validate Prometheus configuration
    logger.info("Validating Prometheus configuration...")
    prometheus_valid = validate_prometheus_config()
    
    if not prometheus_valid:
        all_valid = False
    
    if all_valid:
        logger.info("✓ All configurations are valid")
        sys.exit(0)
    else:
        logger.error("✗ Configuration validation failed")
        sys.exit(1)


if __name__ == "__main__":
    main()