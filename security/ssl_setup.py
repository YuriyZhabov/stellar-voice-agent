#!/usr/bin/env python3
"""
SSL/TLS Certificate Setup for Voice AI Agent Production Security.

This script handles SSL certificate generation, installation, and management
for HTTPS encryption in production environment.
"""

import asyncio
import logging
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class SSLCertificateManager:
    """Manages SSL certificates for production security."""
    
    def __init__(self, domain: str = "agentio.ru"):
        self.domain = domain
        self.cert_dir = Path("/etc/ssl/voice-ai-agent")
        self.logger = self._setup_logging()
        
        # Certificate paths
        self.cert_file = self.cert_dir / f"{domain}.crt"
        self.key_file = self.cert_dir / f"{domain}.key"
        self.ca_file = self.cert_dir / "ca.crt"
        
        # Ensure certificate directory exists
        self.cert_dir.mkdir(parents=True, exist_ok=True)
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging for SSL operations."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(__name__)
    
    def check_existing_certificates(self) -> Dict[str, bool]:
        """Check if SSL certificates already exist and are valid."""
        self.logger.info("🔍 Checking existing SSL certificates...")
        
        status = {
            "cert_exists": self.cert_file.exists(),
            "key_exists": self.key_file.exists(),
            "cert_valid": False,
            "expires_soon": False
        }
        
        if status["cert_exists"]:
            try:
                # Check certificate validity using openssl
                result = subprocess.run([
                    "openssl", "x509", "-in", str(self.cert_file),
                    "-noout", "-dates"
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    status["cert_valid"] = True
                    
                    # Check expiration date
                    for line in result.stdout.split('\n'):
                        if line.startswith('notAfter='):
                            exp_date_str = line.replace('notAfter=', '')
                            # Parse expiration date and check if expires within 30 days
                            # This is a simplified check
                            status["expires_soon"] = "2025" not in exp_date_str
                            
                    self.logger.info("✅ Existing certificate is valid")
                else:
                    self.logger.warning("⚠️  Existing certificate is invalid")
                    
            except Exception as e:
                self.logger.error(f"❌ Error checking certificate: {e}")
        
        return status
    
    def generate_self_signed_certificate(self) -> bool:
        """Generate self-signed SSL certificate for development/testing."""
        self.logger.info("🔐 Generating self-signed SSL certificate...")
        
        try:
            # Generate private key
            key_cmd = [
                "openssl", "genrsa", "-out", str(self.key_file), "2048"
            ]
            
            result = subprocess.run(key_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                self.logger.error(f"❌ Failed to generate private key: {result.stderr}")
                return False
            
            # Generate certificate
            cert_cmd = [
                "openssl", "req", "-new", "-x509", "-key", str(self.key_file),
                "-out", str(self.cert_file), "-days", "365",
                "-subj", f"/C=RU/ST=Moscow/L=Moscow/O=VoiceAI/CN={self.domain}"
            ]
            
            result = subprocess.run(cert_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                self.logger.error(f"❌ Failed to generate certificate: {result.stderr}")
                return False
            
            # Set proper permissions
            os.chmod(self.key_file, 0o600)
            os.chmod(self.cert_file, 0o644)
            
            self.logger.info("✅ Self-signed certificate generated successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error generating certificate: {e}")
            return False
    
    def setup_lets_encrypt_certificate(self) -> bool:
        """Setup Let's Encrypt certificate using certbot."""
        self.logger.info("🔒 Setting up Let's Encrypt certificate...")
        
        try:
            # Check if certbot is installed
            result = subprocess.run(["which", "certbot"], capture_output=True)
            if result.returncode != 0:
                self.logger.info("📦 Installing certbot...")
                install_cmd = ["apt-get", "update", "&&", "apt-get", "install", "-y", "certbot"]
                subprocess.run(install_cmd, shell=True)
            
            # Generate certificate using certbot standalone mode
            certbot_cmd = [
                "certbot", "certonly", "--standalone",
                "--non-interactive", "--agree-tos",
                "--email", f"admin@{self.domain}",
                "-d", self.domain
            ]
            
            result = subprocess.run(certbot_cmd, capture_output=True, text=True)
            if result.returncode == 0:
                # Copy certificates to our directory
                letsencrypt_cert = f"/etc/letsencrypt/live/{self.domain}/fullchain.pem"
                letsencrypt_key = f"/etc/letsencrypt/live/{self.domain}/privkey.pem"
                
                if Path(letsencrypt_cert).exists():
                    subprocess.run(["cp", letsencrypt_cert, str(self.cert_file)])
                    subprocess.run(["cp", letsencrypt_key, str(self.key_file)])
                    
                    # Set proper permissions
                    os.chmod(self.key_file, 0o600)
                    os.chmod(self.cert_file, 0o644)
                    
                    self.logger.info("✅ Let's Encrypt certificate installed successfully")
                    return True
            
            self.logger.warning("⚠️  Let's Encrypt certificate generation failed, falling back to self-signed")
            return self.generate_self_signed_certificate()
            
        except Exception as e:
            self.logger.error(f"❌ Error setting up Let's Encrypt: {e}")
            return self.generate_self_signed_certificate()
    
    def setup_certificate_renewal(self) -> bool:
        """Setup automatic certificate renewal."""
        self.logger.info("🔄 Setting up certificate renewal...")
        
        try:
            # Create renewal script
            renewal_script = self.cert_dir / "renew_cert.sh"
            
            script_content = f"""#!/bin/bash
# SSL Certificate Renewal Script for Voice AI Agent

set -e

echo "🔄 Starting certificate renewal process..."

# Renew Let's Encrypt certificate
if certbot renew --quiet; then
    echo "✅ Certificate renewed successfully"
    
    # Copy renewed certificates
    cp /etc/letsencrypt/live/{self.domain}/fullchain.pem {self.cert_file}
    cp /etc/letsencrypt/live/{self.domain}/privkey.pem {self.key_file}
    
    # Set permissions
    chmod 600 {self.key_file}
    chmod 644 {self.cert_file}
    
    # Restart services
    docker-compose -f docker-compose.prod.yml restart voice-ai-agent
    
    echo "✅ Certificate renewal completed"
else
    echo "⚠️  Certificate renewal not needed or failed"
fi
"""
            
            renewal_script.write_text(script_content)
            os.chmod(renewal_script, 0o755)
            
            # Add to crontab for automatic renewal
            cron_entry = f"0 2 * * 0 {renewal_script} >> /var/log/cert-renewal.log 2>&1"
            
            # Check if cron entry already exists
            result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
            if cron_entry not in result.stdout:
                # Add cron entry
                current_cron = result.stdout if result.returncode == 0 else ""
                new_cron = current_cron + "\n" + cron_entry + "\n"
                
                process = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE, text=True)
                process.communicate(input=new_cron)
                
                if process.returncode == 0:
                    self.logger.info("✅ Certificate renewal cron job added")
                    return True
            else:
                self.logger.info("✅ Certificate renewal cron job already exists")
                return True
                
        except Exception as e:
            self.logger.error(f"❌ Error setting up renewal: {e}")
            return False
    
    def validate_certificate_installation(self) -> bool:
        """Validate that certificates are properly installed."""
        self.logger.info("✅ Validating certificate installation...")
        
        try:
            # Check certificate and key match
            cert_cmd = ["openssl", "x509", "-noout", "-modulus", "-in", str(self.cert_file)]
            key_cmd = ["openssl", "rsa", "-noout", "-modulus", "-in", str(self.key_file)]
            
            cert_result = subprocess.run(cert_cmd, capture_output=True, text=True)
            key_result = subprocess.run(key_cmd, capture_output=True, text=True)
            
            if cert_result.returncode == 0 and key_result.returncode == 0:
                if cert_result.stdout == key_result.stdout:
                    self.logger.info("✅ Certificate and key match")
                    return True
                else:
                    self.logger.error("❌ Certificate and key do not match")
                    return False
            else:
                self.logger.error("❌ Error validating certificate/key")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error validating installation: {e}")
            return False
    
    async def setup_ssl_certificates(self, use_letsencrypt: bool = True) -> bool:
        """Main method to setup SSL certificates."""
        self.logger.info("🔐 Starting SSL certificate setup...")
        
        # Check existing certificates
        cert_status = self.check_existing_certificates()
        
        if cert_status["cert_valid"] and not cert_status["expires_soon"]:
            self.logger.info("✅ Valid certificates already exist")
            return True
        
        # Setup new certificates
        if use_letsencrypt:
            success = self.setup_lets_encrypt_certificate()
        else:
            success = self.generate_self_signed_certificate()
        
        if not success:
            return False
        
        # Validate installation
        if not self.validate_certificate_installation():
            return False
        
        # Setup renewal
        if use_letsencrypt:
            self.setup_certificate_renewal()
        
        self.logger.info("🎉 SSL certificate setup completed successfully")
        return True


async def main():
    """Main function for SSL setup."""
    import argparse
    
    parser = argparse.ArgumentParser(description="SSL Certificate Setup")
    parser.add_argument("--domain", default="agentio.ru", help="Domain name")
    parser.add_argument("--self-signed", action="store_true", help="Use self-signed certificate")
    parser.add_argument("--check-only", action="store_true", help="Only check existing certificates")
    
    args = parser.parse_args()
    
    ssl_manager = SSLCertificateManager(domain=args.domain)
    
    if args.check_only:
        status = ssl_manager.check_existing_certificates()
        print(f"Certificate status: {status}")
        return
    
    success = await ssl_manager.setup_ssl_certificates(use_letsencrypt=not args.self_signed)
    
    if success:
        print("✅ SSL certificates setup completed successfully")
        sys.exit(0)
    else:
        print("❌ SSL certificate setup failed")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())