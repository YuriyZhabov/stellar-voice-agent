# Реализация классификатора файлов проекта

## Обзор

Классификатор файлов проекта LiveKit - это система для автоматической категоризации файлов по типам и функциональному назначению. Система реализует требования из спецификации проекта и обеспечивает точную классификацию файлов различных типов.

## Архитектура

### Основные компоненты

1. **FileClassifier** - главный класс классификации
2. **PythonFileClassifier** - специализированный классификатор для Python файлов
3. **ConfigFileClassifier** - классификатор конфигурационных файлов
4. **DocumentationClassifier** - классификатор документации

### Структура модуля

```
src/classification/
├── __init__.py
└── file_classifier.py
```

## Категории файлов

### 1. Исходный код (source_code)
- **Расширения**: `.py`
- **Подкатегории**:
  - `api_clients` - API клиенты и HTTP интерфейсы
  - `auth` - Аутентификация и авторизация
  - `monitoring` - Мониторинг и метрики
  - `security` - Безопасность и криптография
  - `services` - Сервисы и обработчики
  - `integration` - Интеграции и веб-хуки
  - `config` - Конфигурация приложения
  - `database` - База данных и модели
  - `middleware` - Промежуточное ПО
  - `main` - Основные модули

### 2. Тесты (tests)
- **Расширения**: `.py`
- **Подкатегории**:
  - `integration` - Интеграционные тесты
  - `load` - Нагрузочные тесты
  - `security` - Тесты безопасности
  - `config` - Конфигурация тестов
  - `unit` - Модульные тесты

### 3. Конфигурация (config)
- **Расширения**: `.yaml`, `.yml`, `.json`, `.env`, `.ini`, `.toml`, `.conf`
- **Подкатегории**:
  - `deployment` - Развертывание (Docker, K8s)
  - `monitoring` - Мониторинг (Prometheus, Grafana)
  - `security` - Безопасность и аутентификация
  - `performance` - Производительность и retry политики
  - `livekit` - Конфигурация LiveKit
  - `environment` - Переменные окружения
  - `main` - Основная конфигурация

### 4. Документация (docs)
- **Расширения**: `.md`, `.rst`, `.txt`, `.adoc`
- **Подкатегории**:
  - `troubleshooting` - Устранение неполадок
  - `api_docs` - API документация
  - `architecture` - Архитектура и дизайн
  - `examples` - Примеры использования
  - `reports` - Отчеты и сводки
  - `guides` - Руководства и туториалы
  - `main` - Основная документация

### 5. Скрипты (scripts)
- **Расширения**: `.py`, `.sh`, `.bash`, `.bat`, `.ps1`
- **Подкатегории**:
  - `deployment` - Развертывание и миграции
  - `validation` - Валидация и проверки
  - `monitoring` - Мониторинг и диагностика
  - `utilities` - Утилиты и инструменты
  - `automation` - Автоматизация и запуск

### 6. Данные (data)
- **Расширения**: `.db`, `.sqlite`, `.sqlite3`, `.sql`

### 7. Веб-файлы (web)
- **Расширения**: `.html`, `.css`, `.js`, `.ts`, `.jsx`, `.tsx`

### 8. Прочие (other)
- Все остальные файлы

## Алгоритм классификации

### 1. Определение категории

1. **Специальные файлы** (высший приоритет)
   - `Dockerfile` → config
   - `Makefile` → scripts
   - `requirements.txt` → config
   - `pyproject.toml` → config
   - `setup.py` → scripts

2. **Файлы окружения**
   - `.env*` → config

3. **Тестовые файлы**
   - `test_*.py`, `*_test.py`, `conftest.py` → tests
   - Файлы в папках с "test" в пути → tests

4. **Скрипты**
   - Файлы в папке `scripts/` → scripts

5. **По расширению**
   - Сопоставление с таблицей расширений

### 2. Определение подкатегории

1. **По паттернам пути** (высший приоритет)
   - `clients/`, `auth/`, `monitoring/`, etc.

2. **По паттернам файлов**
   - `*integration*.py`, `docker-compose*.yml`, etc.

3. **По ключевым словам в имени**
   - `client`, `auth`, `monitor`, etc.

4. **По содержимому** (для Python файлов)
   - Анализ импортов и ключевых слов

## API

### FileClassifier

```python
classifier = FileClassifier()

# Основная классификация
category, subcategory = classifier.classify_file(file_path, content_preview)

# Получение информации
category_info = classifier.get_category_info(category)
subcategory_info = classifier.get_subcategory_info(category, subcategory)

# Списки категорий
all_categories = classifier.get_all_categories()
subcategories = classifier.get_subcategories(category)

# Валидация
is_valid = classifier.validate_classification(file_path, category, subcategory)
```

### Специализированные классификаторы

```python
# Python файлы
python_classifier = PythonFileClassifier()
category, subcategory = python_classifier.classify_python_file(file_path, content)

# Конфигурационные файлы
config_classifier = ConfigFileClassifier()
subcategory = config_classifier.classify_config_file(file_path, content)

# Документация
docs_classifier = DocumentationClassifier()
subcategory = docs_classifier.classify_documentation(file_path, content)
```

## Примеры использования

### Базовая классификация

```python
from classification import FileClassifier

classifier = FileClassifier()

# Классификация файла
category, subcategory = classifier.classify_file('src/clients/api_client.py')
print(f"Категория: {category}, Подкатегория: {subcategory}")
# Вывод: Категория: source_code, Подкатегория: api_clients
```

### Классификация с содержимым

```python
content = """
import requests
from livekit import api

class LiveKitClient:
    def make_request(self):
        return requests.get("http://api.example.com")
"""

category, subcategory = classifier.classify_file('src/unknown.py', content)
print(f"Категория: {category}, Подкатегория: {subcategory}")
# Вывод: Категория: source_code, Подкатегория: api_clients
```

### Получение метаданных

```python
# Информация о категории
info = classifier.get_category_info('source_code')
print(info['description'])  # Исходный код Python

# Информация о подкатегории
info = classifier.get_subcategory_info('source_code', 'api_clients')
print(info['description'])  # API клиенты
print(info['keywords'])     # ['client', 'api', 'rest', 'http']
```

## Тестирование

Система включает комплексные тесты:

```bash
# Запуск всех тестов
python3 -m pytest tests/test_file_classifier.py -v

# Запуск конкретного теста
python3 -m pytest tests/test_file_classifier.py::TestFileClassifier::test_python_source_code_classification -v
```

### Покрытие тестами

- ✅ Классификация исходного кода Python
- ✅ Классификация тестовых файлов
- ✅ Классификация конфигурационных файлов
- ✅ Классификация документации
- ✅ Классификация скриптов
- ✅ Специальные файлы
- ✅ Классификация по содержимому
- ✅ API методы
- ✅ Граничные случаи
- ✅ Нечувствительность к регистру
- ✅ Вложенные пути

## Демонстрация

Запустите демонстрационный скрипт:

```bash
python3 examples/file_classifier_demo.py
```

Скрипт покажет:
- Классификацию различных типов файлов
- Группировку по категориям и подкатегориям
- Статистику классификации
- Примеры использования API

## Соответствие требованиям

### Requirement 2.1: Категоризация по функциональности
✅ **Выполнено**: Реализованы все требуемые категории:
- Исходный код с подкатегориями (API клиенты, аутентификация, мониторинг, безопасность, сервисы)
- Тесты с типами (unit, интеграционные, нагрузочные)
- Скрипты с типами (развертывание, валидация, утилиты)
- Документация с типами (API документация, руководства, примеры)

### Requirement 2.2: Система категоризации по расширениям
✅ **Выполнено**: Реализована полная система категоризации по расширениям файлов с поддержкой всех основных типов.

### Requirement 2.3: Специальные правила для Python файлов
✅ **Выполнено**: Реализованы специальные правила для Python файлов:
- Определение тестов по паттернам имен
- Классификация модулей по содержимому
- Анализ импортов для определения типа

### Requirement 2.4: Классификация конфигурационных файлов
✅ **Выполнено**: Реализована детальная классификация конфигурационных файлов по типам (развертывание, мониторинг, безопасность, LiveKit).

### Requirement 2.5: Определение типов документации
✅ **Выполнено**: Реализована система определения типов документации (руководства, API документация, примеры, отчеты, архитектура).

## Заключение

Классификатор файлов проекта успешно реализован в соответствии с требованиями спецификации. Система обеспечивает:

- ✅ Точную категоризацию файлов по типам и функциональности
- ✅ Поддержку специальных правил для различных типов файлов
- ✅ Гибкую систему подкатегорий
- ✅ Классификацию на основе содержимого
- ✅ Комплексное тестирование
- ✅ Простой и понятный API

Система готова к интеграции с другими компонентами проекта классификации файлов.