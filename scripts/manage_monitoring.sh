#!/bin/bash

# Script to manage monitoring services separately
set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

log_info() {
    echo -e "${YELLOW}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

start_monitoring() {
    log_info "Starting monitoring services..."
    
    cd "$PROJECT_ROOT"
    
    # Ensure main network exists
    docker network create voice-ai-network 2>/dev/null || true
    
    # Start monitoring
    docker compose -f docker-compose.monitoring.yml up -d
    
    log_info "Waiting for services to start..."
    sleep 20
    
    # Check services
    if curl -f -s http://localhost:9090/-/healthy > /dev/null 2>&1; then
        log_success "Prometheus is running: http://localhost:9090"
    else
        log_error "Prometheus failed to start"
    fi
    
    if curl -f -s http://localhost:3000/api/health > /dev/null 2>&1; then
        log_success "Grafana is running: http://localhost:3000 (admin/admin)"
    else
        log_error "Grafana failed to start"
    fi
}

stop_monitoring() {
    log_info "Stopping monitoring services..."
    cd "$PROJECT_ROOT"
    docker compose -f docker-compose.monitoring.yml down
    log_success "Monitoring services stopped"
}

status_monitoring() {
    log_info "Monitoring services status:"
    cd "$PROJECT_ROOT"
    docker compose -f docker-compose.monitoring.yml ps
}

case "${1:-}" in
    start)
        start_monitoring
        ;;
    stop)
        stop_monitoring
        ;;
    restart)
        stop_monitoring
        start_monitoring
        ;;
    status)
        status_monitoring
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        echo
        echo "  start   - Start monitoring services (Prometheus + Grafana)"
        echo "  stop    - Stop monitoring services"
        echo "  restart - Restart monitoring services"
        echo "  status  - Show monitoring services status"
        exit 1
        ;;
esac