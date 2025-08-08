#!/usr/bin/env python3
"""
Simple health check script for Docker containers.

This script performs basic health checks and exits with appropriate codes
for Docker container health monitoring.
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from health import check_health
    
    # Perform health check
    health_data = check_health()
    
    # Print status for logging
    print(f"Health Status: {health_data['status']}")
    
    # Exit with appropriate code
    if health_data["status"] == "healthy":
        sys.exit(0)
    elif health_data["status"] == "degraded":
        sys.exit(0)  # Still considered healthy for Docker
    else:
        print("Health check failed:")
        for check, result in health_data["checks"].items():
            if "failed" in str(result):
                print(f"  - {check}: {result}")
        sys.exit(1)
        
except Exception as e:
    print(f"Health check error: {e}")
    sys.exit(1)