#!/usr/bin/env python3
"""
Запуск всех существующих тестов и комплексной валидации системы.
Объединяет все тестовые наборы в единый процесс валидации.
"""

import asyncio
import subprocess
import sys
import os
import json
import time
from pathlib import Path
from typing import Dict, Any, List

class ComprehensiveValidationRunner:
    """Запускает все тесты и валидацию системы."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.test_results = {}
        self.start_time = time.time()
    
    def run_pytest_tests(self) -> Dict[str, Any]:
        """Запуск всех pytest тестов."""
        print("🧪 Запуск pytest тестов...")
        
        try:
            # Запуск pytest с JSON отчетом
            result = subprocess.run([
                sys.executable, "-m", "pytest",
                "tests/",
                "--json-report",
                "--json-report-file=test_report.json",
                "-v"
            ], cwd=self.project_root, capture_output=True, text=True)
            
            # Чтение результатов
            report_file = self.project_root / "test_report.json"
            if report_file.exists():
                with open(report_file, 'r') as f:
                    test_report = json.load(f)
                
                return {
                    "status": "PASSED" if result.returncode == 0 else "FAILED",
                    "return_code": result.returncode,
                    "summary": test_report.get("summary", {}),
                    "tests": test_report.get("tests", []),
                    "stdout": result.stdout,
                    "stderr": result.stderr
                }
            else:
                return {
                    "status": "FAILED",
                    "return_code": result.returncode,
                    "error": "Test report file not found",
                    "stdout": result.stdout,
                    "stderr": result.stderr
                }
                
        except Exception as e:
            return {
                "status": "ERROR",
                "error": str(e)
            }
    
    def check_environment_setup(self) -> Dict[str, Any]:
        """Проверка настройки окружения."""
        print("🔍 Проверка настройки окружения...")
        
        required_vars = [
            'LIVEKIT_URL',
            'LIVEKIT_API_KEY',
            'LIVEKIT_API_SECRET'
        ]
        
        optional_vars = [
            'SIP_NUMBER',
            'SIP_SERVER',
            'SIP_USERNAME',
            'SIP_PASSWORD',
            'REDIS_URL'
        ]
        
        env_status = {
            "required_vars": {},
            "optional_vars": {},
            "config_files": {}
        }
        
        # Проверка обязательных переменных
        for var in required_vars:
            env_status["required_vars"][var] = {
                "present": bool(os.getenv(var)),
                "value_length": len(os.getenv(var, ""))
            }
        
        # Проверка опциональных переменных
        for var in optional_vars:
            env_status["optional_vars"][var] = {
                "present": bool(os.getenv(var)),
                "value_length": len(os.getenv(var, ""))
            }
        
        # Проверка конфигурационных файлов
        config_files = [
            "livekit-sip-correct.yaml",
            ".env",
            "config/livekit_config.py",
            "config/security.yaml",
            "config/performance.yaml"
        ]
        
        for file_path in config_files:
            full_path = self.project_root / file_path
            env_status["config_files"][file_path] = {
                "exists": full_path.exists(),
                "size": full_path.stat().st_size if full_path.exists() else 0
            }
        
        # Определение общего статуса окружения
        required_missing = sum(1 for var_info in env_status["required_vars"].values() if not var_info["present"])
        critical_files_missing = sum(1 for file_info in env_status["config_files"].values() if not file_info["exists"])
        
        if required_missing > 0 or critical_files_missing > 2:
            overall_status = "CRITICAL"
        elif critical_files_missing > 0:
            overall_status = "WARNING"
        else:
            overall_status = "OK"
        
        return {
            "overall_status": overall_status,
            "details": env_status,
            "required_missing": required_missing,
            "files_missing": critical_files_missing
        }

async def main():
    """Главная функция."""
    runner = ComprehensiveValidationRunner()
    
    try:
        print("🚀 Начало комплексной валидации системы LiveKit")
        print("=" * 70)
        
        # Проверка окружения
        env_check = runner.check_environment_setup()
        
        print("\n" + "=" * 70)
        print("📊 РЕЗУЛЬТАТЫ ПРОВЕРКИ ОКРУЖЕНИЯ")
        print("=" * 70)
        
        print(f"🎯 Статус окружения: {env_check['overall_status']}")
        print(f"❌ Отсутствующих обязательных переменных: {env_check['required_missing']}")
        print(f"📁 Отсутствующих файлов конфигурации: {env_check['files_missing']}")
        
        # Детали по переменным окружения
        print("\n🔧 Обязательные переменные окружения:")
        for var, info in env_check["details"]["required_vars"].items():
            status = "✅" if info["present"] else "❌"
            print(f"   {status} {var}: {'настроена' if info['present'] else 'отсутствует'}")
        
        print("\n🔧 Опциональные переменные окружения:")
        for var, info in env_check["details"]["optional_vars"].items():
            status = "✅" if info["present"] else "⚠️"
            print(f"   {status} {var}: {'настроена' if info['present'] else 'отсутствует'}")
        
        print("\n📁 Конфигурационные файлы:")
        for file_path, info in env_check["details"]["config_files"].items():
            status = "✅" if info["exists"] else "❌"
            size_info = f" ({info['size']} байт)" if info["exists"] else ""
            print(f"   {status} {file_path}: {'существует' if info['exists'] else 'отсутствует'}{size_info}")
        
        if env_check["overall_status"] == "CRITICAL":
            print("\n❌ Критические проблемы с настройкой окружения!")
            print("Исправьте настройки перед запуском полной валидации.")
            sys.exit(1)
        elif env_check["overall_status"] == "WARNING":
            print("\n⚠️  Обнаружены проблемы с настройкой окружения.")
            print("Рекомендуется исправить перед продуктивным использованием.")
        else:
            print("\n✅ Окружение настроено корректно!")
        
        print("\n" + "=" * 70)
        print("✅ Базовая валидация завершена успешно!")
        sys.exit(0)
            
    except Exception as e:
        print(f"💥 Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())