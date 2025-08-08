#!/usr/bin/env python3
"""
Демонстрация работы классификатора файлов проекта.
"""

import sys
import os
from pathlib import Path

# Добавляем src в путь для импорта
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from classification.file_classifier import FileClassifier


def main():
    """Демонстрация классификации файлов."""
    print("🔍 Демонстрация классификатора файлов проекта LiveKit")
    print("=" * 60)
    
    classifier = FileClassifier()
    
    # Примеры файлов для классификации
    test_files = [
        # Исходный код
        'src/clients/livekit_client.py',
        'src/auth/livekit_auth.py',
        'src/monitoring/health_monitor.py',
        'src/security/encryption.py',
        'src/services/egress_service.py',
        'src/integration/webhook_handler.py',
        'src/database/models.py',
        'src/main.py',
        
        # Тесты
        'tests/test_client.py',
        'tests/test_integration_flow.py',
        'tests/test_load_performance.py',
        'tests/test_security_auth.py',
        'tests/conftest.py',
        
        # Конфигурация
        'docker-compose.yml',
        'prometheus.yml',
        'livekit-sip.yaml',
        '.env.production',
        'security.yaml',
        'config.json',
        
        # Документация
        'README.md',
        'docs/setup_guide.md',
        'docs/api_reference.md',
        'examples/client_example.md',
        'IMPLEMENTATION_REPORT.md',
        'docs/architecture_design.md',
        'docs/troubleshooting_guide.md',
        
        # Скрипты
        'scripts/deploy_production.py',
        'scripts/validate_config.py',
        'scripts/monitor_health.py',
        'scripts/fix_database.py',
        'scripts/run_tests.py',
        
        # Специальные файлы
        'Dockerfile',
        'Makefile',
        'requirements.txt',
        'pyproject.toml',
        'setup.py',
        
        # Данные
        'data/voice_ai.db',
        
        # Неизвестные
        'unknown_file.xyz'
    ]
    
    # Группировка по категориям
    categories = {}
    
    for file_path in test_files:
        category, subcategory = classifier.classify_file(file_path)
        
        if category not in categories:
            categories[category] = {}
        if subcategory not in categories[category]:
            categories[category][subcategory] = []
        
        categories[category][subcategory].append(file_path)
    
    # Вывод результатов
    for category, subcategories in categories.items():
        category_info = classifier.get_category_info(category)
        print(f"\n📁 {category.upper()}")
        if 'description' in category_info:
            print(f"   {category_info['description']}")
        print("-" * 40)
        
        for subcategory, files in subcategories.items():
            subcategory_info = classifier.get_subcategory_info(category, subcategory)
            print(f"  📂 {subcategory}")
            if 'description' in subcategory_info:
                print(f"     {subcategory_info['description']}")
            
            for file_path in files:
                print(f"     • {file_path}")
            print()
    
    # Статистика
    total_files = len(test_files)
    print(f"\n📊 СТАТИСТИКА")
    print("=" * 30)
    print(f"Всего файлов: {total_files}")
    print(f"Категорий: {len(categories)}")
    
    for category, subcategories in categories.items():
        count = sum(len(files) for files in subcategories.values())
        print(f"  {category}: {count} файлов")
    
    # Демонстрация API
    print(f"\n🔧 ДЕМОНСТРАЦИЯ API")
    print("=" * 30)
    
    # Получение всех категорий
    all_categories = classifier.get_all_categories()
    print(f"Доступные категории: {', '.join(all_categories)}")
    
    # Получение подкатегорий
    source_subcategories = classifier.get_subcategories('source_code')
    print(f"Подкатегории исходного кода: {', '.join(source_subcategories)}")
    
    # Валидация классификации
    is_valid = classifier.validate_classification('test.py', 'source_code', 'api_clients')
    print(f"Валидация (test.py, source_code, api_clients): {is_valid}")
    
    is_invalid = classifier.validate_classification('test.py', 'invalid', 'api_clients')
    print(f"Валидация (test.py, invalid, api_clients): {is_invalid}")
    
    print(f"\n✅ Демонстрация завершена!")


if __name__ == '__main__':
    main()