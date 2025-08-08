#!/bin/bash

# Simplified production deployment script
set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

PROJECT_ROOT="$(dirname "$(dirname "$(realpath "$0")")")"
cd "$PROJECT_ROOT"

log_info "🚀 Starting simplified Voice AI Agent deployment..."

# Clean up any existing containers
log_info "Cleaning up existing containers..."
docker compose -f docker-compose.prod.yml down --remove-orphans || true

# Build the image
log_info "Building Docker image..."
docker build -t voice-ai-agent:production .

# Start Redis first
log_info "Starting Redis..."
docker compose -f docker-compose.prod.yml up -d redis

# Wait for Redis
sleep 5

# Start the main application
log_info "Starting Voice AI Agent..."
docker compose -f docker-compose.prod.yml up -d voice-ai-agent

# Wait and check logs
log_info "Waiting for application to start..."
sleep 10

# Show container status
log_info "Container status:"
docker compose -f docker-compose.prod.yml ps

# Show logs
log_info "Application logs:"
docker compose -f docker-compose.prod.yml logs --tail=50 voice-ai-agent

# Try health check
log_info "Testing health check..."
for i in {1..10}; do
    if curl -f -s http://localhost:8000/health > /dev/null 2>&1; then
        log_success "Health check passed!"
        curl -s http://localhost:8000/health | jq '.' || curl -s http://localhost:8000/health
        break
    else
        log_info "Attempt $i/10: Health check failed, waiting..."
        sleep 5
    fi
done

# Start monitoring if main app is working
if curl -f -s http://localhost:8000/health > /dev/null 2>&1; then
    log_info "Starting monitoring stack..."
    docker compose -f docker-compose.prod.yml up -d prometheus grafana
    
    log_success "Deployment completed!"
    log_info "Services:"
    echo "  - Application: http://localhost:8000"
    echo "  - Health: http://localhost:8000/health"
    echo "  - Metrics: http://localhost:8000/metrics"
    echo "  - Prometheus: http://localhost:9090"
    echo "  - Grafana: http://localhost:3000 (admin/admin)"
else
    log_error "Application failed to start properly"
    log_info "Container logs:"
    docker compose -f docker-compose.prod.yml logs voice-ai-agent
    exit 1
fi