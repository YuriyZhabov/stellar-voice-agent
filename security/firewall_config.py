#!/usr/bin/env python3
"""
Firewall Configuration for Voice AI Agent Production Security.

This script configures UFW (Uncomplicated Firewall) rules for secure
production deployment of the Voice AI Agent system.
"""

import logging
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class FirewallManager:
    """Manages firewall configuration for production security."""
    
    def __init__(self):
        self.logger = self._setup_logging()
        
        # Define required ports and their purposes
        self.required_ports = {
            # Web services
            80: {"protocol": "tcp", "description": "HTTP (redirect to HTTPS)", "source": "anywhere"},
            443: {"protocol": "tcp", "description": "HTTPS", "source": "anywhere"},
            8000: {"protocol": "tcp", "description": "Voice AI Agent API", "source": "anywhere"},
            
            # SIP/RTP for telephony
            5060: {"protocol": "udp", "description": "SIP signaling", "source": "anywhere"},
            5061: {"protocol": "tcp", "description": "SIP over TLS", "source": "anywhere"},
            "10000:20000": {"protocol": "udp", "description": "RTP media", "source": "anywhere"},
            
            # Monitoring and management
            9090: {"protocol": "tcp", "description": "Metrics endpoint", "source": "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"},
            9091: {"protocol": "tcp", "description": "Prometheus", "source": "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"},
            3000: {"protocol": "tcp", "description": "Grafana", "source": "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"},
            
            # SSH (restricted)
            22: {"protocol": "tcp", "description": "SSH", "source": "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"},
        }
        
        # Blocked ports (commonly attacked)
        self.blocked_ports = [
            21,    # FTP
            23,    # Telnet
            25,    # SMTP
            53,    # DNS (unless needed)
            110,   # POP3
            143,   # IMAP
            993,   # IMAPS
            995,   # POP3S
            1433,  # MSSQL
            3306,  # MySQL
            5432,  # PostgreSQL
            6379,  # Redis (should be internal only)
        ]
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging for firewall operations."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(__name__)
    
    def check_ufw_status(self) -> Dict[str, any]:
        """Check current UFW firewall status."""
        self.logger.info("🔍 Checking UFW firewall status...")
        
        try:
            # Check if UFW is installed
            result = subprocess.run(["which", "ufw"], capture_output=True)
            if result.returncode != 0:
                return {"installed": False, "active": False, "rules": []}
            
            # Check UFW status
            result = subprocess.run(["ufw", "status", "verbose"], capture_output=True, text=True)
            
            status = {
                "installed": True,
                "active": "Status: active" in result.stdout,
                "rules": [],
                "raw_output": result.stdout
            }
            
            # Parse existing rules
            lines = result.stdout.split('\n')
            for line in lines:
                if 'ALLOW' in line or 'DENY' in line:
                    status["rules"].append(line.strip())
            
            return status
            
        except Exception as e:
            self.logger.error(f"❌ Error checking UFW status: {e}")
            return {"installed": False, "active": False, "rules": []}
    
    def install_ufw(self) -> bool:
        """Install UFW if not already installed."""
        self.logger.info("📦 Installing UFW firewall...")
        
        try:
            # Update package list
            subprocess.run(["apt-get", "update"], check=True)
            
            # Install UFW
            subprocess.run(["apt-get", "install", "-y", "ufw"], check=True)
            
            self.logger.info("✅ UFW installed successfully")
            return True
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"❌ Failed to install UFW: {e}")
            return False
        except Exception as e:
            self.logger.error(f"❌ Error installing UFW: {e}")
            return False
    
    def configure_default_policies(self) -> bool:
        """Configure default UFW policies (deny incoming, allow outgoing)."""
        self.logger.info("🛡️  Configuring default firewall policies...")
        
        try:
            # Set default policies
            subprocess.run(["ufw", "--force", "default", "deny", "incoming"], check=True)
            subprocess.run(["ufw", "--force", "default", "allow", "outgoing"], check=True)
            
            # Allow loopback
            subprocess.run(["ufw", "allow", "in", "on", "lo"], check=True)
            subprocess.run(["ufw", "allow", "out", "on", "lo"], check=True)
            
            self.logger.info("✅ Default policies configured")
            return True
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"❌ Failed to configure default policies: {e}")
            return False
    
    def configure_required_ports(self) -> bool:
        """Configure required ports for Voice AI Agent."""
        self.logger.info("🔓 Configuring required ports...")
        
        success_count = 0
        total_count = len(self.required_ports)
        
        for port, config in self.required_ports.items():
            try:
                protocol = config["protocol"]
                source = config["source"]
                description = config["description"]
                
                if source == "anywhere":
                    cmd = ["ufw", "allow", f"{port}/{protocol}"]
                else:
                    # Allow from specific networks
                    for network in source.split(","):
                        cmd = ["ufw", "allow", "from", network.strip(), "to", "any", "port", str(port), "proto", protocol]
                        subprocess.run(cmd, check=True)
                        continue
                
                if source == "anywhere":
                    subprocess.run(cmd, check=True)
                
                self.logger.info(f"✅ Allowed {port}/{protocol} - {description}")
                success_count += 1
                
            except subprocess.CalledProcessError as e:
                self.logger.error(f"❌ Failed to configure port {port}: {e}")
            except Exception as e:
                self.logger.error(f"❌ Error configuring port {port}: {e}")
        
        self.logger.info(f"📊 Configured {success_count}/{total_count} ports successfully")
        return success_count == total_count
    
    def block_dangerous_ports(self) -> bool:
        """Block commonly attacked ports."""
        self.logger.info("🚫 Blocking dangerous ports...")
        
        success_count = 0
        
        for port in self.blocked_ports:
            try:
                # Explicitly deny these ports
                subprocess.run(["ufw", "deny", str(port)], check=True)
                self.logger.info(f"✅ Blocked port {port}")
                success_count += 1
                
            except subprocess.CalledProcessError as e:
                self.logger.warning(f"⚠️  Could not block port {port}: {e}")
            except Exception as e:
                self.logger.error(f"❌ Error blocking port {port}: {e}")
        
        self.logger.info(f"📊 Blocked {success_count}/{len(self.blocked_ports)} dangerous ports")
        return True
    
    def configure_rate_limiting(self) -> bool:
        """Configure rate limiting for DDoS protection."""
        self.logger.info("⚡ Configuring rate limiting...")
        
        try:
            # Rate limit SSH connections
            subprocess.run(["ufw", "limit", "ssh"], check=True)
            
            # Rate limit HTTP/HTTPS (basic protection)
            subprocess.run(["ufw", "limit", "80/tcp"], check=True)
            subprocess.run(["ufw", "limit", "443/tcp"], check=True)
            
            # Rate limit Voice AI Agent API
            subprocess.run(["ufw", "limit", "8000/tcp"], check=True)
            
            self.logger.info("✅ Rate limiting configured")
            return True
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"❌ Failed to configure rate limiting: {e}")
            return False
    
    def enable_logging(self) -> bool:
        """Enable UFW logging for security monitoring."""
        self.logger.info("📝 Enabling firewall logging...")
        
        try:
            # Enable logging at medium level
            subprocess.run(["ufw", "logging", "medium"], check=True)
            
            self.logger.info("✅ Firewall logging enabled")
            return True
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"❌ Failed to enable logging: {e}")
            return False
    
    def enable_firewall(self) -> bool:
        """Enable UFW firewall."""
        self.logger.info("🔥 Enabling UFW firewall...")
        
        try:
            # Enable UFW
            subprocess.run(["ufw", "--force", "enable"], check=True)
            
            self.logger.info("✅ UFW firewall enabled")
            return True
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"❌ Failed to enable firewall: {e}")
            return False
    
    def create_firewall_status_script(self) -> bool:
        """Create script to check firewall status."""
        self.logger.info("📋 Creating firewall status script...")
        
        try:
            script_path = Path("/usr/local/bin/check-firewall-status")
            
            script_content = """#!/bin/bash
# Firewall Status Check Script for Voice AI Agent

echo "🔥 UFW Firewall Status"
echo "======================"

# Check UFW status
ufw status verbose

echo ""
echo "📊 Connection Statistics"
echo "======================="

# Show active connections
netstat -tuln | grep LISTEN | head -20

echo ""
echo "🚫 Recent Blocked Connections"
echo "============================="

# Show recent UFW blocks (last 10)
tail -n 20 /var/log/ufw.log | grep BLOCK | tail -10

echo ""
echo "📈 Port Usage Summary"
echo "===================="

# Show listening ports summary
ss -tuln | awk 'NR>1 {print $1, $5}' | sort | uniq -c | sort -nr
"""
            
            script_path.write_text(script_content)
            script_path.chmod(0o755)
            
            self.logger.info("✅ Firewall status script created")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error creating status script: {e}")
            return False
    
    def setup_firewall(self) -> bool:
        """Main method to setup complete firewall configuration."""
        self.logger.info("🛡️  Starting firewall setup...")
        
        # Check current status
        status = self.check_ufw_status()
        
        # Install UFW if needed
        if not status["installed"]:
            if not self.install_ufw():
                return False
        
        # Configure firewall
        steps = [
            ("Default policies", self.configure_default_policies),
            ("Required ports", self.configure_required_ports),
            ("Block dangerous ports", self.block_dangerous_ports),
            ("Rate limiting", self.configure_rate_limiting),
            ("Logging", self.enable_logging),
            ("Status script", self.create_firewall_status_script),
        ]
        
        for step_name, step_func in steps:
            self.logger.info(f"🔧 {step_name}...")
            if not step_func():
                self.logger.error(f"❌ Failed: {step_name}")
                return False
        
        # Enable firewall (do this last)
        if not status["active"]:
            if not self.enable_firewall():
                return False
        
        # Show final status
        final_status = self.check_ufw_status()
        self.logger.info("🎉 Firewall setup completed successfully")
        self.logger.info(f"📊 Active rules: {len(final_status['rules'])}")
        
        return True
    
    def show_firewall_summary(self):
        """Show summary of firewall configuration."""
        print("\n" + "=" * 80)
        print("🛡️  FIREWALL CONFIGURATION SUMMARY")
        print("=" * 80)
        
        status = self.check_ufw_status()
        
        print(f"Status: {'🟢 ACTIVE' if status['active'] else '🔴 INACTIVE'}")
        print(f"Rules configured: {len(status['rules'])}")
        
        print("\n📋 ALLOWED SERVICES:")
        for port, config in self.required_ports.items():
            print(f"   ✅ {port}/{config['protocol']} - {config['description']}")
        
        print("\n🚫 BLOCKED PORTS:")
        for port in self.blocked_ports[:10]:  # Show first 10
            print(f"   ❌ {port}")
        if len(self.blocked_ports) > 10:
            print(f"   ... and {len(self.blocked_ports) - 10} more")
        
        print("\n💡 MANAGEMENT COMMANDS:")
        print("   ufw status verbose          - Show detailed status")
        print("   check-firewall-status       - Custom status script")
        print("   tail -f /var/log/ufw.log    - Monitor firewall logs")
        
        print("\n" + "=" * 80)


def main():
    """Main function for firewall setup."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Firewall Configuration")
    parser.add_argument("--status-only", action="store_true", help="Only show current status")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    
    args = parser.parse_args()
    
    firewall_manager = FirewallManager()
    
    if args.status_only:
        firewall_manager.show_firewall_summary()
        return
    
    if args.dry_run:
        print("🔍 DRY RUN - Would configure:")
        for port, config in firewall_manager.required_ports.items():
            print(f"   Allow {port}/{config['protocol']} - {config['description']}")
        return
    
    success = firewall_manager.setup_firewall()
    
    if success:
        firewall_manager.show_firewall_summary()
        print("✅ Firewall configuration completed successfully")
        sys.exit(0)
    else:
        print("❌ Firewall configuration failed")
        sys.exit(1)


if __name__ == "__main__":
    main()