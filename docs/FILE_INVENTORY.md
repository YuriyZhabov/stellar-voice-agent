# Voice AI Agent - Complete File Inventory

## Overview

This document provides a comprehensive inventory of all files in the Voice AI Agent project, organized by category with descriptions of purpose and functionality.

## Table of Contents

1. [Source Code Files](#source-code-files)
2. [Configuration Files](#configuration-files)
3. [Documentation Files](#documentation-files)
4. [Test Files](#test-files)
5. [Scripts and Utilities](#scripts-and-utilities)
6. [Docker and Deployment](#docker-and-deployment)
7. [Monitoring and Observability](#monitoring-and-observability)
8. [Security Files](#security-files)
9. [Data and Database Files](#data-and-database-files)
10. [Build and Project Files](#build-and-project-files)
11. [Generated and Cache Files](#generated-and-cache-files)

## Source Code Files

### Core Application (`src/`)

| File | Purpose | Key Components |
|------|---------|----------------|
| `src/__init__.py` | Package initialization | Module exports |
| `src/main.py` | Application entry point | `VoiceAIAgent` class, lifecycle management |
| `src/orchestrator.py` | Call orchestration | `CallOrchestrator`, call lifecycle management |
| `src/config.py` | Configuration management | `Settings` class, environment validation |
| `src/config_loader.py` | Configuration loading utilities | Configuration validation, error handling |
| `src/health.py` | Health check system | System health monitoring, component checks |
| `src/metrics.py` | Metrics collection | Performance metrics, monitoring utilities |
| `src/security.py` | Security utilities | Input validation, key management |
| `src/security_monitor.py` | Security monitoring | Threat detection, security metrics |
| `src/logging_config.py` | Logging configuration | Structured logging, log formatting |
| `src/logging_config_production.py` | Production logging | Production-optimized logging |
| `src/livekit_integration.py` | LiveKit integration | SIP call handling, audio streaming |
| `src/webhooks.py` | Webhook handling | HTTP endpoints, event processing |
| `src/performance_optimizer.py` | Performance optimization | Resource management, optimization |

### Client Layer (`src/clients/`)

| File | Purpose | Key Components |
|------|---------|----------------|
| `src/clients/__init__.py` | Client package initialization | Client exports |
| `src/clients/base.py` | Base resilient client | `BaseResilientClient`, retry logic, circuit breaker |
| `src/clients/deepgram_stt.py` | Deepgram STT client | `DeepgramSTTClient`, streaming transcription |
| `src/clients/groq_llm.py` | Groq LLM client | `GroqLLMClient`, context management |
| `src/clients/cartesia_tts.py` | Cartesia TTS client | `CartesiaTTSClient`, audio synthesis |
| `src/clients/openai_llm.py` | OpenAI LLM client (legacy) | `OpenAILLMClient`, GPT integration |

### Conversation Management (`src/conversation/`)

| File | Purpose | Key Components |
|------|---------|----------------|
| `src/conversation/__init__.py` | Conversation package init | Package exports |
| `src/conversation/state_machine.py` | Conversation state machine | `ConversationStateMachine`, state transitions |
| `src/conversation/dialogue_manager.py` | Dialogue management | `DialogueManager`, conversation context |

### Database Layer (`src/database/`)

| File | Purpose | Key Components |
|------|---------|----------------|
| `src/database/__init__.py` | Database package init | Package exports |
| `src/database/connection.py` | Database connection management | `DatabaseManager`, connection pooling |
| `src/database/models.py` | SQLAlchemy models | Database schema, ORM models |
| `src/database/repository.py` | Data access layer | Repository pattern, CRUD operations |
| `src/database/migrations.py` | Database migrations | `MigrationManager`, schema versioning |
| `src/database/logging_integration.py` | Database logging | Conversation logging, data persistence |

### Monitoring (`src/monitoring/`)

| File | Purpose | Key Components |
|------|---------|----------------|
| `src/monitoring/__init__.py` | Monitoring package init | Package exports |
| `src/monitoring/health_monitor.py` | Health monitoring system | `HealthMonitor`, component health tracking |
| `src/monitoring/alerting.py` | Alert management | `AlertManager`, notification channels |
| `src/monitoring/metrics_exporter.py` | Metrics export | `MetricsExportManager`, Prometheus integration |
| `src/monitoring/dashboard.py` | Dashboard management | `DashboardManager`, data aggregation |

### Middleware (`src/middleware/`)

| File | Purpose | Key Components |
|------|---------|----------------|
| `src/middleware/__init__.py` | Middleware package init | Package exports |
| `src/middleware/security.py` | Security middleware | Request validation, CORS, rate limiting |

## Configuration Files

### Environment Configuration

| File | Purpose | Description |
|------|---------|-------------|
| `.env.template` | Environment template | Template with all required variables |
| `.env` | Development environment | Development-specific configuration |
| `.env.production` | Production environment | Production configuration |
| `.env.test` | Test environment | Testing configuration |
| `.env.secrets` | Secret variables | Sensitive configuration (gitignored) |

### Application Configuration

| File | Purpose | Description |
|------|---------|-------------|
| `config/__init__.py` | Config package init | Configuration package |
| `config/production.yaml` | Production config | Production-specific settings |
| `livekit-sip.yaml` | LiveKit SIP config | SIP integration configuration |

### Project Configuration

| File | Purpose | Description |
|------|---------|-------------|
| `pyproject.toml` | Python project config | Dependencies, build system, tools |
| `requirements.txt` | Python dependencies | Production dependencies |
| `.editorconfig` | Editor configuration | Code formatting standards |
| `.pre-commit-config.yaml` | Pre-commit hooks | Code quality automation |

## Documentation Files

### Main Documentation (`docs/`)

| File | Purpose | Description |
|------|---------|-------------|
| `docs/PROJECT_DOCUMENTATION.md` | Project overview | Comprehensive project documentation |
| `docs/API_REFERENCE.md` | API documentation | Complete API reference |
| `docs/MODULE_DOCUMENTATION.md` | Module documentation | Detailed module descriptions |
| `docs/DEVELOPER_ONBOARDING.md` | Developer guide | Onboarding and development guide |
| `docs/FILE_INVENTORY.md` | File inventory | This document - complete file listing |
| `docs/conversation_logging.md` | Conversation logging | Logging system documentation |
| `docs/conversation_state_machine.md` | State machine docs | State machine implementation |
| `docs/deployment_guide.md` | Deployment guide | Production deployment instructions |
| `docs/e2e_testing.md` | E2E testing guide | End-to-end testing documentation |
| `docs/monitoring_system.md` | Monitoring guide | Monitoring and observability |
| `docs/operational_runbook.md` | Operations guide | Production operations manual |
| `docs/production_deployment_guide.md` | Production deployment | Detailed production setup |
| `docs/sip_integration_setup.md` | SIP integration | SIP setup and configuration |

### Project Files

| File | Purpose | Description |
|------|---------|-------------|
| `README.md` | Project README | Main project documentation |
| `CONTRIBUTING.md` | Contribution guide | Guidelines for contributors |

### Generated Documentation

| File | Purpose | Description |
|------|---------|-------------|
| `COMPREHENSIVE_TEST_REPORT.md` | Test report | Comprehensive testing results |
| `CONFIG_TESTS_FIX_REPORT.md` | Config test report | Configuration testing results |
| `DATABASE_IMPLEMENTATION_SUMMARY.md` | Database summary | Database implementation details |
| `DEPLOYMENT_FIX_SUMMARY.md` | Deployment fixes | Deployment issue resolutions |
| `E2E_INTEGRATION_TESTS_IMPLEMENTATION_REPORT.md` | E2E test report | Integration testing results |
| `FINAL_TEST_REPORT.md` | Final test report | Complete testing summary |
| `MONITORING_IMPLEMENTATION_REPORT.md` | Monitoring report | Monitoring system implementation |
| `TASK_16_COMPLETION_SUMMARY.md` | Task 16 summary | Specific task completion report |
| `TASK_17_COMPLETION_SUMMARY.md` | Task 17 summary | Specific task completion report |
| `TASK_18_COMPLETION_SUMMARY.md` | Task 18 summary | Specific task completion report |
| `TASK_19_COMPLETION_SUMMARY.md` | Task 19 summary | Specific task completion report |
| `TEST_EXECUTION_SUMMARY.md` | Test execution | Test execution results |
| `TEST_STATUS_REPORT.md` | Test status | Current test status |
| `TEST_VALIDATION_REPORT.md` | Test validation | Test validation results |

## Test Files

### Test Structure (`tests/`)

| File | Purpose | Test Categories |
|------|---------|-----------------|
| `tests/__init__.py` | Test package init | Test utilities |
| `tests/test_config.py` | Configuration tests | Settings validation, environment loading |
| `tests/test_configuration.py` | Config validation tests | Configuration validation logic |
| `tests/test_health.py` | Health check tests | System health monitoring |
| `tests/test_base_client.py` | Base client tests | Resilient client functionality |
| `tests/test_orchestrator.py` | Orchestrator tests | Call orchestration logic |
| `tests/test_main_integration.py` | Main integration tests | Application lifecycle |
| `tests/test_metrics.py` | Metrics tests | Metrics collection and export |
| `tests/test_monitoring.py` | Monitoring tests | Health monitoring system |
| `tests/test_security.py` | Security tests | Security validation and protection |
| `tests/test_logging_config.py` | Logging tests | Logging configuration |
| `tests/test_e2e_integration.py` | E2E integration tests | End-to-end workflows |
| `tests/test_load_testing.py` | Load tests | Performance and scalability |
| `tests/test_performance_regression.py` | Performance tests | Performance regression testing |
| `tests/test_infrastructure.py` | Infrastructure tests | System infrastructure |

### Client Tests (`tests/test_clients/`)

| File | Purpose | Test Focus |
|------|---------|------------|
| `tests/test_clients/__init__.py` | Client test init | Test utilities |
| `tests/test_clients/test_deepgram_stt.py` | Deepgram STT tests | Speech-to-text functionality |
| `tests/test_clients/test_groq_llm.py` | Groq LLM tests | Language model integration |
| `tests/test_clients/test_cartesia_tts.py` | Cartesia TTS tests | Text-to-speech synthesis |
| `tests/test_clients/test_openai_llm.py` | OpenAI LLM tests | OpenAI integration (legacy) |

### Conversation Tests (`tests/test_conversation/`)

| File | Purpose | Test Focus |
|------|---------|------------|
| `tests/test_conversation/__init__.py` | Conversation test init | Test utilities |
| `tests/test_conversation/test_state_machine.py` | State machine tests | State transitions, validation |
| `tests/test_conversation/test_dialogue_manager.py` | Dialogue tests | Conversation management |

### Database Tests (`tests/test_database/`)

| File | Purpose | Test Focus |
|------|---------|------------|
| `tests/test_database/__init__.py` | Database test init | Test utilities |
| `tests/test_database/test_connection.py` | Connection tests | Database connectivity |
| `tests/test_database/test_models.py` | Model tests | ORM model validation |
| `tests/test_database/test_repository.py` | Repository tests | Data access layer |
| `tests/test_database/test_migrations.py` | Migration tests | Schema migrations |
| `tests/test_database/test_logging_integration.py` | Logging tests | Database logging |

## Scripts and Utilities

### Deployment Scripts (`scripts/`)

| File | Purpose | Functionality |
|------|---------|---------------|
| `scripts/deploy_production.sh` | Production deployment | Automated production deployment |
| `scripts/setup_production_env.sh` | Environment setup | Production environment initialization |
| `scripts/validate_deployment.py` | Deployment validation | Post-deployment testing |
| `scripts/start_production_system.sh` | System startup | Production system startup |
| `scripts/fix_production_deployment.sh` | Deployment fixes | Production deployment fixes |

### Monitoring Scripts

| File | Purpose | Functionality |
|------|---------|---------------|
| `scripts/health_monitor.py` | Health monitoring | Standalone health monitoring |
| `scripts/monitor_system.py` | System monitoring | System metrics collection |
| `scripts/deployment_health_check.py` | Deployment health | Post-deployment health validation |

### Utility Scripts

| File | Purpose | Functionality |
|------|---------|---------------|
| `scripts/backup.sh` | System backup | Database and configuration backup |
| `scripts/cleanup_system.sh` | System cleanup | Log rotation, cache cleanup |
| `scripts/init_system.py` | System initialization | Initial system setup |
| `scripts/comprehensive_file_audit.py` | File audit | Complete file system audit |
| `scripts/final_validation.py` | Final validation | Complete system validation |

### Diagnostic Scripts

| File | Purpose | Functionality |
|------|---------|---------------|
| `scripts/diagnose_sip_issue.py` | SIP diagnostics | SIP connectivity diagnosis |
| `scripts/test_real_call.py` | Call testing | Real call testing |
| `scripts/test_real_calls.py` | Multiple call testing | Concurrent call testing |
| `scripts/fix_cartesia_health_check.py` | Cartesia fixes | Cartesia health check fixes |
| `scripts/verify_cartesia_fix.py` | Cartesia verification | Cartesia fix verification |
| `scripts/apply_cartesia_fixes.py` | Cartesia patches | Apply Cartesia fixes |

### SSL and Security Scripts

| File | Purpose | Functionality |
|------|---------|---------------|
| `scripts/setup_ssl_certificates.sh` | SSL setup | SSL certificate configuration |

## Docker and Deployment

### Container Configuration

| File | Purpose | Description |
|------|---------|-------------|
| `Dockerfile` | Container definition | Main application container |
| `docker-compose.yml` | Development environment | Development stack orchestration |
| `docker-compose.prod.yml` | Production environment | Production stack orchestration |
| `docker-compose.prod.yml.backup` | Production backup | Backup of production config |

### Startup Scripts

| File | Purpose | Description |
|------|---------|-------------|
| `start.sh` | Application startup | Main application startup script |

## Monitoring and Observability

### Prometheus Configuration (`monitoring/prometheus/`)

| File | Purpose | Description |
|------|---------|-------------|
| `monitoring/prometheus/prometheus.yml` | Prometheus config | Main Prometheus configuration |
| `monitoring/prometheus/rules/voice-ai-agent.yml` | Alerting rules | Application-specific alerts |

### Grafana Configuration (`monitoring/grafana/`)

| File | Purpose | Description |
|------|---------|-------------|
| `monitoring/grafana/dashboards/voice-ai-agent.json` | Grafana dashboard | Application monitoring dashboard |
| `monitoring/grafana/datasources/prometheus.yml` | Data sources | Grafana data source configuration |

### Loki Configuration (`monitoring/loki/`)

| File | Purpose | Description |
|------|---------|-------------|
| `monitoring/loki/loki.yml` | Loki config | Log aggregation configuration |

### Metrics and Monitoring

| File | Purpose | Description |
|------|---------|-------------|
| `monitoring/prometheus.yml` | Prometheus config | Alternative Prometheus configuration |
| `metrics/metrics.json` | Metrics data | JSON metrics export |

## Security Files

### Security Configuration (`security/`)

| File | Purpose | Description |
|------|---------|-------------|
| `security/firewall_config.py` | Firewall configuration | Network security rules |
| `security/ssl_setup.py` | SSL configuration | TLS/SSL certificate management |
| `security/secrets_manager.py` | Secrets management | Credential management utilities |
| `security/security-audit-report.md` | Security audit | Security assessment results |
| `security/security-implementation-report.md` | Security implementation | Security feature implementation |

### System Security (`etc/`)

| File | Purpose | Description |
|------|---------|-------------|
| `etc/fail2ban/jail.local` | Fail2ban config | Intrusion prevention configuration |
| `etc/fail2ban/filter.d/sshd-aggressive.conf` | SSH protection | SSH brute force protection |
| `etc/ssh/sshd_config.d/security.conf` | SSH security | SSH daemon security configuration |

## Data and Database Files

### Database Files (`data/`)

| File | Purpose | Description |
|------|---------|-------------|
| `data/voice_ai.db` | Main database | SQLite production database |
| `data/example_voice_ai.db` | Example database | Sample database for testing |

### Redis Configuration (`redis/`)

| File | Purpose | Description |
|------|---------|-------------|
| `redis/redis.conf/` | Redis config | Redis server configuration |

## Build and Project Files

### Build Configuration

| File | Purpose | Description |
|------|---------|-------------|
| `Makefile` | Build automation | Development and build commands |
| `Makefile.backup` | Makefile backup | Backup of Makefile |

### Git Configuration

| File | Purpose | Description |
|------|---------|-------------|
| `.gitignore` | Git ignore rules | Files to exclude from version control |

### IDE Configuration

| File | Purpose | Description |
|------|---------|-------------|
| `.vscode/settings.json` | VS Code settings | IDE configuration |
| `.vscode/launch.json` | Debug configuration | Debugging setup |
| `.vscode/tasks.json` | Task configuration | IDE task automation |
| `.vscode/extensions.json` | Extension recommendations | Recommended VS Code extensions |

### CI/CD Configuration

| File | Purpose | Description |
|------|---------|-------------|
| `.github/workflows/ci.yml` | CI/CD pipeline | GitHub Actions workflow |

## Generated and Cache Files

### Test Coverage (`htmlcov/`)

| File | Purpose | Description |
|------|---------|-------------|
| `htmlcov/index.html` | Coverage report | HTML test coverage report |
| `htmlcov/*.html` | Module coverage | Individual module coverage reports |
| `htmlcov/style_*.css` | Coverage styles | CSS for coverage reports |
| `htmlcov/*.js` | Coverage scripts | JavaScript for coverage reports |

### Python Cache (`__pycache__/`)

| Directory | Purpose | Description |
|-----------|---------|-------------|
| `src/__pycache__/` | Source cache | Compiled Python bytecode |
| `tests/__pycache__/` | Test cache | Test bytecode cache |
| `scripts/__pycache__/` | Script cache | Script bytecode cache |
| `examples/__pycache__/` | Example cache | Example bytecode cache |

### Test Cache (`.pytest_cache/`)

| File | Purpose | Description |
|------|---------|-------------|
| `.pytest_cache/` | Pytest cache | Test execution cache |

### Coverage Data

| File | Purpose | Description |
|------|---------|-------------|
| `.coverage` | Coverage data | Test coverage database |

### Validation Results

| File | Purpose | Description |
|------|---------|-------------|
| `final_validation_results_*.json` | Validation results | System validation results |
| `sip_integration_test_results.json` | SIP test results | SIP integration test results |
| `sip_integration_verification_report.md` | SIP verification | SIP integration verification |
| `performance_baseline.json` | Performance baseline | Performance benchmarking data |

### Utility Files

| File | Purpose | Description |
|------|---------|-------------|
| `fix_sql_queries.py` | SQL fixes | Database query fixes |
| `health_check.py` | Health check utility | Standalone health check |
| `run_e2e_tests.py` | E2E test runner | End-to-end test execution |
| `test_sip_integration.py` | SIP integration test | SIP integration testing |

### Package Information (`voice_ai_agent.egg-info/`)

| File | Purpose | Description |
|------|---------|-------------|
| `voice_ai_agent.egg-info/PKG-INFO` | Package metadata | Python package information |
| `voice_ai_agent.egg-info/SOURCES.txt` | Source files | List of package source files |
| `voice_ai_agent.egg-info/requires.txt` | Requirements | Package dependencies |
| `voice_ai_agent.egg-info/entry_points.txt` | Entry points | Package entry points |
| `voice_ai_agent.egg-info/top_level.txt` | Top level modules | Package top-level modules |

### Examples (`examples/`)

| File | Purpose | Description |
|------|---------|-------------|
| `examples/conversation_logging_example.py` | Logging example | Conversation logging usage |
| `examples/conversation_state_machine_example.py` | State machine example | State machine usage |
| `examples/dialogue_manager_example.py` | Dialogue example | Dialogue manager usage |
| `examples/monitoring_example.py` | Monitoring example | Monitoring system usage |

### System Directories

| Directory | Purpose | Description |
|-----------|---------|-------------|
| `logs/` | Log files | Application log storage |
| `backups/` | Backup files | System backup storage |
| `venv/` | Virtual environment | Python virtual environment |
| `usr/local/bin/` | User binaries | User-installed binaries |
| `root/` | Root directory | Root user files |

## File Statistics

### Total File Count by Category

| Category | File Count | Description |
|----------|------------|-------------|
| Source Code | 45+ | Main application source files |
| Configuration | 15+ | Configuration and settings files |
| Documentation | 25+ | Project documentation |
| Tests | 30+ | Test files and test utilities |
| Scripts | 20+ | Deployment and utility scripts |
| Docker/Deploy | 5+ | Container and deployment files |
| Monitoring | 10+ | Monitoring and observability |
| Security | 8+ | Security configuration and tools |
| Generated | 50+ | Generated files, cache, reports |
| **Total** | **200+** | **Complete project files** |

### File Size Distribution

| Size Range | Count | Examples |
|------------|-------|----------|
| < 1KB | 50+ | `__init__.py`, config files |
| 1KB - 10KB | 80+ | Small modules, tests |
| 10KB - 50KB | 60+ | Main modules, documentation |
| 50KB+ | 10+ | Large modules, generated reports |

### Language Distribution

| Language | File Count | Percentage |
|----------|------------|------------|
| Python | 120+ | 60% |
| Markdown | 30+ | 15% |
| YAML/JSON | 20+ | 10% |
| Shell/Bash | 15+ | 7.5% |
| Other | 15+ | 7.5% |

---

*This file inventory provides a complete catalog of all files in the Voice AI Agent project. Each file is categorized and described to help developers understand the project structure and locate specific functionality.*