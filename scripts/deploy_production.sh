#!/bin/bash

# Production deployment script for Voice AI Agent
# This script sets up and deploys the complete system with monitoring

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_ROOT/.env.production"
DOCKER_COMPOSE_FILE="$PROJECT_ROOT/docker-compose.prod.yml"
LOG_DIR="$PROJECT_ROOT/logs"
DATA_DIR="$PROJECT_ROOT/data"

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

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    # Check Docker Compose
    if ! docker compose version &> /dev/null; then
        log_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    # Check if Docker daemon is running
    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running. Please start Docker first."
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

get_docker_compose_cmd() {
    if command -v docker-compose &> /dev/null; then
        echo "docker-compose"
    else
        echo "docker compose"
    fi
}

create_directories() {
    log_info "Creating necessary directories..."
    
    mkdir -p "$LOG_DIR"
    mkdir -p "$DATA_DIR"
    mkdir -p "$PROJECT_ROOT/monitoring/prometheus/data"
    mkdir -p "$PROJECT_ROOT/monitoring/grafana/data"
    
    # Set proper permissions
    chmod 755 "$LOG_DIR"
    chmod 755 "$DATA_DIR"
    
    log_success "Directories created"
}

check_environment_file() {
    log_info "Checking environment configuration..."
    
    if [[ ! -f "$ENV_FILE" ]]; then
        log_warning "Production environment file not found. Creating template..."
        create_production_env_template
    fi
    
    # Check for required environment variables
    local required_vars=(
        "DEEPGRAM_API_KEY"
        "OPENAI_API_KEY"
        "CARTESIA_API_KEY"
        "LIVEKIT_API_KEY"
        "LIVEKIT_API_SECRET"
        "SECRET_KEY"
    )
    
    local missing_vars=()
    for var in "${required_vars[@]}"; do
        if ! grep -q "^${var}=" "$ENV_FILE" || grep -q "^${var}=$" "$ENV_FILE" || grep -q "^${var}=your_" "$ENV_FILE"; then
            missing_vars+=("$var")
        fi
    done
    
    if [[ ${#missing_vars[@]} -gt 0 ]]; then
        log_error "Missing or empty required environment variables:"
        for var in "${missing_vars[@]}"; do
            echo "  - $var"
        done
        log_error "Please configure these variables in $ENV_FILE"
        exit 1
    fi
    
    log_success "Environment configuration is valid"
}

create_production_env_template() {
    cat > "$ENV_FILE" << 'EOF'
# Production Environment Configuration for Voice AI Agent

# Environment
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO

# Security
SECRET_KEY=your_secret_key_here_generate_with_openssl_rand_hex_32

# AI Service API Keys
DEEPGRAM_API_KEY=your_deepgram_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
CARTESIA_API_KEY=your_cartesia_api_key_here

# LiveKit Configuration
LIVEKIT_URL=wss://your-livekit-server.com
LIVEKIT_API_KEY=your_livekit_api_key_here
LIVEKIT_API_SECRET=your_livekit_api_secret_here

# SIP Configuration
SIP_TRUNK_URI=sip:your-sip-provider.com
SIP_USERNAME=your_sip_username
SIP_PASSWORD=your_sip_password

# Database
DATABASE_URL=sqlite:///data/voice_ai_agent.db

# Performance Settings
MAX_CONCURRENT_CALLS=50
AUDIO_BUFFER_SIZE=4096
RESPONSE_TIMEOUT=10.0
STT_TIMEOUT=5.0
LLM_TIMEOUT=8.0
TTS_TIMEOUT=5.0

# Monitoring
METRICS_PORT=8000
HEALTH_CHECK_PORT=8001
PROMETHEUS_PORT=9090
GRAFANA_PORT=3000

# Logging
LOG_FORMAT=json
LOG_FILE=/app/logs/voice_ai_agent.log
LOG_MAX_SIZE=100MB
LOG_BACKUP_COUNT=5

# Circuit Breaker Settings
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
CIRCUIT_BREAKER_RECOVERY_TIMEOUT=60
CIRCUIT_BREAKER_EXPECTED_EXCEPTION=Exception

# Retry Settings
MAX_RETRIES=3
RETRY_DELAY=1.0
RETRY_BACKOFF=2.0
EOF
    
    log_warning "Created production environment template at $ENV_FILE"
    log_warning "Please configure all required API keys and settings before proceeding"
}

build_images() {
    log_info "Building Docker images..."
    
    cd "$PROJECT_ROOT"
    
    # Build main application image with production target
    log_info "Building production image..."
    docker build --target production -t voice-ai-agent:production -t voice-ai-agent:latest .
    
    # Verify image was built successfully
    if docker images voice-ai-agent:production | grep -q production; then
        log_success "Docker images built successfully"
    else
        log_error "Failed to build Docker image"
        exit 1
    fi
}

create_deployment_backup() {
    log_info "Creating deployment backup..."
    
    local backup_dir="$PROJECT_ROOT/backups/deployment_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$backup_dir"
    
    # Backup configuration files
    if [[ -f "$PROJECT_ROOT/monitoring/prometheus/prometheus.yml" ]]; then
        cp "$PROJECT_ROOT/monitoring/prometheus/prometheus.yml" "$backup_dir/"
        log_info "Backed up Prometheus configuration"
    fi
    
    if [[ -f "$DOCKER_COMPOSE_FILE" ]]; then
        cp "$DOCKER_COMPOSE_FILE" "$backup_dir/"
        log_info "Backed up Docker Compose configuration"
    fi
    
    if [[ -f "$ENV_FILE" ]]; then
        cp "$ENV_FILE" "$backup_dir/"
        log_info "Backed up environment configuration"
    fi
    
    # Save current container state
    docker compose -f "$DOCKER_COMPOSE_FILE" ps > "$backup_dir/container_state.txt" 2>/dev/null || true
    
    echo "$backup_dir" > "$PROJECT_ROOT/.last_backup_path"
    log_success "Deployment backup created at: $backup_dir"
}

rollback_deployment() {
    log_warning "Initiating deployment rollback..."
    
    local backup_path
    if [[ -f "$PROJECT_ROOT/.last_backup_path" ]]; then
        backup_path=$(cat "$PROJECT_ROOT/.last_backup_path")
    else
        log_error "No backup path found for rollback"
        return 1
    fi
    
    if [[ ! -d "$backup_path" ]]; then
        log_error "Backup directory not found: $backup_path"
        return 1
    fi
    
    log_info "Rolling back from backup: $backup_path"
    
    # Stop current services
    log_info "Stopping current services..."
    docker compose -f "$DOCKER_COMPOSE_FILE" down || true
    
    # Restore configuration files
    if [[ -f "$backup_path/prometheus.yml" ]]; then
        cp "$backup_path/prometheus.yml" "$PROJECT_ROOT/monitoring/prometheus/prometheus.yml"
        log_info "Restored Prometheus configuration"
    fi
    
    if [[ -f "$backup_path/docker-compose.prod.yml" ]]; then
        cp "$backup_path/docker-compose.prod.yml" "$DOCKER_COMPOSE_FILE"
        log_info "Restored Docker Compose configuration"
    fi
    
    if [[ -f "$backup_path/.env.production" ]]; then
        cp "$backup_path/.env.production" "$ENV_FILE"
        log_info "Restored environment configuration"
    fi
    
    # Try to restart with backup configuration
    log_info "Attempting to restart with backup configuration..."
    if start_monitoring_stack && start_application; then
        log_success "Rollback completed successfully"
        return 0
    else
        log_error "Rollback failed - manual intervention required"
        return 1
    fi
}

start_monitoring_stack() {
    log_info "Starting monitoring stack..."
    
    # Validate Prometheus configuration before starting
    if ! validate_prometheus_configuration; then
        log_error "Prometheus configuration validation failed"
        return 1
    fi
    
    # Create backup before making changes
    create_deployment_backup
    
    # Start Prometheus first
    log_info "Starting Prometheus..."
    docker compose -f "$DOCKER_COMPOSE_FILE" up -d prometheus
    
    # Wait for Prometheus to be ready
    local max_wait=60
    local wait_time=0
    
    while [[ $wait_time -lt $max_wait ]]; do
        if docker compose -f "$DOCKER_COMPOSE_FILE" ps prometheus | grep -q "Up"; then
            log_info "Prometheus container is up, checking health..."
            
            # Wait a bit more for the service to be ready
            sleep 5
            
            if curl -f -s http://localhost:9091/-/healthy > /dev/null 2>&1; then
                log_success "Prometheus is healthy"
                break
            fi
        fi
        
        log_info "Waiting for Prometheus to be ready... ($wait_time/$max_wait seconds)"
        sleep 5
        wait_time=$((wait_time + 5))
    done
    
    if [[ $wait_time -ge $max_wait ]]; then
        log_error "Prometheus failed to start within timeout"
        log_info "Checking Prometheus logs..."
        docker compose -f "$DOCKER_COMPOSE_FILE" logs --tail=20 prometheus
        
        # Attempt recovery
        log_info "Attempting Prometheus recovery..."
        if python3 -c "
import sys, asyncio
sys.path.insert(0, '$PROJECT_ROOT')
from src.monitoring.prometheus_recovery import recover_prometheus

async def main():
    try:
        result = await recover_prometheus('http://localhost:9091')
        if result.success:
            print('Prometheus recovery successful')
            sys.exit(0)
        else:
            print('Prometheus recovery failed')
            sys.exit(1)
    except Exception as e:
        print(f'Recovery attempt failed: {e}')
        sys.exit(1)

asyncio.run(main())
" 2>/dev/null; then
            log_success "Prometheus recovery successful"
        else
            log_error "Prometheus recovery failed - initiating rollback"
            rollback_deployment
            return 1
        fi
    fi
    
    # Start Grafana
    log_info "Starting Grafana..."
    docker compose -f "$DOCKER_COMPOSE_FILE" up -d grafana
    
    # Wait for Grafana to be ready
    wait_time=0
    while [[ $wait_time -lt $max_wait ]]; do
        if curl -f -s http://localhost:3000/api/health > /dev/null 2>&1; then
            log_success "Grafana is healthy"
            break
        fi
        
        log_info "Waiting for Grafana to be ready... ($wait_time/$max_wait seconds)"
        sleep 5
        wait_time=$((wait_time + 5))
    done
    
    if [[ $wait_time -ge $max_wait ]]; then
        log_error "Grafana failed to start within timeout"
        log_info "Checking Grafana logs..."
        docker compose -f "$DOCKER_COMPOSE_FILE" logs --tail=20 grafana
        return 1
    fi
    
    # Run post-deployment verification
    if ! run_prometheus_health_check; then
        log_error "Post-deployment Prometheus health check failed"
        rollback_deployment
        return 1
    fi
    
    log_success "Monitoring stack started successfully"
    log_info "Prometheus: http://localhost:9091"
    log_info "Grafana: http://localhost:3000 (admin/admin)"
}

start_application() {
    log_info "Starting Voice AI Agent application..."
    
    # Start the main application
    docker compose -f "$DOCKER_COMPOSE_FILE" up -d voice-ai-agent
    
    # Wait for application to start
    log_info "Waiting for application to start..."
    sleep 15
    
    # Check application health
    local max_attempts=30
    local attempt=1
    
    while [[ $attempt -le $max_attempts ]]; do
        if curl -f -s http://localhost:8000/health > /dev/null 2>&1; then
            log_success "Application started successfully and is healthy"
            return 0
        fi
        
        log_info "Attempt $attempt/$max_attempts: Waiting for application to be ready..."
        sleep 2
        ((attempt++))
    done
    
    log_error "Application failed to start or become healthy within timeout"
    return 1
}

run_post_deployment_verification() {
    log_info "Running post-deployment verification of monitoring stack..."
    
    # Generate comprehensive monitoring report
    if python3 -c "
import sys, asyncio, json
sys.path.insert(0, '$PROJECT_ROOT')
from src.monitoring.prometheus_health import generate_prometheus_report

async def main():
    try:
        report = await generate_prometheus_report('http://localhost:9091')
        
        print('=== Prometheus Health Report ===')
        health = report['health_check']
        print(f'Overall Status: {health[\"status\"].upper()}')
        print(f'Service Running: {\"✅\" if health[\"service_running\"] else \"❌\"}')
        print(f'Config Valid: {\"✅\" if health[\"config_valid\"] else \"❌\"}')
        print(f'Response Time: {health[\"response_time_ms\"]}ms')
        
        if health.get('version'):
            print(f'Version: {health[\"version\"]}')
        
        print('\\nEndpoint Accessibility:')
        for endpoint, accessible in health['endpoints_accessible'].items():
            status = '✅' if accessible else '❌'
            print(f'  {status} {endpoint}')
        
        if health['error_messages']:
            print('\\nIssues Found:')
            for error in health['error_messages']:
                print(f'  • {error}')
        
        # Check configuration status
        config = report['configuration_status']
        print(f'\\nConfiguration Status:')
        print(f'  YAML Valid: {\"✅\" if config[\"yaml_valid\"] else \"❌\"}')
        print(f'  Scrape Configs: {len(config[\"scrape_configs\"])}')
        
        accessible_targets = sum(1 for accessible in config['target_accessibility'].values() if accessible)
        total_targets = len(config['target_accessibility'])
        print(f'  Target Accessibility: {accessible_targets}/{total_targets}')
        
        for target, accessible in config['target_accessibility'].items():
            status = '✅' if accessible else '❌'
            print(f'    {status} {target}')
        
        # Exit with appropriate code
        if health['status'] == 'healthy':
            print('\\n🎉 Monitoring stack verification: PASSED')
            sys.exit(0)
        elif health['status'] == 'degraded':
            print('\\n⚠️  Monitoring stack verification: DEGRADED (but functional)')
            sys.exit(1)
        else:
            print('\\n💥 Monitoring stack verification: FAILED')
            sys.exit(2)
            
    except Exception as e:
        print(f'Verification failed: {e}')
        sys.exit(2)

asyncio.run(main())
" 2>/dev/null; then
        log_success "Post-deployment monitoring verification: PASSED"
        return 0
    else
        local exit_code=$?
        if [[ $exit_code -eq 1 ]]; then
            log_warning "Post-deployment monitoring verification: DEGRADED (continuing)"
            return 0
        else
            log_error "Post-deployment monitoring verification: FAILED"
            return 1
        fi
    fi
}

show_status() {
    log_info "System Status:"
    echo
    
    # Show running containers
    docker compose -f "$DOCKER_COMPOSE_FILE" ps
    echo
    
    # Show application logs (last 20 lines)
    log_info "Recent application logs:"
    docker compose -f "$DOCKER_COMPOSE_FILE" logs --tail=20 voice-ai-agent
    echo
    
    # Show service URLs
    log_info "Service URLs:"
    echo "  Application Health: http://localhost:8000/health"
    echo "  Application Metrics: http://localhost:8000/metrics"
    echo "  Prometheus: http://localhost:9091"
    echo "  Grafana: http://localhost:3000"
    echo
    
    # Show system resources
    log_info "System Resources:"
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}"
    echo
    
    # Show monitoring stack health summary
    log_info "Monitoring Stack Health:"
    python3 -c "
import sys, asyncio
sys.path.insert(0, '$PROJECT_ROOT')
from src.monitoring.prometheus_health import check_prometheus_health

async def main():
    try:
        result = await check_prometheus_health('http://localhost:9091')
        status_emoji = '🟢' if result.status == 'healthy' else '🟡' if result.status == 'degraded' else '🔴'
        print(f'  {status_emoji} Prometheus: {result.status.upper()} ({result.response_time_ms}ms)')
        
        accessible_endpoints = sum(1 for accessible in result.endpoints_accessible.values() if accessible)
        total_endpoints = len(result.endpoints_accessible)
        print(f'  📊 Endpoints: {accessible_endpoints}/{total_endpoints} accessible')
        
    except Exception as e:
        print(f'  ❌ Prometheus: ERROR ({e})')

asyncio.run(main())
" 2>/dev/null || echo "  ❌ Prometheus: Health check failed"
}

validate_prometheus_configuration() {
    log_info "Validating Prometheus configuration..."
    
    local prometheus_config="$PROJECT_ROOT/monitoring/prometheus/prometheus.yml"
    
    # Check if configuration file exists
    if [[ ! -f "$prometheus_config" ]]; then
        log_error "Prometheus configuration file not found: $prometheus_config"
        return 1
    fi
    
    # Validate YAML syntax
    if ! python3 -c "import yaml; yaml.safe_load(open('$prometheus_config'))" 2>/dev/null; then
        log_error "Prometheus configuration has invalid YAML syntax"
        return 1
    fi
    
    # Use Python script for comprehensive validation
    if python3 -c "
import sys
sys.path.insert(0, '$PROJECT_ROOT')
from src.monitoring.config_validator import validate_prometheus_config_syntax
result = validate_prometheus_config_syntax('$prometheus_config')
if not result.is_valid:
    print('Configuration validation failed:')
    for error in result.errors:
        print(f'  - {error}')
    sys.exit(1)
else:
    print('Configuration validation passed')
" 2>/dev/null; then
        log_success "Prometheus configuration validation: PASSED"
    else
        log_error "Prometheus configuration validation: FAILED"
        log_info "Attempting auto-correction..."
        
        # Try auto-correction
        if python3 -c "
import sys
sys.path.insert(0, '$PROJECT_ROOT')
from src.monitoring.config_validator import auto_correct_prometheus_config
result = auto_correct_prometheus_config('$prometheus_config', backup=True)
if result.is_valid:
    print('Configuration auto-corrected successfully')
    sys.exit(0)
else:
    print('Auto-correction failed')
    sys.exit(1)
" 2>/dev/null; then
            log_success "Prometheus configuration auto-corrected"
        else
            log_error "Failed to auto-correct Prometheus configuration"
            return 1
        fi
    fi
    
    return 0
}

run_prometheus_health_check() {
    log_info "Running comprehensive Prometheus health check..."
    
    # Use Python script for detailed health check
    if python3 -c "
import sys, asyncio
sys.path.insert(0, '$PROJECT_ROOT')
from src.monitoring.prometheus_health import check_prometheus_health

async def main():
    try:
        result = await check_prometheus_health('http://localhost:9091')
        print(f'Prometheus Status: {result.status}')
        print(f'Service Running: {result.service_running}')
        print(f'Config Valid: {result.config_valid}')
        print(f'Response Time: {result.response_time_ms}ms')
        
        if result.error_messages:
            print('Errors:')
            for error in result.error_messages:
                print(f'  - {error}')
        
        if result.status == 'healthy':
            sys.exit(0)
        elif result.status == 'degraded':
            sys.exit(1)
        else:
            sys.exit(2)
    except Exception as e:
        print(f'Health check failed: {e}')
        sys.exit(2)

asyncio.run(main())
" 2>/dev/null; then
        log_success "Prometheus comprehensive health check: PASSED"
        return 0
    else
        local exit_code=$?
        if [[ $exit_code -eq 1 ]]; then
            log_warning "Prometheus health check: DEGRADED (but functional)"
            return 0  # Allow degraded state to continue
        else
            log_error "Prometheus health check: FAILED"
            return 1
        fi
    fi
}

verify_prometheus_targets() {
    log_info "Verifying Prometheus scrape targets..."
    
    local max_attempts=10
    local attempt=1
    
    while [[ $attempt -le $max_attempts ]]; do
        log_info "Attempt $attempt/$max_attempts: Checking target accessibility..."
        
        if python3 -c "
import sys, asyncio
sys.path.insert(0, '$PROJECT_ROOT')
from src.monitoring.config_validator import check_prometheus_targets

async def main():
    try:
        results = await check_prometheus_targets('$PROJECT_ROOT/monitoring/prometheus/prometheus.yml')
        accessible_count = sum(1 for r in results if r.accessible)
        total_count = len(results)
        
        print(f'Target accessibility: {accessible_count}/{total_count}')
        
        for result in results:
            status = 'OK' if result.accessible else 'FAILED'
            print(f'  {result.target}: {status}')
            if not result.accessible and result.error_message:
                print(f'    Error: {result.error_message}')
        
        # Allow partial success (at least 50% targets accessible)
        if accessible_count >= total_count * 0.5:
            sys.exit(0)
        else:
            sys.exit(1)
    except Exception as e:
        print(f'Target verification failed: {e}')
        sys.exit(1)

asyncio.run(main())
" 2>/dev/null; then
            log_success "Prometheus targets verification: PASSED"
            return 0
        else
            log_warning "Some Prometheus targets are not accessible, retrying in 5 seconds..."
            sleep 5
            ((attempt++))
        fi
    done
    
    log_error "Prometheus targets verification: FAILED after $max_attempts attempts"
    return 1
}

run_health_checks() {
    log_info "Running comprehensive health checks..."
    
    # Check application health endpoint
    if curl -f -s http://localhost:8000/health | jq -e '.status == "healthy"' > /dev/null 2>&1; then
        log_success "Application health check: PASSED"
    else
        log_error "Application health check: FAILED"
        return 1
    fi
    
    # Check metrics endpoint
    if curl -f -s http://localhost:8000/metrics > /dev/null 2>&1; then
        log_success "Metrics endpoint check: PASSED"
    else
        log_error "Metrics endpoint check: FAILED"
        return 1
    fi
    
    # Run comprehensive Prometheus health check
    if ! run_prometheus_health_check; then
        log_error "Prometheus health check: FAILED"
        return 1
    fi
    
    # Verify Prometheus targets
    if ! verify_prometheus_targets; then
        log_warning "Prometheus targets verification: PARTIAL (continuing anyway)"
    fi
    
    # Check Prometheus API endpoints
    if curl -f -s http://localhost:9091/-/healthy > /dev/null 2>&1; then
        log_success "Prometheus health endpoint: PASSED"
    else
        log_error "Prometheus health endpoint: FAILED"
        return 1
    fi
    
    if curl -f -s http://localhost:9091/-/ready > /dev/null 2>&1; then
        log_success "Prometheus ready endpoint: PASSED"
    else
        log_error "Prometheus ready endpoint: FAILED"
        return 1
    fi
    
    # Check if Prometheus can query metrics
    if curl -f -s "http://localhost:9091/api/v1/query?query=up" | jq -e '.status == "success"' > /dev/null 2>&1; then
        log_success "Prometheus query API: PASSED"
    else
        log_error "Prometheus query API: FAILED"
        return 1
    fi
    
    # Check Grafana
    if curl -f -s http://localhost:3000/api/health > /dev/null 2>&1; then
        log_success "Grafana health check: PASSED"
    else
        log_error "Grafana health check: FAILED"
        return 1
    fi
    
    log_success "All health checks passed!"
}

cleanup() {
    log_info "Cleaning up..."
    docker compose -f "$DOCKER_COMPOSE_FILE" down
    log_success "Cleanup completed"
}

show_help() {
    echo "Usage: $0 [COMMAND]"
    echo
    echo "Commands:"
    echo "  start              Start the complete production system"
    echo "  stop               Stop all services"
    echo "  restart            Restart all services"
    echo "  status             Show system status"
    echo "  health             Run health checks"
    echo "  logs               Show application logs"
    echo "  cleanup            Stop services and clean up"
    echo "  validate-config    Validate Prometheus configuration"
    echo "  prometheus-health  Run comprehensive Prometheus health check"
    echo "  prometheus-recover Attempt Prometheus recovery"
    echo "  rollback           Rollback to last backup"
    echo "  help               Show this help message"
    echo
}

# Main execution
main() {
    local command="${1:-start}"
    
    case "$command" in
        "start")
            log_info "Starting Voice AI Agent production deployment..."
            check_prerequisites
            create_directories
            check_environment_file
            
            # Pre-deployment validation
            log_info "Running pre-deployment validation..."
            if ! validate_prometheus_configuration; then
                log_error "Pre-deployment validation failed"
                exit 1
            fi
            
            build_images
            start_monitoring_stack
            start_application
            
            # Post-deployment verification
            log_info "Running post-deployment verification..."
            if ! run_post_deployment_verification; then
                log_error "Post-deployment verification failed - initiating rollback"
                rollback_deployment
                exit 1
            fi
            
            show_status
            run_health_checks
            log_success "Production deployment completed successfully!"
            ;;
        "stop")
            log_info "Stopping Voice AI Agent services..."
            docker compose -f "$DOCKER_COMPOSE_FILE" down
            log_success "Services stopped"
            ;;
        "restart")
            log_info "Restarting Voice AI Agent services..."
            docker compose -f "$DOCKER_COMPOSE_FILE" restart
            sleep 10
            run_health_checks
            log_success "Services restarted"
            ;;
        "status")
            show_status
            ;;
        "health")
            run_health_checks
            ;;
        "logs")
            docker compose -f "$DOCKER_COMPOSE_FILE" logs -f voice-ai-agent
            ;;
        "cleanup")
            cleanup
            ;;
        "validate-config")
            log_info "Validating Prometheus configuration..."
            if validate_prometheus_configuration; then
                log_success "Prometheus configuration is valid"
            else
                log_error "Prometheus configuration validation failed"
                exit 1
            fi
            ;;
        "prometheus-health")
            log_info "Running comprehensive Prometheus health check..."
            if run_prometheus_health_check; then
                log_success "Prometheus health check passed"
            else
                log_error "Prometheus health check failed"
                exit 1
            fi
            ;;
        "prometheus-recover")
            log_info "Attempting Prometheus recovery..."
            if python3 -c "
import sys, asyncio
sys.path.insert(0, '$PROJECT_ROOT')
from src.monitoring.prometheus_recovery import recover_prometheus

async def main():
    try:
        result = await recover_prometheus('http://localhost:9091')
        print(f'Recovery Status: {\"SUCCESS\" if result.success else \"FAILED\"}')
        print(f'Final Status: {result.final_status}')
        
        print('\\nActions Taken:')
        for action in result.actions_taken:
            status = '✅' if action.success else '❌'
            print(f'  {status} {action.action_type}: {action.details}')
        
        if result.success:
            print('\\n🎉 Prometheus recovery completed successfully!')
            sys.exit(0)
        else:
            print('\\n💥 Prometheus recovery failed')
            if result.error_message:
                print(f'Error: {result.error_message}')
            sys.exit(1)
    except Exception as e:
        print(f'Recovery attempt failed: {e}')
        sys.exit(1)

asyncio.run(main())
"; then
                log_success "Prometheus recovery completed"
            else
                log_error "Prometheus recovery failed"
                exit 1
            fi
            ;;
        "rollback")
            log_info "Initiating deployment rollback..."
            if rollback_deployment; then
                log_success "Rollback completed successfully"
            else
                log_error "Rollback failed"
                exit 1
            fi
            ;;
        "help"|"-h"|"--help")
            show_help
            ;;
        *)
            log_error "Unknown command: $command"
            show_help
            exit 1
            ;;
    esac
}

# Handle script interruption
trap cleanup EXIT

# Run main function
main "$@"