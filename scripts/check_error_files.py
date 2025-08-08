#!/usr/bin/env python3
"""
Скрипт для проверки файлов с ошибками в проекте LiveKit.
Анализирует конкретные файлы и показывает детали ошибок.
"""

import json
import sys
from pathlib import Path

def main():
    """Анализирует файлы с ошибками из отчета классификации."""
    
    # Читаем отчет классификации
    try:
        with open('project_analysis.json', 'r', encoding='utf-8') as f:
            report = json.load(f)
    except FileNotFoundError:
        print("❌ Файл project_analysis.json не найден. Запустите сначала project_file_classifier.py")
        sys.exit(1)
    
    # Находим файлы с ошибками
    error_files = [f for f in report['files'] if f['status'] == 'error']
    
    print("🔍 АНАЛИЗ ФАЙЛОВ С ОШИБКАМИ")
    print("=" * 60)
    print(f"Найдено файлов с ошибками: {len(error_files)}")
    
    # Группируем по категориям
    by_category = {}
    for file in error_files:
        category = file['category']
        if category not in by_category:
            by_category[category] = []
        by_category[category].append(file)
    
    print("\n📊 РАСПРЕДЕЛЕНИЕ ПО КАТЕГОРИЯМ:")
    for category, files in by_category.items():
        print(f"  {category}: {len(files)} файлов")
    
    # Показываем детали для каждой категории
    for category, files in by_category.items():
        print(f"\n🔧 {category.upper()} - ФАЙЛЫ С ОШИБКАМИ:")
        print("-" * 40)
        
        for file in files[:10]:  # Показываем первые 10 файлов
            print(f"\n📁 {file['path']}")
            print(f"   Размер: {file['size']} байт")
            print(f"   Подкатегория: {file['subcategory']}")
            
            if file['issues']:
                print("   ❌ Проблемы:")
                for issue in file['issues'][:3]:  # Первые 3 проблемы
                    print(f"      • {issue}")
            
            # Показываем превью содержимого
            preview = file['content_preview'][:100]
            if preview:
                print(f"   📄 Превью: {preview}...")
        
        if len(files) > 10:
            print(f"\n   ... и ещё {len(files) - 10} файлов")
    
    # Рекомендации по исправлению
    print("\n💡 РЕКОМЕНДАЦИИ ПО ИСПРАВЛЕНИЮ:")
    print("-" * 40)
    
    # Анализируем типы ошибок
    syntax_errors = [f for f in error_files if not f['syntax_valid']]
    
    if syntax_errors:
        print(f"1. Исправить синтаксические ошибки в {len(syntax_errors)} файлах")
        
        # Группируем синтаксические ошибки по типам
        python_syntax_errors = [f for f in syntax_errors if f['extension'] == '.py']
        yaml_syntax_errors = [f for f in syntax_errors if f['extension'] in ['.yaml', '.yml']]
        json_syntax_errors = [f for f in syntax_errors if f['extension'] == '.json']
        
        if python_syntax_errors:
            print(f"   • Python файлы: {len(python_syntax_errors)}")
        if yaml_syntax_errors:
            print(f"   • YAML файлы: {len(yaml_syntax_errors)}")
        if json_syntax_errors:
            print(f"   • JSON файлы: {len(json_syntax_errors)}")
    
    # Показываем конкретные файлы для исправления
    print("\n🎯 ПРИОРИТЕТНЫЕ ФАЙЛЫ ДЛЯ ИСПРАВЛЕНИЯ:")
    print("-" * 40)
    
    # Файлы из основных компонентов LiveKit
    livekit_files = [f for f in error_files if any(keyword in f['path'].lower() 
                     for keyword in ['livekit', 'auth', 'api', 'client', 'sip'])]
    
    for file in livekit_files[:5]:
        print(f"🔧 {file['path']}")
        if file['issues']:
            for issue in file['issues'][:2]:
                print(f"   ❌ {issue}")
    
    print(f"\n📈 ОБЩАЯ СТАТИСТИКА:")
    print(f"   • Всего файлов в проекте: {report['classification_summary']['total_files']}")
    print(f"   • Файлов с ошибками: {len(error_files)}")
    print(f"   • Процент ошибок: {len(error_files) / report['classification_summary']['total_files'] * 100:.2f}%")
    print(f"   • Средняя оценка качества: {report['classification_summary']['average_quality_score']:.3f}")

if __name__ == "__main__":
    main()