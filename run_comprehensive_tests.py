#!/usr/bin/env python3
"""
Comprehensive test runner for LiveKit system.
Runs all test suites and generates detailed reports.
"""

import os
import sys
import subprocess
import time
import json
from datetime import datetime, UTC
from pathlib import Path


class ComprehensiveTestRunner:
    """Runner for comprehensive LiveKit testing."""
    
    def __init__(self):
        self.start_time = datetime.now(UTC)
        self.results = {
            "start_time": self.start_time.isoformat(),
            "test_suites": {},
            "summary": {},
            "errors": []
        }
        
        # Test suites configuration
        self.test_suites = {
            "unit": {
                "name": "Unit Tests",
                "files": ["tests/test_livekit_comprehensive.py"],
                "markers": ["unit"],
                "timeout": 300
            },
            "integration": {
                "name": "Integration Tests",
                "files": ["tests/test_livekit_integration_flow.py"],
                "markers": ["integration"],
                "timeout": 600
            },
            "performance": {
                "name": "Performance & Load Tests",
                "files": ["tests/test_livekit_performance_load.py"],
                "markers": ["performance"],
                "timeout": 1800
            },
            "security": {
                "name": "Security & Validation Tests",
                "files": ["tests/test_livekit_security_validation.py"],
                "markers": ["security"],
                "timeout": 600
            },
            "api": {
                "name": "API Endpoint Tests",
                "files": ["tests/test_livekit_api_endpoints.py"],
                "markers": ["api"],
                "timeout": 900
            }
        }
    
    def run_test_suite(self, suite_name, suite_config):
        """Run a specific test suite."""
        print(f"\n{'='*60}")
        print(f"Running {suite_config['name']}")
        print(f"{'='*60}")
        
        suite_start_time = time.time()
        
        # Build pytest command
        cmd = [
            sys.executable, "-m", "pytest",
            "-v",
            "--tb=short",
            "--color=yes",
            f"--timeout={suite_config['timeout']}",
            "--json-report",
            f"--json-report-file=test_results_{suite_name}.json"
        ]
        
        # Add marker filters
        for marker in suite_config['markers']:
            cmd.extend(["-m", marker])
        
        # Add test files
        cmd.extend(suite_config['files'])
        
        try:
            # Run tests
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=suite_config['timeout']
            )
            
            suite_end_time = time.time()
            suite_duration = suite_end_time - suite_start_time
            
            # Parse results
            suite_results = {
                "name": suite_config['name'],
                "duration": suite_duration,
                "return_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "success": result.returncode == 0
            }
            
            # Try to load JSON report if available
            json_report_file = f"test_results_{suite_name}.json"
            if os.path.exists(json_report_file):
                try:
                    with open(json_report_file, 'r') as f:
                        json_report = json.load(f)
                        suite_results["detailed_results"] = json_report
                except Exception as e:
                    suite_results["json_parse_error"] = str(e)
            
            self.results["test_suites"][suite_name] = suite_results
            
            # Print summary
            if result.returncode == 0:
                print(f"✅ {suite_config['name']} PASSED ({suite_duration:.1f}s)")
            else:
                print(f"❌ {suite_config['name']} FAILED ({suite_duration:.1f}s)")
                print(f"Error output: {result.stderr}")
            
            return result.returncode == 0
            
        except subprocess.TimeoutExpired:
            print(f"⏰ {suite_config['name']} TIMED OUT after {suite_config['timeout']}s")
            self.results["test_suites"][suite_name] = {
                "name": suite_config['name'],
                "duration": suite_config['timeout'],
                "return_code": -1,
                "error": "Test suite timed out",
                "success": False
            }
            return False
            
        except Exception as e:
            print(f"💥 {suite_config['name']} ERROR: {str(e)}")
            self.results["test_suites"][suite_name] = {
                "name": suite_config['name'],
                "duration": 0,
                "return_code": -1,
                "error": str(e),
                "success": False
            }
            return False
    
    def run_all_tests(self):
        """Run all test suites."""
        print("🚀 Starting Comprehensive LiveKit Testing")
        print(f"Start time: {self.start_time.isoformat()}")
        
        # Check prerequisites
        if not self.check_prerequisites():
            return False
        
        # Run each test suite
        all_passed = True
        for suite_name, suite_config in self.test_suites.items():
            success = self.run_test_suite(suite_name, suite_config)
            if not success:
                all_passed = False
        
        # Generate final report
        self.generate_final_report()
        
        return all_passed
    
    def check_prerequisites(self):
        """Check if all prerequisites are met."""
        print("\n🔍 Checking Prerequisites...")
        
        # Check Python version
        if sys.version_info < (3, 8):
            print("❌ Python 3.8+ required")
            return False
        print(f"✅ Python {sys.version}")
        
        # Check required packages
        required_packages = [
            "pytest", "pytest-asyncio", "pytest-timeout", 
            "livekit-api", "jwt", "psutil"
        ]
        
        for package in required_packages:
            try:
                __import__(package.replace("-", "_"))
                print(f"✅ {package}")
            except ImportError:
                print(f"❌ {package} not installed")
                return False
        
        # Check test files exist
        for suite_name, suite_config in self.test_suites.items():
            for test_file in suite_config['files']:
                if not os.path.exists(test_file):
                    print(f"❌ Test file missing: {test_file}")
                    return False
                print(f"✅ {test_file}")
        
        return True
    
    def generate_final_report(self):
        """Generate final test report."""
        end_time = datetime.now(UTC)
        total_duration = (end_time - self.start_time).total_seconds()
        
        # Calculate summary statistics
        total_suites = len(self.test_suites)
        passed_suites = sum(1 for r in self.results["test_suites"].values() if r["success"])
        failed_suites = total_suites - passed_suites
        
        # Update results
        self.results.update({
            "end_time": end_time.isoformat(),
            "total_duration": total_duration,
            "summary": {
                "total_suites": total_suites,
                "passed_suites": passed_suites,
                "failed_suites": failed_suites,
                "success_rate": passed_suites / total_suites if total_suites > 0 else 0
            }
        })
        
        # Print summary
        print(f"\n{'='*60}")
        print("📊 COMPREHENSIVE TEST RESULTS")
        print(f"{'='*60}")
        print(f"Total Duration: {total_duration:.1f}s")
        print(f"Test Suites: {total_suites}")
        print(f"Passed: {passed_suites}")
        print(f"Failed: {failed_suites}")
        print(f"Success Rate: {self.results['summary']['success_rate']:.1%}")
        
        # Print individual suite results
        print(f"\n{'Suite Results:'}")
        for suite_name, suite_result in self.results["test_suites"].items():
            status = "✅ PASS" if suite_result["success"] else "❌ FAIL"
            duration = suite_result.get("duration", 0)
            print(f"  {suite_result['name']}: {status} ({duration:.1f}s)")
        
        # Save detailed report
        report_file = f"comprehensive_test_report_{int(time.time())}.json"
        with open(report_file, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        print(f"\n📄 Detailed report saved to: {report_file}")
        
        # Overall result
        if passed_suites == total_suites:
            print("\n🎉 ALL TESTS PASSED!")
            return True
        else:
            print(f"\n💥 {failed_suites} TEST SUITE(S) FAILED!")
            return False
    
    def run_specific_suite(self, suite_name):
        """Run a specific test suite."""
        if suite_name not in self.test_suites:
            print(f"❌ Unknown test suite: {suite_name}")
            print(f"Available suites: {', '.join(self.test_suites.keys())}")
            return False
        
        print(f"🚀 Running {suite_name} test suite only")
        
        if not self.check_prerequisites():
            return False
        
        success = self.run_test_suite(suite_name, self.test_suites[suite_name])
        
        if success:
            print(f"\n🎉 {suite_name.upper()} TESTS PASSED!")
        else:
            print(f"\n💥 {suite_name.upper()} TESTS FAILED!")
        
        return success


def main():
    """Main entry point."""
    runner = ComprehensiveTestRunner()
    
    # Check command line arguments
    if len(sys.argv) > 1:
        suite_name = sys.argv[1]
        success = runner.run_specific_suite(suite_name)
    else:
        success = runner.run_all_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()