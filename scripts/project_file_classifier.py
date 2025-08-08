#!/usr/bin/env python3
"""
Система классификации файлов проекта LiveKit.
Анализирует все файлы в проекте и создает детальную классификацию.
"""

import os
import ast
import json
import yaml
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, asdict
import fnmatch

@dataclass
class FileInfo:
    """Информация о файле в проекте."""
    path: str
    name: str
    extension: str
    size: int
    category: str
    subcategory: str
    status: str  # 'ready', 'incomplete', 'error', 'missing'
    syntax_valid: bool
    dependencies: List[str]
    issues: List[str]
    quality_score: float
    last_modified: str
    content_preview: str

class FileScanner:
    """Сканирует файловую систему проекта."""
    
    def __init__(self, root_path: str):
        self.root_path = Path(root_path)
        self.exclude_patterns = [
            '.git', '.kiro', '__pycache__', '*.pyc', '.pytest_cache',
            'node_modules', '.venv', 'venv', '*.egg-info',
            '.DS_Store', 'Thumbs.db', '*.log'
        ]
        self.logger = logging.getLogger(__name__)
    
    def should_exclude(self, path: Path) -> bool:
        """Проверяет, должен ли файл быть исключен."""
        path_str = str(path)
        
        for pattern in self.exclude_patterns:
            if fnmatch.fnmatch(path.name, pattern):
                return True
            if fnmatch.fnmatch(path_str, f"*/{pattern}/*"):
                return True
        
        return False
    
    def scan_project(self) -> List[Path]:
        """Сканирует проект и возвращает список всех файлов."""
        files = []
        
        for root, dirs, filenames in os.walk(self.root_path):
            root_path = Path(root)
            
            # Исключаем директории
            dirs[:] = [d for d in dirs if not self.should_exclude(root_path / d)]
            
            for filename in filenames:
                file_path = root_path / filename
                if not self.should_exclude(file_path):
                    files.append(file_path)
        
        return files
    
    def get_file_info(self, file_path: Path) -> Dict[str, Any]:
        """Получает базовую информацию о файле."""
        try:
            stat = file_path.stat()
            
            # Попытка прочитать содержимое для превью
            content_preview = ""
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content_preview = f.read(500)  # Первые 500 символов
            except Exception:
                try:
                    with open(file_path, 'r', encoding='latin-1') as f:
                        content_preview = f.read(500)
                except Exception:
                    content_preview = "[Binary file or encoding error]"
            
            return {
                'path': str(file_path.relative_to(self.root_path)),
                'name': file_path.name,
                'extension': file_path.suffix.lower(),
                'size': stat.st_size,
                'last_modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'content_preview': content_preview
            }
        except Exception as e:
            self.logger.error(f"Error getting info for {file_path}: {e}")
            return {
                'path': str(file_path.relative_to(self.root_path)),
                'name': file_path.name,
                'extension': file_path.suffix.lower(),
                'size': 0,
                'last_modified': datetime.now().isoformat(),
                'content_preview': f"[Error reading file: {e}]"
            }

class FileClassifier:
    """Классифицирует файлы по типам и категориям."""
    
    def __init__(self):
        self.categories = {
            'source_code': {
                'extensions': ['.py'],
                'subcategories': {
                    'api_clients': ['client', 'api'],
                    'auth': ['auth', 'token', 'jwt'],
                    'monitoring': ['monitor', 'health', 'alert', 'log'],
                    'security': ['security', 'encrypt', 'hash'],
                    'services': ['service', 'egress', 'ingress'],
                    'integration': ['integration', 'webhook'],
                    'config': ['config', 'setting'],
                    'main': ['main', 'app', 'server'],
                    'utils': ['util', 'helper', 'tool']
                }
            },
            'tests': {
                'extensions': ['.py'],
                'patterns': ['test_*.py', '*_test.py', 'conftest.py', 'pytest.ini'],
                'subcategories': {
                    'unit': ['test_'],
                    'integration': ['integration', 'flow'],
                    'load': ['load', 'performance', 'stress'],
                    'security': ['security'],
                    'validation': ['validation', 'verify']
                }
            },
            'config': {
                'extensions': ['.yaml', '.yml', '.json', '.env', '.ini', '.toml'],
                'subcategories': {
                    'deployment': ['deploy', 'docker', 'k8s'],
                    'monitoring': ['monitor', 'alert'],
                    'security': ['security', 'auth'],
                    'performance': ['performance', 'retry'],
                    'main': ['config', 'setting']
                }
            },
            'docs': {
                'extensions': ['.md', '.rst', '.txt'],
                'subcategories': {
                    'guides': ['guide', 'setup', 'install'],
                    'api_docs': ['api', 'endpoint'],
                    'examples': ['example', 'sample'],
                    'reports': ['report', 'summary'],
                    'architecture': ['architecture', 'design']
                }
            },
            'scripts': {
                'extensions': ['.py', '.sh', '.bash'],
                'patterns': ['scripts/*'],
                'subcategories': {
                    'deployment': ['deploy', 'migrate', 'rollback'],
                    'validation': ['validate', 'test', 'check'],
                    'utilities': ['util', 'tool', 'helper'],
                    'automation': ['auto', 'run']
                }
            }
        }
    
    def classify_file(self, file_info: Dict[str, Any]) -> tuple:
        """Классифицирует файл и возвращает категорию и подкатегорию."""
        path = file_info['path']
        name = file_info['name'].lower()
        extension = file_info['extension']
        content = file_info['content_preview'].lower()
        
        # Специальная обработка для тестов
        if self._is_test_file(path, name):
            subcategory = self._get_test_subcategory(name, content)
            return 'tests', subcategory
        
        # Специальная обработка для скриптов
        if path.startswith('scripts/'):
            subcategory = self._get_script_subcategory(name, content)
            return 'scripts', subcategory
        
        # Классификация по расширению и содержимому
        for category, config in self.categories.items():
            if extension in config.get('extensions', []):
                if category == 'tests':  # Уже обработано выше
                    continue
                
                subcategory = self._get_subcategory(category, name, content, path)
                return category, subcategory
        
        # Неклассифицированные файлы
        return 'other', 'unknown'
    
    def _is_test_file(self, path: str, name: str) -> bool:
        """Проверяет, является ли файл тестом."""
        return (name.startswith('test_') or 
                name.endswith('_test.py') or 
                name == 'conftest.py' or
                'test' in path.split('/'))
    
    def _get_test_subcategory(self, name: str, content: str) -> str:
        """Определяет подкатегорию теста."""
        if 'load' in name or 'performance' in name or 'stress' in name:
            return 'load'
        elif 'integration' in name or 'flow' in name:
            return 'integration'
        elif 'security' in name:
            return 'security'
        elif 'validation' in name or 'verify' in name:
            return 'validation'
        else:
            return 'unit'
    
    def _get_script_subcategory(self, name: str, content: str) -> str:
        """Определяет подкатегорию скрипта."""
        if any(word in name for word in ['deploy', 'migrate', 'rollback']):
            return 'deployment'
        elif any(word in name for word in ['validate', 'test', 'check']):
            return 'validation'
        elif any(word in name for word in ['run', 'auto']):
            return 'automation'
        else:
            return 'utilities'
    
    def _get_subcategory(self, category: str, name: str, content: str, path: str) -> str:
        """Определяет подкатегорию для файла."""
        subcategories = self.categories[category].get('subcategories', {})
        
        for subcategory, keywords in subcategories.items():
            if any(keyword in name or keyword in path for keyword in keywords):
                return subcategory
        
        return 'main'

class SyntaxAnalyzer:
    """Анализирует синтаксис файлов."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def analyze_python_file(self, file_path: Path) -> Dict[str, Any]:
        """Анализирует Python файл."""
        result = {
            'syntax_valid': False,
            'imports': [],
            'issues': [],
            'functions': 0,
            'classes': 0,
            'lines': 0
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Подсчет строк
            result['lines'] = len(content.splitlines())
            
            # Парсинг AST
            tree = ast.parse(content)
            result['syntax_valid'] = True
            
            # Анализ AST
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        result['imports'].append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        result['imports'].append(node.module)
                elif isinstance(node, ast.FunctionDef):
                    result['functions'] += 1
                elif isinstance(node, ast.ClassDef):
                    result['classes'] += 1
            
            # Поиск TODO/FIXME комментариев
            for line_num, line in enumerate(content.splitlines(), 1):
                line_lower = line.lower()
                if any(marker in line_lower for marker in ['todo', 'fixme', 'xxx', 'hack']):
                    result['issues'].append(f"Line {line_num}: {line.strip()}")
            
        except SyntaxError as e:
            result['issues'].append(f"Syntax error: {e}")
        except Exception as e:
            result['issues'].append(f"Analysis error: {e}")
        
        return result
    
    def analyze_yaml_file(self, file_path: Path) -> Dict[str, Any]:
        """Анализирует YAML файл."""
        result = {
            'syntax_valid': False,
            'issues': [],
            'keys': []
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            result['syntax_valid'] = True
            
            if isinstance(data, dict):
                result['keys'] = list(data.keys())
            
        except yaml.YAMLError as e:
            result['issues'].append(f"YAML error: {e}")
        except Exception as e:
            result['issues'].append(f"Analysis error: {e}")
        
        return result
    
    def analyze_json_file(self, file_path: Path) -> Dict[str, Any]:
        """Анализирует JSON файл."""
        result = {
            'syntax_valid': False,
            'issues': [],
            'keys': []
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            result['syntax_valid'] = True
            
            if isinstance(data, dict):
                result['keys'] = list(data.keys())
            
        except json.JSONDecodeError as e:
            result['issues'].append(f"JSON error: {e}")
        except Exception as e:
            result['issues'].append(f"Analysis error: {e}")
        
        return result

class QualityAssessor:
    """Оценивает качество файлов."""
    
    def assess_file_quality(self, file_info: Dict[str, Any], analysis_result: Dict[str, Any]) -> float:
        """Оценивает качество файла (0-1)."""
        score = 1.0
        
        # Штраф за синтаксические ошибки
        if not analysis_result.get('syntax_valid', True):
            score -= 0.5
        
        # Штраф за проблемы
        issues_count = len(analysis_result.get('issues', []))
        score -= min(0.3, issues_count * 0.05)
        
        # Бонус за документацию
        if file_info['extension'] == '.py':
            lines = analysis_result.get('lines', 0)
            if lines > 0:
                # Бонус за разумный размер файла
                if 50 <= lines <= 500:
                    score += 0.1
                elif lines > 1000:
                    score -= 0.1
        
        return max(0.0, min(1.0, score))

class ProjectClassifier:
    """Главный класс для классификации проекта."""
    
    def __init__(self, root_path: str = "."):
        self.root_path = Path(root_path)
        self.scanner = FileScanner(root_path)
        self.classifier = FileClassifier()
        self.syntax_analyzer = SyntaxAnalyzer()
        self.quality_assessor = QualityAssessor()
        self.logger = self._setup_logging()
    
    def _setup_logging(self) -> logging.Logger:
        """Настройка логирования."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(__name__)
    
    def classify_project(self) -> Dict[str, Any]:
        """Классифицирует весь проект."""
        self.logger.info("Начало классификации проекта...")
        start_time = time.time()
        
        # Сканирование файлов
        files = self.scanner.scan_project()
        self.logger.info(f"Найдено {len(files)} файлов")
        
        classified_files = []
        categories_stats = {}
        total_issues = 0
        
        for file_path in files:
            try:
                # Получение базовой информации
                file_info = self.scanner.get_file_info(file_path)
                
                # Классификация
                category, subcategory = self.classifier.classify_file(file_info)
                
                # Анализ синтаксиса
                analysis_result = self._analyze_file_syntax(file_path)
                
                # Оценка качества
                quality_score = self.quality_assessor.assess_file_quality(file_info, analysis_result)
                
                # Определение статуса
                status = self._determine_file_status(analysis_result, quality_score)
                
                # Создание объекта FileInfo
                classified_file = FileInfo(
                    path=file_info['path'],
                    name=file_info['name'],
                    extension=file_info['extension'],
                    size=file_info['size'],
                    category=category,
                    subcategory=subcategory,
                    status=status,
                    syntax_valid=analysis_result.get('syntax_valid', True),
                    dependencies=analysis_result.get('imports', []),
                    issues=analysis_result.get('issues', []),
                    quality_score=quality_score,
                    last_modified=file_info['last_modified'],
                    content_preview=file_info['content_preview'][:200]
                )
                
                classified_files.append(classified_file)
                
                # Статистика
                if category not in categories_stats:
                    categories_stats[category] = {}
                if subcategory not in categories_stats[category]:
                    categories_stats[category][subcategory] = 0
                categories_stats[category][subcategory] += 1
                
                total_issues += len(classified_file.issues)
                
            except Exception as e:
                self.logger.error(f"Ошибка обработки файла {file_path}: {e}")
        
        duration = time.time() - start_time
        
        # Генерация отчета
        report = self._generate_report(classified_files, categories_stats, total_issues, duration)
        
        self.logger.info(f"Классификация завершена за {duration:.2f} секунд")
        return report
    
    def _analyze_file_syntax(self, file_path: Path) -> Dict[str, Any]:
        """Анализирует синтаксис файла в зависимости от типа."""
        extension = file_path.suffix.lower()
        
        if extension == '.py':
            return self.syntax_analyzer.analyze_python_file(file_path)
        elif extension in ['.yaml', '.yml']:
            return self.syntax_analyzer.analyze_yaml_file(file_path)
        elif extension == '.json':
            return self.syntax_analyzer.analyze_json_file(file_path)
        else:
            return {'syntax_valid': True, 'issues': [], 'imports': []}
    
    def _determine_file_status(self, analysis_result: Dict[str, Any], quality_score: float) -> str:
        """Определяет статус файла."""
        if not analysis_result.get('syntax_valid', True):
            return 'error'
        elif quality_score < 0.5:
            return 'incomplete'
        elif len(analysis_result.get('issues', [])) > 0:
            return 'incomplete'
        else:
            return 'ready'
    
    def _generate_report(self, files: List[FileInfo], categories_stats: Dict, total_issues: int, duration: float) -> Dict[str, Any]:
        """Генерирует итоговый отчет."""
        total_files = len(files)
        ready_files = sum(1 for f in files if f.status == 'ready')
        error_files = sum(1 for f in files if f.status == 'error')
        avg_quality = sum(f.quality_score for f in files) / total_files if total_files > 0 else 0
        
        return {
            "classification_summary": {
                "timestamp": datetime.now().isoformat(),
                "duration_seconds": round(duration, 2),
                "total_files": total_files,
                "ready_files": ready_files,
                "error_files": error_files,
                "incomplete_files": total_files - ready_files - error_files,
                "total_issues": total_issues,
                "average_quality_score": round(avg_quality, 3),
                "categories_distribution": categories_stats
            },
            "files": [asdict(f) for f in files],
            "recommendations": self._generate_recommendations(files, categories_stats)
        }
    
    def _generate_recommendations(self, files: List[FileInfo], categories_stats: Dict) -> List[str]:
        """Генерирует рекомендации по улучшению проекта."""
        recommendations = []
        
        error_files = [f for f in files if f.status == 'error']
        if error_files:
            recommendations.append(f"Исправить синтаксические ошибки в {len(error_files)} файлах")
        
        incomplete_files = [f for f in files if f.status == 'incomplete']
        if incomplete_files:
            recommendations.append(f"Доработать {len(incomplete_files)} незавершенных файлов")
        
        files_with_todos = [f for f in files if any('todo' in issue.lower() for issue in f.issues)]
        if files_with_todos:
            recommendations.append(f"Обработать TODO комментарии в {len(files_with_todos)} файлах")
        
        # Проверка покрытия тестами
        source_files = sum(categories_stats.get('source_code', {}).values())
        test_files = sum(categories_stats.get('tests', {}).values())
        if source_files > 0 and test_files / source_files < 0.5:
            recommendations.append("Увеличить покрытие тестами - мало тестовых файлов")
        
        if not recommendations:
            recommendations.append("Проект в хорошем состоянии!")
        
        return recommendations

def main():
    """Главная функция."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Классификация файлов проекта LiveKit')
    parser.add_argument('--path', default='.', help='Путь к проекту (по умолчанию: текущая директория)')
    parser.add_argument('--output', default='project_classification_report.json', help='Файл для сохранения отчета')
    
    args = parser.parse_args()
    
    # Классификация проекта
    classifier = ProjectClassifier(args.path)
    report = classifier.classify_project()
    
    # Сохранение отчета
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    # Вывод краткой статистики
    summary = report['classification_summary']
    print("\n" + "="*60)
    print("📊 ОТЧЕТ ПО КЛАССИФИКАЦИИ ПРОЕКТА")
    print("="*60)
    print(f"Всего файлов: {summary['total_files']}")
    print(f"Готовых файлов: {summary['ready_files']}")
    print(f"Файлов с ошибками: {summary['error_files']}")
    print(f"Незавершенных файлов: {summary['incomplete_files']}")
    print(f"Всего проблем: {summary['total_issues']}")
    print(f"Средняя оценка качества: {summary['average_quality_score']}")
    print(f"Время анализа: {summary['duration_seconds']} сек")
    
    print("\n📋 РАСПРЕДЕЛЕНИЕ ПО КАТЕГОРИЯМ:")
    for category, subcategories in summary['categories_distribution'].items():
        total_in_category = sum(subcategories.values())
        print(f"  {category}: {total_in_category}")
        for subcategory, count in subcategories.items():
            print(f"    - {subcategory}: {count}")
    
    print("\n💡 РЕКОМЕНДАЦИИ:")
    for i, rec in enumerate(report['recommendations'], 1):
        print(f"  {i}. {rec}")
    
    print(f"\n📄 Полный отчет сохранен в {args.output}")

if __name__ == "__main__":
    main()