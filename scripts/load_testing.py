#!/usr/bin/env python3
"""
Нагрузочное тестирование LiveKit системы.
Проверяет производительность под различными нагрузками.
"""

import asyncio
import time
import statistics
import json
import sys
import os
from typing import Dict, Any, List
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import aiohttp

# Добавляем путь к src для импортов
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from clients.livekit_api_client import LiveKitAPIClient

@dataclass
class LoadTestResult:
    """Результат нагрузочного теста."""
    test_name: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_response_time_ms: float
    min_response_time_ms: float
    max_response_time_ms: float
    requests_per_second: float
    error_rate: float
    duration_seconds: float

class LoadTester:
    """Класс для проведения нагрузочного тестирования."""
    
    def __init__(self):
        self.api_client = None
        self.results: List[LoadTestResult] = []
        
    async def initialize(self):
        """Инициализация клиента API."""
        livekit_url = os.getenv('LIVEKIT_URL')
        api_key = os.getenv('LIVEKIT_API_KEY')
        api_secret = os.getenv('LIVEKIT_API_SECRET')
        
        if not all([livekit_url, api_key, api_secret]):
            raise ValueError("Отсутствуют обязательные переменные окружения")
        
        self.api_client = LiveKitAPIClient(livekit_url, api_key, api_secret)
    
    async def run_room_creation_load_test(self, concurrent_requests: int = 50, total_requests: int = 200) -> LoadTestResult:
        """Нагрузочный тест создания комнат."""
        print(f"🏗️  Тест создания комнат: {concurrent_requests} одновременных, {total_requests} всего")
        
        start_time = time.time()
        response_times = []
        successful_requests = 0
        failed_requests = 0
        
        # Семафор для ограничения одновременных запросов
        semaphore = asyncio.Semaphore(concurrent_requests)
        
        async def create_room_task(room_id: int):
            nonlocal successful_requests, failed_requests
            
            async with semaphore:
                request_start = time.time()
                try:
                    room_name = f"load-test-room-{room_id}-{int(time.time())}"
                    await self.api_client.create_room(
                        name=room_name,
                        metadata={"load_test": True, "room_id": room_id}
                    )
                    
                    # Удаляем комнату сразу после создания
                    await self.api_client.delete_room(room_name)
                    
                    response_time = (time.time() - request_start) * 1000
                    response_times.append(response_time)
                    successful_requests += 1
                    
                except Exception as e:
                    failed_requests += 1
                    print(f"Ошибка создания комнаты {room_id}: {e}")
        
        # Запуск всех задач
        tasks = [create_room_task(i) for i in range(total_requests)]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        duration = time.time() - start_time
        
        # Расчет метрик
        if response_times:
            avg_response_time = statistics.mean(response_times)
            min_response_time = min(response_times)
            max_response_time = max(response_times)
        else:
            avg_response_time = min_response_time = max_response_time = 0
        
        requests_per_second = total_requests / duration if duration > 0 else 0
        error_rate = failed_requests / total_requests if total_requests > 0 else 0
        
        result = LoadTestResult(
            test_name="Room Creation Load Test",
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            avg_response_time_ms=avg_response_time,
            min_response_time_ms=min_response_time,
            max_response_time_ms=max_response_time,
            requests_per_second=requests_per_second,
            error_rate=error_rate,
            duration_seconds=duration
        )
        
        self.results.append(result)
        return result
    
    async def run_room_listing_load_test(self, concurrent_requests: int = 100, total_requests: int = 500) -> LoadTestResult:
        """Нагрузочный тест получения списка комнат."""
        print(f"📋 Тест получения списка комнат: {concurrent_requests} одновременных, {total_requests} всего")
        
        start_time = time.time()
        response_times = []
        successful_requests = 0
        failed_requests = 0
        
        semaphore = asyncio.Semaphore(concurrent_requests)
        
        async def list_rooms_task():
            nonlocal successful_requests, failed_requests
            
            async with semaphore:
                request_start = time.time()
                try:
                    await self.api_client.list_rooms()
                    
                    response_time = (time.time() - request_start) * 1000
                    response_times.append(response_time)
                    successful_requests += 1
                    
                except Exception as e:
                    failed_requests += 1
        
        # Запуск всех задач
        tasks = [list_rooms_task() for _ in range(total_requests)]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        duration = time.time() - start_time
        
        # Расчет метрик
        if response_times:
            avg_response_time = statistics.mean(response_times)
            min_response_time = min(response_times)
            max_response_time = max(response_times)
        else:
            avg_response_time = min_response_time = max_response_time = 0
        
        requests_per_second = total_requests / duration if duration > 0 else 0
        error_rate = failed_requests / total_requests if total_requests > 0 else 0
        
        result = LoadTestResult(
            test_name="Room Listing Load Test",
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            avg_response_time_ms=avg_response_time,
            min_response_time_ms=min_response_time,
            max_response_time_ms=max_response_time,
            requests_per_second=requests_per_second,
            error_rate=error_rate,
            duration_seconds=duration
        )
        
        self.results.append(result)
        return result    a
sync def run_concurrent_rooms_test(self, max_concurrent_rooms: int = 20) -> LoadTestResult:
        """Тест максимального количества одновременных комнат."""
        print(f"🏢 Тест одновременных комнат: максимум {max_concurrent_rooms}")
        
        start_time = time.time()
        created_rooms = []
        successful_requests = 0
        failed_requests = 0
        response_times = []
        
        try:
            # Создание комнат
            for i in range(max_concurrent_rooms):
                request_start = time.time()
                try:
                    room_name = f"concurrent-test-{i}-{int(time.time())}"
                    await self.api_client.create_room(
                        name=room_name,
                        metadata={"concurrent_test": True, "room_index": i}
                    )
                    created_rooms.append(room_name)
                    
                    response_time = (time.time() - request_start) * 1000
                    response_times.append(response_time)
                    successful_requests += 1
                    
                except Exception as e:
                    failed_requests += 1
                    print(f"Ошибка создания комнаты {i}: {e}")
            
            # Проверка что все комнаты активны
            rooms_list = await self.api_client.list_rooms()
            active_test_rooms = [r for r in rooms_list if r.name.startswith("concurrent-test-")]
            
            print(f"Создано комнат: {len(created_rooms)}, активных: {len(active_test_rooms)}")
            
            # Небольшая пауза для стабилизации
            await asyncio.sleep(2)
            
        finally:
            # Очистка - удаление всех созданных комнат
            cleanup_tasks = []
            for room_name in created_rooms:
                cleanup_tasks.append(self.api_client.delete_room(room_name))
            
            if cleanup_tasks:
                await asyncio.gather(*cleanup_tasks, return_exceptions=True)
        
        duration = time.time() - start_time
        
        # Расчет метрик
        if response_times:
            avg_response_time = statistics.mean(response_times)
            min_response_time = min(response_times)
            max_response_time = max(response_times)
        else:
            avg_response_time = min_response_time = max_response_time = 0
        
        requests_per_second = max_concurrent_rooms / duration if duration > 0 else 0
        error_rate = failed_requests / max_concurrent_rooms if max_concurrent_rooms > 0 else 0
        
        result = LoadTestResult(
            test_name="Concurrent Rooms Test",
            total_requests=max_concurrent_rooms,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            avg_response_time_ms=avg_response_time,
            min_response_time_ms=min_response_time,
            max_response_time_ms=max_response_time,
            requests_per_second=requests_per_second,
            error_rate=error_rate,
            duration_seconds=duration
        )
        
        self.results.append(result)
        return result
    
    async def run_stress_test(self, duration_seconds: int = 60) -> LoadTestResult:
        """Стресс-тест системы в течение определенного времени."""
        print(f"⚡ Стресс-тест: {duration_seconds} секунд непрерывной нагрузки")
        
        start_time = time.time()
        end_time = start_time + duration_seconds
        
        response_times = []
        successful_requests = 0
        failed_requests = 0
        request_counter = 0
        
        async def stress_worker():
            nonlocal successful_requests, failed_requests, request_counter
            
            while time.time() < end_time:
                request_start = time.time()
                request_counter += 1
                
                try:
                    # Чередуем операции для разнообразия нагрузки
                    if request_counter % 3 == 0:
                        # Создание и удаление комнаты
                        room_name = f"stress-test-{request_counter}-{int(time.time())}"
                        await self.api_client.create_room(name=room_name)
                        await self.api_client.delete_room(room_name)
                    else:
                        # Получение списка комнат
                        await self.api_client.list_rooms()
                    
                    response_time = (time.time() - request_start) * 1000
                    response_times.append(response_time)
                    successful_requests += 1
                    
                except Exception as e:
                    failed_requests += 1
                
                # Небольшая пауза между запросами
                await asyncio.sleep(0.1)
        
        # Запуск нескольких воркеров параллельно
        workers = [stress_worker() for _ in range(5)]
        await asyncio.gather(*workers, return_exceptions=True)
        
        actual_duration = time.time() - start_time
        total_requests = successful_requests + failed_requests
        
        # Расчет метрик
        if response_times:
            avg_response_time = statistics.mean(response_times)
            min_response_time = min(response_times)
            max_response_time = max(response_times)
        else:
            avg_response_time = min_response_time = max_response_time = 0
        
        requests_per_second = total_requests / actual_duration if actual_duration > 0 else 0
        error_rate = failed_requests / total_requests if total_requests > 0 else 0
        
        result = LoadTestResult(
            test_name="Stress Test",
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            avg_response_time_ms=avg_response_time,
            min_response_time_ms=min_response_time,
            max_response_time_ms=max_response_time,
            requests_per_second=requests_per_second,
            error_rate=error_rate,
            duration_seconds=actual_duration
        )
        
        self.results.append(result)
        return result
    
    async def run_all_load_tests(self) -> Dict[str, Any]:
        """Запуск всех нагрузочных тестов."""
        print("🚀 Начало комплексного нагрузочного тестирования")
        print("=" * 60)
        
        await self.initialize()
        
        # Запуск всех тестов
        await self.run_room_creation_load_test(concurrent_requests=20, total_requests=100)
        await self.run_room_listing_load_test(concurrent_requests=50, total_requests=200)
        await self.run_concurrent_rooms_test(max_concurrent_rooms=15)
        await self.run_stress_test(duration_seconds=30)
        
        return self._generate_load_test_report()
    
    def _generate_load_test_report(self) -> Dict[str, Any]:
        """Генерация отчета по нагрузочному тестированию."""
        
        # Общая статистика
        total_requests = sum(r.total_requests for r in self.results)
        total_successful = sum(r.successful_requests for r in self.results)
        total_failed = sum(r.failed_requests for r in self.results)
        
        overall_error_rate = total_failed / total_requests if total_requests > 0 else 0
        avg_requests_per_second = statistics.mean([r.requests_per_second for r in self.results])
        avg_response_time = statistics.mean([r.avg_response_time_ms for r in self.results])
        
        # Определение общего статуса
        if overall_error_rate > 0.1:  # Более 10% ошибок
            overall_status = "FAILED"
        elif overall_error_rate > 0.05:  # Более 5% ошибок
            overall_status = "WARNING"
        elif avg_response_time > 2000:  # Более 2 секунд средний ответ
            overall_status = "WARNING"
        else:
            overall_status = "PASSED"
        
        report = {
            "load_test_summary": {
                "overall_status": overall_status,
                "total_requests": total_requests,
                "successful_requests": total_successful,
                "failed_requests": total_failed,
                "overall_error_rate": overall_error_rate,
                "avg_requests_per_second": avg_requests_per_second,
                "avg_response_time_ms": avg_response_time,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            },
            "individual_test_results": [
                {
                    "test_name": r.test_name,
                    "total_requests": r.total_requests,
                    "successful_requests": r.successful_requests,
                    "failed_requests": r.failed_requests,
                    "avg_response_time_ms": r.avg_response_time_ms,
                    "min_response_time_ms": r.min_response_time_ms,
                    "max_response_time_ms": r.max_response_time_ms,
                    "requests_per_second": r.requests_per_second,
                    "error_rate": r.error_rate,
                    "duration_seconds": r.duration_seconds
                }
                for r in self.results
            ],
            "performance_recommendations": self._generate_performance_recommendations()
        }
        
        # Сохранение отчета
        report_file = f"load_test_report_{int(time.time())}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 Отчет по нагрузочному тестированию сохранен в {report_file}")
        return report
    
    def _generate_performance_recommendations(self) -> List[str]:
        """Генерация рекомендаций по производительности."""
        recommendations = []
        
        # Анализ времени ответа
        avg_response_times = [r.avg_response_time_ms for r in self.results]
        max_avg_response_time = max(avg_response_times) if avg_response_times else 0
        
        if max_avg_response_time > 2000:
            recommendations.append("Оптимизируйте время ответа API - обнаружены задержки более 2 секунд")
        elif max_avg_response_time > 1000:
            recommendations.append("Рассмотрите оптимизацию времени ответа API")
        
        # Анализ частоты ошибок
        error_rates = [r.error_rate for r in self.results]
        max_error_rate = max(error_rates) if error_rates else 0
        
        if max_error_rate > 0.1:
            recommendations.append("Критически высокая частота ошибок - требуется немедленная оптимизация")
        elif max_error_rate > 0.05:
            recommendations.append("Повышенная частота ошибок - рекомендуется оптимизация")
        
        # Анализ пропускной способности
        rps_values = [r.requests_per_second for r in self.results]
        min_rps = min(rps_values) if rps_values else 0
        
        if min_rps < 10:
            recommendations.append("Низкая пропускная способность - рассмотрите масштабирование")
        
        if not recommendations:
            recommendations.append("Производительность системы соответствует требованиям")
        
        return recommendations

async def main():
    """Главная функция запуска нагрузочного тестирования."""
    tester = LoadTester()
    
    try:
        report = await tester.run_all_load_tests()
        
        print("\n" + "=" * 60)
        print("📊 ОТЧЕТ ПО НАГРУЗОЧНОМУ ТЕСТИРОВАНИЮ")
        print("=" * 60)
        
        summary = report["load_test_summary"]
        print(f"Общий статус: {summary['overall_status']}")
        print(f"Всего запросов: {summary['total_requests']}")
        print(f"Успешных: {summary['successful_requests']}")
        print(f"Неудачных: {summary['failed_requests']}")
        print(f"Частота ошибок: {summary['overall_error_rate']*100:.2f}%")
        print(f"Среднее RPS: {summary['avg_requests_per_second']:.2f}")
        print(f"Среднее время ответа: {summary['avg_response_time_ms']:.2f} мс")
        
        print("\n📋 РЕКОМЕНДАЦИИ:")
        for i, rec in enumerate(report["performance_recommendations"], 1):
            print(f"{i}. {rec}")
        
        # Детальные результаты
        print("\n📈 ДЕТАЛЬНЫЕ РЕЗУЛЬТАТЫ:")
        for result in report["individual_test_results"]:
            print(f"\n{result['test_name']}:")
            print(f"  Запросов: {result['total_requests']} (успешных: {result['successful_requests']})")
            print(f"  Время ответа: {result['avg_response_time_ms']:.2f} мс (мин: {result['min_response_time_ms']:.2f}, макс: {result['max_response_time_ms']:.2f})")
            print(f"  RPS: {result['requests_per_second']:.2f}")
            print(f"  Частота ошибок: {result['error_rate']*100:.2f}%")
        
        # Возврат кода выхода
        if summary['overall_status'] == "FAILED":
            sys.exit(1)
        elif summary['overall_status'] == "WARNING":
            sys.exit(2)
        else:
            sys.exit(0)
            
    except Exception as e:
        print(f"❌ Критическая ошибка нагрузочного тестирования: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())