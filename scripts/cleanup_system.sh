#!/bin/bash

# System cleanup script for Voice AI Agent
# This script stops and removes all containers, networks, and volumes

set -eo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DOCKER_COMPOSE_FILE="$PROJECT_ROOT/docker-compose.prod.yml"

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

print_banner() {
    echo -e "${BLUE}"
    echo "╔══════════════════════════════════════════════════════════════════════════════╗"
    echo "║                        Voice AI Agent System Cleanup                        ║"
    echo "║                     Stop and Remove All Components                          ║"
    echo "╚══════════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

stop_and_remove_containers() {
    log_info "Stopping and removing Docker containers..."
    
    # Stop and remove containers using docker-compose
    if [[ -f "$DOCKER_COMPOSE_FILE" ]]; then
        log_info "Using docker-compose to stop services..."
        if docker compose -f "$DOCKER_COMPOSE_FILE" ps -q 2>/dev/null | grep -q .; then
            docker compose -f "$DOCKER_COMPOSE_FILE" down --remove-orphans --volumes 2>/dev/null || true
            log_success "Docker Compose services stopped and removed"
        else
            log_info "No docker-compose services running"
        fi
    else
        log_warning "Docker Compose file not found: $DOCKER_COMPOSE_FILE"
    fi
    
    # Stop all Voice AI Agent related containers
    log_info "Stopping all Voice AI Agent containers..."
    
    local containers=(
        "voice-ai-agent-prod"
        "voice-ai-nginx" 
        "voice-ai-redis"
        "voice-ai-prometheus"
        "voice-ai-grafana"
        "voice-ai-loki"
        "voice-ai-promtail"
        "voice-ai-backup"
    )
    
    for container in "${containers[@]}"; do
        if docker ps -a --format '{{.Names}}' 2>/dev/null | grep -q "^${container}$"; then
            log_info "Stopping container: $container"
            docker stop "$container" 2>/dev/null || true
            log_info "Removing container: $container"
            docker rm "$container" 2>/dev/null || true
        fi
    done
    
    # Remove any containers with voice-ai prefix
    log_info "Removing any remaining voice-ai containers..."
    local voice_containers=$(docker ps -a --format '{{.Names}}' 2>/dev/null | grep '^voice-ai' || true)
    if [[ -n "$voice_containers" ]]; then
        echo "$voice_containers" | while read -r container; do
            if [[ -n "$container" ]]; then
                log_info "Stopping and removing: $container"
                docker stop "$container" 2>/dev/null || true
                docker rm "$container" 2>/dev/null || true
            fi
        done
    fi
    
    log_success "All containers stopped and removed"
}

remove_networks() {
    log_info "Removing Docker networks..."
    
    local networks=(
        "root_voice-ai-network"
        "voice-ai-network"
        "voice_ai_network"
    )
    
    for network in "${networks[@]}"; do
        if docker network ls --format '{{.Name}}' 2>/dev/null | grep -q "^${network}$"; then
            log_info "Removing network: $network"
            docker network rm "$network" 2>/dev/null || true
        fi
    done
    
    log_success "Networks removed"
}

remove_volumes() {
    log_info "Removing Docker volumes..."
    
    local volumes=(
        "root_redis_data"
        "root_prometheus_data"
        "root_grafana_data"
        "root_loki_data"
        "redis_data"
        "prometheus_data"
        "grafana_data"
        "loki_data"
    )
    
    for volume in "${volumes[@]}"; do
        if docker volume ls --format '{{.Name}}' 2>/dev/null | grep -q "^${volume}$"; then
            log_info "Removing volume: $volume"
            docker volume rm "$volume" 2>/dev/null || true
        fi
    done
    
    # Remove any volumes with voice-ai prefix
    local voice_volumes=$(docker volume ls --format '{{.Name}}' 2>/dev/null | grep 'voice.ai\|voice_ai' || true)
    if [[ -n "$voice_volumes" ]]; then
        echo "$voice_volumes" | while read -r volume; do
            if [[ -n "$volume" ]]; then
                log_info "Removing volume: $volume"
                docker volume rm "$volume" 2>/dev/null || true
            fi
        done
    fi
    
    log_success "Volumes removed"
}

remove_images() {
    log_info "Removing Docker images..."
    
    # Remove Voice AI Agent images
    local images=(
        "voice-ai-agent:latest"
        "voice-ai-agent:production"
        "voice-ai-agent-test:latest"
    )
    
    for image in "${images[@]}"; do
        if docker images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null | grep -q "^${image}$"; then
            log_info "Removing image: $image"
            docker rmi "$image" 2>/dev/null || true
        fi
    done
    
    # Remove any dangling images
    local dangling_images=$(docker images -qf dangling=true 2>/dev/null || true)
    if [[ -n "$dangling_images" ]]; then
        log_info "Removing dangling images..."
        echo "$dangling_images" | xargs docker rmi 2>/dev/null || true
    fi
    
    log_success "Images removed"
}

cleanup_processes() {
    log_info "Cleaning up background processes..."
    
    # Kill any background monitoring processes
    if [[ -f "$PROJECT_ROOT/monitor.pid" ]]; then
        local pid=$(cat "$PROJECT_ROOT/monitor.pid" 2>/dev/null || true)
        if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
            log_info "Stopping background monitor process (PID: $pid)"
            kill "$pid" 2>/dev/null || true
        fi
        rm -f "$PROJECT_ROOT/monitor.pid"
    fi
    
    # Kill any Python processes related to Voice AI Agent
    pkill -f "voice.*ai.*agent" 2>/dev/null || true
    pkill -f "monitor_system.py" 2>/dev/null || true
    pkill -f "test_real_calls.py" 2>/dev/null || true
    
    log_success "Background processes cleaned up"
}

cleanup_logs_and_data() {
    log_info "Cleaning up logs and temporary data..."
    
    # Clean up log files
    if [[ -d "$PROJECT_ROOT/logs" ]]; then
        log_info "Cleaning log directory..."
        rm -rf "$PROJECT_ROOT/logs"/*
    fi
    
    # Clean up temporary files
    rm -f "$PROJECT_ROOT"/*.log 2>/dev/null || true
    rm -f "$PROJECT_ROOT"/monitor.log 2>/dev/null || true
    rm -f "$PROJECT_ROOT"/call_test_*.md 2>/dev/null || true
    rm -f "$PROJECT_ROOT"/call_test_*.json 2>/dev/null || true
    rm -f "$PROJECT_ROOT"/metrics_export_*.json 2>/dev/null || true
    
    # Clean up test data
    if [[ -d "$PROJECT_ROOT/test_data" ]]; then
        log_info "Cleaning test data directory..."
        rm -rf "$PROJECT_ROOT/test_data"
    fi
    
    # Clean up backup files
    rm -f "$PROJECT_ROOT"/.env.production.backup.* 2>/dev/null || true
    
    log_success "Logs and temporary data cleaned up"
}

prune_docker_system() {
    log_info "Pruning Docker system..."
    
    # Remove unused containers, networks, images, and build cache
    docker system prune -f --volumes 2>/dev/null || true
    
    log_success "Docker system pruned"
}

show_cleanup_summary() {
    echo
    log_success "System cleanup completed!"
    echo
    log_info "Cleanup Summary:"
    echo "  ✅ All Voice AI Agent containers stopped and removed"
    echo "  ✅ Docker networks removed"
    echo "  ✅ Docker volumes removed"
    echo "  ✅ Docker images removed"
    echo "  ✅ Background processes terminated"
    echo "  ✅ Logs and temporary data cleaned"
    echo "  ✅ Docker system pruned"
    echo
    log_info "System Status:"
    
    # Show remaining containers
    local remaining_containers=$(docker ps -a --format '{{.Names}}' | grep -c 'voice' || echo "0")
    echo "  📦 Remaining voice-related containers: $remaining_containers"
    
    # Show remaining networks
    local remaining_networks=$(docker network ls --format '{{.Name}}' | grep -c 'voice' || echo "0")
    echo "  🌐 Remaining voice-related networks: $remaining_networks"
    
    # Show remaining volumes
    local remaining_volumes=$(docker volume ls --format '{{.Name}}' | grep -c 'voice\|redis\|prometheus\|grafana\|loki' || echo "0")
    echo "  💾 Remaining related volumes: $remaining_volumes"
    
    echo
    log_info "The system is now clean and ready for fresh deployment!"
}

force_cleanup() {
    log_warning "Performing force cleanup..."
    
    # Force stop all containers
    log_info "Force stopping all containers..."
    docker ps -q | xargs -r docker stop 2>/dev/null || true
    
    # Force remove all containers
    log_info "Force removing all containers..."
    docker ps -aq | xargs -r docker rm -f 2>/dev/null || true
    
    # Remove all networks except default ones
    log_info "Removing all custom networks..."
    docker network ls --format '{{.Name}}' | grep -v -E '^(bridge|host|none)$' | xargs -r docker network rm 2>/dev/null || true
    
    # Remove all volumes
    log_info "Removing all volumes..."
    docker volume ls -q | xargs -r docker volume rm -f 2>/dev/null || true
    
    # Remove all images
    log_info "Removing all images..."
    docker images -q | xargs -r docker rmi -f 2>/dev/null || true
    
    # System prune
    docker system prune -af --volumes 2>/dev/null || true
    
    log_warning "Force cleanup completed - ALL Docker resources removed!"
}

show_system_status() {
    log_info "Current system status:"
    echo
    
    # Show containers
    local containers=$(docker ps -a --filter "name=voice-ai" --format "table {{.Names}}\t{{.Status}}" 2>/dev/null || true)
    if [[ -n "$containers" && $(echo "$containers" | wc -l) -gt 1 ]]; then
        echo -e "${YELLOW}Voice AI containers:${NC}"
        echo "$containers"
    else
        echo -e "${GREEN}✅ No Voice AI containers found${NC}"
    fi
    echo
    
    # Show networks
    local networks=$(docker network ls --filter "name=voice-ai" --format "table {{.Name}}\t{{.Driver}}" 2>/dev/null || true)
    if [[ -n "$networks" && $(echo "$networks" | wc -l) -gt 1 ]]; then
        echo -e "${YELLOW}Voice AI networks:${NC}"
        echo "$networks"
    else
        echo -e "${GREEN}✅ No Voice AI networks found${NC}"
    fi
    echo
    
    # Show volumes
    local volumes=$(docker volume ls --filter "name=voice-ai" --format "table {{.Name}}\t{{.Driver}}" 2>/dev/null || true)
    if [[ -n "$volumes" && $(echo "$volumes" | wc -l) -gt 1 ]]; then
        echo -e "${YELLOW}Voice AI volumes:${NC}"
        echo "$volumes"
    else
        echo -e "${GREEN}✅ No Voice AI volumes found${NC}"
    fi
    echo
    
    # Show images
    local images=$(docker images --filter "reference=voice-ai-agent*" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}" 2>/dev/null || true)
    if [[ -n "$images" && $(echo "$images" | wc -l) -gt 1 ]]; then
        echo -e "${YELLOW}Voice AI images:${NC}"
        echo "$images"
    else
        echo -e "${GREEN}✅ No Voice AI images found${NC}"
    fi
    echo
    
    # Show disk usage
    echo -e "${BLUE}Docker disk usage:${NC}"
    docker system df 2>/dev/null || true
}

show_help() {
    echo "Usage: $0 [COMMAND]"
    echo
    echo "Commands:"
    echo "  clean     Standard cleanup - removes Voice AI Agent resources (default)"
    echo "  force     Force cleanup - removes ALL Docker resources"
    echo "  status    Show current system status"
    echo "  help      Show this help message"
    echo
    echo "Examples:"
    echo "  $0                    # Standard cleanup"
    echo "  $0 clean             # Standard cleanup"
    echo "  $0 force             # Force cleanup (removes everything)"
    echo "  $0 status            # Show system status"
    echo
    echo "Standard cleanup removes only Voice AI Agent related resources."
    echo "Force cleanup removes ALL Docker containers, networks, volumes, and images."
    echo
}

# Main execution
main() {
    local mode="${1:-clean}"
    
    case "$mode" in
        "clean")
            print_banner
            log_info "Starting standard system cleanup..."
            
            stop_and_remove_containers
            remove_networks
            remove_volumes
            remove_images
            cleanup_processes
            cleanup_logs_and_data
            prune_docker_system
            show_cleanup_summary
            ;;
        "force")
            print_banner
            log_warning "Starting FORCE cleanup - this will remove ALL Docker resources!"
            
            # Check if running in non-interactive mode
            if [[ ! -t 0 ]]; then
                log_warning "Running in non-interactive mode - proceeding with force cleanup"
                force_cleanup
                cleanup_processes
                cleanup_logs_and_data
                log_success "Force cleanup completed!"
            else
                echo -n -e "${RED}Are you sure you want to continue? This will remove ALL containers, networks, volumes, and images! (y/N): ${NC}"
                read -r response
                
                if [[ "$response" =~ ^[Yy]$ ]]; then
                    force_cleanup
                    cleanup_processes
                    cleanup_logs_and_data
                    log_success "Force cleanup completed!"
                else
                    log_info "Force cleanup cancelled."
                fi
            fi
            ;;
        "status")
            show_system_status
            ;;
        "help"|"-h"|"--help")
            show_help
            ;;
        *)
            log_error "Unknown command: $mode"
            show_help
            exit 1
            ;;
    esac
}

# Handle script interruption
cleanup_on_interrupt() {
    echo
    log_warning "Cleanup interrupted by user"
    exit 130
}

trap cleanup_on_interrupt INT TERM

# Run main function
main "$@"