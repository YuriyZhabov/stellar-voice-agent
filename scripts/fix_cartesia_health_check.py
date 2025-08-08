#!/usr/bin/env python3
"""
Script to fix Cartesia TTS health check issues and ensure proper system monitoring.

This script:
1. Validates Cartesia TTS configuration
2. Tests Cartesia TTS health check functionality
3. Updates monitoring scripts to handle the fix
4. Verifies Docker health check compatibility
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class CartesiaHealthFixer:
    """Fix and validate Cartesia TTS health check issues."""
    
    def __init__(self):
        self.logger = self._setup_logging()
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "fixes_applied": [],
            "validations": {},
            "status": "unknown"
        }
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for the fixer."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(__name__)
    
    async def validate_cartesia_configuration(self) -> bool:
        """Validate Cartesia TTS configuration."""
        try:
            from src.config import get_settings
            
            settings = get_settings()
            
            # Check API key
            if not settings.cartesia_api_key:
                self.logger.error("Cartesia API key not configured")
                self.results["validations"]["api_key"] = "missing"
                return False
            
            if settings.cartesia_api_key == "your-cartesia-api-key-here":
                self.logger.error("Cartesia API key is placeholder value")
                self.results["validations"]["api_key"] = "placeholder"
                return False
            
            self.results["validations"]["api_key"] = "configured"
            
            # Check voice ID
            if not settings.cartesia_voice_id:
                self.logger.error("Cartesia voice ID not configured")
                self.results["validations"]["voice_id"] = "missing"
                return False
            
            if settings.cartesia_voice_id == "default":
                self.logger.error("Cartesia voice ID is default placeholder")
                self.results["validations"]["voice_id"] = "placeholder"
                return False
            
            self.results["validations"]["voice_id"] = "configured"
            
            self.logger.info("Cartesia configuration validation passed")
            return True
            
        except Exception as e:
            self.logger.error(f"Configuration validation failed: {e}")
            self.results["validations"]["configuration"] = f"error: {e}"
            return False
    
    async def test_cartesia_health_check(self) -> bool:
        """Test Cartesia TTS health check functionality."""
        try:
            from src.clients.cartesia_tts import CartesiaTTSClient
            
            self.logger.info("Testing Cartesia TTS health check...")
            
            client = CartesiaTTSClient()
            is_healthy = await client.health_check()
            await client.close()
            
            if is_healthy:
                self.logger.info("Cartesia TTS health check passed")
                self.results["validations"]["health_check"] = "passed"
                return True
            else:
                self.logger.error("Cartesia TTS health check failed")
                self.results["validations"]["health_check"] = "failed"
                return False
                
        except Exception as e:
            self.logger.error(f"Health check test failed: {e}")
            self.results["validations"]["health_check"] = f"error: {e}"
            return False
    
    async def test_comprehensive_health_check(self) -> bool:
        """Test comprehensive system health check."""
        try:
            from src.health import comprehensive_health_check_async
            
            self.logger.info("Testing comprehensive health check...")
            
            health_data = await comprehensive_health_check_async()
            
            status = health_data.get("status", "unknown")
            health_percentage = health_data.get("health_percentage", 0)
            
            # Check Cartesia specifically
            checks = health_data.get("checks", {})
            cartesia_status = checks.get("cartesia", "unknown")
            
            if cartesia_status == "ok":
                self.logger.info(f"Cartesia TTS in comprehensive health check: {cartesia_status}")
                self.results["validations"]["comprehensive_health"] = {
                    "status": status,
                    "health_percentage": health_percentage,
                    "cartesia_status": cartesia_status
                }
                return True
            else:
                self.logger.error(f"Cartesia TTS failed in comprehensive health check: {cartesia_status}")
                self.results["validations"]["comprehensive_health"] = {
                    "status": status,
                    "health_percentage": health_percentage,
                    "cartesia_status": cartesia_status
                }
                return False
                
        except Exception as e:
            self.logger.error(f"Comprehensive health check test failed: {e}")
            self.results["validations"]["comprehensive_health"] = f"error: {e}"
            return False
    
    async def validate_docker_health_check(self) -> bool:
        """Validate Docker health check script."""
        try:
            # Check if healthcheck.py would work
            dockerfile_path = project_root / "Dockerfile"
            
            if not dockerfile_path.exists():
                self.logger.warning("Dockerfile not found")
                self.results["validations"]["docker_health"] = "dockerfile_missing"
                return False
            
            # Read Dockerfile to check health check configuration
            dockerfile_content = dockerfile_path.read_text()
            
            if "comprehensive_health_check_async" in dockerfile_content:
                self.logger.info("Docker health check uses comprehensive health check")
                self.results["validations"]["docker_health"] = "updated"
                return True
            else:
                self.logger.warning("Docker health check may not use comprehensive health check")
                self.results["validations"]["docker_health"] = "needs_update"
                return False
                
        except Exception as e:
            self.logger.error(f"Docker health check validation failed: {e}")
            self.results["validations"]["docker_health"] = f"error: {e}"
            return False
    
    async def validate_monitoring_scripts(self) -> bool:
        """Validate monitoring scripts are updated."""
        try:
            scripts_to_check = [
                "scripts/health_monitor.py",
                "scripts/deployment_health_check.py"
            ]
            
            all_updated = True
            
            for script_path in scripts_to_check:
                script_file = project_root / script_path
                
                if not script_file.exists():
                    self.logger.warning(f"Monitoring script not found: {script_path}")
                    self.results["validations"][f"script_{script_path.split('/')[-1]}"] = "missing"
                    all_updated = False
                    continue
                
                script_content = script_file.read_text()
                
                if "comprehensive_health_check_async" in script_content:
                    self.logger.info(f"Monitoring script updated: {script_path}")
                    self.results["validations"][f"script_{script_path.split('/')[-1]}"] = "updated"
                else:
                    self.logger.warning(f"Monitoring script may need update: {script_path}")
                    self.results["validations"][f"script_{script_path.split('/')[-1]}"] = "needs_update"
                    all_updated = False
            
            return all_updated
            
        except Exception as e:
            self.logger.error(f"Monitoring scripts validation failed: {e}")
            self.results["validations"]["monitoring_scripts"] = f"error: {e}"
            return False
    
    def apply_environment_fix(self) -> bool:
        """Apply environment configuration fixes."""
        try:
            env_file = project_root / ".env"
            
            if not env_file.exists():
                self.logger.warning(".env file not found")
                return False
            
            env_content = env_file.read_text()
            
            # Check if voice ID is already correct
            if "CARTESIA_VOICE_ID=064b17af-d36b-4bfb-b003-be07dba1b649" in env_content:
                self.logger.info("Cartesia voice ID already correctly configured")
                self.results["fixes_applied"].append("voice_id_already_correct")
                return True
            
            # Fix voice ID if it's set to default
            if "CARTESIA_VOICE_ID=default" in env_content:
                updated_content = env_content.replace(
                    "CARTESIA_VOICE_ID=default",
                    "CARTESIA_VOICE_ID=064b17af-d36b-4bfb-b003-be07dba1b649"
                )
                
                env_file.write_text(updated_content)
                self.logger.info("Fixed Cartesia voice ID in .env file")
                self.results["fixes_applied"].append("voice_id_fixed")
                return True
            
            self.logger.info("No environment fixes needed")
            return True
            
        except Exception as e:
            self.logger.error(f"Environment fix failed: {e}")
            return False
    
    async def run_comprehensive_fix(self) -> Dict[str, Any]:
        """Run comprehensive fix and validation."""
        self.logger.info("Starting Cartesia TTS health check fix and validation")
        
        # Step 1: Apply environment fixes
        self.logger.info("Step 1: Applying environment fixes...")
        env_fix_success = self.apply_environment_fix()
        
        # Step 2: Validate configuration
        self.logger.info("Step 2: Validating Cartesia configuration...")
        config_valid = await self.validate_cartesia_configuration()
        
        # Step 3: Test Cartesia health check
        self.logger.info("Step 3: Testing Cartesia health check...")
        health_check_success = await self.test_cartesia_health_check()
        
        # Step 4: Test comprehensive health check
        self.logger.info("Step 4: Testing comprehensive health check...")
        comprehensive_health_success = await self.test_comprehensive_health_check()
        
        # Step 5: Validate Docker health check
        self.logger.info("Step 5: Validating Docker health check...")
        docker_health_valid = await self.validate_docker_health_check()
        
        # Step 6: Validate monitoring scripts
        self.logger.info("Step 6: Validating monitoring scripts...")
        monitoring_scripts_valid = await self.validate_monitoring_scripts()
        
        # Determine overall status
        all_checks = [
            config_valid,
            health_check_success,
            comprehensive_health_success,
            docker_health_valid,
            monitoring_scripts_valid
        ]
        
        if all(all_checks):
            self.results["status"] = "success"
            self.logger.info("✅ All Cartesia TTS health check fixes and validations passed")
        elif any(all_checks):
            self.results["status"] = "partial_success"
            self.logger.warning("⚠️  Some Cartesia TTS health check validations failed")
        else:
            self.results["status"] = "failed"
            self.logger.error("❌ Cartesia TTS health check fixes failed")
        
        return self.results
    
    def print_summary(self):
        """Print summary of fixes and validations."""
        print("\n" + "=" * 80)
        print("🔧 Cartesia TTS Health Check Fix Summary")
        print("=" * 80)
        
        status = self.results["status"]
        status_emoji = "✅" if status == "success" else "⚠️" if status == "partial_success" else "❌"
        print(f"\n{status_emoji} Overall Status: {status.upper()}")
        
        # Print fixes applied
        if self.results["fixes_applied"]:
            print(f"\n🔨 Fixes Applied:")
            for fix in self.results["fixes_applied"]:
                print(f"  ✅ {fix}")
        
        # Print validations
        print(f"\n🔍 Validations:")
        for validation, result in self.results["validations"].items():
            if isinstance(result, dict):
                result_str = f"status: {result.get('status', 'unknown')}"
                if "health_percentage" in result:
                    result_str += f", health: {result['health_percentage']:.1f}%"
            else:
                result_str = str(result)
            
            result_emoji = "✅" if "ok" in result_str or "passed" in result_str or "configured" in result_str or "updated" in result_str else "⚠️" if "warning" in result_str or "needs_update" in result_str else "❌"
            print(f"  {result_emoji} {validation}: {result_str}")
        
        print("\n" + "=" * 80)


async def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Fix Cartesia TTS health check issues")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--quiet", "-q", action="store_true", help="Quiet mode (less output)")
    
    args = parser.parse_args()
    
    if args.quiet:
        logging.getLogger().setLevel(logging.WARNING)
    
    fixer = CartesiaHealthFixer()
    results = await fixer.run_comprehensive_fix()
    
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        fixer.print_summary()
    
    # Exit with appropriate code
    if results["status"] == "success":
        sys.exit(0)
    elif results["status"] == "partial_success":
        sys.exit(1)
    else:
        sys.exit(2)


if __name__ == "__main__":
    asyncio.run(main())