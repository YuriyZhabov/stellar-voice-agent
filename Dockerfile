# Production-optimized Dockerfile for Voice AI Agent
FROM python:3.11-slim AS base

# Set environment variables for production optimization
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app \
    ENVIRONMENT=production

# Install system dependencies and security updates
RUN apt-get update && apt-get install -y \
    # Build dependencies
    gcc \
    g++ \
    make \
    # Audio processing
    portaudio19-dev \
    libasound2-dev \
    ffmpeg \
    libsndfile1 \
    # Python development
    python3-dev \
    # Network tools
    curl \
    wget \
    netcat-openbsd \
    # Security and monitoring
    ca-certificates \
    # Performance tools
    htop \
    iotop \
    # Cleanup
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get autoremove -y

# Create non-root user for security
RUN groupadd -r voiceai --gid=1000 && \
    useradd -r -g voiceai --uid=1000 --home-dir=/app --shell=/bin/bash voiceai

# Set work directory
WORKDIR /app

# Copy dependency files first for better caching
COPY pyproject.toml ./
COPY README.md ./
COPY requirements.txt* ./

# Install Python dependencies with production optimizations
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -e . && \
    # Install additional production dependencies
    pip install --no-cache-dir \
        uvloop \
        gunicorn \
        prometheus-client \
        sentry-sdk \
        psutil \
        redis

# Copy application code
COPY src/ ./src/
COPY config/ ./config/
COPY scripts/ ./scripts/
COPY docs/ ./docs/

# Copy additional files
COPY .env.template ./
COPY livekit-sip.yaml ./
COPY Makefile ./

# Create necessary directories with proper permissions
RUN mkdir -p \
    /app/logs \
    /app/data \
    /app/backups \
    /app/metrics \
    /app/tmp \
    && chown -R voiceai:voiceai /app \
    && chmod -R 755 /app \
    && chmod +x /app/scripts/*.py

# Install production logging configuration
COPY src/logging_config_production.py ./src/

# Switch to non-root user
USER voiceai

# Add health check script
COPY --chown=voiceai:voiceai <<EOF /app/healthcheck.py
#!/usr/bin/env python3
import sys
import asyncio
import json
from pathlib import Path

sys.path.append('/app')

async def main():
    try:
        from src.health import comprehensive_health_check_async
        
        # Perform comprehensive health check
        health_data = await comprehensive_health_check_async()
        status = health_data.get('status')
        health_percentage = health_data.get('health_percentage', 0)
        
        if status == 'healthy':
            print(f"Health check passed: {status} ({health_percentage:.1f}%)")
            sys.exit(0)
        elif status == 'degraded' and health_percentage >= 50.0:
            # Accept degraded status if health is above 50%
            print(f"Health check passed: {status} ({health_percentage:.1f}%)")
            sys.exit(0)
        else:
            print(f"Health check failed: {status} ({health_percentage:.1f}%)")
            failed_checks = health_data.get('failed_checks', [])
            if failed_checks:
                print(f"Failed components: {', '.join(failed_checks)}")
            sys.exit(1)
            
    except Exception as e:
        print(f"Health check error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
EOF

RUN chmod +x /app/healthcheck.py

# Production-optimized health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python /app/healthcheck.py

# Expose ports
EXPOSE 8000 9090

# Add labels for better container management
LABEL maintainer="Voice AI Team <team@voiceai.com>" \
      version="1.0.0" \
      description="Production Voice AI Agent for natural telephone conversations" \
      org.opencontainers.image.title="Voice AI Agent" \
      org.opencontainers.image.description="Production-ready Voice AI Agent system" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.vendor="Voice AI Team"

# Production startup script
COPY --chown=voiceai:voiceai <<EOF /app/start.sh
#!/bin/bash
set -e

echo "🚀 Starting Voice AI Agent in production mode..."

# Set production environment
export ENVIRONMENT=production
export PYTHONPATH=/app

# Create required directories
mkdir -p /app/logs /app/data /app/metrics

# Wait a bit for dependencies to be ready
sleep 5

# Check if we can import main modules
echo "🔍 Checking module imports..."
python -c "
import sys
sys.path.append('/app')
try:
    from src.config import get_settings
    from src.health import check_health
    print('✅ Core modules imported successfully')
except Exception as e:
    print(f'❌ Import error: {e}')
    sys.exit(1)
"

# Run database migrations if needed
if [ -f "/app/src/database/migrations.py" ]; then
    echo "📊 Running database migrations..."
    python -c "
import sys
sys.path.append('/app')
try:
    from src.database.migrations import MigrationManager
    import asyncio
    manager = MigrationManager()
    asyncio.run(manager.migrate_to_latest())
    print('✅ Database migrations completed')
except Exception as e:
    print(f'⚠️ Migration warning: {e}')
"
fi

# Start the main application
echo "🎯 Starting Voice AI Agent application..."
exec python -m src.main
EOF

RUN chmod +x /app/start.sh

# Default command uses production startup script
CMD ["/app/start.sh"]

# Multi-stage build for smaller production image
FROM base AS production

# Copy only necessary files for production
COPY --from=base --chown=voiceai:voiceai /app /app

# Final production optimizations
USER voiceai
WORKDIR /app

# Set production environment variables
ENV ENVIRONMENT=production \
    LOG_LEVEL=INFO \
    STRUCTURED_LOGGING=true \
    LOG_FORMAT=json \
    ENABLE_METRICS=true \
    OPTIMIZATION_LEVEL=balanced

# Production command
CMD ["/app/start.sh"]