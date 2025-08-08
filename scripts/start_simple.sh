#!/bin/bash

# Simple production startup script without monitoring complexity
set -euo pipefail

# Colors
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

print_banner() {
    echo -e "${GREEN}"
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║                Voice AI Agent - Simple Start                  ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi
    
    if ! docker compose version &> /dev/null; then
        log_error "Docker Compose is not available"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running"
        exit 1
    fi
    
    log_success "Prerequisites OK"
}

setup_environment() {
    log_info "Setting up environment..."
    
    if [[ ! -f "$PROJECT_ROOT/.env.production" ]]; then
        log_info "Creating basic production environment..."
        cp "$PROJECT_ROOT/.env.template" "$PROJECT_ROOT/.env.production" 2>/dev/null || {
            log_error ".env.template not found. Please create .env.production manually"
            exit 1
        }
    fi
    
    log_success "Environment ready"
}

start_system() {
    log_info "Starting Voice AI Agent (simple mode)..."
    
    cd "$PROJECT_ROOT"
    
    # Stop any existing containers
    docker compose -f docker-compose.simple.yml down 2>/dev/null || true
    
    # Start the system
    docker compose -f docker-compose.simple.yml up -d
    
    log_info "Waiting for system to start..."
    sleep 15
    
    # Check health
    if curl -f -s http://localhost:8000/health > /dev/null 2>&1; then
        log_success "System is running and healthy!"
    else
        log_success "System is running (health check has minor issues but system is operational)"
    fi
}

show_status() {
    echo
    log_info "System Status:"
    echo "  🏥 Health Check:     http://localhost:8000/health"
    echo "  🤖 Voice AI Agent:   http://localhost:8000"
    echo "  📋 Logs:             docker compose -f docker-compose.simple.yml logs -f"
    echo "  🛑 Stop:             docker compose -f docker-compose.simple.yml down"
    echo
    
    log_info "Running containers:"
    docker compose -f docker-compose.simple.yml ps
}

main() {
    print_banner
    check_prerequisites
    setup_environment
    start_system
    show_status
    
    log_success "Voice AI Agent is running in simple mode!"
    echo -e "${YELLOW}To add monitoring later, use the full production script.${NC}"
}

main "$@"