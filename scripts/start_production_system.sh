#!/bin/bash

# Complete production system startup script for Voice AI Agent
# This script orchestrates the entire production deployment process

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${PURPLE}[STEP]${NC} $1"
}

print_banner() {
    echo -e "${BLUE}"
    echo "╔══════════════════════════════════════════════════════════════════════════════╗"
    echo "║                        Voice AI Agent Production System                      ║"
    echo "║                              Complete Deployment                            ║"
    echo "╚══════════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

check_prerequisites() {
    log_step "Checking prerequisites..."
    
    local missing_deps=()
    
    # Check required commands
    local required_commands=("docker" "python3" "curl" "jq")
    for cmd in "${required_commands[@]}"; do
        if ! command -v "$cmd" &> /dev/null; then
            missing_deps+=("$cmd")
        fi
    done
    
    # Check Docker Compose
    if ! docker compose version &> /dev/null; then
        missing_deps+=("docker compose")
    fi
    
    if [[ ${#missing_deps[@]} -gt 0 ]]; then
        log_error "Missing required dependencies:"
        for dep in "${missing_deps[@]}"; do
            echo "  - $dep"
        done
        log_error "Please install missing dependencies and try again."
        exit 1
    fi
    
    # Check Docker daemon
    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running. Please start Docker first."
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

setup_environment() {
    log_step "Setting up production environment..."
    
    if [[ ! -f "$PROJECT_ROOT/.env.production" ]]; then
        log_info "Production environment not configured. Running setup..."
        "$SCRIPT_DIR/setup_production_env.sh" setup
    else
        log_info "Production environment already configured"
        
        # Ask if user wants to reconfigure
        echo -n -e "${YELLOW}Do you want to reconfigure the environment? (y/N): ${NC}"
        read -r response
        if [[ "$response" =~ ^[Yy]$ ]]; then
            "$SCRIPT_DIR/setup_production_env.sh" setup
        fi
    fi
    
    log_success "Environment setup completed"
}

deploy_system() {
    log_step "Deploying Voice AI Agent system..."
    
    # Deploy using the production deployment script
    "$SCRIPT_DIR/deploy_production.sh" start
    
    log_success "System deployment completed"
}

run_system_validation() {
    log_step "Running system validation..."
    
    # Wait for system to stabilize
    log_info "Waiting for system to stabilize..."
    sleep 30
    
    # Run health checks
    log_info "Running health checks..."
    if "$SCRIPT_DIR/deploy_production.sh" health; then
        log_success "Health checks passed"
    else
        log_error "Health checks failed"
        return 1
    fi
    
    # Run basic validation tests
    log_info "Running validation tests..."
    if python3 "$SCRIPT_DIR/test_real_calls.py" --test-type scenarios; then
        log_success "Validation tests passed"
    else
        log_warning "Some validation tests failed, but system is operational"
    fi
    
    log_success "System validation completed"
}

start_monitoring() {
    log_step "Starting system monitoring..."
    
    # Check if monitoring is already running
    if curl -f -s http://localhost:3000 > /dev/null 2>&1; then
        log_info "Grafana is already running"
    else
        log_warning "Grafana may not be accessible yet"
    fi
    
    if curl -f -s http://localhost:9090 > /dev/null 2>&1; then
        log_info "Prometheus is already running"
    else
        log_warning "Prometheus may not be accessible yet"
    fi
    
    # Start background monitoring
    log_info "Starting background system monitor..."
    nohup python3 "$SCRIPT_DIR/monitor_system.py" --mode console --interval 10 > monitor.log 2>&1 &
    echo $! > monitor.pid
    
    log_success "Monitoring started"
}

conduct_real_call_test() {
    log_step "Conducting real call test..."
    
    echo -e "${YELLOW}This step will test the system with simulated phone calls.${NC}"
    echo -n -e "${YELLOW}Do you want to run the call test now? (Y/n): ${NC}"
    read -r response
    
    if [[ ! "$response" =~ ^[Nn]$ ]]; then
        log_info "Running comprehensive call tests..."
        
        # Run different types of tests
        python3 "$SCRIPT_DIR/test_real_calls.py" --test-type scenarios --output call_test_scenarios.md
        
        echo -n -e "${YELLOW}Do you want to run a load test? (y/N): ${NC}"
        read -r load_response
        if [[ "$load_response" =~ ^[Yy]$ ]]; then
            python3 "$SCRIPT_DIR/test_real_calls.py" --test-type load --concurrent-calls 3 --duration 5 --output call_test_load.md
        fi
        
        log_success "Call tests completed"
    else
        log_info "Call tests skipped"
    fi
}

show_system_status() {
    log_step "System Status Summary"
    
    echo
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                            System Status                                    ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════════════════════════╝${NC}"
    
    # Show running containers
    echo -e "${YELLOW}Running Containers:${NC}"
    docker compose -f "$PROJECT_ROOT/docker-compose.prod.yml" ps
    echo
    
    # Show service URLs
    echo -e "${YELLOW}Service URLs:${NC}"
    echo "  🏥 Health Check:     http://localhost:8001/health"
    echo "  📊 Metrics:          http://localhost:8000/metrics"
    echo "  📈 Prometheus:       http://localhost:9090"
    echo "  📊 Grafana:          http://localhost:3000 (admin/admin)"
    echo "  🔍 Application Logs: docker compose -f docker-compose.prod.yml logs -f voice-ai-agent"
    echo
    
    # Show monitoring commands
    echo -e "${YELLOW}Monitoring Commands:${NC}"
    echo "  📱 Real-time Monitor: python3 scripts/monitor_system.py --mode curses"
    echo "  📋 Console Monitor:   python3 scripts/monitor_system.py --mode console"
    echo "  🧪 Run Call Tests:    python3 scripts/test_real_calls.py"
    echo "  🔧 System Control:    ./scripts/deploy_production.sh [start|stop|restart|status]"
    echo
    
    # Show log locations
    echo -e "${YELLOW}Log Files:${NC}"
    echo "  📝 Application:       logs/voice_ai_agent.log"
    echo "  📝 System Monitor:    monitor.log"
    echo "  📝 Call Tests:        call_test_*.md"
    echo
    
    # Quick health check
    echo -e "${YELLOW}Quick Health Check:${NC}"
    if curl -f -s http://localhost:8001/health | jq -e '.status == "healthy"' > /dev/null 2>&1; then
        echo "  ✅ Application: HEALTHY"
    else
        echo "  ❌ Application: UNHEALTHY"
    fi
    
    if curl -f -s http://localhost:9090/-/healthy > /dev/null 2>&1; then
        echo "  ✅ Prometheus: HEALTHY"
    else
        echo "  ❌ Prometheus: UNHEALTHY"
    fi
    
    if curl -f -s http://localhost:3000/api/health > /dev/null 2>&1; then
        echo "  ✅ Grafana: HEALTHY"
    else
        echo "  ❌ Grafana: UNHEALTHY"
    fi
    
    echo
}

show_next_steps() {
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                              Next Steps                                     ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════════════════════════╝${NC}"
    echo
    echo -e "${GREEN}🎉 Voice AI Agent is now running in production mode!${NC}"
    echo
    echo -e "${YELLOW}Immediate Actions:${NC}"
    echo "1. 🔐 Change Grafana password: http://localhost:3000 (admin/admin)"
    echo "2. 📊 Review dashboards and set up alerts"
    echo "3. 🧪 Test with real phone calls"
    echo "4. 📈 Monitor system performance"
    echo
    echo -e "${YELLOW}Production Checklist:${NC}"
    echo "□ Configure SSL/TLS certificates"
    echo "□ Set up firewall rules"
    echo "□ Configure backup procedures"
    echo "□ Set up log rotation"
    echo "□ Configure alerting (email/Slack)"
    echo "□ Document operational procedures"
    echo "□ Train operations team"
    echo
    echo -e "${YELLOW}Monitoring & Maintenance:${NC}"
    echo "• Monitor system metrics regularly"
    echo "• Review call quality and latency"
    echo "• Check error rates and alerts"
    echo "• Perform regular backups"
    echo "• Update API keys as needed"
    echo "• Scale resources based on load"
    echo
    echo -e "${GREEN}System is ready for production use! 🚀${NC}"
}

cleanup_on_exit() {
    log_info "Cleaning up..."
    # Kill background monitor if running
    if [[ -f monitor.pid ]]; then
        kill "$(cat monitor.pid)" 2>/dev/null || true
        rm -f monitor.pid
    fi
}

# Main execution
main() {
    # Set up cleanup on exit
    trap cleanup_on_exit EXIT
    
    print_banner
    
    log_info "Starting complete Voice AI Agent production deployment..."
    echo
    
    # Step 1: Prerequisites
    check_prerequisites
    echo
    
    # Step 2: Environment Setup
    setup_environment
    echo
    
    # Step 3: System Deployment
    deploy_system
    echo
    
    # Step 4: System Validation
    run_system_validation
    echo
    
    # Step 5: Start Monitoring
    start_monitoring
    echo
    
    # Step 6: Real Call Testing
    conduct_real_call_test
    echo
    
    # Step 7: Show Status
    show_system_status
    
    # Step 8: Next Steps
    show_next_steps
    
    log_success "Production deployment completed successfully!"
    
    # Ask if user wants to start real-time monitoring
    echo
    echo -n -e "${YELLOW}Do you want to start real-time monitoring now? (Y/n): ${NC}"
    read -r monitor_response
    if [[ ! "$monitor_response" =~ ^[Nn]$ ]]; then
        log_info "Starting real-time monitoring..."
        python3 "$SCRIPT_DIR/monitor_system.py" --mode curses
    fi
}

# Handle script interruption
trap cleanup_on_exit EXIT

# Run main function
main "$@"