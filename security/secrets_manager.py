#!/usr/bin/env python3
"""
Secrets Management for Voice AI Agent Production Security.

This script handles secure generation, storage, and rotation of secrets
including API keys, passwords, and encryption keys.
"""

import base64
import hashlib
import json
import logging
import os
import secrets
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class SecretsManager:
    """Manages secrets for production security."""
    
    def __init__(self):
        self.logger = self._setup_logging()
        self.secrets_dir = Path("/etc/voice-ai-agent/secrets")
        self.backup_dir = Path("/etc/voice-ai-agent/secrets/backups")
        
        # Ensure directories exist with proper permissions
        self.secrets_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.backup_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        
        # Secret definitions
        self.secret_definitions = {
            "SECRET_KEY": {
                "type": "random_string",
                "length": 64,
                "description": "Django/FastAPI secret key",
                "rotation_days": 90
            },
            "JWT_SECRET": {
                "type": "random_string", 
                "length": 64,
                "description": "JWT signing secret",
                "rotation_days": 30
            },
            "WEBHOOK_SECRET": {
                "type": "random_string",
                "length": 32,
                "description": "Webhook validation secret",
                "rotation_days": 60
            },
            "DB_PASSWORD": {
                "type": "random_password",
                "length": 32,
                "description": "Database password",
                "rotation_days": 180
            },
            "REDIS_PASSWORD": {
                "type": "random_password",
                "length": 24,
                "description": "Redis password",
                "rotation_days": 90
            },
            "ENCRYPTION_KEY": {
                "type": "encryption_key",
                "length": 32,
                "description": "Data encryption key",
                "rotation_days": 365
            }
        }
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging for secrets operations."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(__name__)
    
    def generate_random_string(self, length: int = 32, include_special: bool = True) -> str:
        """Generate cryptographically secure random string."""
        if include_special:
            # Include letters, digits, and safe special characters
            alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
        else:
            # Only letters and digits
            alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    def generate_random_password(self, length: int = 24) -> str:
        """Generate secure password with mixed character types."""
        # Ensure we have at least one of each type
        password = []
        
        # Add required character types
        password.append(secrets.choice("abcdefghijklmnopqrstuvwxyz"))  # lowercase
        password.append(secrets.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))  # uppercase
        password.append(secrets.choice("0123456789"))  # digit
        password.append(secrets.choice("!@#$%^&*"))  # special
        
        # Fill the rest randomly
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
        for _ in range(length - 4):
            password.append(secrets.choice(alphabet))
        
        # Shuffle the password
        secrets.SystemRandom().shuffle(password)
        return ''.join(password)
    
    def generate_encryption_key(self, length: int = 32) -> str:
        """Generate base64-encoded encryption key."""
        key_bytes = secrets.token_bytes(length)
        return base64.b64encode(key_bytes).decode('utf-8')
    
    def generate_secret(self, secret_type: str, length: int) -> str:
        """Generate secret based on type."""
        if secret_type == "random_string":
            return self.generate_random_string(length, include_special=False)
        elif secret_type == "random_password":
            return self.generate_random_password(length)
        elif secret_type == "encryption_key":
            return self.generate_encryption_key(length)
        else:
            raise ValueError(f"Unknown secret type: {secret_type}")
    
    def load_existing_secrets(self) -> Dict[str, Dict]:
        """Load existing secrets from storage."""
        secrets_file = self.secrets_dir / "secrets.json"
        
        if not secrets_file.exists():
            return {}
        
        try:
            with open(secrets_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"❌ Error loading secrets: {e}")
            return {}
    
    def save_secrets(self, secrets: Dict[str, Dict]) -> bool:
        """Save secrets to secure storage."""
        secrets_file = self.secrets_dir / "secrets.json"
        
        try:
            # Create backup of existing secrets
            if secrets_file.exists():
                backup_name = f"secrets_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                backup_path = self.backup_dir / backup_name
                secrets_file.rename(backup_path)
                self.logger.info(f"📦 Created backup: {backup_name}")
            
            # Save new secrets
            with open(secrets_file, 'w') as f:
                json.dump(secrets, f, indent=2)
            
            # Set restrictive permissions
            os.chmod(secrets_file, 0o600)
            
            self.logger.info("✅ Secrets saved successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error saving secrets: {e}")
            return False
    
    def check_secret_expiration(self, secret_data: Dict) -> bool:
        """Check if a secret needs rotation."""
        if "created_at" not in secret_data or "rotation_days" not in secret_data:
            return True  # Rotate if missing metadata
        
        created_at = datetime.fromisoformat(secret_data["created_at"])
        rotation_days = secret_data["rotation_days"]
        
        expiry_date = created_at + timedelta(days=rotation_days)
        return datetime.now() >= expiry_date
    
    def generate_all_secrets(self, force_regenerate: bool = False) -> Dict[str, str]:
        """Generate all required secrets."""
        self.logger.info("🔐 Generating secrets...")
        
        existing_secrets = self.load_existing_secrets()
        new_secrets = {}
        generated_secrets = {}
        
        for secret_name, config in self.secret_definitions.items():
            existing_secret = existing_secrets.get(secret_name, {})
            
            # Check if we need to generate/rotate this secret
            needs_generation = (
                force_regenerate or 
                secret_name not in existing_secrets or
                self.check_secret_expiration(existing_secret)
            )
            
            if needs_generation:
                # Generate new secret
                secret_value = self.generate_secret(config["type"], config["length"])
                
                new_secrets[secret_name] = {
                    "value": secret_value,
                    "type": config["type"],
                    "length": config["length"],
                    "description": config["description"],
                    "rotation_days": config["rotation_days"],
                    "created_at": datetime.now().isoformat(),
                    "hash": hashlib.sha256(secret_value.encode()).hexdigest()[:16]
                }
                
                generated_secrets[secret_name] = secret_value
                self.logger.info(f"✅ Generated {secret_name}")
            else:
                # Keep existing secret
                new_secrets[secret_name] = existing_secret
                generated_secrets[secret_name] = existing_secret["value"]
                self.logger.info(f"♻️  Kept existing {secret_name}")
        
        # Save all secrets
        if self.save_secrets(new_secrets):
            return generated_secrets
        else:
            return {}
    
    def create_env_file(self, secrets: Dict[str, str], env_file_path: str = ".env.secrets") -> bool:
        """Create environment file with secrets."""
        self.logger.info(f"📝 Creating environment file: {env_file_path}")
        
        try:
            env_content = [
                "# Generated secrets for Voice AI Agent",
                f"# Generated at: {datetime.now().isoformat()}",
                "# DO NOT COMMIT THIS FILE TO VERSION CONTROL",
                "",
                "# =============================================================================",
                "# SECURITY SECRETS",
                "# =============================================================================",
                ""
            ]
            
            for secret_name, secret_value in secrets.items():
                description = self.secret_definitions[secret_name]["description"]
                env_content.extend([
                    f"# {description}",
                    f"{secret_name}={secret_value}",
                    ""
                ])
            
            # Write to file
            env_file = Path(env_file_path)
            env_file.write_text('\n'.join(env_content))
            
            # Set restrictive permissions
            os.chmod(env_file, 0o600)
            
            self.logger.info("✅ Environment file created")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error creating environment file: {e}")
            return False
    
    def update_docker_secrets(self, secrets: Dict[str, str]) -> bool:
        """Update Docker secrets for production deployment."""
        self.logger.info("🐳 Updating Docker secrets...")
        
        try:
            import subprocess
            
            for secret_name, secret_value in secrets.items():
                # Create Docker secret
                docker_secret_name = f"voice-ai-{secret_name.lower()}"
                
                # Remove existing secret if it exists
                try:
                    subprocess.run(
                        ["docker", "secret", "rm", docker_secret_name],
                        capture_output=True, check=False
                    )
                except:
                    pass  # Secret might not exist
                
                # Create new secret
                process = subprocess.Popen(
                    ["docker", "secret", "create", docker_secret_name, "-"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                stdout, stderr = process.communicate(input=secret_value)
                
                if process.returncode == 0:
                    self.logger.info(f"✅ Created Docker secret: {docker_secret_name}")
                else:
                    self.logger.warning(f"⚠️  Could not create Docker secret {docker_secret_name}: {stderr}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error updating Docker secrets: {e}")
            return False
    
    def create_secrets_rotation_script(self) -> bool:
        """Create script for automatic secrets rotation."""
        self.logger.info("🔄 Creating secrets rotation script...")
        
        try:
            script_path = Path("/usr/local/bin/rotate-secrets")
            
            script_content = f"""#!/bin/bash
# Secrets Rotation Script for Voice AI Agent

set -e

echo "🔄 Starting secrets rotation..."

# Run secrets manager
python3 {Path(__file__).absolute()} --rotate

# Restart services to pick up new secrets
echo "🔄 Restarting services..."
docker-compose -f docker-compose.prod.yml restart

echo "✅ Secrets rotation completed"

# Log rotation event
echo "$(date): Secrets rotated" >> /var/log/voice-ai-secrets.log
"""
            
            script_path.write_text(script_content)
            script_path.chmod(0o755)
            
            # Add to crontab for monthly rotation
            cron_entry = f"0 3 1 * * {script_path} >> /var/log/voice-ai-secrets.log 2>&1"
            
            # Check if cron entry already exists
            import subprocess
            result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
            if cron_entry not in result.stdout:
                # Add cron entry
                current_cron = result.stdout if result.returncode == 0 else ""
                new_cron = current_cron + "\n" + cron_entry + "\n"
                
                process = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE, text=True)
                process.communicate(input=new_cron)
                
                if process.returncode == 0:
                    self.logger.info("✅ Secrets rotation cron job added")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error creating rotation script: {e}")
            return False
    
    def audit_secrets(self) -> Dict[str, any]:
        """Audit current secrets for security compliance."""
        self.logger.info("🔍 Auditing secrets...")
        
        secrets = self.load_existing_secrets()
        audit_results = {
            "total_secrets": len(secrets),
            "expired_secrets": [],
            "weak_secrets": [],
            "missing_secrets": [],
            "compliance_score": 0
        }
        
        # Check for missing secrets
        for secret_name in self.secret_definitions:
            if secret_name not in secrets:
                audit_results["missing_secrets"].append(secret_name)
        
        # Check existing secrets
        for secret_name, secret_data in secrets.items():
            # Check expiration
            if self.check_secret_expiration(secret_data):
                audit_results["expired_secrets"].append(secret_name)
            
            # Check strength (basic check)
            if "value" in secret_data:
                value = secret_data["value"]
                if len(value) < 16:
                    audit_results["weak_secrets"].append(f"{secret_name} (too short)")
        
        # Calculate compliance score
        total_checks = len(self.secret_definitions) * 2  # existence + strength
        failed_checks = len(audit_results["missing_secrets"]) + len(audit_results["expired_secrets"]) + len(audit_results["weak_secrets"])
        audit_results["compliance_score"] = max(0, (total_checks - failed_checks) / total_checks * 100)
        
        return audit_results
    
    def setup_secrets_management(self, force_regenerate: bool = False) -> bool:
        """Main method to setup complete secrets management."""
        self.logger.info("🔐 Starting secrets management setup...")
        
        # Generate secrets
        secrets = self.generate_all_secrets(force_regenerate)
        if not secrets:
            return False
        
        # Create environment file
        if not self.create_env_file(secrets):
            return False
        
        # Update Docker secrets
        self.update_docker_secrets(secrets)
        
        # Create rotation script
        if not self.create_secrets_rotation_script():
            return False
        
        # Audit secrets
        audit_results = self.audit_secrets()
        
        self.logger.info("🎉 Secrets management setup completed")
        self.logger.info(f"📊 Compliance score: {audit_results['compliance_score']:.1f}%")
        
        return True


def main():
    """Main function for secrets management."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Secrets Management")
    parser.add_argument("--generate", action="store_true", help="Generate new secrets")
    parser.add_argument("--rotate", action="store_true", help="Rotate expired secrets")
    parser.add_argument("--audit", action="store_true", help="Audit current secrets")
    parser.add_argument("--force", action="store_true", help="Force regenerate all secrets")
    
    args = parser.parse_args()
    
    secrets_manager = SecretsManager()
    
    if args.audit:
        audit_results = secrets_manager.audit_secrets()
        print(f"📊 Secrets Audit Results:")
        print(f"   Total secrets: {audit_results['total_secrets']}")
        print(f"   Expired: {len(audit_results['expired_secrets'])}")
        print(f"   Weak: {len(audit_results['weak_secrets'])}")
        print(f"   Missing: {len(audit_results['missing_secrets'])}")
        print(f"   Compliance score: {audit_results['compliance_score']:.1f}%")
        return
    
    if args.generate or args.rotate:
        secrets = secrets_manager.generate_all_secrets(force_regenerate=args.force)
        if secrets:
            secrets_manager.create_env_file(secrets)
            print("✅ Secrets generated successfully")
        else:
            print("❌ Failed to generate secrets")
            sys.exit(1)
        return
    
    # Default: full setup
    success = secrets_manager.setup_secrets_management(force_regenerate=args.force)
    
    if success:
        print("✅ Secrets management setup completed successfully")
        sys.exit(0)
    else:
        print("❌ Secrets management setup failed")
        sys.exit(1)


if __name__ == "__main__":
    main()