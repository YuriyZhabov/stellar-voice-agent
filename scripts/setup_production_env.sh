#!/bin/bash

# Production environment setup script for Voice AI Agent
# This script helps configure API keys and production settings

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

prompt_user() {
    local prompt="$1"
    local default="$2"
    local secret="${3:-false}"
    
    if [[ "$secret" == "true" ]]; then
        echo -n -e "${BLUE}$prompt${NC}"
        if [[ -n "$default" ]]; then
            echo -n " (default: [hidden]): "
        else
            echo -n ": "
        fi
        read -s user_input
        echo  # New line after hidden input
    else
        echo -n -e "${BLUE}$prompt${NC}"
        if [[ -n "$default" ]]; then
            echo -n " (default: $default): "
        else
            echo -n ": "
        fi
        read user_input
    fi
    
    if [[ -z "$user_input" && -n "$default" ]]; then
        echo "$default"
    else
        echo "$user_input"
    fi
}

generate_secret_key() {
    if command -v openssl &> /dev/null; then
        openssl rand -hex 32
    elif command -v python3 &> /dev/null; then
        python3 -c "import secrets; print(secrets.token_hex(32))"
    else
        # Fallback to urandom
        head -c 32 /dev/urandom | xxd -p -c 32
    fi
}

validate_api_key() {
    local key="$1"
    local service="$2"
    
    # Basic validation - just check if key is not empty and has reasonable length
    if [[ -z "$key" ]]; then
        log_error "$service API key is empty"
        return 1
    fi
    
    if [[ ${#key} -lt 10 ]]; then
        log_warning "$service API key seems too short (${#key} characters)"
        return 1
    fi
    
    # Service-specific basic checks (more lenient)
    case "$service" in
        "deepgram")
            if [[ ${#key} -lt 20 ]]; then
                log_warning "Deepgram API key seems short, but proceeding"
            fi
            ;;
        "openai")
            if [[ ! "$key" =~ ^sk- ]]; then
                log_warning "OpenAI API key should start with 'sk-', but proceeding"
            fi
            ;;
        "cartesia")
            if [[ ${#key} -lt 20 ]]; then
                log_warning "Cartesia API key seems short, but proceeding"
            fi
            ;;
        "livekit")
            if [[ ${#key} -lt 15 ]]; then
                log_warning "LiveKit API key seems short, but proceeding"
            fi
            ;;
    esac
    
    log_info "$service API key format looks acceptable"
    return 0
}

setup_environment_file() {
    log_info "Setting up production environment file..."
    
    # Check if .env file exists and use it as .env.production
    if [[ -f ".env" && ! -f "$ENV_FILE" ]]; then
        log_info "Found existing .env file, copying to .env.production"
        cp ".env" "$ENV_FILE"
        log_success "Environment file created from existing .env"
        return 0
    fi
    
    # Backup existing file if it exists
    if [[ -f "$ENV_FILE" ]]; then
        cp "$ENV_FILE" "$ENV_FILE.backup.$(date +%Y%m%d_%H%M%S)"
        log_info "Backed up existing environment file"
    fi
    
    # Generate secret key
    log_info "Generating secure secret key..."
    SECRET_KEY=$(generate_secret_key)
    
    # Collect API keys
    echo
    log_info "Please provide your API keys. You can find these in your service dashboards:"
    echo "  - Deepgram: https://console.deepgram.com/project/[project-id]/overview"
    echo "  - OpenAI: https://platform.openai.com/api-keys"
    echo "  - Cartesia: https://play.cartesia.ai/console"
    echo "  - LiveKit: https://cloud.livekit.io/projects/[project]/settings/keys"
    echo
    
    DEEPGRAM_API_KEY=$(prompt_user "Deepgram API Key" "" "true")
    while [[ -z "$DEEPGRAM_API_KEY" ]]; do
        log_error "Deepgram API key is required"
        DEEPGRAM_API_KEY=$(prompt_user "Deepgram API Key" "" "true")
    done
    validate_api_key "$DEEPGRAM_API_KEY" "deepgram"
    
    OPENAI_API_KEY=$(prompt_user "OpenAI API Key" "" "true")
    while [[ -z "$OPENAI_API_KEY" ]]; do
        log_error "OpenAI API key is required"
        OPENAI_API_KEY=$(prompt_user "OpenAI API Key" "" "true")
    done
    validate_api_key "$OPENAI_API_KEY" "openai"
    
    CARTESIA_API_KEY=$(prompt_user "Cartesia API Key" "" "true")
    while [[ -z "$CARTESIA_API_KEY" ]]; do
        log_error "Cartesia API key is required"
        CARTESIA_API_KEY=$(prompt_user "Cartesia API Key" "" "true")
    done
    validate_api_key "$CARTESIA_API_KEY" "cartesia"
    
    # LiveKit configuration
    echo
    log_info "LiveKit configuration:"
    LIVEKIT_URL=$(prompt_user "LiveKit Server URL" "wss://your-livekit-server.com")
    LIVEKIT_API_KEY=$(prompt_user "LiveKit API Key" "" "true")
    while [[ -z "$LIVEKIT_API_KEY" ]]; do
        log_error "LiveKit API key is required"
        LIVEKIT_API_KEY=$(prompt_user "LiveKit API Key" "" "true")
    done
    validate_api_key "$LIVEKIT_API_KEY" "livekit"
    
    LIVEKIT_API_SECRET=$(prompt_user "LiveKit API Secret" "" "true")
    while [[ -z "$LIVEKIT_API_SECRET" ]]; do
        log_error "LiveKit API secret is required"
        LIVEKIT_API_SECRET=$(prompt_user "LiveKit API Secret" "" "true")
    done
    
    # SIP configuration
    echo
    log_info "SIP configuration (for phone connectivity):"
    SIP_TRUNK_URI=$(prompt_user "SIP Trunk URI" "sip:your-sip-provider.com")
    SIP_USERNAME=$(prompt_user "SIP Username" "")
    SIP_PASSWORD=$(prompt_user "SIP Password" "" "true")
    
    # Performance settings
    echo
    log_info "Performance settings:"
    MAX_CONCURRENT_CALLS=$(prompt_user "Maximum concurrent calls" "50")
    RESPONSE_TIMEOUT=$(prompt_user "Response timeout (seconds)" "10.0")
    
    # Create environment file
    cat > "$ENV_FILE" << EOF
# Production Environment Configuration for Voice AI Agent
# Generated on $(date)

# Environment
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO

# Security
SECRET_KEY=$SECRET_KEY

# AI Service API Keys
DEEPGRAM_API_KEY=$DEEPGRAM_API_KEY
OPENAI_API_KEY=$OPENAI_API_KEY
CARTESIA_API_KEY=$CARTESIA_API_KEY

# LiveKit Configuration
LIVEKIT_URL=$LIVEKIT_URL
LIVEKIT_API_KEY=$LIVEKIT_API_KEY
LIVEKIT_API_SECRET=$LIVEKIT_API_SECRET

# SIP Configuration
SIP_TRUNK_URI=$SIP_TRUNK_URI
SIP_USERNAME=$SIP_USERNAME
SIP_PASSWORD=$SIP_PASSWORD

# Database
DATABASE_URL=sqlite:///data/voice_ai_agent.db

# Performance Settings
MAX_CONCURRENT_CALLS=$MAX_CONCURRENT_CALLS
AUDIO_BUFFER_SIZE=4096
RESPONSE_TIMEOUT=$RESPONSE_TIMEOUT
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

# Security Settings
ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ORIGINS=http://localhost:3000,https://your-domain.com
RATE_LIMIT_PER_MINUTE=60

# AI Model Settings
DEEPGRAM_MODEL=nova-2
DEEPGRAM_LANGUAGE=en-US
OPENAI_MODEL=gpt-4-turbo
OPENAI_MAX_TOKENS=150
OPENAI_TEMPERATURE=0.7
CARTESIA_VOICE_ID=default

# Audio Settings
AUDIO_SAMPLE_RATE=16000
AUDIO_CHANNELS=1
AUDIO_BIT_DEPTH=16
EOF

    # Set secure permissions
    chmod 600 "$ENV_FILE"
    
    log_success "Production environment file created at $ENV_FILE"
    log_warning "Keep this file secure and never commit it to version control!"
}

test_api_connections() {
    log_info "Testing API connections..."
    
    # Source the environment file
    set -a
    source "$ENV_FILE"
    set +a
    
    # Test Deepgram
    log_info "Testing Deepgram connection..."
    if curl -s -H "Authorization: Token $DEEPGRAM_API_KEY" \
            "https://api.deepgram.com/v1/projects" > /dev/null; then
        log_success "Deepgram API connection successful"
    else
        log_error "Deepgram API connection failed"
    fi
    
    # Test OpenAI
    log_info "Testing OpenAI connection..."
    if curl -s -H "Authorization: Bearer $OPENAI_API_KEY" \
            "https://api.openai.com/v1/models" > /dev/null; then
        log_success "OpenAI API connection successful"
    else
        log_error "OpenAI API connection failed"
    fi
    
    # Test Cartesia (if endpoint is available)
    log_info "Testing Cartesia connection..."
    if curl -s -H "X-API-Key: $CARTESIA_API_KEY" \
            "https://api.cartesia.ai/voices" > /dev/null 2>&1; then
        log_success "Cartesia API connection successful"
    else
        log_warning "Cartesia API connection test skipped (endpoint may not be available)"
    fi
    
    log_info "API connection tests completed"
}

create_systemd_service() {
    log_info "Creating systemd service file..."
    
    local service_file="/tmp/voice-ai-agent.service"
    
    cat > "$service_file" << EOF
[Unit]
Description=Voice AI Agent
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$PROJECT_ROOT
ExecStart=/usr/bin/docker-compose -f docker-compose.prod.yml up -d
ExecStop=/usr/bin/docker-compose -f docker-compose.prod.yml down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF
    
    log_info "Systemd service file created at $service_file"
    log_info "To install it, run:"
    echo "  sudo cp $service_file /etc/systemd/system/"
    echo "  sudo systemctl daemon-reload"
    echo "  sudo systemctl enable voice-ai-agent"
    echo "  sudo systemctl start voice-ai-agent"
}

show_next_steps() {
    echo
    log_success "Production environment setup completed!"
    echo
    log_info "Next steps:"
    echo "1. Review the configuration in $ENV_FILE"
    echo "2. Start the system: ./scripts/deploy_production.sh start"
    echo "3. Check system status: ./scripts/deploy_production.sh status"
    echo "4. Run health checks: ./scripts/deploy_production.sh health"
    echo "5. Test with real calls: python3 scripts/test_real_calls.py"
    echo "6. Monitor the system at:"
    echo "   - Grafana: http://localhost:3000 (admin/admin)"
    echo "   - Prometheus: http://localhost:9090"
    echo "   - Health: http://localhost:8001/health"
    echo "   - Metrics: http://localhost:8000/metrics"
    echo
    log_warning "Important security notes:"
    echo "- Keep your .env.production file secure"
    echo "- Change default Grafana password"
    echo "- Configure firewall rules for production"
    echo "- Set up SSL/TLS certificates"
    echo "- Configure backup procedures"
}

# Main execution
main() {
    local command="${1:-setup}"
    
    case "$command" in
        "setup")
            log_info "Starting Voice AI Agent production environment setup..."
            setup_environment_file
            test_api_connections
            create_systemd_service
            show_next_steps
            ;;
        "test")
            if [[ ! -f "$ENV_FILE" ]]; then
                log_error "Environment file not found. Run setup first."
                exit 1
            fi
            test_api_connections
            ;;
        "help"|"-h"|"--help")
            echo "Usage: $0 [COMMAND]"
            echo
            echo "Commands:"
            echo "  setup     Set up production environment (default)"
            echo "  test      Test API connections"
            echo "  help      Show this help message"
            echo
            ;;
        *)
            log_error "Unknown command: $command"
            exit 1
            ;;
    esac
}

# Run main function
main "$@"