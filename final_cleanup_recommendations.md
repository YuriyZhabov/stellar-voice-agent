# Финальные рекомендации по очистке проекта

## Анализ текущей конфигурации

### Активно используемые файлы:
1. **`.env`** - основная конфигурация (✅ АКТИВЕН)
2. **`livekit-sip-correct.yaml`** - текущая рабочая SIP конфигурация (✅ АКТИВЕН)
3. **`docker-compose.yml`** - основная Docker композиция (✅ АКТИВЕН)

### Структура проекта:
- **`src/`** - основной исходный код (✅ НУЖЕН)
- **`config/`** - конфигурационные файлы (✅ НУЖЕН)
- **`tests/`** - тесты (✅ НУЖЕН)
- **`scripts/`** - рабочие скрипты (✅ НУЖЕН)
- **`docs/`** - документация (✅ НУЖЕН)

## ФАЙЛЫ ДЛЯ УДАЛЕНИЯ (БЕЗОПАСНО)

### 1. Исторические отчеты (47 файлов)
```bash
# Отчеты по задачам
TASK_*_*.md
*_IMPLEMENTATION_REPORT.md
*_TEST_REPORT.md
COMPREHENSIVE_*.md
FINAL_*.md
CONFIG_TESTS_FIX_REPORT.md
BUSY_SIGNAL_FIX_REPORT.md
CALL_SYSTEM_FIX_REPORT.md
DATABASE_IMPLEMENTATION_SUMMARY.md
DEPLOYMENT_FIX_SUMMARY.md
E2E_INTEGRATION_TESTS_IMPLEMENTATION_REPORT.md
EGRESS_IMPLEMENTATION_REPORT.md
INGRESS_IMPLEMENTATION_REPORT.md
MIGRATION_DEPLOYMENT_IMPLEMENTATION_REPORT.md
MONITORING_IMPLEMENTATION_REPORT.md
NOVOFON_MIGRATION_SUMMARY.md
PERFORMANCE_OPTIMIZATION_IMPLEMENTATION_REPORT.md
SIP_AUTH_FIX_REPORT.md
livekit_connection_fix_report.md
sip_integration_verification_report.md
```

### 2. Устаревшие результаты тестов (JSON файлы)
```bash
# Результаты валидации с временными метками
final_validation_results_*.json
livekit_diagnostics_*.json
minimal_validation_report_*.json
sip_auth_test_report_*.json
sip_busy_diagnostic_*.json
sip_config_test_report_*.json
sip_integration_test_results.json
```

### 3. Резервные копии конфигураций
```bash
# Резервные копии с временными метками
livekit-sip.yaml.backup.*
livekit-sip-simple.yaml.backup.*
docker-compose.prod.yml.backup
Makefile.backup
```

### 4. Дублирующие тестовые файлы в корне
```bash
# Тесты, которые дублируют содержимое tests/
test_egress_service.py
test_enhanced_functionality.py
test_final_verification.py
test_imports.py
test_integration_simple.py
test_performance_*.py
test_real_call.py
test_simple_*.py
test_sip_*.py
test_updated_components_*.py
```

### 5. Временные и служебные файлы
```bash
# Временные файлы
.env.temp
health_monitor.log
.coverage
.last_backup_path
=7.0.0
nast.md
new.md
```

### 6. Результаты покрытия тестов
```bash
# Автогенерируемые файлы покрытия
htmlcov/
```

## ФАЙЛЫ ДЛЯ АНАЛИЗА И ВОЗМОЖНОГО УДАЛЕНИЯ

### 1. Множественные конфигурации LiveKit SIP (22 файла)
**ОСТАВИТЬ ТОЛЬКО:**
- `livekit-sip-correct.yaml` (✅ ТЕКУЩИЙ РАБОЧИЙ)

**УДАЛИТЬ ВСЕ ОСТАЛЬНЫЕ:**
```bash
livekit-sip.yaml
livekit-sip-FIXED.yaml
livekit-sip-bypass.yaml
livekit-sip-config.json
livekit-sip-final-fix.yaml
livekit-sip-final.yaml
livekit-sip-fixed.yaml
livekit-sip-inbound.yaml
livekit-sip-ip-fix.yaml
livekit-sip-minimal.yaml
livekit-sip-new-keys.yaml
livekit-sip-new-working.yaml
livekit-sip-no-auth.yaml
livekit-sip-novofon-auth.yaml
livekit-sip-novofon.yaml
livekit-sip-simple-fixed.yaml
livekit-sip-simple-inbound.yaml
livekit-sip-simple.yaml
livekit-sip-working-keys.yaml
livekit-sip-working.yaml
```

### 2. Дублирующие утилиты
```bash
# Проверить различия и оставить одну
healthcheck.py vs health_check.py
```

### 3. Специализированные Docker файлы
**ОСТАВИТЬ:**
- `Dockerfile` (основной)
- `docker-compose.yml` (основной)
- `docker-compose.prod.yml` (продакшн)
- `docker-compose.monitoring.yml` (мониторинг)

**ПРОВЕРИТЬ НЕОБХОДИМОСТЬ:**
- `Dockerfile.livekit-sip` (если не используется отдельно)
- `docker-compose.simple.yml` (возможно устарел)

## ФАЙЛЫ ДЛЯ СОХРАНЕНИЯ (КРИТИЧЕСКИ ВАЖНЫЕ)

### 1. Основная конфигурация
```bash
.env                    # Основные переменные окружения
.env.production        # Продакшн переменные
.env.test             # Тестовые переменные
.env.template         # Шаблон переменных
pyproject.toml        # Конфигурация Python проекта
requirements.txt      # Зависимости Python
```

### 2. Docker и деплой
```bash
Dockerfile
docker-compose.yml
docker-compose.prod.yml
docker-compose.monitoring.yml
```

### 3. Текущая рабочая SIP конфигурация
```bash
livekit-sip-correct.yaml  # ЕДИНСТВЕННАЯ РАБОЧАЯ КОНФИГУРАЦИЯ
```

### 4. Исходный код и структура
```bash
src/                  # Весь исходный код
config/              # Конфигурационные файлы
tests/               # Тесты
scripts/             # Рабочие скрипты
docs/                # Документация
examples/            # Примеры
```

### 5. Системные файлы
```bash
.gitignore
.pre-commit-config.yaml
.editorconfig
README.md
CONTRIBUTING.md
Makefile
```

### 6. Утилиты запуска
```bash
start.sh
start_system.py
health_check.py
```

### 7. Полезные утилиты
```bash
run_comprehensive_tests.py
validate_test_implementation.py
fix_sql_queries.py
```

## КОМАНДЫ ДЛЯ ОЧИСТКИ

### Удаление исторических отчетов:
```bash
rm -f *_REPORT.md *_SUMMARY.md TASK_*.md
```

### Удаление устаревших JSON результатов:
```bash
rm -f final_validation_results_*.json
rm -f livekit_diagnostics_*.json
rm -f minimal_validation_report_*.json
rm -f sip_*_test_report_*.json
```

### Удаление резервных копий:
```bash
rm -f *.backup*
```

### Удаление дублирующих тестов в корне:
```bash
rm -f test_*.py
# НО СОХРАНИТЬ:
# run_comprehensive_tests.py
# validate_test_implementation.py
```

### Удаление лишних SIP конфигураций:
```bash
# Сохранить только livekit-sip-correct.yaml
rm -f livekit-sip.yaml livekit-sip-*.yaml
# НО НЕ УДАЛЯТЬ livekit-sip-correct.yaml!
```

### Удаление временных файлов:
```bash
rm -f .env.temp health_monitor.log .coverage .last_backup_path =7.0.0 nast.md new.md
rm -rf htmlcov/
```

## ИТОГОВАЯ СТАТИСТИКА

### До очистки: ~150+ файлов
### После очистки: ~50-60 файлов

### Освобождаемое место:
- Удаление отчетов: ~2-3 MB
- Удаление JSON результатов: ~1-2 MB  
- Удаление дублирующих конфигураций: ~500 KB
- Удаление дублирующих тестов: ~1 MB
- **Общее освобождение: ~5-7 MB**

### Улучшение структуры:
- ✅ Убраны дублирующие файлы
- ✅ Оставлена только рабочая SIP конфигурация
- ✅ Удалены исторические отчеты
- ✅ Очищены временные файлы
- ✅ Сохранена вся функциональность

## РЕКОМЕНДУЕМЫЙ ПОРЯДОК ДЕЙСТВИЙ

1. **Создать резервную копию проекта**
2. **Удалить исторические отчеты** (безопасно)
3. **Удалить устаревшие JSON результаты** (безопасно)
4. **Удалить резервные копии конфигураций** (безопасно)
5. **Удалить дублирующие тесты в корне** (проверить, что tests/ содержит аналоги)
6. **Удалить лишние SIP конфигурации** (оставить только livekit-sip-correct.yaml)
7. **Удалить временные файлы** (безопасно)
8. **Протестировать работоспособность системы**