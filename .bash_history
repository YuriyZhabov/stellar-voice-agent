whoami
ufw --version
which fail2ban-server
apt update
apt install -y fail2ban
ufw status
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
ufw status verbose
systemctl enable fail2ban
systemctl start fail2ban
systemctl status fail2ban
fail2ban-client status
fail2ban-client status sshd
cp /etc/ssh/sshd_config /etc/ssh/sshd_config.backup
cat /etc/ssh/sshd_config | grep -E "^(PermitRootLogin|PasswordAuthentication|PubkeyAuthentication|MaxAuthTries|ClientAliveInterval|ClientAliveCountMax)"
sshd -t
systemctl reload sshd
systemctl reload ssh
ufw logging on
chmod +x /usr/local/bin/security-status.sh
chmod +x /root/usr/local/bin/security-status.sh
/root/usr/local/bin/security-status.sh
apt install -y net-tools
/root/usr/local/bin/security-status.sh
apt update
apt list --upgradable
apt upgrade -y
apt upgrade -y --fix-missing
apt list --upgradable
uname -r
systemctl status ssh
systemctl status fail2ban
ssh -V
systemctl --version
/root/usr/local/bin/security-status.sh
apt autoremove -y
apt autoclean
apt-get remove docker-compose
uname -r
uname -a
ls -la /boot/vmlinuz*
dpkg -l | grep linux-image
find . -type f -name "*.py" | head -10
python -m src.main
python3 -m src.main
python3 -c "import sys; sys.path.append('.'); from src.health import check_health; check_health()"
make help
apt update && apt install -y make
make help
make health
make run
make help | head -20
python3 -m src.health
python3 -m pytest tests/test_infrastructure.py -v
pip3 install pytest
apt install -y python3-pip
pip3 install pytest psutil
apt install -y python3-pytest python3-psutil
python3 -m src.health
python3 -m pytest tests/test_infrastructure.py -v
python3 -c "import tomllib; f=open('pyproject.toml','rb'); tomllib.load(f); print('✅ pyproject.toml syntax is valid')"
python3 -m pytest tests/test_infrastructure.py -v
pip3 install pytest-cov
apt install python3-pytest-cov
python3 -m pytest tests/test_infrastructure.py -v
apt install python3-pytest-asyncio
python3 -m pytest tests/test_infrastructure.py -v
apt update
apt install -y docker.io docker-compose
systemctl start docker
systemctl enable docker
docker --version
docker-compose --version
python3 -m pytest tests/test_infrastructure.py::test_docker_build -v
apt autoremove
apt-get update
apt-get install docker-compose-plugin
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt-get update
apt-get install docker-compose-plugin
docker compose version
python3 -m pytest tests/test_infrastructure.py::test_docker_build -v
make health
make test
make docker-build
head -10 .gitignore
python3 -c "from src.health import check_health; print('Health check works:', check_health()['status'])"
make test
make health
python3 -m pytest tests/test_config.py -v
apt install python3-pydantic
apt remove python3-pydantic python3-typing-extensions
pip3 install -e .
python3 -m venv venv
apt install python3.12-venv python3-full
python3 -m venv venv
source venv/bin/activate && pip install --upgrade pip
source venv/bin/activate && pip install -e ".[dev]"
apt install -y portaudio19-dev python3-dev
source venv/bin/activate && pip install -e ".[dev]"
source venv/bin/activate && python -m pytest tests/test_config.py -v
source venv/bin/activate && python -m pytest tests/test_config.py::TestSettings::test_default_settings -v
tail -10 src/config_loader.py
source venv/bin/activate && python -c "from src.config import Settings; print('Config import works')"
source venv/bin/activate && python -m pytest tests/test_config.py::TestSettings::test_default_settings -v
source venv/bin/activate && python -m src.main
source venv/bin/activate && python -m src.main --test-init
make test-init
git status
git init
git config user.name "Voice AI Agent Developer"
git config user.email "developer@voiceai.agent"
git branch -m main
git add .
git status
git add .
git commit -m "feat: implement base resilient client infrastructure

- Add BaseResilientClient with retry logic and circuit breaker
- Implement exponential backoff with jitter support
- Add centralized logging with JSON format and correlation IDs
- Create metrics collection system for monitoring
- Add comprehensive test suite for all components
- Update configuration to support logging settings
- Integrate logging system into main application

Task 4 completed: Base resilient client infrastructure ready"
python -m pytest tests/test_base_client.py -v
python -m pytest tests/ -v
python -m pytest tests/ -v --tb=short
python -m py_compile src/clients/base.py
python -m py_compile src/logging_config.py
python -m py_compile src/metrics.py
python -m pytest tests/ -v
python -m pytest tests/test_config.py::TestSettings::test_production_requirements_validation -v
python -m pytest tests/test_config.py::TestSettings::test_production_requirements_validation tests/test_config.py::TestConfigLoader::test_load_with_fallbacks_from_env tests/test_config.py::TestConfigLoader::test_validate_required_for_environment tests/test_config.py::TestConfigurationErrors::test_missing_required_production_config tests/test_config.py::TestEdgeCases::test_empty_string_values -v
python -m pytest tests/test_config.py::TestSettings::test_production_requirements_validation tests/test_config.py::TestConfigLoader::test_validate_required_for_environment tests/test_config.py::TestEdgeCases::test_empty_string_values -v
python -m pytest tests/test_config.py::TestSettings::test_production_requirements_validation tests/test_config.py::TestConfigLoader::test_validate_required_for_environment -v
python -m pytest tests/test_config.py::TestConfigLoader::test_validate_required_for_environment -v
python -m pytest tests/ -v --tb=short
python3 -m venv venv
https://github.com/astral-sh/ruff.git
pip install ruff
python3 -m venv venv
source venv/bin/activate && pip install ruff
source venv/bin/activate && python -m pytest tests/test_metrics.py -v
ps aux | grep pytest
source venv/bin/activate && python -m pytest tests/test_metrics.py::TestMetricsCollector::test_percentile_calculation -v
python -m pytest tests/test_metrics.py -v
python -m pytest tests/test_clients/test_openai_llm.py::TestMessage::test_message_creation -v
python -m pytest tests/test_metrics.py -v
python -m pytest tests/test_base_client.py -v
python3 -m pytest tests/test_base_client.py -v
pip install -e ".[dev]"
source venv/bin/activate && pip install -e ".[dev]"
python3 -m pytest tests/test_base_client.py -v
python -m pytest tests/test_clients/test_deepgram_stt.py -v
python -m pytest tests/test_clients/test_deepgram_stt.py::TestDeepgramSTTClient::test_transcribe_stream_max_reconnections_exceeded -v
python -m pytest tests/test_clients/test_deepgram_stt.py -v
python -m pytest tests/test_base_client.py -v
python -c "from src.clients.deepgram_stt import DeepgramSTTClient, TranscriptionResult, StreamingConfig; print('Import successful')"
python -m pytest tests/test_clients/test_openai_llm.py -v
python -c "from openai.types.chat import ChatCompletion; print(dir(ChatCompletion))"
python -c "from openai.types.chat import ChatCompletion; print(ChatCompletion.__annotations__)"
cd
mkdir -p security
mv security-audit-report.md security/
mv security-fixes.py security/
python -m pytest tests/ -v --tb=short
python3 -m pytest tests/ -v --tb=short
python3 -m py_compile src/security.py
pip install httpx pydantic pydantic-settings websockets openai deepgram-sdk
pip install --break-system-packages httpx pydantic pydantic-settings websockets openai deepgram-sdk
python3 -m venv venv
source venv/bin/activate && pip install httpx pydantic pydantic-settings websockets openai deepgram-sdk
source venv/bin/activate && python -m pytest tests/ -v --tb=short
source venv/bin/activate && python -m pytest tests/test_security.py -v
source venv/bin/activate && python -m pytest tests/test_security.py::TestAPIKeyValidation::test_validate_livekit_api_key_valid -v
source venv/bin/activate && python -m pytest tests/test_security.py::TestLogDataSanitization::test_sanitize_string_with_api_key -v
source venv/bin/activate && python -m pytest tests/test_security.py -v
source venv/bin/activate && python -c "
from src.security import generate_secret_key, validate_api_key, validate_audio_data, APIKeyType
from src.middleware.security import create_security_middleware
from src.logging_config import setup_logging
from src.config import Settings, Environment

print('🔐 Testing security components...')

# Test secret key generation
key = generate_secret_key()
print(f'✅ Generated secure secret key: {key[:8]}...{key[-8:]}')

# Test API key validation
openai_key = 'sk-proj-abcdefghijklmnopqrstuvwxyz1234567890'
result = validate_api_key(openai_key, APIKeyType.OPENAI)
print(f'✅ API key validation: {result.is_valid} ({result.key_type})')

# Test audio validation
test_audio = b'RIFF' + b'\\x00' * 100 + b'test audio data' * 10
audio_result = validate_audio_data(test_audio)
print(f'✅ Audio validation: {audio_result.is_valid} (format: {audio_result.detected_format})')

# Test security middleware
middleware = create_security_middleware(rate_limit_per_minute=100)
stats = middleware.get_rate_limit_stats()
print(f'✅ Security middleware initialized: {stats}')

# Test configuration with security
try:
    settings = Settings(environment=Environment.TESTING)
    print(f'✅ Configuration loaded successfully for {settings.environment}')
except Exception as e:
    print(f'❌ Configuration error: {e}')

print('🎉 All security components working correctly!')
"
python -m pytest tests/test_clients/test_openai_llm.py -v
python -m pytest tests/ -x --tb=short
python -m pytest tests/test_clients/test_cartesia_tts.py -v
python -m pytest tests/test_clients/test_cartesia_tts.py::TestCartesiaTTSClient::test_initialization -v
python -m pytest tests/test_clients/test_cartesia_tts.py -v
python -c "import src.clients.cartesia_tts"
python -m pytest tests/test_clients/test_cartesia_tts.py -v
python -m pytest tests/test_clients/test_cartesia_tts.py::TestCartesiaTTSClient::test_synthesize_batch_success -v
python -m pytest tests/test_clients/test_cartesia_tts.py::TestCartesiaTTSClient::test_health_check_success -v
python -m pytest tests/test_clients/test_cartesia_tts.py::TestResiliencePatterns::test_retry_on_failure -v
python -m pytest tests/test_clients/test_cartesia_tts.py -v
продолжай
python -m pytest tests/test_conversation/test_state_machine.py -v
python examples/conversation_state_machine_example.py
python -m pytest tests/test_conversation/ -v
git add .
git commit -m "feat: implement conversation state machine for voice AI agent

- Add ConversationState enum with LISTENING, PROCESSING, SPEAKING states
- Implement ConversationStateMachine with state transition validation
- Add state duration tracking and transition history logging
- Include state handlers and transition callbacks for extensibility
- Implement error recovery mechanisms with force transitions
- Add comprehensive metrics collection and monitoring
- Ensure thread safety with async locks for concurrent access
- Create 27 unit tests covering all functionality and edge cases
- Add detailed documentation with integration examples
- Include working example demonstrating all features

Requirements: 1.1, 1.5, 6.1"
git status
git remote -v
git log --oneline -5
git remote add origin https://github.com/username/voice-ai-agent.git
git push -u origin main
git remote remove origin
git remote add origin https://github.com/YuriyZhabov/stellar-voice-agent.git
git remote -v
git push -u origin main
git status
find . -name ".kiro*" -type d
find . -name ".docker" -type d
git rm -r --cached .kiro-server/
git rm -r --cached .docker/
git status
git add .gitignore
git commit -m "chore: update .gitignore to exclude Kiro IDE files

- Add .kiro-server/ and .docker/ to gitignore
- Remove already tracked Kiro IDE files from repository
- Clean up repository to exclude IDE-specific files from version control"
git push
python -m pytest tests/test_conversation/test_dialogue_manager.py -v
python -m pytest tests/test_conversation/ -v
python examples/dialogue_manager_example.py
python -m pytest tests/test_conversation/ tests/test_clients/test_openai_llm.py -v --tb=short
python -m pytest tests/test_orchestrator.py -v --tb=short
python -c "import tests.test_orchestrator; print('Import successful')"
python -m pytest tests/test_orchestrator.py --collect-only
python -m pytest tests/test_orchestrator.py::TestCallOrchestrator::test_initialization -v
python -m pytest tests/test_orchestrator.py::TestCallOrchestrator::test_handle_call_start_success -v
python -m pytest tests/test_orchestrator.py -v --tb=short
python -m pytest tests/test_orchestrator.py::TestCallOrchestrator::test_handle_audio_received -v
python -m pytest tests/test_orchestrator.py -v
python -m pytest tests/test_conversation/ -v
python -m pytest tests/test_clients/ -v --tb=short
python -m pytest tests/test_clients/test_deepgram_stt.py::TestDeepgramSTTClient::test_transcribe_batch_success -v
python -m pytest tests/test_clients/test_deepgram_stt.py::TestDeepgramSTTClient::test_transcribe_batch_success tests/test_clients/test_deepgram_stt.py::TestDeepgramSTTClient::test_transcribe_batch_with_options tests/test_clients/test_deepgram_stt.py::TestDeepgramSTTClient::test_transcribe_batch_failure -v
python -m pytest tests/test_clients/ -v --tb=short
python -m pytest tests/test_orchestrator.py -v
git add .
git commit -m "feat: implement CallOrchestrator with comprehensive testing

- Add CallOrchestrator class for managing call lifecycle and component interactions
- Implement LiveKit event handling for call start, audio received, and call end events
- Add audio stream management with proper buffering and processing
- Create error handling and recovery mechanisms for service failures
- Implement metrics collection for call duration, latency, and success rates
- Add comprehensive unit tests covering all orchestrator functionality
- Support concurrent call handling with configurable limits
- Include health status monitoring and component health checks
- Implement event handler system for extensibility
- Add proper resource cleanup and connection management

Requirements covered: 1.1, 1.5, 2.1, 2.2, 4.3"
git status
python -m pytest tests/test_database/test_models.py -v
python -m pytest tests/test_database/test_models.py::TestCallModel::test_call_with_metadata -v
python -m pytest tests/test_database/ -v --tb=short
python fix_sql_queries.py
python -m pytest tests/test_database/test_models.py -v
python -m pytest tests/test_database/test_connection.py::TestDatabaseManager::test_initialization -v
find . -name "*.py" -type f | grep -E "(src/|tests/)" | head -20
find . -name "*.py" -type f | grep -E "(src/|tests/)" | wc -l
python -m pytest tests/ -v --tb=short --maxfail=10
python -m pytest tests/test_database/ -v --tb=short
python -m pytest tests/test_database/test_models.py -v
python -m pytest tests/test_clients/ -v --tb=short
find . -name "*.py" -type f | grep -E "(src/|tests/)" | head -30
find . -name "*.py" -type f -not -path "./venv/*" -not -path "./.pytest_cache/*" | sort
find . -name "*.py" -type f -not -path "./venv/*" -not -path "./.pytest_cache/*" -not -path "./.kiro-server/*" | sort
python -m py_compile $(find . -name "*.py" -type f -not -path "./venv/*" -not -path "./.pytest_cache/*" -not -path "./.kiro-server/*" | head -20)
python -m py_compile $(find . -name "*.py" -type f -not -path "./venv/*" -not -path "./.pytest_cache/*" -not -path "./.kiro-server/*" | tail -30)
python -c "
import py_compile
import sys
import os

files = [
    './config/__init__.py',
    './examples/conversation_state_machine_example.py',
    './examples/dialogue_manager_example.py',
    './fix_sql_queries.py',
    './src/clients/base.py',
    './src/clients/cartesia_tts.py',
    './src/clients/deepgram_stt.py',
    './src/clients/__init__.py',
    './src/clients/openai_llm.py',
    './src/config_loader.py',
    './src/config.py',
    './src/conversation/dialogue_manager.py',
    './src/conversation/__init__.py',
    './src/conversation/state_machine.py',
    './src/database/connection.py',
    './src/database/__init__.py',
    './src/database/logging_integration.py',
    './src/database/migrations.py',
    './src/database/models.py',
    './src/database/repository.py',
    './src/health.py',
    './src/__init__.py',
    './src/logging_config.py',
    './src/main.py',
    './src/metrics.py',
    './src/middleware/__init__.py',
    './src/middleware/security.py',
    './src/orchestrator.py',
    './src/security.py'
]

errors = []
for file in files:
    if os.path.exists(file):
        try:
            py_compile.compile(file, doraise=True)
            print(f'✅ {file}')
        except py_compile.PyCompileError as e:
            print(f'❌ {file}: {e}')
            errors.append(file)
    else:
        print(f'⚠️  {file}: File not found')

if errors:
    print(f'\n{len(errors)} files have syntax errors')
    sys.exit(1)
else:
    print(f'\nAll {len(files)} source files have valid syntax!')
"
python -c "
import py_compile
import sys
import os

test_files = [
    './tests/__init__.py',
    './tests/test_base_client.py',
    './tests/test_clients/__init__.py',
    './tests/test_clients/test_cartesia_tts.py',
    './tests/test_clients/test_deepgram_stt.py',
    './tests/test_clients/test_openai_llm.py',
    './tests/test_config.py',
    './tests/test_configuration.py',
    './tests/test_conversation/__init__.py',
    './tests/test_conversation/test_dialogue_manager.py',
    './tests/test_conversation/test_state_machine.py',
    './tests/test_database/__init__.py',
    './tests/test_database/test_connection.py',
    './tests/test_database/test_logging_integration.py',
    './tests/test_database/test_migrations.py',
    './tests/test_database/test_models.py',
    './tests/test_database/test_repository.py',
    './tests/test_health.py',
    './tests/test_infrastructure.py',
    './tests/test_logging_config.py',
    './tests/test_metrics.py',
    './tests/test_orchestrator.py',
    './tests/test_security.py'
]

errors = []
for file in test_files:
    if os.path.exists(file):
        try:
            py_compile.compile(file, doraise=True)
            print(f'✅ {file}')
        except py_compile.PyCompileError as e:
            print(f'❌ {file}: {e}')
            errors.append(file)
    else:
        print(f'⚠️  {file}: File not found')

if errors:
    print(f'\n{len(errors)} test files have syntax errors')
    sys.exit(1)
else:
    print(f'\nAll {len(test_files)} test files have valid syntax!')
"
python -c "
import importlib.util
import sys
import os

# Добавляем текущую директорию в Python path
sys.path.insert(0, '.')

def check_imports(file_path):
    '''Проверяет, можно ли импортировать модуль'''
    try:
        spec = importlib.util.spec_from_file_location('test_module', file_path)
        if spec is None:
            return False, 'Cannot create module spec'
        
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return True, 'OK'
    except Exception as e:
        return False, str(e)

# Проверяем основные модули
key_modules = [
    './src/config.py',
    './src/database/models.py',
    './src/database/connection.py',
    './src/database/repository.py',
    './src/database/migrations.py',
    './src/database/logging_integration.py',
    './src/clients/base.py',
    './src/security.py',
    './src/health.py'
]

print('🔍 Checking key module imports...')
errors = []

for module_path in key_modules:
    if os.path.exists(module_path):
        success, message = check_imports(module_path)
        if success:
            print(f'✅ {module_path}')
        else:
            print(f'❌ {module_path}: {message}')
            errors.append((module_path, message))
    else:
        print(f'⚠️  {module_path}: File not found')

if errors:
    print(f'\n❌ {len(errors)} modules have import issues:')
    for path, error in errors:
        print(f'  - {path}: {error}')
else:
    print(f'\n✅ All {len(key_modules)} key modules can be imported successfully!')
"
echo "📊 Project Structure Analysis"
echo "================================"
echo ""
echo "📁 Source files:"
find ./src -name "*.py" | wc -l
echo ""
echo "🧪 Test files:"
find ./tests -name "*.py" | wc -l
echo ""
echo "📋 Examples:"
find ./examples -name "*.py" | wc -l
echo ""
echo "🔧 Config files:"
find ./config -name "*.py" | wc -l
echo ""
echo "📊 Total Python files:"
find . -name "*.py" -not -path "./venv/*" -not -path "./.pytest_cache/*" -not -path "./.kiro-server/*" | wc -l
python -m pytest tests/ --tb=short -v --maxfail=5
python -m pytest tests/test_config.py::TestSettings::test_default_settings -v
python -m pytest tests/test_config.py::TestSettings::test_environment_validation -v
env | grep -E "(API|KEY|SECRET)" | head -10
env | grep -i livekit
python -m pytest tests/test_config.py::TestSettings::test_environment_validation -v
python -m pytest tests/test_config.py::TestSettings::test_port_validation -v
python -m pytest tests/test_config.py::TestSettings::test_ip_address_validation -v
python -m pytest tests/test_config.py::TestSettings::test_cors_origins_parsing -v
python -m pytest tests/test_config.py::TestSettings -v
python -m pytest tests/test_config.py::TestSettings::test_properties -v
python -m pytest tests/test_config.py::TestSettings -v
python -m pytest tests/test_config.py::TestSettings::test_production_requirements_validation -v
python -m pytest tests/test_config.py::TestSettings -v
python -m pytest tests/test_config.py -v
python -m pytest tests/test_config.py::TestConfigurationErrors::test_missing_required_production_config -v
python -m pytest tests/test_config.py -v
python -m pytest tests/test_config.py tests/test_security.py tests/test_health.py -v --tb=short
python -m pytest --tb=short -v
python -m py_compile tests/test_database/test_connection.py
python -m py_compile tests/test_database/test_migrations.py
python -m py_compile tests/test_database/test_models.py
python -m py_compile tests/test_database/test_repository.py
python -m py_compile tests/test_database/test_logging_integration.py
python -m pytest tests/test_database/ -v
python -m pytest tests/test_database/test_connection.py tests/test_database/test_migrations.py -v --tb=short
python -m pytest tests/test_database/test_repository.py::TestCallManagement::test_create_call -v
python -m pytest tests/test_database/test_repository.py::TestSystemEvents::test_log_system_event -v
python -m pytest tests/test_database/test_repository.py::TestCallManagement -v
python -m pytest tests/test_database/test_repository.py::TestSystemEvents -v
python -m pytest tests/test_database/test_repository.py::TestCallManagement::test_create_call tests/test_database/test_repository.py::TestSystemEvents::test_log_system_event -v
python -m pytest tests/test_database/test_repository.py::TestCallManagement::test_end_call -v
python -m pytest tests/test_database/test_repository.py::TestConversationManagement::test_end_conversation -v
python -m pytest tests/test_database/test_repository.py::TestCallManagement::test_end_call -v
python -m pytest tests/test_database/test_repository.py::TestConversationManagement::test_end_conversation -v
python -m pytest tests/test_database/test_repository.py::TestCallManagement::test_end_call tests/test_database/test_repository.py::TestConversationManagement::test_end_conversation -v
python -m pytest tests/test_database/test_repository.py -v
python -m pytest tests/test_database/test_repository.py::TestCallManagement::test_end_call tests/test_database/test_repository.py::TestConversationManagement::test_end_conversation -v
python -m pytest tests/test_database/test_repository.py::TestMetricsManagement::test_update_conversation_metrics -v
python -m pytest tests/test_database/test_repository.py::TestMetricsManagement -v
python -m pytest tests/test_database/test_repository.py::TestMetricsManagement::test_update_conversation_metrics -v --tb=short
python -m pytest tests/test_logging_config.py::TestJSONFormatter::test_basic_formatting -v
python -m pytest tests/test_logging_config.py -v
python -m pytest tests/test_database/test_logging_integration.py::TestGlobalConversationLogger::test_conversation_logger_integration -v
python -m pytest tests/test_database/test_logging_integration.py -v
python -m pytest tests/test_database/test_logging_integration.py::TestGlobalConversationLogger::test_conversation_logger_integration -v
python -m pytest tests/test_database/test_logging_integration.py -v
python -m pytest tests/test_logging_config.py tests/test_database/test_logging_integration.py -v
python -m pytest tests/test_database/test_migrations.py::TestMigrationManager::test_get_migration_status -v
python -m pytest tests/test_database/test_migrations.py::TestMigrationManager::test_migrate_to_latest -v
python -m pytest tests/test_database/test_migrations.py::TestMigrationIntegration::test_full_migration_cycle -v
python -m pytest tests/test_database/test_migrations.py::TestMigrationManager::test_create_tables_if_not_exist -v
python -m pytest tests/test_database/test_migrations.py::TestMigrationManager::test_migrate_to_latest -v
python -m pytest tests/test_database/test_migrations.py::TestMigrationManager::test_get_migration_status -v
python -m pytest tests/test_database/test_migrations.py::TestMigrationIntegration::test_full_migration_cycle -v
python -m pytest tests/test_database/test_migrations.py -v
python -m pytest tests/test_database/test_migrations.py::TestMigrationManager::test_apply_migration -v
python -m pytest tests/test_database/test_migrations.py::TestMigrationSQL::test_migration_001_sql -v
python -m pytest tests/test_logging_config.py -v
python -m pytest -v 2>&1 | grep -i "deprecation\|warning" | head -20
python -m pytest -v 2>&1 | grep -i "datetime.*deprecation\|utcnow.*deprecation"
python -m pytest tests/test_logging_config.py tests/test_database/test_repository.py::TestCallManagement::test_end_call -v
python -m pytest tests/test_conversation/test_dialogue_manager.py::TestDialogueManager::test_conversation_summary -v
python -m pytest tests/test_conversation/test_dialogue_manager.py --collect-only
python -m pytest tests/test_conversation/test_dialogue_manager.py::TestConversationSummary::test_get_conversation_summary -v
python test_datetime_usage.py
python -m pytest tests/ -v --tb=short
python -m pytest tests/ --tb=no -q
python -m pytest tests/test_database/test_migrations.py::TestMigrationSQL::test_migration_002_sql -v
python -m pytest tests/test_database/test_migrations.py::TestMigrationSQL::test_migration_003_sql -v
python -m pytest tests/test_database/test_migrations.py::TestMigrationSQL::test_migration_rollback_sql -v
python -m pytest tests/ --tb=no -q
python -m pytest tests/ --cov=src --cov-report=term-missing --cov-report=html
python -m pytest tests/test_database/ -v
python examples/conversation_logging_example.py
python test_sip_integration.py
TEST_MODE=true python -m src.main
pip install fastapi uvicorn
TEST_MODE=true python -m src.main
TEST_MODE=true LIVEKIT_API_KEY=API48Ajeeuv4tYL python -c "
from src.security import validate_api_key, APIKeyType
result = validate_api_key('API48Ajeeuv4tYL', APIKeyType.LIVEKIT)
print(f'Valid: {result.is_valid}')
print(f'Error: {result.error_message}')
print(f'Masked: {result.masked_key}')
"
TEST_MODE=true LIVEKIT_API_KEY=API48Ajeeuv4tYL python -m src.main
LIVEKIT_API_KEY=API48Ajeeuv4tYL python test_sip_integration.py
python -c "
import yaml
with open('livekit-sip.yaml', 'r') as f:
    config = yaml.safe_load(f)
print('✅ YAML файл корректен')
print(f'SIP trunks: {len(config.get(\"sip_trunks\", []))}')
print(f'Audio codecs: {len(config.get(\"audio_codecs\", []))}')
print(f'Routing rules: {len(config.get(\"routing\", {}).get(\"inbound_rules\", []))}')
print(f'LiveKit config: {\"livekit\" in config}')
print(f'Monitoring config: {\"monitoring\" in config}')
"
python -c "
from src.security import validate_api_key, APIKeyType

# Тест с вашим API ключом
result = validate_api_key('API48Ajeeuv4tYL', APIKeyType.LIVEKIT)
print(f'✅ LiveKit API key validation: {result.is_valid}')
print(f'Masked key: {result.masked_key}')

# Тест с другими типами ключей
test_keys = {
    'OpenAI': ('sk-1234567890abcdef1234567890abcdef', APIKeyType.OPENAI),
    'Deepgram': ('1234567890abcdef1234567890abcdef12345678', APIKeyType.DEEPGRAM),
    'Cartesia': ('cart_1234567890abcdef1234567890abcdef', APIKeyType.CARTESIA)
}

for name, (key, key_type) in test_keys.items():
    result = validate_api_key(key, key_type)
    print(f'{name} validation: {result.is_valid}')
"
python test_sip_integration.py
python -m pytest tests/ -v --tb=short
python -m pytest tests/test_security.py::TestAPIKeyValidation -v
python -m pytest tests/test_config.py -v
TEST_MODE=true LIVEKIT_API_KEY=API48Ajeeuv4tYL LIVEKIT_URL=wss://test.livekit.cloud LIVEKIT_API_SECRET=test-secret python -m src.main
python -m pytest tests/test_main_integration.py -v --tb=short
python -m pytest tests/test_main_integration.py::TestVoiceAIAgentIntegration::test_signal_handling tests/test_main_integration.py::TestVoiceAIAgentIntegration::test_health_monitoring_loop -v --tb=short
python -m pytest tests/test_main_integration.py::TestVoiceAIAgentIntegration::test_health_monitoring_loop -v --tb=short
python -m pytest tests/test_main_integration.py -v --tb=short
python src/main.py --test-init
python -c "from src.main import VoiceAIAgent; import asyncio; agent = VoiceAIAgent(); print('✅ VoiceAIAgent can be imported and instantiated successfully')"
python src/health.py
