# Анализ и классификация файлов проекта

## Категории файлов

### 1. АКТИВНЫЕ РАБОЧИЕ ФАЙЛЫ (необходимы для работы)

#### Основная конфигурация
- `.env` - основные переменные окружения ✅ НУЖЕН
- `pyproject.toml` - конфигурация Python проекта ✅ НУЖЕН
- `requirements.txt` - зависимости Python ✅ НУЖЕН
- `Dockerfile` - основной Docker образ ✅ НУЖЕН
- `docker-compose.yml` - основная композиция ✅ НУЖЕН

#### Исходный код (папки)
- `src/` - основной исходный код ✅ НУЖЕН
- `config/` - конфигурационные файлы ✅ НУЖЕН
- `tests/` - тесты ✅ НУЖЕН
- `scripts/` - рабочие скрипты ✅ НУЖЕН

#### Документация
- `README.md` - основная документация ✅ НУЖЕН
- `docs/` - папка с документацией ✅ НУЖЕН

### 2. КОНФИГУРАЦИИ LIVEKIT SIP (множественные версии)

#### Текущая рабочая версия
- `livekit-sip-correct.yaml` - ✅ ТЕКУЩАЯ РАБОЧАЯ ВЕРСИЯ

#### Резервные и альтернативные версии
- `livekit-sip.yaml` - базовая версия
- `livekit-sip-working.yaml` - рабочая версия
- `livekit-sip-final.yaml` - финальная версия
- `livekit-sip-simple.yaml` - упрощенная версия

#### Экспериментальные и исправления
- `livekit-sip-FIXED.yaml` - исправленная
- `livekit-sip-bypass.yaml` - обходная
- `livekit-sip-final-fix.yaml` - финальное исправление
- `livekit-sip-fixed.yaml` - исправленная
- `livekit-sip-inbound.yaml` - входящие вызовы
- `livekit-sip-ip-fix.yaml` - исправление IP
- `livekit-sip-minimal.yaml` - минимальная
- `livekit-sip-new-keys.yaml` - новые ключи
- `livekit-sip-new-working.yaml` - новая рабочая
- `livekit-sip-no-auth.yaml` - без аутентификации
- `livekit-sip-novofon-auth.yaml` - аутентификация Novofon
- `livekit-sip-novofon.yaml` - конфигурация Novofon
- `livekit-sip-simple-fixed.yaml` - простая исправленная
- `livekit-sip-simple-inbound.yaml` - простая входящая
- `livekit-sip-working-keys.yaml` - рабочие ключи

#### Резервные копии с временными метками
- `livekit-sip.yaml.backup.1754187420` - ❌ УСТАРЕЛ
- `livekit-sip.yaml.backup.1754264302` - ❌ УСТАРЕЛ
- `livekit-sip-simple.yaml.backup.1754187420` - ❌ УСТАРЕЛ

### 3. ТЕСТОВЫЕ ФАЙЛЫ

#### Корневые тестовые файлы (дублируют tests/)
- `test_*.py` (множество файлов в корне) - ❌ ДУБЛИРУЮТ tests/
- `run_comprehensive_tests.py` - ✅ НУЖЕН (утилита запуска)
- `validate_test_implementation.py` - ✅ НУЖЕН (валидация)

### 4. ОТЧЕТЫ И ЛОГИ

#### Отчеты по задачам (исторические)
- `TASK_*_*.md` - ❌ ИСТОРИЧЕСКИЕ ОТЧЕТЫ
- `*_IMPLEMENTATION_REPORT.md` - ❌ ИСТОРИЧЕСКИЕ ОТЧЕТЫ
- `*_TEST_REPORT.md` - ❌ ИСТОРИЧЕСКИЕ ОТЧЕТЫ

#### JSON результаты тестов (исторические)
- `final_validation_results_*.json` - ❌ УСТАРЕВШИЕ РЕЗУЛЬТАТЫ
- `livekit_diagnostics_*.json` - ❌ УСТАРЕВШИЕ ДИАГНОСТИКИ
- `minimal_validation_report_*.json` - ❌ УСТАРЕВШИЕ ОТЧЕТЫ
- `sip_*_test_report_*.json` - ❌ УСТАРЕВШИЕ ОТЧЕТЫ

#### Актуальные конфигурационные JSON
- `project_analysis.json` - ✅ МОЖЕТ БЫТЬ ПОЛЕЗЕН
- `performance_baseline.json` - ✅ МОЖЕТ БЫТЬ ПОЛЕЗЕН

### 5. DOCKER И ДЕПЛОЙ

#### Основные
- `Dockerfile` - ✅ НУЖЕН
- `docker-compose.yml` - ✅ НУЖЕН

#### Специализированные
- `Dockerfile.livekit-sip` - ✅ НУЖЕН ДЛЯ SIP
- `docker-compose.prod.yml` - ✅ НУЖЕН ДЛЯ ПРОДАКШН
- `docker-compose.monitoring.yml` - ✅ НУЖЕН ДЛЯ МОНИТОРИНГА
- `docker-compose.simple.yml` - ❓ ВОЗМОЖНО УСТАРЕЛ

#### Резервные копии
- `docker-compose.prod.yml.backup` - ❌ РЕЗЕРВНАЯ КОПИЯ
- `Makefile.backup` - ❌ РЕЗЕРВНАЯ КОПИЯ

### 6. ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ

#### Основные
- `.env` - ✅ ОСНОВНОЙ ФАЙЛ

#### Специализированные
- `.env.production` - ✅ ДЛЯ ПРОДАКШН
- `.env.test` - ✅ ДЛЯ ТЕСТОВ
- `.env.template` - ✅ ШАБЛОН

#### Временные/служебные
- `.env.secrets` - ❓ ПРОВЕРИТЬ ИСПОЛЬЗОВАНИЕ
- `.env.temp` - ❌ ВРЕМЕННЫЙ
- `.last_backup_path` - ❌ СЛУЖЕБНЫЙ

### 7. СИСТЕМНЫЕ И СЛУЖЕБНЫЕ

#### Git и разработка
- `.gitignore` - ✅ НУЖЕН
- `.pre-commit-config.yaml` - ✅ НУЖЕН
- `.editorconfig` - ✅ НУЖЕН

#### Системные папки (не трогать)
- `.git/`, `.github/`, `.vscode/`, `.kiro/` - ✅ СИСТЕМНЫЕ
- `venv/`, `__pycache__/`, `.pytest_cache/` - ✅ АВТОГЕНЕРИРУЕМЫЕ

#### Логи и кэш
- `health_monitor.log` - ❌ ВРЕМЕННЫЙ ЛОГ
- `.coverage` - ❌ РЕЗУЛЬТАТ ТЕСТОВ
- `htmlcov/` - ❌ РЕЗУЛЬТАТ ПОКРЫТИЯ

### 8. УТИЛИТЫ И СКРИПТЫ

#### Основные утилиты
- `start.sh` - ✅ СКРИПТ ЗАПУСКА
- `start_system.py` - ✅ ЗАПУСК СИСТЕМЫ
- `health_check.py` - ✅ ПРОВЕРКА ЗДОРОВЬЯ
- `healthcheck.py` - ❓ ДУБЛИРУЕТ health_check.py?

#### Исправления и утилиты
- `fix_sql_queries.py` - ❓ ПРОВЕРИТЬ АКТУАЛЬНОСТЬ

### 9. НЕОПОЗНАННЫЕ/ПРОБЛЕМНЫЕ
- `=7.0.0` - ❌ НЕОПОЗНАННЫЙ ФАЙЛ
- `nast.md` - ❓ НЕЯСНОЕ НАЗНАЧЕНИЕ
- `new.md` - ❓ НЕЯСНОЕ НАЗНАЧЕНИЕ

## Рекомендации по очистке

### МОЖНО УДАЛИТЬ БЕЗОПАСНО:
1. Все файлы `*_REPORT.md` и `TASK_*.md` (исторические отчеты)
2. Все JSON файлы с временными метками (результаты старых тестов)
3. Резервные копии с `.backup` в названии
4. Временные файлы `.env.temp`
5. Тестовые файлы в корне (дублируют tests/)
6. Файл `=7.0.0`
7. Логи `health_monitor.log`
8. Результаты покрытия `.coverage`, `htmlcov/`

### ТРЕБУЕТ АНАЛИЗА:
1. Множественные конфигурации LiveKit SIP - оставить только рабочие
2. Файлы `healthcheck.py` vs `health_check.py` - возможно дублируют
3. Файлы `nast.md`, `new.md` - проверить содержимое
4. `.env.secrets` - проверить использование

### ОБЯЗАТЕЛЬНО СОХРАНИТЬ:
1. Основную конфигурацию (.env, pyproject.toml, requirements.txt)
2. Исходный код (src/, config/, tests/, scripts/)
3. Docker файлы (Dockerfile, docker-compose.yml)
4. Документацию (README.md, docs/)
5. Текущую рабочую конфигурацию LiveKit SIP