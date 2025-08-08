#!/usr/bin/env python3
"""
Prometheus Deployment Validation Script

This script provides comprehensive validation of Prometheus deployment,
including pre-deployment checks, post-deployment verification, and
rollback capabilities for failed deployments.
"""

import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.monitoring.prometheus_health import PrometheusHealthChecker, generate_prometheus_report
from src.monitoring.config_validator import PrometheusConfigValidator, validate_prometheus_config_comprehensive
from src.monitoring.prometheus_recovery import PrometheusRecovery, recover_prometheus


class PrometheusDeploymentValidator:
    """Comprehensive Prometheus deployment validator."""
    
    def __init__(self, 
                 prometheus_url: str = "http://localhost:9091",
                 config_path: str = "monitoring/prometheus/prometheus.yml",
                 docker_compose_path: str = "docker-compose.prod.yml"):
        self.prometheus_url = prometheus_url
        self.config_path = Path(config_path)
        self.docker_compose_path = Path(docker_compose_path)
        
        # Initialize components
        self.health_checker = PrometheusHealthChecker(prometheus_url, str(config_path))
        self.config_validator = PrometheusConfigValidator()
        self.recovery_system = PrometheusRecovery(prometheus_url, str(config_path), str(docker_compose_path))
        
        # Setup logging
        self.logger = self._setup_logging()
        
        self.logger.info(f"Initialized Prometheus deployment validator")
        self.logger.info(f"  Prometheus URL: {prometheus_url}")
        self.logger.info(f"  Config Path: {config_path}")
        self.logger.info(f"  Docker Compose: {docker_compose_path}")
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging for the validator."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('prometheus_deployment_validation.log'),
                logging.StreamHandler()
            ]
        )
        return logging.getLogger(__name__)
    
    async def run_pre_deployment_validation(self) -> Dict[str, Any]:
        """
        Run comprehensive pre-deployment validation.
        
        Returns:
            Dict with validation results
        """
        self.logger.info("🔍 Starting pre-deployment validation")
        
        validation_results = {
            'timestamp': datetime.now().isoformat(),
            'phase': 'pre_deployment',
            'overall_status': 'unknown',
            'checks': {},
            'issues': [],
            'recommendations': []
        }
        
        try:
            # 1. Configuration validation
            self.logger.info("Validating Prometheus configuration...")
            config_validation = await validate_prometheus_config_comprehensive(self.config_path)
            validation_results['checks']['configuration'] = config_validation
            
            if config_validation['overall_status'] != 'healthy':
                validation_results['issues'].append("Prometheus configuration has issues")
                validation_results['recommendations'].extend([
                    "Review configuration validation errors",
                    "Consider using auto-correction feature",
                    "Verify scrape target accessibility"
                ])
            
            # 2. Docker Compose validation
            self.logger.info("Validating Docker Compose configuration...")
            docker_validation = self._validate_docker_compose()
            validation_results['checks']['docker_compose'] = docker_validation
            
            if not docker_validation['valid']:
                validation_results['issues'].append("Docker Compose configuration issues")
                validation_results['recommendations'].extend(docker_validation['recommendations'])
            
            # 3. System prerequisites
            self.logger.info("Checking system prerequisites...")
            prereq_validation = self._check_system_prerequisites()
            validation_results['checks']['prerequisites'] = prereq_validation
            
            if not prereq_validation['all_met']:
                validation_results['issues'].append("System prerequisites not met")
                validation_results['recommendations'].extend(prereq_validation['recommendations'])
            
            # 4. Port availability
            self.logger.info("Checking port availability...")
            port_validation = self._check_port_availability()
            validation_results['checks']['ports'] = port_validation
            
            if not port_validation['all_available']:
                validation_results['issues'].append("Required ports are not available")
                validation_results['recommendations'].extend(port_validation['recommendations'])
            
            # Determine overall status
            if len(validation_results['issues']) == 0:
                validation_results['overall_status'] = 'passed'
                self.logger.info("✅ Pre-deployment validation: PASSED")
            else:
                validation_results['overall_status'] = 'failed'
                self.logger.error(f"❌ Pre-deployment validation: FAILED ({len(validation_results['issues'])} issues)")
            
            return validation_results
            
        except Exception as e:
            error_msg = f"Pre-deployment validation failed with exception: {str(e)}"
            self.logger.error(error_msg)
            validation_results['overall_status'] = 'error'
            validation_results['issues'].append(error_msg)
            return validation_results
    
    async def run_post_deployment_verification(self) -> Dict[str, Any]:
        """
        Run comprehensive post-deployment verification.
        
        Returns:
            Dict with verification results
        """
        self.logger.info("🔍 Starting post-deployment verification")
        
        verification_results = {
            'timestamp': datetime.now().isoformat(),
            'phase': 'post_deployment',
            'overall_status': 'unknown',
            'checks': {},
            'issues': [],
            'recommendations': []
        }
        
        try:
            # 1. Service health check
            self.logger.info("Checking Prometheus service health...")
            health_result = await self.health_checker.comprehensive_health_check()
            verification_results['checks']['service_health'] = health_result.to_dict()
            
            if health_result.status != 'healthy':
                verification_results['issues'].append(f"Prometheus service status: {health_result.status}")
                verification_results['recommendations'].extend(health_result.recovery_actions)
            
            # 2. API endpoints verification
            self.logger.info("Verifying Prometheus API endpoints...")
            api_verification = await self._verify_api_endpoints()
            verification_results['checks']['api_endpoints'] = api_verification
            
            if not api_verification['all_accessible']:
                verification_results['issues'].append("Some Prometheus API endpoints are not accessible")
                verification_results['recommendations'].extend(api_verification['recommendations'])
            
            # 3. Scrape targets verification
            self.logger.info("Verifying scrape targets...")
            targets_verification = await self._verify_scrape_targets()
            verification_results['checks']['scrape_targets'] = targets_verification
            
            if targets_verification['failed_targets'] > 0:
                verification_results['issues'].append(f"{targets_verification['failed_targets']} scrape targets are not accessible")
                verification_results['recommendations'].extend(targets_verification['recommendations'])
            
            # 4. Data collection verification
            self.logger.info("Verifying data collection...")
            data_verification = await self._verify_data_collection()
            verification_results['checks']['data_collection'] = data_verification
            
            if not data_verification['collecting_data']:
                verification_results['issues'].append("Prometheus is not collecting metrics data")
                verification_results['recommendations'].extend(data_verification['recommendations'])
            
            # 5. Integration verification
            self.logger.info("Verifying monitoring stack integration...")
            integration_verification = await self._verify_monitoring_integration()
            verification_results['checks']['integration'] = integration_verification
            
            if not integration_verification['fully_integrated']:
                verification_results['issues'].append("Monitoring stack integration issues")
                verification_results['recommendations'].extend(integration_verification['recommendations'])
            
            # Determine overall status
            critical_issues = sum(1 for issue in verification_results['issues'] 
                                if 'not accessible' in issue or 'not collecting' in issue)
            
            if len(verification_results['issues']) == 0:
                verification_results['overall_status'] = 'passed'
                self.logger.info("✅ Post-deployment verification: PASSED")
            elif critical_issues == 0:
                verification_results['overall_status'] = 'degraded'
                self.logger.warning(f"⚠️  Post-deployment verification: DEGRADED ({len(verification_results['issues'])} non-critical issues)")
            else:
                verification_results['overall_status'] = 'failed'
                self.logger.error(f"❌ Post-deployment verification: FAILED ({critical_issues} critical issues)")
            
            return verification_results
            
        except Exception as e:
            error_msg = f"Post-deployment verification failed with exception: {str(e)}"
            self.logger.error(error_msg)
            verification_results['overall_status'] = 'error'
            verification_results['issues'].append(error_msg)
            return verification_results
    
    async def attempt_deployment_recovery(self) -> Dict[str, Any]:
        """
        Attempt to recover from deployment failures.
        
        Returns:
            Dict with recovery results
        """
        self.logger.info("🔧 Starting deployment recovery")
        
        recovery_results = {
            'timestamp': datetime.now().isoformat(),
            'phase': 'recovery',
            'overall_status': 'unknown',
            'recovery_actions': [],
            'final_verification': {}
        }
        
        try:
            # Attempt Prometheus recovery
            recovery_result = await self.recovery_system.attempt_recovery()
            
            recovery_results['recovery_actions'] = [
                {
                    'action_type': action.action_type,
                    'success': action.success,
                    'details': action.details,
                    'duration_seconds': action.duration_seconds,
                    'timestamp': action.timestamp.isoformat()
                }
                for action in recovery_result.actions_taken
            ]
            
            if recovery_result.success:
                self.logger.info("✅ Recovery attempt successful")
                
                # Run verification after recovery
                verification_results = await self.run_post_deployment_verification()
                recovery_results['final_verification'] = verification_results
                
                if verification_results['overall_status'] in ['passed', 'degraded']:
                    recovery_results['overall_status'] = 'success'
                else:
                    recovery_results['overall_status'] = 'partial'
            else:
                self.logger.error("❌ Recovery attempt failed")
                recovery_results['overall_status'] = 'failed'
                recovery_results['error_message'] = recovery_result.error_message
            
            return recovery_results
            
        except Exception as e:
            error_msg = f"Recovery attempt failed with exception: {str(e)}"
            self.logger.error(error_msg)
            recovery_results['overall_status'] = 'error'
            recovery_results['error_message'] = error_msg
            return recovery_results
    
    def _validate_docker_compose(self) -> Dict[str, Any]:
        """Validate Docker Compose configuration."""
        try:
            if not self.docker_compose_path.exists():
                return {
                    'valid': False,
                    'error': f"Docker Compose file not found: {self.docker_compose_path}",
                    'recommendations': ["Create Docker Compose configuration file"]
                }
            
            # Basic validation - check if file is readable
            with open(self.docker_compose_path, 'r') as f:
                content = f.read()
            
            # Check for Prometheus service definition
            if 'prometheus:' not in content:
                return {
                    'valid': False,
                    'error': "Prometheus service not defined in Docker Compose",
                    'recommendations': ["Add Prometheus service to Docker Compose configuration"]
                }
            
            return {
                'valid': True,
                'recommendations': []
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': f"Docker Compose validation error: {str(e)}",
                'recommendations': ["Check Docker Compose file syntax and permissions"]
            }
    
    def _check_system_prerequisites(self) -> Dict[str, Any]:
        """Check system prerequisites for Prometheus deployment."""
        import subprocess
        import shutil
        
        prerequisites = {
            'docker': shutil.which('docker') is not None,
            'docker_compose': shutil.which('docker-compose') is not None or shutil.which('docker') is not None,
            'python3': shutil.which('python3') is not None,
            'curl': shutil.which('curl') is not None,
            'jq': shutil.which('jq') is not None
        }
        
        # Check Docker daemon
        try:
            result = subprocess.run(['docker', 'info'], capture_output=True, timeout=10)
            prerequisites['docker_daemon'] = result.returncode == 0
        except:
            prerequisites['docker_daemon'] = False
        
        all_met = all(prerequisites.values())
        
        recommendations = []
        for prereq, met in prerequisites.items():
            if not met:
                if prereq == 'docker':
                    recommendations.append("Install Docker")
                elif prereq == 'docker_compose':
                    recommendations.append("Install Docker Compose")
                elif prereq == 'python3':
                    recommendations.append("Install Python 3")
                elif prereq == 'curl':
                    recommendations.append("Install curl")
                elif prereq == 'jq':
                    recommendations.append("Install jq for JSON processing")
                elif prereq == 'docker_daemon':
                    recommendations.append("Start Docker daemon")
        
        return {
            'all_met': all_met,
            'prerequisites': prerequisites,
            'recommendations': recommendations
        }
    
    def _check_port_availability(self) -> Dict[str, Any]:
        """Check if required ports are available."""
        import socket
        
        required_ports = [9091, 3000, 8000]  # Prometheus, Grafana, Application
        port_status = {}
        
        for port in required_ports:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(1)
                    result = s.connect_ex(('localhost', port))
                    port_status[port] = result != 0  # True if port is available (connection failed)
            except:
                port_status[port] = True  # Assume available if check fails
        
        all_available = all(port_status.values())
        
        recommendations = []
        for port, available in port_status.items():
            if not available:
                recommendations.append(f"Port {port} is in use - stop conflicting service or change port configuration")
        
        return {
            'all_available': all_available,
            'port_status': port_status,
            'recommendations': recommendations
        }
    
    async def _verify_api_endpoints(self) -> Dict[str, Any]:
        """Verify Prometheus API endpoints."""
        import aiohttp
        
        endpoints = {
            'health': '/-/healthy',
            'ready': '/-/ready',
            'config': '/api/v1/status/config',
            'targets': '/api/v1/targets',
            'query': '/api/v1/query?query=up',
            'metrics': '/metrics'
        }
        
        endpoint_status = {}
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            for name, endpoint in endpoints.items():
                try:
                    url = f"{self.prometheus_url}{endpoint}"
                    async with session.get(url) as response:
                        endpoint_status[name] = {
                            'accessible': response.status == 200,
                            'status_code': response.status,
                            'response_time_ms': 0  # Simplified
                        }
                except Exception as e:
                    endpoint_status[name] = {
                        'accessible': False,
                        'error': str(e),
                        'response_time_ms': None
                    }
        
        all_accessible = all(status['accessible'] for status in endpoint_status.values())
        
        recommendations = []
        for name, status in endpoint_status.items():
            if not status['accessible']:
                recommendations.append(f"Fix {name} endpoint accessibility")
        
        return {
            'all_accessible': all_accessible,
            'endpoints': endpoint_status,
            'recommendations': recommendations
        }
    
    async def _verify_scrape_targets(self) -> Dict[str, Any]:
        """Verify Prometheus scrape targets."""
        try:
            # Load configuration and check targets
            config_validation = await validate_prometheus_config_comprehensive(self.config_path)
            
            target_results = config_validation.get('target_accessibility', [])
            
            total_targets = len(target_results)
            failed_targets = sum(1 for result in target_results if not result.get('accessible', False))
            
            recommendations = []
            if failed_targets > 0:
                recommendations.extend([
                    "Check network connectivity to failed targets",
                    "Verify target services are running and healthy",
                    "Review firewall and security group settings"
                ])
            
            return {
                'total_targets': total_targets,
                'failed_targets': failed_targets,
                'success_rate': (total_targets - failed_targets) / total_targets if total_targets > 0 else 0,
                'target_details': target_results,
                'recommendations': recommendations
            }
            
        except Exception as e:
            return {
                'total_targets': 0,
                'failed_targets': 0,
                'success_rate': 0,
                'error': str(e),
                'recommendations': ["Fix configuration validation issues"]
            }
    
    async def _verify_data_collection(self) -> Dict[str, Any]:
        """Verify that Prometheus is collecting metrics data."""
        import aiohttp
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                # Query for 'up' metric to see if data is being collected
                url = f"{self.prometheus_url}/api/v1/query"
                params = {'query': 'up'}
                
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get('status') == 'success':
                            results = data.get('data', {}).get('result', [])
                            collecting_data = len(results) > 0
                            
                            return {
                                'collecting_data': collecting_data,
                                'active_targets': len(results),
                                'recommendations': [] if collecting_data else [
                                    "Check scrape target configurations",
                                    "Verify target services are exposing metrics",
                                    "Review Prometheus logs for scraping errors"
                                ]
                            }
                        else:
                            return {
                                'collecting_data': False,
                                'error': f"Query failed: {data.get('error', 'Unknown error')}",
                                'recommendations': ["Check Prometheus query API functionality"]
                            }
                    else:
                        return {
                            'collecting_data': False,
                            'error': f"HTTP {response.status}",
                            'recommendations': ["Check Prometheus API accessibility"]
                        }
                        
        except Exception as e:
            return {
                'collecting_data': False,
                'error': str(e),
                'recommendations': ["Check Prometheus service connectivity"]
            }
    
    async def _verify_monitoring_integration(self) -> Dict[str, Any]:
        """Verify monitoring stack integration."""
        integration_checks = {
            'prometheus_to_grafana': False,
            'application_to_prometheus': False,
            'alerting_configured': False
        }
        
        recommendations = []
        
        try:
            # Check if Grafana can connect to Prometheus (simplified check)
            import aiohttp
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                # Check Grafana health
                try:
                    async with session.get('http://localhost:3000/api/health') as response:
                        if response.status == 200:
                            integration_checks['prometheus_to_grafana'] = True
                        else:
                            recommendations.append("Check Grafana connectivity to Prometheus")
                except:
                    recommendations.append("Grafana is not accessible")
                
                # Check if application metrics are being scraped
                try:
                    url = f"{self.prometheus_url}/api/v1/query"
                    params = {'query': 'up{job="voice-ai-agent"}'}
                    
                    async with session.get(url, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data.get('status') == 'success' and data.get('data', {}).get('result'):
                                integration_checks['application_to_prometheus'] = True
                            else:
                                recommendations.append("Application metrics are not being scraped by Prometheus")
                        else:
                            recommendations.append("Cannot query application metrics from Prometheus")
                except:
                    recommendations.append("Failed to verify application metrics integration")
                
                # Check if alerting rules are configured (simplified)
                try:
                    async with session.get(f"{self.prometheus_url}/api/v1/rules") as response:
                        if response.status == 200:
                            data = await response.json()
                            if data.get('status') == 'success':
                                rules = data.get('data', {}).get('groups', [])
                                integration_checks['alerting_configured'] = len(rules) > 0
                            else:
                                recommendations.append("Configure Prometheus alerting rules")
                        else:
                            recommendations.append("Cannot access Prometheus alerting rules")
                except:
                    recommendations.append("Failed to verify alerting configuration")
            
        except Exception as e:
            recommendations.append(f"Integration verification failed: {str(e)}")
        
        fully_integrated = all(integration_checks.values())
        
        return {
            'fully_integrated': fully_integrated,
            'integration_status': integration_checks,
            'recommendations': recommendations
        }
    
    def generate_validation_report(self, 
                                 pre_deployment: Optional[Dict[str, Any]] = None,
                                 post_deployment: Optional[Dict[str, Any]] = None,
                                 recovery: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate comprehensive validation report."""
        report = {
            'report_timestamp': datetime.now().isoformat(),
            'prometheus_url': self.prometheus_url,
            'config_path': str(self.config_path),
            'docker_compose_path': str(self.docker_compose_path),
            'validation_phases': {},
            'overall_assessment': 'unknown',
            'summary': {
                'total_issues': 0,
                'critical_issues': 0,
                'recommendations': []
            }
        }
        
        # Include phase results
        if pre_deployment:
            report['validation_phases']['pre_deployment'] = pre_deployment
            report['summary']['total_issues'] += len(pre_deployment.get('issues', []))
        
        if post_deployment:
            report['validation_phases']['post_deployment'] = post_deployment
            report['summary']['total_issues'] += len(post_deployment.get('issues', []))
        
        if recovery:
            report['validation_phases']['recovery'] = recovery
        
        # Collect all recommendations
        all_recommendations = set()
        for phase_data in report['validation_phases'].values():
            all_recommendations.update(phase_data.get('recommendations', []))
        
        report['summary']['recommendations'] = list(all_recommendations)
        
        # Determine overall assessment
        if post_deployment:
            if post_deployment['overall_status'] == 'passed':
                report['overall_assessment'] = 'deployment_successful'
            elif post_deployment['overall_status'] == 'degraded':
                report['overall_assessment'] = 'deployment_degraded'
            else:
                report['overall_assessment'] = 'deployment_failed'
        elif pre_deployment:
            if pre_deployment['overall_status'] == 'passed':
                report['overall_assessment'] = 'ready_for_deployment'
            else:
                report['overall_assessment'] = 'not_ready_for_deployment'
        
        return report
    
    def close(self):
        """Clean up resources."""
        if hasattr(self, 'health_checker'):
            self.health_checker.close()
        if hasattr(self, 'config_validator'):
            self.config_validator.close()


async def main():
    """Main function for command-line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate Prometheus deployment")
    parser.add_argument("--prometheus-url", default="http://localhost:9091", 
                       help="Prometheus URL")
    parser.add_argument("--config-path", default="monitoring/prometheus/prometheus.yml",
                       help="Prometheus configuration file path")
    parser.add_argument("--docker-compose", default="docker-compose.prod.yml",
                       help="Docker Compose file path")
    parser.add_argument("--phase", choices=['pre', 'post', 'recovery', 'all'], default='all',
                       help="Validation phase to run")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    validator = PrometheusDeploymentValidator(
        prometheus_url=args.prometheus_url,
        config_path=args.config_path,
        docker_compose_path=args.docker_compose
    )
    
    try:
        pre_deployment_results = None
        post_deployment_results = None
        recovery_results = None
        
        if args.phase in ['pre', 'all']:
            print("🔍 Running pre-deployment validation...")
            pre_deployment_results = await validator.run_pre_deployment_validation()
        
        if args.phase in ['post', 'all']:
            print("🔍 Running post-deployment verification...")
            post_deployment_results = await validator.run_post_deployment_verification()
        
        if args.phase in ['recovery', 'all']:
            # Only run recovery if post-deployment failed
            if post_deployment_results and post_deployment_results['overall_status'] == 'failed':
                print("🔧 Running deployment recovery...")
                recovery_results = await validator.attempt_deployment_recovery()
        
        # Generate comprehensive report
        report = validator.generate_validation_report(
            pre_deployment=pre_deployment_results,
            post_deployment=post_deployment_results,
            recovery=recovery_results
        )
        
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            # Print formatted report
            print("\n" + "=" * 80)
            print("🏥 Prometheus Deployment Validation Report")
            print("=" * 80)
            print(f"Timestamp: {report['report_timestamp']}")
            print(f"Prometheus URL: {report['prometheus_url']}")
            print(f"Overall Assessment: {report['overall_assessment'].replace('_', ' ').title()}")
            
            if report['summary']['total_issues'] > 0:
                print(f"\n⚠️  Issues Found: {report['summary']['total_issues']}")
            
            # Show phase results
            for phase_name, phase_data in report['validation_phases'].items():
                status_emoji = {
                    'passed': '✅',
                    'degraded': '⚠️',
                    'failed': '❌',
                    'error': '💥',
                    'success': '✅',
                    'partial': '⚠️'
                }.get(phase_data['overall_status'], '❓')
                
                print(f"\n{status_emoji} {phase_name.replace('_', ' ').title()}: {phase_data['overall_status'].upper()}")
                
                if phase_data.get('issues'):
                    for issue in phase_data['issues'][:3]:  # Show first 3 issues
                        print(f"  • {issue}")
            
            # Show recommendations
            if report['summary']['recommendations']:
                print(f"\n💡 Key Recommendations:")
                for rec in report['summary']['recommendations'][:5]:  # Show top 5
                    print(f"  • {rec}")
        
        # Exit with appropriate code
        if report['overall_assessment'] in ['deployment_successful', 'ready_for_deployment']:
            sys.exit(0)
        elif report['overall_assessment'] in ['deployment_degraded']:
            sys.exit(1)
        else:
            sys.exit(2)
            
    except Exception as e:
        print(f"❌ Validation failed with exception: {str(e)}")
        sys.exit(2)
    finally:
        validator.close()


if __name__ == "__main__":
    asyncio.run(main())