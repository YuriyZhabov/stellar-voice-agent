#!/usr/bin/env python3
"""
Классификатор файлов проекта LiveKit.
Реализует систему категоризации файлов по расширениям и содержимому.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass
import logging


@dataclass
class FileInfo:
    """Информация о файле для классификации."""
    path: str
    name: str
    extension: str
    size: int
    category: str
    subcategory: str
    status: str
    syntax_valid: bool
    dependencies: List[str]
    issues: List[str]
    quality_score: float
    last_modified: str


class FileClassifier:
    """
    Классификатор файлов проекта.
    Реализует категоризацию по расширениям и анализ содержимого.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._init_classification_rules()
    
    def _init_classification_rules(self):
        """Инициализация правил классификации."""
        
        # Основные категории файлов
        self.categories = {
            'source_code': {
                'extensions': {'.py'},
                'description': 'Исходный код Python'
            },
            'tests': {
                'extensions': {'.py'},
                'description': 'Тестовые файлы'
            },
            'config': {
                'extensions': {'.yaml', '.yml', '.json', '.env', '.ini', '.toml', '.conf'},
                'description': 'Конфигурационные файлы'
            },
            'docs': {
                'extensions': {'.md', '.rst', '.txt', '.adoc'},
                'description': 'Документация'
            },
            'scripts': {
                'extensions': {'.py', '.sh', '.bash', '.bat', '.ps1'},
                'description': 'Скрипты и утилиты'
            },
            'data': {
                'extensions': {'.db', '.sqlite', '.sqlite3', '.sql'},
                'description': 'Файлы данных'
            },
            'web': {
                'extensions': {'.html', '.css', '.js', '.ts', '.jsx', '.tsx'},
                'description': 'Веб-файлы'
            },
            'other': {
                'extensions': set(),
                'description': 'Прочие файлы'
            }
        }
        
        # Подкатегории для исходного кода
        self.source_code_subcategories = {
            'api_clients': {
                'keywords': ['client', 'api', 'rest', 'http'],
                'path_patterns': ['clients/', 'api/'],
                'description': 'API клиенты'
            },
            'auth': {
                'keywords': ['auth', 'token', 'jwt', 'login', 'oauth'],
                'path_patterns': ['auth/', 'authentication/'],
                'description': 'Аутентификация и авторизация'
            },
            'monitoring': {
                'keywords': ['monitor', 'health', 'alert', 'metric', 'prometheus'],
                'path_patterns': ['monitoring/', 'metrics/'],
                'description': 'Мониторинг и метрики'
            },
            'security': {
                'keywords': ['security', 'encrypt', 'hash', 'crypto', 'ssl'],
                'path_patterns': ['security/', 'crypto/'],
                'description': 'Безопасность'
            },
            'services': {
                'keywords': ['service', 'egress', 'ingress'],
                'path_patterns': ['services/', 'handlers/'],
                'description': 'Сервисы и обработчики'
            },
            'integration': {
                'keywords': ['integration', 'webhook', 'livekit'],
                'path_patterns': ['integration/', 'webhooks/'],
                'description': 'Интеграции'
            },
            'config': {
                'keywords': ['config', 'setting', 'loader'],
                'path_patterns': ['config/'],
                'description': 'Конфигурация'
            },
            'database': {
                'keywords': ['database', 'db', 'model', 'repository', 'migration'],
                'path_patterns': ['database/', 'models/', 'db/'],
                'description': 'База данных'
            },
            'middleware': {
                'keywords': ['middleware', 'decorator', 'wrapper'],
                'path_patterns': ['middleware/'],
                'description': 'Промежуточное ПО'
            },
            'main': {
                'keywords': ['main', 'app', 'server', 'orchestrator'],
                'path_patterns': [],
                'description': 'Основные модули'
            }
        }
        
        # Подкатегории для тестов
        self.test_subcategories = {
            'integration': {
                'keywords': ['integration', 'flow', 'e2e'],
                'patterns': ['*integration*.py', '*flow*.py'],
                'description': 'Интеграционные тесты'
            },
            'load': {
                'keywords': ['load', 'performance', 'stress', 'benchmark'],
                'patterns': ['*load*.py', '*performance*.py'],
                'description': 'Нагрузочные тесты'
            },
            'security': {
                'keywords': ['security', 'auth', 'validation'],
                'patterns': ['*security*.py', '*auth*.py'],
                'description': 'Тесты безопасности'
            },
            'config': {
                'keywords': ['conftest', 'fixture', 'config'],
                'patterns': ['conftest.py', 'pytest.ini'],
                'description': 'Конфигурация тестов'
            },
            'unit': {
                'keywords': ['test_', 'unit'],
                'patterns': ['test_*.py'],
                'description': 'Модульные тесты'
            }
        }
        
        # Подкатегории для конфигурационных файлов
        self.config_subcategories = {
            'deployment': {
                'keywords': ['deploy', 'docker', 'compose', 'k8s', 'kubernetes'],
                'patterns': ['docker-compose*.yml', 'Dockerfile*', '*.k8s.yaml'],
                'description': 'Развертывание'
            },
            'monitoring': {
                'keywords': ['prometheus', 'grafana', 'alert', 'monitor'],
                'patterns': ['prometheus*.yml', 'grafana*.json'],
                'description': 'Мониторинг'
            },
            'security': {
                'keywords': ['security', 'auth', 'ssl', 'cert'],
                'patterns': ['*security*.yaml', '*auth*.yml'],
                'description': 'Безопасность'
            },
            'performance': {
                'keywords': ['performance', 'retry', 'timeout'],
                'patterns': ['*performance*.yaml', '*retry*.yml'],
                'description': 'Производительность'
            },
            'livekit': {
                'keywords': ['livekit', 'sip', 'webrtc'],
                'patterns': ['livekit*.yaml', '*sip*.yml'],
                'description': 'LiveKit конфигурация'
            },
            'environment': {
                'keywords': ['env', 'environment', 'production'],
                'patterns': ['.env*', '*.env'],
                'description': 'Переменные окружения'
            },
            'main': {
                'keywords': ['config', 'setting'],
                'patterns': [],
                'description': 'Основная конфигурация'
            }
        }
        
        # Подкатегории для документации (порядок важен - более специфичные первыми)
        self.docs_subcategories = {
            'troubleshooting': {
                'keywords': ['troubleshoot', 'debug', 'problem', 'issue'],
                'patterns': ['*troubleshoot*.md', '*debug*.md'],
                'description': 'Устранение неполадок'
            },
            'api_docs': {
                'keywords': ['api', 'endpoint', 'reference'],
                'patterns': ['*api*.md', '*reference*.md'],
                'description': 'API документация'
            },
            'architecture': {
                'keywords': ['architecture', 'design', 'diagram'],
                'patterns': ['*architecture*.md', '*design*.md'],
                'description': 'Архитектура'
            },
            'examples': {
                'keywords': ['example', 'sample', 'demo'],
                'patterns': ['*example*.md', '*sample*.md'],
                'description': 'Примеры'
            },
            'reports': {
                'keywords': ['report', 'summary', 'implementation'],
                'patterns': ['*REPORT*.md', '*SUMMARY*.md'],
                'description': 'Отчеты'
            },
            'guides': {
                'keywords': ['guide', 'setup', 'install', 'tutorial', 'howto'],
                'patterns': ['*guide*.md', '*setup*.md', '*install*.md'],
                'description': 'Руководства'
            },
            'main': {
                'keywords': ['readme', 'doc', 'documentation'],
                'patterns': ['README*.md', 'CONTRIBUTING*.md'],
                'description': 'Основная документация'
            }
        }
        
        # Подкатегории для скриптов
        self.script_subcategories = {
            'deployment': {
                'keywords': ['deploy', 'migrate', 'rollback', 'setup'],
                'patterns': ['deploy*.py', '*migrate*.py', 'setup*.py'],
                'description': 'Развертывание'
            },
            'validation': {
                'keywords': ['validate', 'check', 'verify'],
                'patterns': ['validate*.py', 'check*.py'],
                'description': 'Валидация'
            },
            'monitoring': {
                'keywords': ['monitor', 'health', 'watch', 'diagnose'],
                'patterns': ['monitor*.py', 'health*.py', 'watch*.py'],
                'description': 'Мониторинг'
            },
            'utilities': {
                'keywords': ['util', 'tool', 'helper', 'fix'],
                'patterns': ['util*.py', 'tool*.py', 'fix*.py'],
                'description': 'Утилиты'
            },
            'automation': {
                'keywords': ['run', 'auto', 'comprehensive', 'test'],
                'patterns': ['run*.py', 'auto*.py'],
                'description': 'Автоматизация'
            }
        }
    
    def classify_file(self, file_path: str, content_preview: str = "") -> Tuple[str, str]:
        """
        Классифицирует файл и возвращает категорию и подкатегорию.
        
        Args:
            file_path: Путь к файлу
            content_preview: Превью содержимого файла
            
        Returns:
            Tuple[str, str]: (категория, подкатегория)
        """
        path = Path(file_path)
        name = path.name.lower()
        extension = path.suffix.lower()
        path_str = str(path).lower()
        content_lower = content_preview.lower()
        
        # Определение основной категории
        category = self._determine_category(path, extension, name, path_str)
        
        # Определение подкатегории
        subcategory = self._determine_subcategory(category, path, name, path_str, content_lower)
        
        self.logger.debug(f"Classified {file_path} as {category}/{subcategory}")
        
        return category, subcategory
    
    def _determine_category(self, path: Path, extension: str, name: str, path_str: str) -> str:
        """Определяет основную категорию файла."""
        
        # Специальные случаи по имени файла (высший приоритет)
        special_files = {
            'dockerfile': 'config',
            'makefile': 'scripts',
            'requirements.txt': 'config',
            'pyproject.toml': 'config',
            'setup.py': 'scripts'
        }
        
        for special_name, special_category in special_files.items():
            if special_name == name or special_name in name:
                return special_category
        
        # Обработка .env файлов
        if name.startswith('.env') or name.endswith('.env'):
            return 'config'
        
        # Специальная обработка для тестов
        if self._is_test_file(path, name, path_str):
            return 'tests'
        
        # Специальная обработка для скриптов в папке scripts/
        if 'scripts/' in path_str and extension in {'.py', '.sh', '.bash'}:
            return 'scripts'
        
        # Классификация по расширению
        for category, config in self.categories.items():
            if extension in config['extensions']:
                return category
        
        return 'other'
    
    def _is_test_file(self, path: Path, name: str, path_str: str) -> bool:
        """Проверяет, является ли файл тестом."""
        # Проверка по имени файла
        test_patterns = [
            name.startswith('test_'),
            name.endswith('_test.py'),
            name == 'conftest.py',
            name == 'pytest.ini'
        ]
        
        if any(test_patterns):
            return True
        
        # Проверка по пути
        test_path_indicators = ['test', 'tests']
        path_parts = path_str.split('/')
        
        return any(indicator in path_parts for indicator in test_path_indicators)
    
    def _determine_subcategory(self, category: str, path: Path, name: str, 
                             path_str: str, content: str) -> str:
        """Определяет подкатегорию файла."""
        
        subcategory_map = {
            'source_code': self.source_code_subcategories,
            'tests': self.test_subcategories,
            'config': self.config_subcategories,
            'docs': self.docs_subcategories,
            'scripts': self.script_subcategories
        }
        
        if category not in subcategory_map:
            return 'main'
        
        subcategories = subcategory_map[category]
        
        # Проверка по паттернам пути (приоритет выше)
        for subcategory, config in subcategories.items():
            path_patterns = config.get('path_patterns', [])
            if any(pattern in path_str for pattern in path_patterns):
                return subcategory
        
        # Проверка по паттернам файлов
        for subcategory, config in subcategories.items():
            patterns = config.get('patterns', [])
            for pattern in patterns:
                if self._match_pattern(name, pattern):
                    return subcategory
        
        # Проверка по ключевым словам в имени файла
        for subcategory, config in subcategories.items():
            keywords = config.get('keywords', [])
            if any(keyword in name for keyword in keywords):
                return subcategory
        
        # Проверка по содержимому (для Python файлов)
        if category == 'source_code' and content:
            return self._classify_by_content(content)
        
        return 'main'
    
    def _match_pattern(self, filename: str, pattern: str) -> bool:
        """Проверяет соответствие имени файла паттерну."""
        import fnmatch
        return fnmatch.fnmatch(filename, pattern)
    
    def _classify_by_content(self, content: str) -> str:
        """Классифицирует Python файл по содержимому."""
        content_indicators = {
            'api_clients': ['requests', 'http', 'client', 'api'],
            'auth': ['jwt', 'token', 'authenticate', 'login'],
            'monitoring': ['prometheus', 'metrics', 'health', 'alert'],
            'security': ['encrypt', 'hash', 'security', 'crypto'],
            'services': ['service', 'handler', 'processor'],
            'integration': ['webhook', 'livekit', 'integration'],
            'database': ['sqlalchemy', 'database', 'model', 'repository'],
            'config': ['config', 'settings', 'environment']
        }
        
        for subcategory, indicators in content_indicators.items():
            if any(indicator in content for indicator in indicators):
                return subcategory
        
        return 'main'
    
    def get_category_info(self, category: str) -> Dict:
        """Возвращает информацию о категории."""
        return self.categories.get(category, {})
    
    def get_subcategory_info(self, category: str, subcategory: str) -> Dict:
        """Возвращает информацию о подкатегории."""
        subcategory_map = {
            'source_code': self.source_code_subcategories,
            'tests': self.test_subcategories,
            'config': self.config_subcategories,
            'docs': self.docs_subcategories,
            'scripts': self.script_subcategories
        }
        
        if category in subcategory_map:
            return subcategory_map[category].get(subcategory, {})
        
        return {}
    
    def get_all_categories(self) -> List[str]:
        """Возвращает список всех категорий."""
        return list(self.categories.keys())
    
    def get_subcategories(self, category: str) -> List[str]:
        """Возвращает список подкатегорий для категории."""
        subcategory_map = {
            'source_code': self.source_code_subcategories,
            'tests': self.test_subcategories,
            'config': self.config_subcategories,
            'docs': self.docs_subcategories,
            'scripts': self.script_subcategories
        }
        
        if category in subcategory_map:
            return list(subcategory_map[category].keys())
        
        return ['main']
    
    def validate_classification(self, file_path: str, category: str, subcategory: str) -> bool:
        """Валидирует корректность классификации."""
        if category not in self.categories:
            return False
        
        valid_subcategories = self.get_subcategories(category)
        return subcategory in valid_subcategories


# Специализированные классификаторы для разных типов файлов

class PythonFileClassifier:
    """Специализированный классификатор для Python файлов."""
    
    def __init__(self):
        self.test_indicators = [
            'test_', '_test.py', 'conftest.py', 'pytest',
            'unittest', 'mock', 'fixture'
        ]
        
        self.module_types = {
            'client': ['client', 'api', 'http', 'rest'],
            'service': ['service', 'handler', 'processor'],
            'model': ['model', 'schema', 'entity'],
            'config': ['config', 'settings', 'env'],
            'util': ['util', 'helper', 'tool'],
            'main': ['main', 'app', 'server']
        }
    
    def classify_python_file(self, file_path: str, content: str) -> Tuple[str, str]:
        """Классифицирует Python файл."""
        path = Path(file_path)
        name = path.name.lower()
        
        # Проверка на тест
        if any(indicator in name for indicator in self.test_indicators):
            return 'tests', self._classify_test_type(name, content)
        
        # Классификация по типу модуля
        for module_type, keywords in self.module_types.items():
            if any(keyword in name for keyword in keywords):
                return 'source_code', module_type
        
        return 'source_code', 'main'
    
    def _classify_test_type(self, name: str, content: str) -> str:
        """Определяет тип теста."""
        if 'integration' in name or 'flow' in name:
            return 'integration'
        elif 'load' in name or 'performance' in name:
            return 'load'
        elif 'security' in name:
            return 'security'
        elif 'conftest' in name:
            return 'config'
        else:
            return 'unit'


class ConfigFileClassifier:
    """Специализированный классификатор для конфигурационных файлов."""
    
    def __init__(self):
        self.config_types = {
            'deployment': ['docker', 'compose', 'k8s', 'deploy'],
            'monitoring': ['prometheus', 'grafana', 'alert'],
            'security': ['auth', 'ssl', 'cert', 'security'],
            'livekit': ['livekit', 'sip', 'webrtc'],
            'environment': ['env', 'environment']
        }
    
    def classify_config_file(self, file_path: str, content: str) -> str:
        """Классифицирует конфигурационный файл."""
        name = Path(file_path).name.lower()
        
        for config_type, keywords in self.config_types.items():
            if any(keyword in name for keyword in keywords):
                return config_type
        
        return 'main'


class DocumentationClassifier:
    """Специализированный классификатор для документации."""
    
    def __init__(self):
        # Порядок важен - более специфичные первыми
        self.doc_types = {
            'troubleshooting': ['troubleshoot', 'debug', 'problem'],
            'api_docs': ['api', 'reference', 'endpoint'],
            'architecture': ['architecture', 'design', 'diagram'],
            'examples': ['example', 'sample', 'demo'],
            'reports': ['report', 'summary', 'implementation'],
            'guides': ['guide', 'tutorial', 'howto', 'setup']
        }
    
    def classify_documentation(self, file_path: str, content: str) -> str:
        """Классифицирует документацию."""
        name = Path(file_path).name.lower()
        
        # Специальные файлы
        if name.startswith('readme'):
            return 'main'
        elif name.startswith('contributing'):
            return 'guides'
        
        # Проверка по ключевым словам (более точное совпадение)
        for doc_type, keywords in self.doc_types.items():
            for keyword in keywords:
                if keyword in name:
                    return doc_type
        
        return 'main'