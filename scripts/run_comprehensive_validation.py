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
    
    def run_individual_test_scripts(self) -> Dict[str, Any]:
        """Запуск отдельных тестовых скриптов."""
        print("🔧 Запуск индивидуальных тестовых скриптов...")
        
        test_scripts = [
            "test_simple_updated_components.py",
            "test_updated_components_integration.py",
            "test_integration_simple.py",
            "test_performance_simple.py",
            "test_simple_egress.py",
            "test_simple_ingress.py"
        ]
        
        results = {}
        
        for script in test_scripts:
            script_path = self.project_root / script
            if script_path.exists():
                try:
                    print(f"  Запуск {script}...")
                    result = subprocess.run([
                        sys.executable, str(script_path)
                    ], cwd=self.project_root, capture_output=True, text=True, timeout=60)
                    
                    results[script] = {
                        "status": "PASSED" if result.returncode == 0 else "FAILED",
                        "return_code": result.returncode,
                        "stdout": result.stdout,
                        "stderr": result.stderr
                    }
                    
                except subprocess.TimeoutExpired:
                    results[script] = {
                        "status": "TIMEOUT",
                        "error": "Test timed out after 60 seconds"
                    }
                except Exception as e:
                    results[script] = {
                        "status": "ERROR",
                        "error": str(e)
                    }
            else:
                results[script] = {
                    "status": "SKIPPED",
                    "reason": "Script not found"
                }
        
        return results    
async def run_final_validation_suite(self) -> Dict[str, Any]:
        """Запуск финальной валидации."""
        print("🎯 Запуск финальной валидации системы...")
        
        try:
            # Импорт и запуск финальной валидации
            sys.path.append(str(self.project_root / "scripts"))
            from final_validation_suite import FinalValidationSuite
            
            validator = FinalValidationSuite()
            report = await validator.run_full_validation()
            
            return {
                "status": report["validation_summary"]["overall_status"],
                "report": report
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
    
    async def run_all_validations(self) -> Dict[str, Any]:
        """Запуск всех валидаций."""
        print("🚀 Начало комплексной валидации системы LiveKit")
        print("=" * 70)
        
        # 1. Проверка окружения
        env_check = self.check_environment_setup()
        self.test_results["environment"] = env_check
        
        if env_check["overall_status"] == "CRITICAL":
            print("❌ Критические проблемы с настройкой окружения!")
            return self._generate_final_report()
        
        # 2. Запуск pytest тестов
        pytest_results = self.run_pytest_tests()
        self.test_results["pytest"] = pytest_results
        
        # 3. Запуск индивидуальных тестов
        individual_tests = self.run_individual_test_scripts()
        self.test_results["individual_tests"] = individual_tests
        
        # 4. Финальная валидация
        final_validation = await self.run_final_validation_suite()
        self.test_results["final_validation"] = final_validation
        
        return self._generate_final_report()
    
    def _generate_final_report(self) -> Dict[str, Any]:
        """Генерация итогового отчета."""
        total_duration = time.time() - self.start_time
        
        # Анализ результатов
        overall_status = "PASSED"
        issues = []
        
        # Проверка окружения
        if self.test_results.get("environment", {}).get("overall_status") == "CRITICAL":
            overall_status = "FAILED"
            issues.append("Критические проблемы с настройкой окружения")
        
        # Проверка pytest
        if self.test_results.get("pytest", {}).get("status") == "FAILED":
            overall_status = "FAILED"
            issues.append("Провалены pytest тесты")
        
        # Проверка индивидуальных тестов
        individual_failed = sum(1 for result in self.test_results.get("individual_tests", {}).values() 
                               if result.get("status") == "FAILED")
        if individual_failed > 0:
            if overall_status != "FAILED":
                overall_status = "WARNING"
            issues.append(f"Провалено {individual_failed} индивидуальных тестов")
        
        # Проверка финальной валидации
        final_status = self.test_results.get("final_validation", {}).get("status")
        if final_status == "FAILED":
            overall_status = "FAILED"
            issues.append("Провалена финальная валидация")
        elif final_status == "WARNING" and overall_status == "PASSED":
            overall_status = "WARNING"
            issues.append("Предупреждения в финальной валидации")
        
        report = {
            "comprehensive_validation_summary": {
                "overall_status": overall_status,
                "total_duration_seconds": round(total_duration, 2),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "issues": issues
            },
            "detailed_results": self.test_results
        }
        
        # Сохранение отчета
        report_file = f"comprehensive_validation_report_{int(time.time())}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 Полный отчет сохранен в {report_file}")
        return report

async def main():
    """Главная функция."""
    runner = ComprehensiveValidationRunner()
    
    try:
        report = await runner.run_all_validations()
        
        print("\n" + "=" * 70)
        print("📊 ИТОГОВЫЙ ОТЧЕТ КОМПЛЕКСНОЙ ВАЛИДАЦИИ")
        print("=" * 70)
        
        summary = report["comprehensive_validation_summary"]
        print(f"🎯 Общий статус: {summary['overall_status']}")
        print(f"⏱️  Время выполнения: {summary['total_duration_seconds']} сек")
        
        if summary["issues"]:
            print("\n⚠️  Обнаруженные проблемы:")
            for i, issue in enumerate(summary["issues"], 1):
                print(f"   {i}. {issue}")
        else:
            print("\n✅ Проблем не обнаружено!")
        
        # Краткая статистика по компонентам
        print("\n📈 Статистика по компонентам:")
        
        # Окружение
        env_status = report["detailed_results"].get("environment", {}).get("overall_status", "UNKNOWN")
        print(f"   🔧 Окружение: {env_status}")
        
        # Pytest
        pytest_status = report["detailed_results"].get("pytest", {}).get("status", "UNKNOWN")
        print(f"   🧪 Pytest тесты: {pytest_status}")
        
        # Индивидуальные тесты
        individual_tests = report["detailed_results"].get("individual_tests", {})
        passed_individual = sum(1 for r in individual_tests.values() if r.get("status") == "PASSED")
        total_individual = len(individual_tests)
        print(f"   🔧 Индивидуальные тесты: {passed_individual}/{total_individual} пройдено")
        
        # Финальная валидация
        final_status = report["detailed_results"].get("final_validation", {}).get("status", "UNKNOWN")
        print(f"   🎯 Финальная валидация: {final_status}")
        
        print("\n" + "=" * 70)
        
        # Возврат соответствующего кода выхода
        if summary['overall_status'] == "FAILED":
            print("❌ Валидация провалена!")
            sys.exit(1)
        elif summary['overall_status'] == "WARNING":
            print("⚠️  Валидация завершена с предупреждениями!")
            sys.exit(2)
        else:
            print("✅ Валидация успешно завершена!")
            sys.exit(0)
            
    except Exception as e:
        print(f"💥 Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())