#!/usr/bin/env python3
"""
Example usage of the Prometheus Configuration Validator

This script demonstrates how to use the PrometheusConfigValidator
to validate, check targets, and auto-correct Prometheus configurations.
"""

import asyncio
import tempfile
import yaml
from pathlib import Path

from src.monitoring.config_validator import (
    PrometheusConfigValidator,
    validate_prometheus_config_syntax,
    check_prometheus_targets,
    validate_prometheus_config_comprehensive,
    auto_correct_prometheus_config
)


def create_sample_configs():
    """Create sample configuration files for testing."""
    
    # Valid configuration
    valid_config = {
        'global': {
            'scrape_interval': '15s',
            'evaluation_interval': '15s',
            'external_labels': {
                'monitor': 'example'
            }
        },
        'scrape_configs': [
            {
                'job_name': 'prometheus',
                'static_configs': [
                    {'targets': ['localhost:9090']}
                ]
            },
            {
                'job_name': 'example-app',
                'static_configs': [
                    {'targets': ['app:8000']}
                ],
                'metrics_path': '/metrics',
                'scrape_interval': '10s'
            }
        ]
    }
    
    # Invalid configuration (missing global, job_name, and ports)
    invalid_config = {
        'scrape_configs': [
            {
                'static_configs': [
                    {'targets': ['localhost', 'app']}
                ]
            }
        ]
    }
    
    # Create temporary files
    valid_file = Path(tempfile.mktemp(suffix='.yml'))
    invalid_file = Path(tempfile.mktemp(suffix='.yml'))
    
    with open(valid_file, 'w') as f:
        yaml.dump(valid_config, f, default_flow_style=False, indent=2)
    
    with open(invalid_file, 'w') as f:
        yaml.dump(invalid_config, f, default_flow_style=False, indent=2)
    
    return valid_file, invalid_file


async def example_basic_validation():
    """Example of basic YAML syntax validation."""
    print("🔍 Example 1: Basic YAML Syntax Validation")
    print("-" * 50)
    
    valid_file, invalid_file = create_sample_configs()
    
    try:
        # Test valid configuration
        result = validate_prometheus_config_syntax(valid_file)
        print(f"Valid config: {'✅ PASSED' if result.is_valid else '❌ FAILED'}")
        
        # Test invalid configuration
        result = validate_prometheus_config_syntax(invalid_file)
        print(f"Invalid config: {'✅ PASSED' if result.is_valid else '❌ FAILED'}")
        
        if result.warnings:
            print("Warnings:")
            for warning in result.warnings:
                print(f"  • {warning}")
                
    finally:
        valid_file.unlink()
        invalid_file.unlink()
    
    print()


async def example_target_accessibility():
    """Example of target accessibility checking."""
    print("🌐 Example 2: Target Accessibility Checking")
    print("-" * 50)
    
    valid_file, invalid_file = create_sample_configs()
    
    try:
        # Check targets in valid configuration
        results = await check_prometheus_targets(valid_file)
        
        print(f"Checked {len(results)} targets:")
        for result in results:
            status = "✅" if result.accessible else "❌"
            print(f"  {status} {result.target}")
            if not result.accessible and result.error_message:
                print(f"    Error: {result.error_message}")
                
    finally:
        valid_file.unlink()
        invalid_file.unlink()
    
    print()


async def example_comprehensive_validation():
    """Example of comprehensive validation."""
    print("📋 Example 3: Comprehensive Validation")
    print("-" * 50)
    
    valid_file, invalid_file = create_sample_configs()
    
    try:
        # Comprehensive validation of valid config
        result = await validate_prometheus_config_comprehensive(valid_file)
        
        print(f"Overall Status: {result['overall_status'].upper()}")
        print(f"YAML Syntax: {'✅' if result['syntax_validation']['is_valid'] else '❌'}")
        print(f"Structure: {'✅' if result['structure_validation']['is_valid'] else '❌'}")
        print(f"Targets: {result['summary']['accessible_targets']}/{result['summary']['total_targets']} accessible")
        
        if result['summary']['total_errors'] > 0:
            print(f"Errors: {result['summary']['total_errors']}")
        if result['summary']['total_warnings'] > 0:
            print(f"Warnings: {result['summary']['total_warnings']}")
            
    finally:
        valid_file.unlink()
        invalid_file.unlink()
    
    print()


async def example_auto_correction():
    """Example of auto-correction functionality."""
    print("🔧 Example 4: Auto-Correction")
    print("-" * 50)
    
    valid_file, invalid_file = create_sample_configs()
    
    try:
        print("Before auto-correction:")
        with open(invalid_file, 'r') as f:
            original = yaml.safe_load(f)
        print(f"  Has global section: {'global' in original}")
        print(f"  First job has name: {'job_name' in original['scrape_configs'][0]}")
        print(f"  First target: {original['scrape_configs'][0]['static_configs'][0]['targets'][0]}")
        
        # Auto-correct the invalid configuration
        result = auto_correct_prometheus_config(invalid_file, backup=False)
        
        print(f"\nAuto-correction: {'✅ SUCCESS' if result.is_valid else '❌ FAILED'}")
        
        if result.is_valid:
            print("After auto-correction:")
            with open(invalid_file, 'r') as f:
                corrected = yaml.safe_load(f)
            print(f"  Has global section: {'global' in corrected}")
            print(f"  First job name: {corrected['scrape_configs'][0]['job_name']}")
            print(f"  First target: {corrected['scrape_configs'][0]['static_configs'][0]['targets'][0]}")
        
        if result.warnings:
            print("Warnings:")
            for warning in result.warnings:
                print(f"  • {warning}")
                
    finally:
        valid_file.unlink()
        invalid_file.unlink()
    
    print()


async def example_advanced_usage():
    """Example of advanced validator usage."""
    print("⚙️  Example 5: Advanced Usage with Custom Validator")
    print("-" * 50)
    
    # Create validator with custom timeout
    validator = PrometheusConfigValidator(timeout=5)
    
    try:
        # Create a test configuration
        test_config = {
            'global': {'scrape_interval': '30s'},
            'scrape_configs': [
                {
                    'job_name': 'test-service',
                    'static_configs': [
                        {'targets': ['service1:8080', 'service2:8080']}
                    ],
                    'metrics_path': '/custom/metrics',
                    'scrape_interval': '5s'
                }
            ]
        }
        
        # Validate structure
        structure_result = validator.validate_configuration_structure(test_config)
        print(f"Structure validation: {'✅ PASSED' if structure_result.is_valid else '❌ FAILED'}")
        
        if structure_result.warnings:
            print("Structure warnings:")
            for warning in structure_result.warnings:
                print(f"  • {warning}")
        
        # Check target accessibility
        targets = await validator.check_scrape_targets_accessibility(test_config)
        accessible_count = sum(1 for t in targets if t.accessible)
        print(f"Target accessibility: {accessible_count}/{len(targets)} accessible")
        
        for target in targets:
            status = "✅" if target.accessible else "❌"
            response_time = f" ({target.response_time_ms:.1f}ms)" if target.response_time_ms else ""
            print(f"  {status} {target.target}{response_time}")
            
    finally:
        validator.close()
    
    print()


async def main():
    """Run all examples."""
    print("🚀 Prometheus Configuration Validator Examples")
    print("=" * 60)
    print()
    
    await example_basic_validation()
    await example_target_accessibility()
    await example_comprehensive_validation()
    await example_auto_correction()
    await example_advanced_usage()
    
    print("✨ All examples completed!")


if __name__ == "__main__":
    asyncio.run(main())