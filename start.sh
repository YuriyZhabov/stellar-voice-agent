#!/bin/bash
set -e

echo "🚀 Starting Voice AI Agent..."

# Set environment variables
export PYTHONPATH="$(pwd)"
export ENVIRONMENT="${ENVIRONMENT:-development}"

# Function to check if service is healthy
check_health() {
    echo "🏥 Checking system health..."
    python scripts/health_monitor.py --single
    return $?
}

# Function to wait for dependencies
wait_for_dependencies() {
    echo "⏳ Waiting for dependencies..."
    
    # Wait for Redis if running in Docker
    if [ "${ENVIRONMENT}" = "production" ] || [ "${ENVIRONMENT}" = "docker" ]; then
        echo "Waiting for Redis..."
        while ! nc -z redis 6379; do
            sleep 1
        done
        echo "✅ Redis is ready"
    fi
}

# Function to start the application
start_application() {
    echo "🎯 Starting Voice AI Agent application..."
    
    # Run initial health check
    if check_health; then
        echo "✅ Initial health check passed"
    else
        echo "⚠️  Initial health check failed, but continuing..."
    fi
    
    # Start the main application
    if [ "${ENVIRONMENT}" = "production" ]; then
        echo "Starting in production mode..."
        python -m src.main
    else
        echo "Starting in development mode..."
        python -m src.main
    fi
}

# Function to handle shutdown
cleanup() {
    echo "🛑 Shutting down Voice AI Agent..."
    # Kill any background processes
    jobs -p | xargs -r kill
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Main execution
main() {
    echo "Voice AI Agent Startup Script"
    echo "Environment: ${ENVIRONMENT}"
    echo "Python Path: ${PYTHONPATH}"
    echo ""
    
    # Wait for dependencies
    wait_for_dependencies
    
    # Start application
    start_application
}

# Run main function
main "$@"