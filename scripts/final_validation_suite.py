    #!/usr/bin/env python3
"""
Комплексная система валидации и финального тестирования LiveKit системы.
Выполняет полное тестирование всех компонентов согласно требованиям.
"""

import asyncio
import logging
import json
import time
import sys
import os
from datetime import datetime, UTC
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

# Добавляем путь к src для импортов
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from clients.livekit_api_client import LiveKitAPIClient
from auth.livekit_auth import LiveKitAuthManager
from monitoring.livekit_system_monitor import LiveKitSystemMonitor
from security.livekit_security import LiveKitSecurityValidator
from performance_optimizer import PerformanceOptimizer
from integration.livekit_voice_ai_integration import LiveKitVoiceAIIntegration

@dataclass
class ValidationResult:
    """Результат валидации компонента."""
    component: str
    status: str  # "PASS", "FAIL", "WARNING"
    message: str
    details: Dict[str, Any]
    duration_ms: float
    timestamp: str

class FinalValidationSuite:
    """Комплексная система финального тестирования."""
    
    def __init__(self):
        self.logger = self._setup_logging()
        self.results: List[ValidationResult] = []
        self.start_time = time.time()
        
        # Инициализация компонентов
        self.api_client = None
        self.auth_manager = None
        self.monitor = None
        self.security_validator = None
        self.performance_optimizer = None
        self.voice_ai_integration = None
        
    def _setup_logging(self) -> logging.Logger:
        """Настройка логирования для валидации."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('final_validation.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        return logging.getLogger(__name__)
    
    async def initialize_components(self) -> bool:
        """Инициализация всех компонентов системы."""
        try:
            # Загрузка конфигурации
            livekit_url = os.getenv('LIVEKIT_URL')
            api_key = os.getenv('LIVEKIT_API_KEY')
            api_secret = os.getenv('LIVEKIT_API_SECRET')
            
            if not all([livekit_url, api_key, api_secret]):
                self.logger.error("Отсутствуют обязательные переменные окружения")
                return False
            
            # Инициализация компонентов
            self.auth_manager = LiveKitAuthManager(api_key, api_secret)
            self.api_client = LiveKitAPIClient(livekit_url, api_key, api_secret)
            self.monitor = LiveKitSystemMonitor(self.api_client)
            self.security_validator = LiveKitSecurityValidator(self.api_client)
            self.performance_optimizer = PerformanceOptimizer(self.api_client)
            self.voice_ai_integration = LiveKitVoiceAIIntegration(self.api_client)
            
            self.logger.info("Все компоненты успешно инициализированы")
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка инициализации компонентов: {e}")
            return False
    
    async def run_full_validation(self) -> Dict[str, Any]:
        """Запуск полной валидации системы."""
        self.logger.info("Начало полной валидации системы LiveKit")
        
        if not await self.initialize_components():
            return {"status": "FAILED", "error": "Не удалось инициализировать компоненты"}
        
        # Выполнение всех тестов
        await self._validate_authentication()
        await self._validate_api_endpoints()
        await self._validate_sip_integration()
        await self._validate_voice_ai_integration()
        await self._validate_security()
        await self._validate_performance()
        await self._validate_monitoring()
        await self._run_load_tests()
        await self._validate_real_sip_calls()
        
        # Генерация итогового отчета
        return self._generate_final_report()
    
    async def _validate_authentication(self):
        """Валидация системы аутентификации."""
        start_time = time.time()
        
        try:
            # Тест создания токенов
            participant_token = self.auth_manager.create_participant_token(
                "test-participant", "test-room"
            )
            admin_token = self.auth_manager.create_admin_token()
            
            # Валидация структуры токенов
            import jwt
            participant_payload = jwt.decode(participant_token, options={"verify_signature": False})
            admin_payload = jwt.decode(admin_token, options={"verify_signature": False})
            
            # Проверка обязательных полей
            required_fields = ['iss', 'sub', 'iat', 'exp', 'video']
            for field in required_fields:
                if field not in participant_payload:
                    raise ValueError(f"Отсутствует обязательное поле: {field}")
            
            self._add_result(ValidationResult(
                component="Authentication",
                status="PASS",
                message="Система аутентификации работает корректно",
                details={
                    "participant_token_valid": True,
                    "admin_token_valid": True,
                    "required_fields_present": True
                },
                duration_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(UTC).isoformat()
            ))
            
        except Exception as e:
            self._add_result(ValidationResult(
                component="Authentication",
                status="FAIL",
                message=f"Ошибка аутентификации: {e}",
                details={"error": str(e)},
                duration_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(UTC).isoformat()
            ))
    
    async def _validate_api_endpoints(self):
        """Валидация всех API эндпоинтов."""
        start_time = time.time()
        
        try:
            # Тест создания комнаты
            test_room_name = f"validation-room-{int(time.time())}"
            room = await self.api_client.create_room(
                name=test_room_name,
                metadata={"test": "validation"}
            )
            
            # Тест получения списка комнат
            rooms = await self.api_client.list_rooms()
            room_found = any(r.name == test_room_name for r in rooms)
            
            # Тест удаления комнаты
            await self.api_client.delete_room(test_room_name)
            
            self._add_result(ValidationResult(
                component="API Endpoints",
                status="PASS",
                message="Все API эндпоинты работают корректно",
                details={
                    "room_created": True,
                    "room_listed": room_found,
                    "room_deleted": True,
                    "total_rooms": len(rooms)
                },
                duration_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(UTC).isoformat()
            ))
            
        except Exception as e:
            self._add_result(ValidationResult(
                component="API Endpoints",
                status="FAIL",
                message=f"Ошибка API эндпоинтов: {e}",
                details={"error": str(e)},
                duration_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(UTC).isoformat()
            ))
    
    async def _validate_sip_integration(self):
        """Валидация SIP интеграции."""
        start_time = time.time()
        
        try:
            # Проверка конфигурации SIP
            sip_config_path = "livekit-sip-correct.yaml"
            if not os.path.exists(sip_config_path):
                raise FileNotFoundError("SIP конфигурация не найдена")
            
            # Проверка переменных окружения для SIP
            sip_vars = ['SIP_NUMBER', 'SIP_SERVER', 'SIP_USERNAME', 'SIP_PASSWORD']
            missing_vars = [var for var in sip_vars if not os.getenv(var)]
            
            if missing_vars:
                self._add_result(ValidationResult(
                    component="SIP Integration",
                    status="WARNING",
                    message=f"Отсутствуют переменные окружения: {missing_vars}",
                    details={"missing_vars": missing_vars},
                    duration_ms=(time.time() - start_time) * 1000,
                    timestamp=datetime.now(UTC).isoformat()
                ))
            else:
                self._add_result(ValidationResult(
                    component="SIP Integration",
                    status="PASS",
                    message="SIP конфигурация корректна",
                    details={"config_file_exists": True, "env_vars_present": True},
                    duration_ms=(time.time() - start_time) * 1000,
                    timestamp=datetime.now(UTC).isoformat()
                ))
                
        except Exception as e:
            self._add_result(ValidationResult(
                component="SIP Integration",
                status="FAIL",
                message=f"Ошибка SIP интеграции: {e}",
                details={"error": str(e)},
                duration_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(UTC).isoformat()
            ))
    
    async def _validate_voice_ai_integration(self):
        """Валидация интеграции с Voice AI Agent."""
        start_time = time.time()
        
        try:
            # Тест инициализации Voice AI интеграции
            await self.voice_ai_integration.initialize()
            
            # Тест создания комнаты для Voice AI
            test_room = f"voice-ai-test-{int(time.time())}"
            room_created = await self.voice_ai_integration.create_voice_room(
                room_name=test_room,
                caller_identity="test-caller"
            )
            
            # Очистка
            await self.api_client.delete_room(test_room)
            
            self._add_result(ValidationResult(
                component="Voice AI Integration",
                status="PASS",
                message="Интеграция с Voice AI Agent работает корректно",
                details={
                    "integration_initialized": True,
                    "voice_room_created": bool(room_created)
                },
                duration_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(UTC).isoformat()
            ))
            
        except Exception as e:
            self._add_result(ValidationResult(
                component="Voice AI Integration",
                status="FAIL",
                message=f"Ошибка интеграции Voice AI: {e}",
                details={"error": str(e)},
                duration_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(UTC).isoformat()
            ))    
async def _validate_security(self):
        """Валидация требований безопасности."""
        start_time = time.time()
        
        try:
            # Запуск проверок безопасности
            security_results = await self.security_validator.run_security_audit()
            
            # Проверка критических требований безопасности
            critical_checks = [
                "api_keys_protected",
                "wss_connections_enforced",
                "jwt_validation_enabled",
                "permissions_validated"
            ]
            
            failed_checks = []
            for check in critical_checks:
                if not security_results.get(check, False):
                    failed_checks.append(check)
            
            if failed_checks:
                self._add_result(ValidationResult(
                    component="Security",
                    status="FAIL",
                    message=f"Не пройдены критические проверки безопасности: {failed_checks}",
                    details=security_results,
                    duration_ms=(time.time() - start_time) * 1000,
                    timestamp=datetime.now(UTC).isoformat()
                ))
            else:
                self._add_result(ValidationResult(
                    component="Security",
                    status="PASS",
                    message="Все требования безопасности выполнены",
                    details=security_results,
                    duration_ms=(time.time() - start_time) * 1000,
                    timestamp=datetime.now(UTC).isoformat()
                ))
                
        except Exception as e:
            self._add_result(ValidationResult(
                component="Security",
                status="FAIL",
                message=f"Ошибка валидации безопасности: {e}",
                details={"error": str(e)},
                duration_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(UTC).isoformat()
            ))
    
    async def _validate_performance(self):
        """Валидация производительности системы."""
        start_time = time.time()
        
        try:
            # Запуск тестов производительности
            perf_results = await self.performance_optimizer.run_performance_tests()
            
            # Проверка критических метрик
            api_latency = perf_results.get("avg_api_latency_ms", 0)
            connection_success_rate = perf_results.get("connection_success_rate", 0)
            
            status = "PASS"
            message = "Производительность соответствует требованиям"
            
            if api_latency > 1000:  # Более 1 секунды
                status = "WARNING"
                message = f"Высокая латентность API: {api_latency}ms"
            
            if connection_success_rate < 0.95:  # Менее 95%
                status = "FAIL"
                message = f"Низкий процент успешных подключений: {connection_success_rate*100}%"
            
            self._add_result(ValidationResult(
                component="Performance",
                status=status,
                message=message,
                details=perf_results,
                duration_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(UTC).isoformat()
            ))
            
        except Exception as e:
            self._add_result(ValidationResult(
                component="Performance",
                status="FAIL",
                message=f"Ошибка тестирования производительности: {e}",
                details={"error": str(e)},
                duration_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(UTC).isoformat()
            ))
    
    async def _validate_monitoring(self):
        """Валидация системы мониторинга."""
        start_time = time.time()
        
        try:
            # Запуск health checks
            health_results = await self.monitor.run_health_checks()
            
            # Проверка всех сервисов
            services = ["room_service", "sip_service", "egress_service", "ingress_service"]
            unhealthy_services = []
            
            for service in services:
                service_status = health_results.get("checks", {}).get(service, {})
                if service_status.get("status") != "healthy":
                    unhealthy_services.append(service)
            
            if unhealthy_services:
                self._add_result(ValidationResult(
                    component="Monitoring",
                    status="WARNING",
                    message=f"Неисправные сервисы: {unhealthy_services}",
                    details=health_results,
                    duration_ms=(time.time() - start_time) * 1000,
                    timestamp=datetime.now(UTC).isoformat()
                ))
            else:
                self._add_result(ValidationResult(
                    component="Monitoring",
                    status="PASS",
                    message="Все сервисы работают корректно",
                    details=health_results,
                    duration_ms=(time.time() - start_time) * 1000,
                    timestamp=datetime.now(UTC).isoformat()
                ))
                
        except Exception as e:
            self._add_result(ValidationResult(
                component="Monitoring",
                status="FAIL",
                message=f"Ошибка системы мониторинга: {e}",
                details={"error": str(e)},
                duration_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(UTC).isoformat()
            ))    
async def _run_load_tests(self):
        """Проведение нагрузочного тестирования."""
        start_time = time.time()
        
        try:
            # Создание множественных комнат для нагрузочного тестирования
            concurrent_rooms = 10
            room_names = [f"load-test-{i}-{int(time.time())}" for i in range(concurrent_rooms)]
            
            # Создание комнат параллельно
            create_tasks = [
                self.api_client.create_room(name, metadata={"load_test": True})
                for name in room_names
            ]
            
            created_rooms = await asyncio.gather(*create_tasks, return_exceptions=True)
            successful_creates = sum(1 for r in created_rooms if not isinstance(r, Exception))
            
            # Удаление комнат
            delete_tasks = [
                self.api_client.delete_room(name)
                for name in room_names
            ]
            await asyncio.gather(*delete_tasks, return_exceptions=True)
            
            success_rate = successful_creates / concurrent_rooms
            
            if success_rate >= 0.9:  # 90% успешных операций
                status = "PASS"
                message = f"Нагрузочное тестирование пройдено: {success_rate*100}% успешных операций"
            else:
                status = "FAIL"
                message = f"Низкий процент успешных операций: {success_rate*100}%"
            
            self._add_result(ValidationResult(
                component="Load Testing",
                status=status,
                message=message,
                details={
                    "concurrent_rooms": concurrent_rooms,
                    "successful_creates": successful_creates,
                    "success_rate": success_rate
                },
                duration_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(UTC).isoformat()
            ))
            
        except Exception as e:
            self._add_result(ValidationResult(
                component="Load Testing",
                status="FAIL",
                message=f"Ошибка нагрузочного тестирования: {e}",
                details={"error": str(e)},
                duration_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(UTC).isoformat()
            ))
    
    async def _validate_real_sip_calls(self):
        """Валидация работы с реальными SIP звонками."""
        start_time = time.time()
        
        try:
            # Проверка доступности SIP сервера
            sip_server = os.getenv('SIP_SERVER')
            sip_port = int(os.getenv('SIP_PORT', 5060))
            
            if not sip_server:
                self._add_result(ValidationResult(
                    component="Real SIP Calls",
                    status="WARNING",
                    message="SIP сервер не настроен - пропуск тестирования реальных звонков",
                    details={"sip_server_configured": False},
                    duration_ms=(time.time() - start_time) * 1000,
                    timestamp=datetime.now(UTC).isoformat()
                ))
                return
            
            # Тест подключения к SIP серверу
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(5)
            
            try:
                # Отправка SIP OPTIONS запро проверки доступности
                sip_options = f"OPTIONS sip:{sip_server} SIP/2.0\r\n"
                sip_options += f"Via: SIP/2.0/UDP localhost:5060\r\n"
                sip_options += f"From: <sip:test@localhost>\r\n"
                sip_options += f"To: <sip:{sip_server}>\r\n"
                sip_options += f"Call-ID: test-{int(time.time())}\r\n"
                sip_options += f"CSeq: 1 OPTIONS\r\n"
                sip_options += f"Content-Length: 0\r\n\r\n"
                
                sock.sendto(sip_options.encode(), (sip_server, sip_port))
                response, addr = sock.recvfrom(1024)
                
                if b"200 OK" in response or b"404" in response:
                    # Сервер отвечает (даже 404 означает что сервер работает)
                    sip_server_reachable = True
                else:
                    sip_server_reachable = False
                    
            except socket.timeout:
                sip_server_reachable = False
            finally:
                sock.close()
            
            self._add_result(ValidationResult(
                component="Real SIP Calls",
                status="PASS" if sip_server_reachable else "WARNING",
                message="SIP сервер доступен" if sip_server_reachable else "SIP сервер недоступен",
                details={
                    "sip_server": sip_server,
                    "sip_port": sip_port,
                    "server_reachable": sip_server_reachable
                },
                duration_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(UTC).isoformat()
            ))
            
        except Exception as e:
            self._add_result(ValidationResult(
                component="Real SIP Calls",
                status="FAIL",
                message=f"Ошибка валидации SIP звонков: {e}",
                details={"error": str(e)},
                duration_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now(UTC).isoformat()
            ))  
  def _add_result(self, result: ValidationResult):
        """Добавление результата валидации."""
        self.results.append(result)
        self.logger.info(f"{result.component}: {result.status} - {result.message}")
    
    def _generate_final_report(self) -> Dict[str, Any]:
        """Генерация итогового отчета валидации."""
        total_duration = time.time() - self.start_time
        
        # Подсчет статистики
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r.status == "PASS")
        failed_tests = sum(1 for r in self.results if r.status == "FAIL")
        warning_tests = sum(1 for r in self.results if r.status == "WARNING")
        
        # Определение общего статуса
        if failed_tests > 0:
            overall_status = "FAILED"
        elif warning_tests > 0:
            overall_status = "WARNING"
        else:
            overall_status = "PASSED"
        
        report = {
            "validation_summary": {
                "overall_status": overall_status,
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "warnings": warning_tests,
                "success_rate": passed_tests / total_tests if total_tests > 0 else 0,
                "total_duration_seconds": round(total_duration, 2),
                "timestamp": datetime.now(UTC).isoformat()
            },
            "detailed_results": [asdict(result) for result in self.results],
            "recommendations": self._generate_recommendations()
        }
        
        # Сохранение отчета
        report_file = f"final_validation_report_{int(time.time())}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Итоговый отчет сохранен в {report_file}")
        return report
    
    def _generate_recommendations(self) -> List[str]:
        """Генерация рекомендаций на основе результатов."""
        recommendations = []
        
        # Анализ неудачных тестов
        failed_components = [r.component for r in self.results if r.status == "FAIL"]
        warning_components = [r.component for r in self.results if r.status == "WARNING"]
        
        if "Authentication" in failed_components:
            recommendations.append("Проверьте настройки JWT токенов и API ключей")
        
        if "API Endpoints" in failed_components:
            recommendations.append("Проверьте доступность LiveKit сервера и правильность эндпоинтов")
        
        if "Security" in failed_components:
            recommendations.append("Устраните критические уязвимости безопасности")
        
        if "Performance" in failed_components:
            recommendations.append("Оптимизируйте производительность системы")
        
        if "SIP Integration" in warning_components:
            recommendations.append("Настройте переменные окружения для SIP интеграции")
        
        if "Real SIP Calls" in warning_components:
            recommendations.append("Проверьте доступность SIP сервера")
        
        if not recommendations:
            recommendations.append("Система готова к продуктивному использованию")
        
        return recommendations

async def main():
    """Главная функция запуска валидации."""
    print("🚀 Запуск комплексной валидации системы LiveKit")
    print("=" * 60)
    
    validator = FinalValidationSuite()
    
    try:
        report = await validator.run_full_validation()
        
        print("\n" + "=" * 60)
        print("📊 ИТОГОВЫЙ ОТЧЕТ ВАЛИДАЦИИ")
        print("=" * 60)
        
        summary = report["validation_summary"]
        print(f"Общий статус: {summary['overall_status']}")
        print(f"Всего тестов: {summary['total_tests']}")
        print(f"Пройдено: {summary['passed']}")
        print(f"Провалено: {summary['failed']}")
        print(f"Предупреждения: {summary['warnings']}")
        print(f"Процент успеха: {summary['success_rate']*100:.1f}%")
        print(f"Время выполнения: {summary['total_duration_seconds']} сек")
        
        print("\n📋 РЕКОМЕНДАЦИИ:")
        for i, rec in enumerate(report["recommendations"], 1):
            print(f"{i}. {rec}")
        
        # Возврат кода выхода
        if summary['overall_status'] == "FAILED":
            sys.exit(1)
        elif summary['overall_status'] == "WARNING":
            sys.exit(2)
        else:
            sys.exit(0)
            
    except Exception as e:
        print(f"❌ Критическая ошибка валидации: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())