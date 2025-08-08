#!/bin/bash
# Comprehensive LiveKit Migration Deployment Script
# Комплексный скрипт развертывания миграции LiveKit
# Requirements: 1.1, 2.1, 3.1

set -e  # Exit on any error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="deployment_${TIMESTAMP}.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

# Function to check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check if Docker is running
    if ! docker info >/dev/null 2>&1; then
        error "Docker is not running. Please start Docker and try again."
        exit 1
    fi
    
    # Check if docker-compose is available
    if ! command -v docker-compose >/dev/null 2>&1; then
        error "docker-compose is not installed. Please install docker-compose and try again."
        exit 1
    fi
    
    # Check if Python is available
    if ! command -v python3 >/dev/null 2>&1; then
        error "Python 3 is not installed. Please install Python 3 and try again."
        exit 1
    fi
    
    # Check if required Python packages are available
    if ! python3 -c "import yaml, requests, aiohttp" >/dev/null 2>&1; then
        warning "Some Python packages may be missing. Installing requirements..."
        pip3 install -r requirements.txt || {
            error "Failed to install Python requirements"
            exit 1
        }
    fi
    
    success "Prerequisites check completed"
}

# Function to create backup
create_backup() {
    log "Creating pre-deployment backup..."
    
    if python3 "$SCRIPT_DIR/migration_plan.py" --backup; then
        success "Backup created successfully"
    else
        error "Failed to create backup"
        exit 1
    fi
}

# Function to update environment variables
update_environment() {
    log "Updating environment variables..."
    
    if python3 "$SCRIPT_DIR/update_env_vars.py" --create-all; then
        success "Environment variables updated"
    else
        error "Failed to update environment variables"
        exit 1
    fi
}

# Function to validate configuration
validate_configuration() {
    log "Validating configuration..."
    
    # Validate environment variables
    if python3 "$SCRIPT_DIR/update_env_vars.py" --validate; then
        success "Environment variables validation passed"
    else
        warning "Environment variables validation failed, continuing..."
    fi
    
    # Validate deployment configuration
    if python3 "$SCRIPT_DIR/automated_deployment.py" --validate; then
        success "Deployment configuration validation passed"
    else
        error "Deployment configuration validation failed"
        exit 1
    fi
}

# Function to stop existing services
stop_services() {
    log "Stopping existing services..."
    
    # Stop all possible compose configurations
    for compose_file in docker-compose.yml docker-compose.prod.yml docker-compose.blue.yml docker-compose.green.yml; do
        if [ -f "$compose_file" ]; then
            log "Stopping services from $compose_file"
            docker-compose -f "$compose_file" down || warning "Could not stop services from $compose_file"
        fi
    done
    
    success "Services stopped"
}

# Function to deploy services
deploy_services() {
    local environment=${1:-"development"}
    
    log "Deploying services to $environment environment..."
    
    if [ "$environment" = "production" ]; then
        # Use blue-green deployment for production
        if python3 "$SCRIPT_DIR/blue_green_deployment.py" --deploy; then
            success "Blue-green deployment completed"
        else
            error "Blue-green deployment failed"
            return 1
        fi
    else
        # Standard deployment for development/staging
        if python3 "$SCRIPT_DIR/automated_deployment.py" --deploy "$environment"; then
            success "Standard deployment completed"
        else
            error "Standard deployment failed"
            return 1
        fi
    fi
}

# Function to validate deployment
validate_deployment() {
    log "Validating deployment..."
    
    # Wait for services to start
    log "Waiting for services to initialize..."
    sleep 30
    
    # Run migration validation
    if python3 "$SCRIPT_DIR/validate_migration.py" --full; then
        success "Migration validation passed"
    else
        error "Migration validation failed"
        return 1
    fi
    
    # Run staging environment tests if available
    if [ -f "$SCRIPT_DIR/staging_environment_tests.py" ]; then
        log "Running staging environment tests..."
        if python3 "$SCRIPT_DIR/staging_environment_tests.py" --suite infrastructure; then
            success "Infrastructure tests passed"
        else
            warning "Some infrastructure tests failed"
        fi
    fi
}

# Function to perform rollback
perform_rollback() {
    local rollback_point=$1
    
    error "Deployment failed, performing rollback..."
    
    if [ -n "$rollback_point" ] && python3 "$SCRIPT_DIR/rollback_procedures.py" --rollback "$rollback_point"; then
        success "Rollback completed successfully"
    else
        error "Rollback failed - manual intervention required"
        exit 1
    fi
}

# Function to cleanup old resources
cleanup_resources() {
    log "Cleaning up old resources..."
    
    # Remove unused Docker images
    docker image prune -f || warning "Could not prune Docker images"
    
    # Remove old backup files (keep last 5)
    find backups/ -name "rollback_*" -type d | sort -r | tail -n +6 | xargs rm -rf || warning "Could not cleanup old backups"
    
    success "Resource cleanup completed"
}

# Function to send notification
send_notification() {
    local status=$1
    local message=$2
    
    if [ -n "$DEPLOYMENT_WEBHOOK_URL" ]; then
        curl -X POST "$DEPLOYMENT_WEBHOOK_URL" \
            -H "Content-Type: application/json" \
            -d "{\"status\":\"$status\",\"message\":\"$message\",\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" \
            >/dev/null 2>&1 || warning "Could not send notification"
    fi
}

# Main deployment function
main_deployment() {
    local environment=${1:-"development"}
    local skip_backup=${2:-false}
    
    log "Starting LiveKit migration deployment to $environment environment"
    log "Deployment ID: $TIMESTAMP"
    
    # Create rollback point
    local rollback_point=""
    if [ "$skip_backup" != "true" ]; then
        rollback_point=$(python3 "$SCRIPT_DIR/rollback_procedures.py" --create "pre_deployment_$TIMESTAMP" --description "Pre-deployment backup for $environment")
        if [ $? -eq 0 ]; then
            success "Rollback point created: $rollback_point"
        else
            error "Failed to create rollback point"
            exit 1
        fi
    fi
    
    # Deployment steps
    local deployment_failed=false
    
    # Step 1: Prerequisites
    check_prerequisites || deployment_failed=true
    
    # Step 2: Update environment
    if [ "$deployment_failed" = false ]; then
        update_environment || deployment_failed=true
    fi
    
    # Step 3: Validate configuration
    if [ "$deployment_failed" = false ]; then
        validate_configuration || deployment_failed=true
    fi
    
    # Step 4: Stop services
    if [ "$deployment_failed" = false ]; then
        stop_services || deployment_failed=true
    fi
    
    # Step 5: Deploy services
    if [ "$deployment_failed" = false ]; then
        deploy_services "$environment" || deployment_failed=true
    fi
    
    # Step 6: Validate deployment
    if [ "$deployment_failed" = false ]; then
        validate_deployment || deployment_failed=true
    fi
    
    # Handle deployment result
    if [ "$deployment_failed" = true ]; then
        send_notification "failed" "LiveKit migration deployment to $environment failed"
        
        if [ -n "$rollback_point" ]; then
            perform_rollback "$rollback_point"
        fi
        
        error "Deployment failed"
        exit 1
    else
        # Step 7: Cleanup
        cleanup_resources
        
        send_notification "success" "LiveKit migration deployment to $environment completed successfully"
        success "Deployment completed successfully"
        
        # Display deployment summary
        echo ""
        echo "=== DEPLOYMENT SUMMARY ==="
        echo "Environment: $environment"
        echo "Deployment ID: $TIMESTAMP"
        echo "Log file: $LOG_FILE"
        if [ -n "$rollback_point" ]; then
            echo "Rollback point: $rollback_point"
        fi
        echo "=========================="
    fi
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS] [ENVIRONMENT]"
    echo ""
    echo "Deploy LiveKit migration to specified environment"
    echo ""
    echo "ENVIRONMENT:"
    echo "  development    Deploy to development environment (default)"
    echo "  staging        Deploy to staging environment"
    echo "  production     Deploy to production environment (uses blue-green)"
    echo ""
    echo "OPTIONS:"
    echo "  --skip-backup  Skip creating rollback point"
    echo "  --validate-only Validate configuration without deploying"
    echo "  --rollback POINT Rollback to specified point"
    echo "  --status       Show deployment status"
    echo "  --help         Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                          # Deploy to development"
    echo "  $0 staging                  # Deploy to staging"
    echo "  $0 production               # Deploy to production with blue-green"
    echo "  $0 --validate-only          # Only validate configuration"
    echo "  $0 --rollback /path/to/point # Rollback to specific point"
}

# Parse command line arguments
ENVIRONMENT="development"
SKIP_BACKUP=false
VALIDATE_ONLY=false
ROLLBACK_POINT=""
SHOW_STATUS=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-backup)
            SKIP_BACKUP=true
            shift
            ;;
        --validate-only)
            VALIDATE_ONLY=true
            shift
            ;;
        --rollback)
            ROLLBACK_POINT="$2"
            shift 2
            ;;
        --status)
            SHOW_STATUS=true
            shift
            ;;
        --help)
            show_usage
            exit 0
            ;;
        development|staging|production)
            ENVIRONMENT="$1"
            shift
            ;;
        *)
            error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Change to project root directory
cd "$PROJECT_ROOT"

# Execute based on options
if [ "$SHOW_STATUS" = true ]; then
    log "Showing deployment status..."
    python3 "$SCRIPT_DIR/automated_deployment.py" --status
    python3 "$SCRIPT_DIR/blue_green_deployment.py" --status
    python3 "$SCRIPT_DIR/rollback_procedures.py" --status
    
elif [ -n "$ROLLBACK_POINT" ]; then
    log "Performing rollback to: $ROLLBACK_POINT"
    perform_rollback "$ROLLBACK_POINT"
    
elif [ "$VALIDATE_ONLY" = true ]; then
    log "Validating configuration only..."
    check_prerequisites
    validate_configuration
    success "Configuration validation completed"
    
else
    # Main deployment
    main_deployment "$ENVIRONMENT" "$SKIP_BACKUP"
fi