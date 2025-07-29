.PHONY: help setup test lint format run stop clean health install-dev docker-build docker-up docker-down

# Default target
help: ## Show this help message
	@echo "Voice AI Agent - Available Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Development setup
setup: ## Set up development environment (idempotent)
	@echo "Setting up development environment..."
	@python3 -m pip install --upgrade pip
	@pip3 install -e ".[dev]"
	@pre-commit install --install-hooks
	@echo "✅ Development environment ready"

install-dev: setup ## Alias for setup

# Code quality
lint: ## Run linting checks
	@echo "Running linting checks..."
	@python3 -m ruff check .
	@python3 -m mypy src/
	@echo "✅ Linting passed"

format: ## Format code with black and ruff
	@echo "Formatting code..."
	@python3 -m black .
	@python3 -m ruff check --fix .
	@echo "✅ Code formatted"

format-check: ## Check code formatting without making changes
	@echo "Checking code formatting..."
	@python3 -m black --check .
	@python3 -m ruff check .
	@echo "✅ Code formatting is correct"

# Testing
test: ## Run all tests
	@echo "Running tests..."
	@python3 -m pytest
	@echo "✅ All tests passed"

test-unit: ## Run unit tests only
	@echo "Running unit tests..."
	@python3 -m pytest -m "unit"
	@echo "✅ Unit tests passed"

test-integration: ## Run integration tests only
	@echo "Running integration tests..."
	@python3 -m pytest -m "integration"
	@echo "✅ Integration tests passed"

test-coverage: ## Run tests with coverage report
	@echo "Running tests with coverage..."
	@python3 -m pytest --cov=src --cov-report=html --cov-report=term
	@echo "✅ Coverage report generated in htmlcov/"

# Application lifecycle
run: ## Start the voice AI agent
	@echo "Starting Voice AI Agent..."
	@if [ ! -f .env ]; then echo "⚠️  .env file not found. Copy .env.template and configure it."; exit 1; fi
	@python3 -m src.main

test-init: ## Test application initialization without running main loop
	@echo "Testing Voice AI Agent initialization..."
	@if [ ! -f .env ]; then echo "⚠️  .env file not found. Copy .env.template and configure it."; exit 1; fi
	@python3 -m src.main --test-init

run-dev: ## Start the application in development mode
	@echo "Starting Voice AI Agent in development mode..."
	@if [ ! -f .env ]; then echo "⚠️  .env file not found. Copy .env.template and configure it."; exit 1; fi
	@python3 -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

stop: ## Stop the voice AI agent (if running in background)
	@echo "Stopping Voice AI Agent..."
	@pkill -f "python3 -m src.main" || echo "No running instance found"
	@pkill -f "uvicorn src.main:app" || echo "No running uvicorn instance found"
	@echo "✅ Application stopped"

health: ## Check application health
	@echo "Checking application health..."
	@python3 -c "import sys; sys.path.append('.'); from src.health import check_health; check_health()" || echo "❌ Health check failed"

# Docker operations
docker-build: ## Build Docker image
	@echo "Building Docker image..."
	@docker build -t voice-ai-agent:latest .
	@echo "✅ Docker image built"

docker-up: ## Start application with Docker Compose
	@echo "Starting application with Docker Compose..."
	@docker compose up -d
	@echo "✅ Application started with Docker"

docker-down: ## Stop Docker Compose services
	@echo "Stopping Docker Compose services..."
	@docker compose down
	@echo "✅ Docker services stopped"

docker-logs: ## View Docker logs
	@docker compose logs -f

# Cleanup
clean: ## Clean up temporary files and caches
	@echo "Cleaning up..."
	@find . -type f -name "*.pyc" -delete
	@find . -type d -name "__pycache__" -delete
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf build/ dist/ .coverage htmlcov/ .pytest_cache/ .mypy_cache/ .ruff_cache/
	@docker system prune -f 2>/dev/null || true
	@echo "✅ Cleanup completed"

clean-all: clean ## Clean everything including Docker images
	@echo "Deep cleaning..."
	@docker rmi voice-ai-agent:latest 2>/dev/null || true
	@docker volume prune -f 2>/dev/null || true
	@echo "✅ Deep cleanup completed"

# Database operations
db-upgrade: ## Run database migrations
	@echo "Running database migrations..."
	@python3 -m alembic upgrade head
	@echo "✅ Database upgraded"

db-downgrade: ## Rollback database migration
	@echo "Rolling back database migration..."
	@python3 -m alembic downgrade -1
	@echo "✅ Database downgraded"

# Pre-commit hooks
pre-commit: ## Run pre-commit hooks on all files
	@echo "Running pre-commit hooks..."
	@python3 -m pre_commit run --all-files
	@echo "✅ Pre-commit hooks completed"

# Development utilities
shell: ## Start Python shell with application context
	@python3 -c "import sys; sys.path.append('.'); from src import *; print('Voice AI Agent shell ready')"

# Validation
validate: lint test ## Run all validation checks (lint + test)
	@echo "✅ All validation checks passed"

# CI/CD simulation
ci: format-check lint test ## Simulate CI pipeline locally
	@echo "✅ CI pipeline simulation completed successfully"