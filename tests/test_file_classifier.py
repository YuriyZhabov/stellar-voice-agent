#!/usr/bin/env python3
"""
Тесты для классификатора файлов проекта.
"""

import pytest
import sys
import os
from pathlib import Path

# Добавляем src в путь для импорта
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from classification.file_classifier import (
    FileClassifier,
    PythonFileClassifier,
    ConfigFileClassifier,
    DocumentationClassifier
)


class TestFileClassifier:
    """Тесты основного классификатора файлов."""
    
    def setup_method(self):
        """Настройка перед каждым тестом."""
        self.classifier = FileClassifier()
    
    def test_python_source_code_classification(self):
        """Тест классификации исходного кода Python."""
        test_cases = [
            ('src/clients/livekit_client.py', 'source_code', 'api_clients'),
            ('src/auth/livekit_auth.py', 'source_code', 'auth'),
            ('src/monitoring/health_monitor.py', 'source_code', 'monitoring'),
            ('src/security/encryption.py', 'source_code', 'security'),
            ('src/services/egress_service.py', 'source_code', 'services'),
            ('src/integration/webhook_handler.py', 'source_code', 'integration'),
            ('src/config/settings.py', 'source_code', 'config'),
            ('src/database/models.py', 'source_code', 'database'),
            ('src/middleware/auth_middleware.py', 'source_code', 'middleware'),
            ('src/main.py', 'source_code', 'main'),
        ]
        
        for file_path, expected_category, expected_subcategory in test_cases:
            category, subcategory = self.classifier.classify_file(file_path)
            assert category == expected_category, f"Wrong category for {file_path}: {category} != {expected_category}"
            assert subcategory == expected_subcategory, f"Wrong subcategory for {file_path}: {subcategory} != {expected_subcategory}"
    
    def test_test_files_classification(self):
        """Тест классификации тестовых файлов."""
        test_cases = [
            ('tests/test_client.py', 'tests', 'unit'),
            ('tests/test_integration_flow.py', 'tests', 'integration'),
            ('tests/test_load_testing.py', 'tests', 'load'),
            ('tests/test_security_validation.py', 'tests', 'security'),
            ('tests/conftest.py', 'tests', 'config'),
            ('test_performance.py', 'tests', 'load'),
            ('integration_test.py', 'tests', 'integration'),
        ]
        
        for file_path, expected_category, expected_subcategory in test_cases:
            category, subcategory = self.classifier.classify_file(file_path)
            assert category == expected_category, f"Wrong category for {file_path}: {category} != {expected_category}"
            assert subcategory == expected_subcategory, f"Wrong subcategory for {file_path}: {subcategory} != {expected_subcategory}"
    
    def test_config_files_classification(self):
        """Тест классификации конфигурационных файлов."""
        test_cases = [
            ('docker-compose.yml', 'config', 'deployment'),
            ('prometheus.yml', 'config', 'monitoring'),
            ('livekit-sip.yaml', 'config', 'livekit'),
            ('.env.production', 'config', 'environment'),
            ('security.yaml', 'config', 'security'),
            ('performance.yaml', 'config', 'performance'),
            ('config.json', 'config', 'main'),
        ]
        
        for file_path, expected_category, expected_subcategory in test_cases:
            category, subcategory = self.classifier.classify_file(file_path)
            assert category == expected_category, f"Wrong category for {file_path}: {category} != {expected_category}"
            assert subcategory == expected_subcategory, f"Wrong subcategory for {file_path}: {subcategory} != {expected_subcategory}"
    
    def test_documentation_classification(self):
        """Тест классификации документации."""
        test_cases = [
            ('README.md', 'docs', 'main'),
            ('docs/setup_guide.md', 'docs', 'guides'),
            ('docs/api_reference.md', 'docs', 'api_docs'),
            ('examples/client_example.md', 'docs', 'examples'),
            ('IMPLEMENTATION_REPORT.md', 'docs', 'reports'),
            ('docs/architecture_diagram.md', 'docs', 'architecture'),
            ('docs/troubleshooting_guide.md', 'docs', 'troubleshooting'),
        ]
        
        for file_path, expected_category, expected_subcategory in test_cases:
            category, subcategory = self.classifier.classify_file(file_path)
            assert category == expected_category, f"Wrong category for {file_path}: {category} != {expected_category}"
            assert subcategory == expected_subcategory, f"Wrong subcategory for {file_path}: {subcategory} != {expected_subcategory}"
    
    def test_script_files_classification(self):
        """Тест классификации скриптов."""
        test_cases = [
            ('scripts/deploy_production.py', 'scripts', 'deployment'),
            ('scripts/validate_config.py', 'scripts', 'validation'),
            ('scripts/monitor_health.py', 'scripts', 'monitoring'),
            ('scripts/fix_database.py', 'scripts', 'utilities'),
            ('scripts/run_tests.py', 'scripts', 'automation'),
        ]
        
        for file_path, expected_category, expected_subcategory in test_cases:
            category, subcategory = self.classifier.classify_file(file_path)
            assert category == expected_category, f"Wrong category for {file_path}: {category} != {expected_category}"
            assert subcategory == expected_subcategory, f"Wrong subcategory for {file_path}: {subcategory} != {expected_subcategory}"
    
    def test_special_files_classification(self):
        """Тест классификации специальных файлов."""
        test_cases = [
            ('Dockerfile', 'config', 'deployment'),
            ('Makefile', 'scripts', 'automation'),
            ('requirements.txt', 'config', 'main'),
            ('pyproject.toml', 'config', 'main'),
            ('setup.py', 'scripts', 'deployment'),
            ('data/voice_ai.db', 'data', 'main'),
        ]
        
        for file_path, expected_category, expected_subcategory in test_cases:
            category, subcategory = self.classifier.classify_file(file_path)
            assert category == expected_category, f"Wrong category for {file_path}: {category} != {expected_category}"
    
    def test_content_based_classification(self):
        """Тест классификации на основе содержимого."""
        # Тест для Python файла с содержимым
        content = """
import requests
from livekit import api

class LiveKitClient:
    def __init__(self):
        self.api_key = "test"
    
    def make_request(self):
        return requests.get("http://api.example.com")
        """
        
        category, subcategory = self.classifier.classify_file('src/unknown.py', content)
        assert category == 'source_code'
        assert subcategory == 'api_clients'
    
    def test_get_category_info(self):
        """Тест получения информации о категории."""
        info = self.classifier.get_category_info('source_code')
        assert 'extensions' in info
        assert 'description' in info
        assert '.py' in info['extensions']
    
    def test_get_subcategory_info(self):
        """Тест получения информации о подкатегории."""
        info = self.classifier.get_subcategory_info('source_code', 'api_clients')
        assert 'keywords' in info
        assert 'description' in info
        assert 'client' in info['keywords']
    
    def test_get_all_categories(self):
        """Тест получения всех категорий."""
        categories = self.classifier.get_all_categories()
        expected_categories = ['source_code', 'tests', 'config', 'docs', 'scripts', 'data', 'web', 'other']
        for category in expected_categories:
            assert category in categories
    
    def test_get_subcategories(self):
        """Тест получения подкатегорий."""
        subcategories = self.classifier.get_subcategories('source_code')
        expected_subcategories = ['api_clients', 'auth', 'monitoring', 'security', 'services']
        for subcategory in expected_subcategories:
            assert subcategory in subcategories
    
    def test_validate_classification(self):
        """Тест валидации классификации."""
        # Валидная классификация
        assert self.classifier.validate_classification('test.py', 'source_code', 'api_clients')
        
        # Невалидная категория
        assert not self.classifier.validate_classification('test.py', 'invalid_category', 'api_clients')
        
        # Невалидная подкатегория
        assert not self.classifier.validate_classification('test.py', 'source_code', 'invalid_subcategory')


class TestPythonFileClassifier:
    """Тесты специализированного классификатора Python файлов."""
    
    def setup_method(self):
        """Настройка перед каждым тестом."""
        self.classifier = PythonFileClassifier()
    
    def test_python_test_classification(self):
        """Тест классификации Python тестов."""
        test_cases = [
            ('test_client.py', 'tests', 'unit'),
            ('test_integration_flow.py', 'tests', 'integration'),
            ('test_load_performance.py', 'tests', 'load'),
            ('test_security_auth.py', 'tests', 'security'),
            ('conftest.py', 'tests', 'config'),
        ]
        
        for file_path, expected_category, expected_subcategory in test_cases:
            category, subcategory = self.classifier.classify_python_file(file_path, "")
            assert category == expected_category
            assert subcategory == expected_subcategory
    
    def test_python_module_classification(self):
        """Тест классификации Python модулей."""
        test_cases = [
            ('api_client.py', 'source_code', 'client'),
            ('user_service.py', 'source_code', 'service'),
            ('user_model.py', 'source_code', 'model'),
            ('app_config.py', 'source_code', 'config'),
            ('string_util.py', 'source_code', 'util'),
            ('main_app.py', 'source_code', 'main'),
        ]
        
        for file_path, expected_category, expected_subcategory in test_cases:
            category, subcategory = self.classifier.classify_python_file(file_path, "")
            assert category == expected_category
            assert subcategory == expected_subcategory


class TestConfigFileClassifier:
    """Тесты специализированного классификатора конфигурационных файлов."""
    
    def setup_method(self):
        """Настройка перед каждым тестом."""
        self.classifier = ConfigFileClassifier()
    
    def test_config_classification(self):
        """Тест классификации конфигурационных файлов."""
        test_cases = [
            ('docker-compose.yml', 'deployment'),
            ('prometheus.yml', 'monitoring'),
            ('auth_config.yaml', 'security'),
            ('livekit_sip.yaml', 'livekit'),
            ('.env.production', 'environment'),
            ('app_config.json', 'main'),
        ]
        
        for file_path, expected_subcategory in test_cases:
            subcategory = self.classifier.classify_config_file(file_path, "")
            assert subcategory == expected_subcategory


class TestDocumentationClassifier:
    """Тесты специализированного классификатора документации."""
    
    def setup_method(self):
        """Настройка перед каждым тестом."""
        self.classifier = DocumentationClassifier()
    
    def test_documentation_classification(self):
        """Тест классификации документации."""
        test_cases = [
            ('README.md', 'main'),
            ('CONTRIBUTING.md', 'guides'),
            ('setup_guide.md', 'guides'),
            ('api_reference.md', 'api_docs'),
            ('client_example.md', 'examples'),
            ('implementation_report.md', 'reports'),
            ('architecture_design.md', 'architecture'),
            ('troubleshooting_guide.md', 'troubleshooting'),
            ('user_manual.md', 'main'),
        ]
        
        for file_path, expected_subcategory in test_cases:
            subcategory = self.classifier.classify_documentation(file_path, "")
            assert subcategory == expected_subcategory


class TestEdgeCases:
    """Тесты граничных случаев."""
    
    def setup_method(self):
        """Настройка перед каждым тестом."""
        self.classifier = FileClassifier()
    
    def test_files_without_extension(self):
        """Тест файлов без расширения."""
        test_cases = [
            ('Dockerfile', 'config'),
            ('Makefile', 'scripts'),
            ('LICENSE', 'other'),
        ]
        
        for file_path, expected_category in test_cases:
            category, _ = self.classifier.classify_file(file_path)
            assert category == expected_category
    
    def test_nested_paths(self):
        """Тест вложенных путей."""
        test_cases = [
            ('src/clients/api/livekit_client.py', 'source_code', 'api_clients'),
            ('tests/integration/flow/test_user_flow.py', 'tests', 'integration'),
            ('docs/guides/setup/installation.md', 'docs', 'guides'),
        ]
        
        for file_path, expected_category, expected_subcategory in test_cases:
            category, subcategory = self.classifier.classify_file(file_path)
            assert category == expected_category
            assert subcategory == expected_subcategory
    
    def test_case_insensitive_classification(self):
        """Тест нечувствительности к регистру."""
        test_cases = [
            ('SRC/CLIENTS/API_CLIENT.PY', 'source_code', 'api_clients'),
            ('TESTS/TEST_INTEGRATION.PY', 'tests', 'integration'),
            ('CONFIG/PROMETHEUS.YML', 'config', 'monitoring'),
        ]
        
        for file_path, expected_category, expected_subcategory in test_cases:
            category, subcategory = self.classifier.classify_file(file_path)
            assert category == expected_category
            assert subcategory == expected_subcategory
    
    def test_unknown_extensions(self):
        """Тест неизвестных расширений."""
        category, subcategory = self.classifier.classify_file('unknown_file.xyz')
        assert category == 'other'
        assert subcategory == 'main'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])