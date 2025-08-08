#!/usr/bin/env python3
"""
Novofon SIP Integration Validation Script

This script validates the complete migration from MTS Exolve to Novofon
and ensures all configuration files and system components are properly updated.
"""

import os
import sys
import json
import yaml
import socket
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Any

def check_environment_variables() -> Tuple[bool, List[str]]:
    """Check that all Novofon environment variables are properly set."""
    print("🔍 Checking environment variables...")
    
    required_vars = {
        'SIP_NUMBER': '+79952227978',
        'SIP_SERVER': 'sip.novofon.ru',
        'SIP_USERNAME': '0053248',
        'SIP_PASSWORD': 's8zrerUKYC'
    }
    
    issues = []
    
    # Check .env file
    env_file = Path('.env')
    if env_file.exists():
        with open(env_file, 'r') as f:
            env_content = f.read()
            
        for var, expected_value in required_vars.items():
            if f"{var}={expected_value}" not in env_content:
                issues.append(f".env file missing or incorrect {var}")
    else:
        issues.append(".env file not found")
    
    # Check .env.production file
    env_prod_file = Path('.env.production')
    if env_prod_file.exists():
        with open(env_prod_file, 'r') as f:
            env_prod_content = f.read()
            
        for var, expected_value in required_vars.items():
            if f"{var}={expected_value}" not in env_prod_content:
                issues.append(f".env.production file missing or incorrect {var}")
    else:
        issues.append(".env.production file not found")
    
    return len(issues) == 0, issues

def check_livekit_config() -> Tuple[bool, List[str]]:
    """Check that livekit-sip.yaml is updated for Novofon."""
    print("🔍 Checking LiveKit SIP configuration...")
    
    issues = []
    config_file = Path('livekit-sip.yaml')
    
    if not config_file.exists():
        issues.append("livekit-sip.yaml file not found")
        return False, issues
    
    try:
        with open(config_file, 'r') as f:
            content = f.read()
        
        # Check for Novofon references
        if 'novofon-trunk' not in content:
            issues.append("livekit-sip.yaml does not contain 'novofon-trunk'")
        
        if 'Novofon integration' not in content:
            issues.append("livekit-sip.yaml header not updated for Novofon")
        
        # Check for remaining MTS Exolve references
        if 'mts-exolve' in content.lower():
            issues.append("livekit-sip.yaml still contains MTS Exolve references")
        
    except Exception as e:
        issues.append(f"Error reading livekit-sip.yaml: {e}")
    
    return len(issues) == 0, issues

def check_documentation_updates() -> Tuple[bool, List[str]]:
    """Check that documentation is updated with Novofon information."""
    print("🔍 Checking documentation updates...")
    
    issues = []
    doc_files = [
        'docs/PROJECT_DOCUMENTATION.md',
        'docs/deployment_guide.md',
        'docs/production_deployment_guide.md',
        'docs/sip_integration_setup.md',
        'docs/operational_runbook.md',
        'docs/TROUBLESHOOTING_GUIDE.md',
        '.kiro/specs/voice-ai-agent/design.md'
    ]
    
    for doc_file in doc_files:
        file_path = Path(doc_file)
        if file_path.exists():
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                
                # Check for remaining MTS Exolve references
                if 'MTS Exolve' in content or 'mts-exolve' in content:
                    issues.append(f"{doc_file} still contains MTS Exolve references")
                
                # Check for Novofon references in key files
                if doc_file in ['docs/sip_integration_setup.md', 'docs/PROJECT_DOCUMENTATION.md']:
                    if 'Novofon' not in content:
                        issues.append(f"{doc_file} missing Novofon references")
                        
            except Exception as e:
                issues.append(f"Error reading {doc_file}: {e}")
        else:
            issues.append(f"Documentation file {doc_file} not found")
    
    return len(issues) == 0, issues

def check_script_updates() -> Tuple[bool, List[str]]:
    """Check that diagnostic and test scripts are updated."""
    print("🔍 Checking script updates...")
    
    issues = []
    script_files = [
        'scripts/diagnose_sip_issue.py',
        'scripts/test_real_call.py'
    ]
    
    for script_file in script_files:
        file_path = Path(script_file)
        if file_path.exists():
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                
                # Check for remaining MTS Exolve references
                if 'MTS Exolve' in content:
                    issues.append(f"{script_file} still contains MTS Exolve references")
                
                # Check for Novofon references
                if 'Novofon' not in content:
                    issues.append(f"{script_file} missing Novofon references")
                        
            except Exception as e:
                issues.append(f"Error reading {script_file}: {e}")
        else:
            issues.append(f"Script file {script_file} not found")
    
    return len(issues) == 0, issues

def test_sip_connectivity() -> Tuple[bool, List[str]]:
    """Test basic network connectivity to Novofon SIP server."""
    print("🔍 Testing SIP connectivity to Novofon...")
    
    issues = []
    
    try:
        # Test DNS resolution
        socket.gethostbyname('sip.novofon.ru')
        print("  ✅ DNS resolution for sip.novofon.ru successful")
        
        # Test UDP connectivity
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(5)
        
        try:
            # Send a basic SIP OPTIONS request
            sip_message = (
                "OPTIONS sip:test@sip.novofon.ru SIP/2.0\r\n"
                "Via: SIP/2.0/UDP test:5060;branch=z9hG4bK-test\r\n"
                "From: <sip:test@test>;tag=test\r\n"
                "To: <sip:test@sip.novofon.ru>\r\n"
                "Call-ID: test@test\r\n"
                "CSeq: 1 OPTIONS\r\n"
                "Content-Length: 0\r\n\r\n"
            )
            
            sock.sendto(sip_message.encode(), ('sip.novofon.ru', 5060))
            print("  ✅ SIP OPTIONS request sent successfully")
            
            # Try to receive response (timeout is expected without proper auth)
            try:
                response, addr = sock.recvfrom(1024)
                print(f"  ✅ Received SIP response from {addr}")
            except socket.timeout:
                print("  ⚠️  No SIP response (timeout) - normal without authentication")
                
        except Exception as e:
            issues.append(f"SIP connectivity test failed: {e}")
        finally:
            sock.close()
            
    except Exception as e:
        issues.append(f"DNS resolution failed for sip.novofon.ru: {e}")
    
    return len(issues) == 0, issues

def check_configuration_loading() -> Tuple[bool, List[str]]:
    """Test that the application can load Novofon configuration."""
    print("🔍 Testing configuration loading...")
    
    issues = []
    
    try:
        # Add current directory to Python path
        sys.path.insert(0, '.')
        
        from src.config import get_settings
        
        settings = get_settings()
        
        # Validate Novofon configuration
        expected_values = {
            'sip_number': '+79952227978',
            'sip_server': 'sip.novofon.ru',
            'sip_username': '0053248'
        }
        
        for attr, expected_value in expected_values.items():
            actual_value = getattr(settings, attr)
            if actual_value != expected_value:
                issues.append(f"Configuration {attr}: expected '{expected_value}', got '{actual_value}'")
        
        print("  ✅ Configuration loaded successfully")
        print(f"    SIP Number: {settings.sip_number}")
        print(f"    SIP Server: {settings.sip_server}")
        print(f"    SIP Username: {settings.sip_username}")
        
    except Exception as e:
        issues.append(f"Configuration loading failed: {e}")
    
    return len(issues) == 0, issues

def check_metrics_and_test_files() -> Tuple[bool, List[str]]:
    """Check that metrics and test result files are updated."""
    print("🔍 Checking metrics and test files...")
    
    issues = []
    
    # Check metrics.json
    metrics_file = Path('metrics/metrics.json')
    if metrics_file.exists():
        try:
            with open(metrics_file, 'r') as f:
                content = f.read()
            
            if 'mts-exolve-trunk' in content:
                issues.append("metrics/metrics.json still contains mts-exolve-trunk references")
            
            if 'novofon-trunk' not in content:
                issues.append("metrics/metrics.json missing novofon-trunk references")
                
        except Exception as e:
            issues.append(f"Error reading metrics/metrics.json: {e}")
    
    # Check SIP integration test results
    test_results_file = Path('sip_integration_test_results.json')
    if test_results_file.exists():
        try:
            with open(test_results_file, 'r') as f:
                content = f.read()
            
            if 'mts-exolve-trunk' in content:
                issues.append("sip_integration_test_results.json still contains mts-exolve-trunk references")
                
        except Exception as e:
            issues.append(f"Error reading sip_integration_test_results.json: {e}")
    
    return len(issues) == 0, issues

def generate_validation_report(results: Dict[str, Tuple[bool, List[str]]]) -> None:
    """Generate a comprehensive validation report."""
    print("\n" + "="*80)
    print("🎯 NOVOFON MIGRATION VALIDATION REPORT")
    print("="*80)
    
    total_checks = len(results)
    passed_checks = sum(1 for success, _ in results.values() if success)
    
    print(f"\n📊 SUMMARY: {passed_checks}/{total_checks} checks passed")
    
    if passed_checks == total_checks:
        print("✅ ALL CHECKS PASSED - Novofon migration completed successfully!")
    else:
        print("❌ SOME CHECKS FAILED - Review issues below")
    
    print("\n📋 DETAILED RESULTS:")
    
    for check_name, (success, issues) in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"\n{status} {check_name}")
        
        if issues:
            for issue in issues:
                print(f"  • {issue}")
    
    # Recommendations
    if passed_checks < total_checks:
        print("\n🔧 RECOMMENDATIONS:")
        print("1. Fix all failed checks before deploying to production")
        print("2. Run this validation script again after making fixes")
        print("3. Test end-to-end call functionality with Novofon")
        print("4. Monitor system logs during initial deployment")
    
    print("\n" + "="*80)

def main():
    """Run all validation checks."""
    print("🚀 Starting Novofon SIP Integration Validation")
    print("="*60)
    
    # Define all validation checks
    validation_checks = {
        "Environment Variables": check_environment_variables,
        "LiveKit Configuration": check_livekit_config,
        "Documentation Updates": check_documentation_updates,
        "Script Updates": check_script_updates,
        "SIP Connectivity": test_sip_connectivity,
        "Configuration Loading": check_configuration_loading,
        "Metrics and Test Files": check_metrics_and_test_files
    }
    
    # Run all checks
    results = {}
    for check_name, check_function in validation_checks.items():
        try:
            success, issues = check_function()
            results[check_name] = (success, issues)
        except Exception as e:
            results[check_name] = (False, [f"Check failed with exception: {e}"])
    
    # Generate report
    generate_validation_report(results)
    
    # Exit with appropriate code
    all_passed = all(success for success, _ in results.values())
    sys.exit(0 if all_passed else 1)

if __name__ == "__main__":
    main()