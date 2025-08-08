"""
Prometheus Configuration Validator

This module provides comprehensive validation and auto-correction capabilities
for Prometheus configuration files, including YAML syntax validation,
scrape target accessibility checking, and configuration auto-correction.
"""

import asyncio
import logging
import socket
import yaml
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Union

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of configuration validation."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    suggestions: List[str]
    corrected_config: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class TargetAccessibilityResult:
    """Result of target accessibility check."""
    target: str
    accessible: bool
    response_time_ms: Optional[float]
    status_code: Optional[int]
    error_message: Optional[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class PrometheusConfigValidator:
    """Comprehensive Prometheus configuration validator with auto-correction."""
    
    def __init__(self, timeout: int = 10):
        """Initialize the configuration validator."""
        self.timeout = timeout
        
        # Setup HTTP session with retries
        self.session = requests.Session()
        retry_strategy = Retry(
            total=2,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Default configuration template
        self.default_config = {
            'global': {
                'scrape_interval': '15s',
                'evaluation_interval': '15s',
                'external_labels': {
                    'monitor': 'voice-ai-agent'
                }
            },
            'scrape_configs': [
                {
                    'job_name': 'prometheus',
                    'static_configs': [
                        {'targets': ['localhost:9090']}
                    ]
                }
            ]
        }
        
        logger.info("Prometheus configuration validator initialized")
    
    def validate_yaml_syntax(self, config_path: Union[str, Path]) -> ValidationResult:
        """Validate YAML syntax of Prometheus configuration file."""
        config_path = Path(config_path)
        errors = []
        warnings = []
        suggestions = []
        
        logger.info(f"Validating YAML syntax for {config_path}")
        
        try:
            # Check if file exists
            if not config_path.exists():
                errors.append(f"Configuration file not found: {config_path}")
                suggestions.append("Create the configuration file using the default template")
                return ValidationResult(
                    is_valid=False,
                    errors=errors,
                    warnings=warnings,
                    suggestions=suggestions,
                    corrected_config=self.default_config
                )
            
            # Check file permissions
            if not config_path.is_file():
                errors.append(f"Path is not a file: {config_path}")
                return ValidationResult(False, errors, warnings, suggestions)
            
            if not config_path.stat().st_size:
                errors.append("Configuration file is empty")
                suggestions.append("Use the default configuration template")
                return ValidationResult(
                    is_valid=False,
                    errors=errors,
                    warnings=warnings,
                    suggestions=suggestions,
                    corrected_config=self.default_config
                )
            
            # Parse YAML
            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Check for common YAML issues before parsing
            if '\t' in content:
                warnings.append("Configuration contains tabs, consider using spaces for consistency")
                suggestions.append("Replace tabs with spaces (2 or 4 spaces per indentation level)")
            
            config_data = yaml.safe_load(content)
            
            if config_data is None:
                errors.append("Configuration file parsed to None (empty or invalid YAML)")
                return ValidationResult(
                    is_valid=False,
                    errors=errors,
                    warnings=warnings,
                    suggestions=suggestions,
                    corrected_config=self.default_config
                )
            
            if not isinstance(config_data, dict):
                errors.append("Configuration root must be a dictionary/object")
                return ValidationResult(False, errors, warnings, suggestions)
            
            logger.info("YAML syntax validation passed")
            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings,
                suggestions=suggestions
            )
            
        except yaml.YAMLError as e:
            error_msg = f"YAML syntax error: {str(e)}"
            errors.append(error_msg)
            suggestions.extend([
                "Check YAML indentation (use spaces, not tabs)",
                "Validate YAML syntax using online validator",
                "Ensure proper quoting of string values",
                "Check for missing colons or incorrect list formatting"
            ])
            
            logger.error(f"YAML syntax validation failed: {e}")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                suggestions=suggestions,
                corrected_config=self.default_config
            )
            
        except Exception as e:
            error_msg = f"Error reading configuration file: {str(e)}"
            errors.append(error_msg)
            logger.error(f"Configuration file read error: {e}")
            return ValidationResult(False, errors, warnings, suggestions)
    
    def validate_configuration_structure(self, config_data: Dict[str, Any]) -> ValidationResult:
        """Validate the structure and content of Prometheus configuration."""
        errors = []
        warnings = []
        suggestions = []
        corrected_config = config_data.copy()
        
        # Validate global section
        if 'global' not in config_data:
            warnings.append("Missing 'global' section")
            suggestions.append("Add global section with scrape_interval and evaluation_interval")
            corrected_config['global'] = self.default_config['global']
        else:
            global_config = config_data['global']
            if not isinstance(global_config, dict):
                errors.append("'global' section must be a dictionary")
            else:
                # Check required global settings
                if 'scrape_interval' not in global_config:
                    warnings.append("Missing 'scrape_interval' in global section")
                    suggestions.append("Add scrape_interval (e.g., '15s') to global section")
                    if 'global' not in corrected_config:
                        corrected_config['global'] = {}
                    corrected_config['global']['scrape_interval'] = '15s'
                
                if 'evaluation_interval' not in global_config:
                    warnings.append("Missing 'evaluation_interval' in global section")
                    suggestions.append("Add evaluation_interval (e.g., '15s') to global section")
                    if 'global' not in corrected_config:
                        corrected_config['global'] = {}
                    corrected_config['global']['evaluation_interval'] = '15s'
        
        # Validate scrape_configs section
        if 'scrape_configs' not in config_data:
            errors.append("Missing required 'scrape_configs' section")
            suggestions.append("Add scrape_configs section with at least one job")
            corrected_config['scrape_configs'] = self.default_config['scrape_configs']
        else:
            scrape_configs = config_data['scrape_configs']
            if not isinstance(scrape_configs, list):
                errors.append("'scrape_configs' must be a list")
                corrected_config['scrape_configs'] = self.default_config['scrape_configs']
            elif len(scrape_configs) == 0:
                warnings.append("'scrape_configs' is empty")
                suggestions.append("Add at least one scrape job configuration")
                corrected_config['scrape_configs'] = self.default_config['scrape_configs']
            else:
                corrected_scrape_configs = []
                for i, scrape_config in enumerate(scrape_configs):
                    corrected_scrape_config = self._validate_scrape_config(
                        scrape_config, i, errors, warnings, suggestions
                    )
                    corrected_scrape_configs.append(corrected_scrape_config)
                corrected_config['scrape_configs'] = corrected_scrape_configs
        
        is_valid = len(errors) == 0
        
        logger.info(f"Configuration structure validation completed. Valid: {is_valid}")
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions,
            corrected_config=corrected_config if corrected_config != config_data else None
        )
    
    def _validate_scrape_config(self, scrape_config: Dict[str, Any], index: int,
                              errors: List[str], warnings: List[str], 
                              suggestions: List[str]) -> Dict[str, Any]:
        """Validate individual scrape configuration."""
        corrected_config = scrape_config.copy()
        
        # Validate job_name
        if 'job_name' not in scrape_config:
            errors.append(f"Scrape config {index}: missing required 'job_name'")
            suggestions.append(f"Add job_name to scrape config {index}")
            corrected_config['job_name'] = f'job_{index}'
        elif not isinstance(scrape_config['job_name'], str):
            warnings.append(f"Scrape config {index}: 'job_name' must be a string")
            corrected_config['job_name'] = str(scrape_config['job_name'])
        
        job_name = corrected_config.get('job_name', f'job_{index}')
        
        # Validate static_configs
        if 'static_configs' not in scrape_config:
            errors.append(f"Job '{job_name}': missing 'static_configs'")
            suggestions.append(f"Add static_configs to job '{job_name}'")
            corrected_config['static_configs'] = [{'targets': ['localhost:9090']}]
        else:
            static_configs = scrape_config['static_configs']
            if not isinstance(static_configs, list):
                errors.append(f"Job '{job_name}': 'static_configs' must be a list")
                corrected_config['static_configs'] = [{'targets': ['localhost:9090']}]
            else:
                corrected_static_configs = []
                for j, static_config in enumerate(static_configs):
                    if not isinstance(static_config, dict):
                        warnings.append(f"Job '{job_name}': static_config {j} should be a dictionary")
                        corrected_static_configs.append({'targets': ['localhost:9090']})
                        continue
                    
                    corrected_static_config = static_config.copy()
                    
                    if 'targets' not in static_config:
                        warnings.append(f"Job '{job_name}': missing 'targets' in static_config {j}")
                        corrected_static_config['targets'] = ['localhost:9090']
                    elif not isinstance(static_config['targets'], list):
                        warnings.append(f"Job '{job_name}': 'targets' should be a list")
                        corrected_static_config['targets'] = [str(static_config['targets'])]
                    else:
                        # Validate target format
                        corrected_targets = []
                        for target in static_config['targets']:
                            if not isinstance(target, str):
                                warnings.append(f"Job '{job_name}': target should be string: {target}")
                                corrected_targets.append(str(target))
                            elif ':' not in target:
                                warnings.append(f"Job '{job_name}': target missing port: {target}")
                                suggestions.append(f"Add port to target (e.g., '{target}:9090')")
                                corrected_targets.append(f"{target}:9090")
                            else:
                                corrected_targets.append(target)
                        corrected_static_config['targets'] = corrected_targets
                    
                    corrected_static_configs.append(corrected_static_config)
                corrected_config['static_configs'] = corrected_static_configs
        
        return corrected_config
    
    async def check_scrape_targets_accessibility(self, config_data: Dict[str, Any]) -> List[TargetAccessibilityResult]:
        """Check accessibility of all scrape targets in the configuration."""
        results = []
        
        if 'scrape_configs' not in config_data:
            logger.warning("No scrape_configs found in configuration")
            return results
        
        logger.info("Checking scrape targets accessibility")
        
        # Collect all targets
        targets_to_check = []
        for scrape_config in config_data['scrape_configs']:
            job_name = scrape_config.get('job_name', 'unknown')
            metrics_path = scrape_config.get('metrics_path', '/metrics')
            
            if 'static_configs' in scrape_config:
                for static_config in scrape_config['static_configs']:
                    if 'targets' in static_config:
                        for target in static_config['targets']:
                            targets_to_check.append((target, job_name, metrics_path))
        
        # Check each target
        for target, job_name, metrics_path in targets_to_check:
            result = await self._check_single_target_accessibility(target, job_name, metrics_path)
            results.append(result)
        
        accessible_count = sum(1 for r in results if r.accessible)
        logger.info(f"Target accessibility check completed: {accessible_count}/{len(results)} accessible")
        
        return results
    
    async def _check_single_target_accessibility(self, target: str, job_name: str, 
                                               metrics_path: str = '/metrics') -> TargetAccessibilityResult:
        """Check accessibility of a single target."""
        import time
        
        start_time = time.time()
        
        try:
            # Parse target
            if ':' not in target:
                return TargetAccessibilityResult(
                    target=target,
                    accessible=False,
                    response_time_ms=None,
                    status_code=None,
                    error_message="Invalid target format (missing port)"
                )
            
            host, port = target.split(':', 1)
            
            # Try to parse port
            try:
                port_num = int(port)
            except ValueError:
                return TargetAccessibilityResult(
                    target=target,
                    accessible=False,
                    response_time_ms=None,
                    status_code=None,
                    error_message="Invalid port number"
                )
            
            # Test TCP connectivity first
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self.timeout)
                result = sock.connect_ex((host, port_num))
                sock.close()
                
                if result != 0:
                    response_time = (time.time() - start_time) * 1000
                    return TargetAccessibilityResult(
                        target=target,
                        accessible=False,
                        response_time_ms=round(response_time, 2),
                        status_code=None,
                        error_message="TCP connection failed"
                    )
            except socket.gaierror:
                response_time = (time.time() - start_time) * 1000
                return TargetAccessibilityResult(
                    target=target,
                    accessible=False,
                    response_time_ms=round(response_time, 2),
                    status_code=None,
                    error_message="DNS resolution failed"
                )
            
            # Try HTTP request
            url = f"http://{target}{metrics_path}"
            try:
                response = self.session.get(url, timeout=self.timeout)
                response_time = (time.time() - start_time) * 1000
                
                return TargetAccessibilityResult(
                    target=target,
                    accessible=response.status_code < 500,
                    response_time_ms=round(response_time, 2),
                    status_code=response.status_code,
                    error_message=None if response.status_code < 400 else f"HTTP {response.status_code}"
                )
                
            except requests.RequestException as e:
                response_time = (time.time() - start_time) * 1000
                return TargetAccessibilityResult(
                    target=target,
                    accessible=False,
                    response_time_ms=round(response_time, 2),
                    status_code=None,
                    error_message=f"HTTP request failed: {str(e)}"
                )
                
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return TargetAccessibilityResult(
                target=target,
                accessible=False,
                response_time_ms=round(response_time, 2),
                status_code=None,
                error_message=f"Unexpected error: {str(e)}"
            )
    
    def auto_correct_configuration(self, config_path: Union[str, Path], 
                                 backup: bool = True) -> ValidationResult:
        """Auto-correct common configuration issues."""
        config_path = Path(config_path)
        logger.info(f"Auto-correcting configuration: {config_path}")
        
        # First validate syntax
        syntax_result = self.validate_yaml_syntax(config_path)
        
        # If file doesn't exist or has critical syntax errors, return the error
        if not syntax_result.is_valid and syntax_result.corrected_config is None:
            return syntax_result
        
        # If file doesn't exist but we have a corrected config, create the file
        if not config_path.exists() and syntax_result.corrected_config:
            try:
                # Create directory if it doesn't exist
                config_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Write default configuration
                with open(config_path, 'w', encoding='utf-8') as f:
                    yaml.dump(syntax_result.corrected_config, f, 
                             default_flow_style=False, indent=2, sort_keys=False)
                
                logger.info(f"Created new configuration file: {config_path}")
                
                return ValidationResult(
                    is_valid=True,
                    errors=[],
                    warnings=[],
                    suggestions=["New configuration file created with default settings", "Review and customize the configuration"],
                    corrected_config=syntax_result.corrected_config
                )
            except Exception as e:
                error_msg = f"Error creating configuration file: {str(e)}"
                logger.error(error_msg)
                return ValidationResult(
                    is_valid=False,
                    errors=[error_msg],
                    warnings=[],
                    suggestions=["Check file permissions and directory structure"]
                )
        
        try:
            # Load current configuration or use corrected version
            if syntax_result.is_valid:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = yaml.safe_load(f)
            else:
                config_data = syntax_result.corrected_config
            
            # Validate structure and get corrections
            structure_result = self.validate_configuration_structure(config_data)
            
            if structure_result.corrected_config:
                # Create backup if requested
                if backup and config_path.exists():
                    backup_path = config_path.with_suffix(f'.backup.{datetime.now().strftime("%Y%m%d_%H%M%S")}.yml')
                    backup_path.write_text(config_path.read_text())
                    logger.info(f"Created backup: {backup_path}")
                
                # Write corrected configuration
                with open(config_path, 'w', encoding='utf-8') as f:
                    yaml.dump(structure_result.corrected_config, f, 
                             default_flow_style=False, indent=2, sort_keys=False)
                
                logger.info(f"Configuration auto-corrected and saved to {config_path}")
                
                return ValidationResult(
                    is_valid=True,
                    errors=[],
                    warnings=structure_result.warnings,
                    suggestions=["Configuration has been auto-corrected", "Review the changes and test the configuration"],
                    corrected_config=structure_result.corrected_config
                )
            else:
                return structure_result
                
        except Exception as e:
            error_msg = f"Error during auto-correction: {str(e)}"
            logger.error(error_msg)
            return ValidationResult(
                is_valid=False,
                errors=[error_msg],
                warnings=[],
                suggestions=["Manual correction may be required"]
            )
    
    async def comprehensive_validation(self, config_path: Union[str, Path]) -> Dict[str, Any]:
        """Perform comprehensive validation including syntax, structure, and target accessibility."""
        config_path = Path(config_path)
        logger.info(f"Starting comprehensive validation for {config_path}")
        
        results = {
            'config_path': str(config_path),
            'timestamp': datetime.now().isoformat(),
            'overall_status': 'unknown',
            'syntax_validation': {},
            'structure_validation': {},
            'target_accessibility': [],
            'summary': {
                'total_errors': 0,
                'total_warnings': 0,
                'total_targets': 0,
                'accessible_targets': 0,
                'inaccessible_targets': 0
            }
        }
        
        try:
            # 1. Validate YAML syntax
            syntax_result = self.validate_yaml_syntax(config_path)
            results['syntax_validation'] = syntax_result.to_dict()
            
            if not syntax_result.is_valid:
                results['overall_status'] = 'failed'
                results['summary']['total_errors'] += len(syntax_result.errors)
                results['summary']['total_warnings'] += len(syntax_result.warnings)
                return results
            
            # 2. Load configuration for further validation
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            
            # 3. Validate configuration structure
            structure_result = self.validate_configuration_structure(config_data)
            results['structure_validation'] = structure_result.to_dict()
            results['summary']['total_errors'] += len(structure_result.errors)
            results['summary']['total_warnings'] += len(structure_result.warnings)
            
            if not structure_result.is_valid:
                results['overall_status'] = 'failed'
                return results
            
            # 4. Check target accessibility
            target_results = await self.check_scrape_targets_accessibility(config_data)
            results['target_accessibility'] = [result.to_dict() for result in target_results]
            
            # 5. Calculate summary statistics
            results['summary']['total_targets'] = len(target_results)
            results['summary']['accessible_targets'] = sum(1 for r in target_results if r.accessible)
            results['summary']['inaccessible_targets'] = results['summary']['total_targets'] - results['summary']['accessible_targets']
            
            # 6. Determine overall status
            if results['summary']['total_errors'] > 0:
                results['overall_status'] = 'failed'
            elif results['summary']['inaccessible_targets'] > 0 or results['summary']['total_warnings'] > 0:
                results['overall_status'] = 'degraded'
            else:
                results['overall_status'] = 'healthy'
            
            logger.info(f"Comprehensive validation completed. Status: {results['overall_status']}")
            return results
            
        except Exception as e:
            error_msg = f"Error during comprehensive validation: {str(e)}"
            logger.error(error_msg)
            results['overall_status'] = 'failed'
            results['summary']['total_errors'] += 1
            if 'syntax_validation' not in results or not results['syntax_validation']:
                results['syntax_validation'] = {
                    'is_valid': False,
                    'errors': [error_msg],
                    'warnings': [],
                    'suggestions': []
                }
            return results

    def close(self):
        """Clean up resources."""
        if hasattr(self, 'session'):
            self.session.close()
        logger.info("Configuration validator closed")


# Convenience functions
def validate_prometheus_config_syntax(config_path: Union[str, Path]) -> ValidationResult:
    """Convenience function to validate Prometheus configuration syntax."""
    validator = PrometheusConfigValidator()
    try:
        return validator.validate_yaml_syntax(config_path)
    finally:
        validator.close()


async def check_prometheus_targets(config_path: Union[str, Path]) -> List[TargetAccessibilityResult]:
    """Convenience function to check Prometheus scrape targets accessibility."""
    validator = PrometheusConfigValidator()
    try:
        # Load configuration
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        
        return await validator.check_scrape_targets_accessibility(config_data)
    finally:
        validator.close()


async def validate_prometheus_config_comprehensive(config_path: Union[str, Path]) -> Dict[str, Any]:
    """Convenience function to perform comprehensive Prometheus configuration validation."""
    validator = PrometheusConfigValidator()
    try:
        return await validator.comprehensive_validation(config_path)
    finally:
        validator.close()


def auto_correct_prometheus_config(config_path: Union[str, Path], backup: bool = True) -> ValidationResult:
    """Convenience function to auto-correct Prometheus configuration."""
    validator = PrometheusConfigValidator()
    try:
        return validator.auto_correct_configuration(config_path, backup)
    finally:
        validator.close()


if __name__ == "__main__":
    import sys
    
    async def main():
        """Main function for command-line usage."""
        if len(sys.argv) < 2:
            print("Usage: python config_validator.py <config_path> [--auto-correct]")
            sys.exit(1)
        
        config_path = sys.argv[1]
        auto_correct = '--auto-correct' in sys.argv
        
        print("🔍 Prometheus Configuration Validator")
        print(f"Configuration file: {config_path}")
        print("-" * 60)
        
        if auto_correct:
            print("🔧 Auto-correcting configuration...")
            result = auto_correct_prometheus_config(config_path)
            
            if result.is_valid:
                print("✅ Configuration auto-corrected successfully!")
                if result.warnings:
                    print("Warnings:")
                    for warning in result.warnings:
                        print(f"  • {warning}")
            else:
                print("❌ Auto-correction failed:")
                for error in result.errors:
                    print(f"  • {error}")
        else:
            # Basic validation
            validator = PrometheusConfigValidator()
            try:
                syntax_result = validator.validate_yaml_syntax(config_path)
                print(f"📝 YAML Syntax: {'✅ Valid' if syntax_result.is_valid else '❌ Invalid'}")
                
                if syntax_result.errors:
                    print("  Errors:")
                    for error in syntax_result.errors:
                        print(f"    • {error}")
                
                if syntax_result.is_valid:
                    with open(config_path, 'r') as f:
                        config_data = yaml.safe_load(f)
                    
                    structure_result = validator.validate_configuration_structure(config_data)
                    print(f"🏗️  Structure: {'✅ Valid' if structure_result.is_valid else '❌ Invalid'}")
                    
                    if structure_result.errors:
                        print("  Errors:")
                        for error in structure_result.errors:
                            print(f"    • {error}")
                    
                    if structure_result.warnings:
                        print("  Warnings:")
                        for warning in structure_result.warnings:
                            print(f"    • {warning}")
                    
                    # Check targets
                    targets = await validator.check_scrape_targets_accessibility(config_data)
                    accessible = sum(1 for t in targets if t.accessible)
                    print(f"🌐 Target Accessibility: {accessible}/{len(targets)} accessible")
                    
                    for target_result in targets:
                        status = "✅" if target_result.accessible else "❌"
                        print(f"  {status} {target_result.target}")
                        if not target_result.accessible and target_result.error_message:
                            print(f"    Error: {target_result.error_message}")
                
            finally:
                validator.close()
    
    # Run the main function
    asyncio.run(main())