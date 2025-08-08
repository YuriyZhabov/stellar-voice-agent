#!/usr/bin/env python3
"""
Примеры использования всех API LiveKit
Демонстрирует правильное использование всех компонентов системы согласно спецификации.
"""

import asyncio
import os
import json
from datetime import datetime, UTC
from typing import Dict, Any, List, Optional

# Импорты компонентов системы
from src.auth.livekit_auth import LiveKitAuthManager
from src.clients.livekit_api_client import LiveKitAPIClient
from src.services.livekit_egress import LiveKitEgressService
from src.services.livekit_ingress import LiveKitIngressService
from src.monitoring.livekit_system_monitor import LiveKitSystemMonitor
from src.security.livekit_security import LiveKitSecurityManager
from src.integration.livekit_voice_ai_integration import LiveKitVoiceAIIntegration

class LiveKitAPIExamples:
    """Класс с примерами использования всех API LiveKit."""
    
    def __init__(self):
        """Инициализация с переменными окружения."""
        self.url = os.getenv('LIVEKIT_URL', 'wss://your-livekit-server.com')
        self.api_key = os.getenv('LIVEKIT_API_KEY', 'your_api_key')
        self.api_secret = os.getenv('LIVEKIT_API_SECRET', 'your_api_secret')
        
        # Инициализация компонентов
        self.auth_manager = LiveKitAuthManager(self.api_key, self.api_secret)
        self.api_client = LiveKitAPIClient(self.url, self.api_key, self.api_secret)
        self.egress_service = LiveKitEgressService(self.api_client)
        self.ingress_service = LiveKitIngressService(self.api_client)
        self.monitor = LiveKitSystemMonitor(self.api_client)
        self.security_manager = LiveKitSecurityManager(self.api_key, self.api_secret)
        self.voice_ai_integration = LiveKitVoiceAIIntegration(self.api_client)
    
    async def authentication_examples(self):
        """Примеры работы с аутентификацией."""
        print("=== Примеры аутентификации ===")
        
        # 1. Создание токена участника
        print("\n1. Создание токена участника:")
        participant_token = self.auth_manager.create_participant_token(
            identity="user123",
            room_name="voice-ai-call-123"
        )
        print(f"Токен участника создан: {participant_token[:50]}...")
        
        # 2. Создание административного токена
        print("\n2. Создание административного токена:")
        admin_token = self.auth_manager.create_admin_token()
        print(f"Административный токен создан: {admin_token[:50]}...")
        
        # 3. Создание токена только для просмотра
        print("\n3. Создание токена только для просмотра:")
        from livekit.api import VideoGrants
        
        view_only_grants = VideoGrants(
            room_join=True,
            can_subscribe=True,
            can_publish=False,
            can_publish_data=False
        )
        
        view_token = self.auth_manager.create_participant_token(
            identity="viewer456",
            room_name="voice-ai-call-123",
            grants=view_only_grants
        )
        print(f"Токен для просмотра создан: {view_token[:50]}...")
        
        # 4. Создание токена с ограниченными источниками
        print("\n4. Создание токена с ограниченными источниками:")
        camera_grants = VideoGrants(
            room_join=True,
            can_publish=True,
            can_subscribe=True,
            can_publish_sources=["camera"]  # Только камера
        )
        
        camera_token = self.auth_manager.create_participant_token(
            identity="camera_user",
            room_name="voice-ai-call-123",
            grants=camera_grants
        )
        print(f"Токен для камеры создан: {camera_token[:50]}...")
    
    async def room_service_examples(self):
        """Примеры работы с RoomService API."""
        print("\n=== Примеры RoomService API ===")
        
        # 1. Создание комнаты
        print("\n1. Создание комнаты:")
        room_name = f"example-room-{int(datetime.now(UTC).timestamp())}"
        
        room = await self.api_client.create_room(
            name=room_name,
            empty_timeout=300,  # 5 минут
            departure_timeout=20,  # 20 секунд
            max_participants=10,
            metadata={
                "call_type": "voice_ai",
                "created_by": "api_example",
                "timestamp": datetime.now(UTC).isoformat()
            }
        )
        print(f"Комната создана: {room.name}")
        
        # 2. Список всех комнат
        print("\n2. Получение списка комнат:")
        rooms = await self.api_client.list_rooms()
        print(f"Найдено комнат: {len(rooms)}")
        for room in rooms[:3]:  # Показать первые 3
            print(f"  - {room.name} (участников: {room.num_participants})")
        
        # 3. Получение информации о конкретной комнате
        print(f"\n3. Информация о комнате {room_name}:")
        room_info = await self.api_client.get_room(room_name)
        print(f"  Название: {room_info.name}")
        print(f"  Участников: {room_info.num_participants}")
        print(f"  Создана: {room_info.creation_time}")
        
        # 4. Список участников комнаты
        print(f"\n4. Участники комнаты {room_name}:")
        participants = await self.api_client.list_participants(room_name)
        print(f"Участников в комнате: {len(participants)}")
        
        # 5. Обновление метаданных комнаты
        print(f"\n5. Обновление метаданных комнаты:")
        updated_metadata = {
            "status": "active",
            "last_updated": datetime.now(UTC).isoformat()
        }
        await self.api_client.update_room_metadata(room_name, updated_metadata)
        print("Метаданные обновлены")
        
        # 6. Удаление комнаты
        print(f"\n6. Удаление комнаты {room_name}:")
        await self.api_client.delete_room(room_name)
        print("Комната удалена")
    
    async def participant_management_examples(self):
        """Примеры управления участниками."""
        print("\n=== Примеры управления участниками ===")
        
        # Создаем тестовую комнату
        room_name = f"participant-test-{int(datetime.now(UTC).timestamp())}"
        await self.api_client.create_room(room_name)
        
        try:
            # 1. Симуляция подключения участника (в реальности участник подключается через SDK)
            print("\n1. Управление участниками:")
            print("Участники подключаются через LiveKit SDK с токенами")
            
            # 2. Получение информации об участнике
            participants = await self.api_client.list_participants(room_name)
            if participants:
                participant = participants[0]
                print(f"\n2. Информация об участнике:")
                print(f"  Identity: {participant.identity}")
                print(f"  Name: {participant.name}")
                print(f"  Подключен: {participant.joined_at}")
                
                # 3. Обновление метаданных участника
                print(f"\n3. Обновление метаданных участника:")
                await self.api_client.update_participant(
                    room_name=room_name,
                    identity=participant.identity,
                    metadata=json.dumps({"role": "speaker", "updated": True})
                )
                print("Метаданные участника обновлены")
                
                # 4. Управление треками участника
                print(f"\n4. Управление треками:")
                for track in participant.tracks:
                    print(f"  Трек: {track.sid} ({track.type})")
                    
                    # Отключение трека
                    await self.api_client.mute_track(
                        room_name=room_name,
                        identity=participant.identity,
                        track_sid=track.sid,
                        muted=True
                    )
                    print(f"  Трек {track.sid} отключен")
                
                # 5. Удаление участника
                print(f"\n5. Удаление участника:")
                await self.api_client.remove_participant(room_name, participant.identity)
                print("Участник удален")
            else:
                print("Нет активных участников для демонстрации")
        
        finally:
            # Очистка
            await self.api_client.delete_room(room_name)
    
    async def egress_examples(self):
        """Примеры работы с Egress API."""
        print("\n=== Примеры Egress API ===")
        
        # Создаем тестовую комнату
        room_name = f"egress-test-{int(datetime.now(UTC).timestamp())}"
        await self.api_client.create_room(room_name)
        
        try:
            # 1. Room Composite Egress - запись всей комнаты
            print("\n1. Запись комнаты в MP4:")
            
            # Конфигурация для записи в файл
            file_output = self.egress_service.create_file_output_config(
                filename=f"room-recording-{room_name}.mp4",
                filepath="/recordings/"
            )
            
            egress_id = await self.egress_service.start_room_recording(
                room_name=room_name,
                output_config=file_output
            )
            print(f"Запись начата, Egress ID: {egress_id}")
            
            # 2. RTMP Stream Egress - трансляция в реальном времени
            print("\n2. RTMP трансляция:")
            
            rtmp_output = self.egress_service.create_rtmp_output_config([
                "rtmp://live.twitch.tv/live/YOUR_STREAM_KEY",
                "rtmp://a.rtmp.youtube.com/live2/YOUR_STREAM_KEY"
            ])
            
            stream_egress_id = await self.egress_service.start_room_recording(
                room_name=room_name,
                output_config=rtmp_output
            )
            print(f"RTMP трансляция начата, Egress ID: {stream_egress_id}")
            
            # 3. S3 Upload Egress
            print("\n3. Загрузка записи в S3:")
            
            s3_output = self.egress_service.create_s3_output_config(
                filename=f"s3-recording-{room_name}.mp4",
                bucket="my-recordings-bucket",
                access_key="YOUR_ACCESS_KEY",
                secret="YOUR_SECRET_KEY",
                region="us-east-1"
            )
            
            s3_egress_id = await self.egress_service.start_room_recording(
                room_name=room_name,
                output_config=s3_output
            )
            print(f"S3 запись начата, Egress ID: {s3_egress_id}")
            
            # 4. Track Composite Egress - запись отдельных треков
            print("\n4. Запись отдельных треков:")
            
            track_output = {
                "file": {
                    "filename": f"tracks-{room_name}.mp4",
                    "filepath": "/recordings/tracks/"
                }
            }
            
            track_egress_id = await self.egress_service.start_track_composite_egress(
                room_name=room_name,
                audio_track_id="audio_track_123",
                video_track_id="video_track_456",
                output_config=track_output
            )
            print(f"Запись треков начата, Egress ID: {track_egress_id}")
            
            # 5. Получение статуса Egress
            print("\n5. Статус записей:")
            egress_list = await self.egress_service.list_egress(room_name)
            for egress in egress_list:
                print(f"  Egress {egress.egress_id}: {egress.status}")
            
            # 6. Остановка записи
            print("\n6. Остановка записи:")
            await self.egress_service.stop_egress(egress_id)
            print(f"Запись {egress_id} остановлена")
        
        finally:
            # Очистка
            await self.api_client.delete_room(room_name)
    
    async def ingress_examples(self):
        """Примеры работы с Ingress API."""
        print("\n=== Примеры Ingress API ===")
        
        # 1. RTMP Ingress - прием потока от OBS/XSplit
        print("\n1. Создание RTMP Ingress:")
        
        rtmp_ingress = await self.ingress_service.create_rtmp_ingress(
            name="obs-stream-ingress",
            room_name="streaming-room",
            participant_identity="streamer",
            participant_name="OBS Streamer"
        )
        
        print(f"RTMP Ingress создан:")
        print(f"  ID: {rtmp_ingress['ingress_id']}")
        print(f"  URL: {rtmp_ingress['url']}")
        print(f"  Stream Key: {rtmp_ingress['stream_key']}")
        print(f"  Настройки OBS: Server = {rtmp_ingress['url']}, Key = {rtmp_ingress['stream_key']}")
        
        # 2. WHIP Ingress - WebRTC-HTTP Ingestion
        print("\n2. Создание WHIP Ingress:")
        
        whip_ingress = await self.ingress_service.create_whip_ingress(
            name="webrtc-ingress",
            room_name="webrtc-room",
            participant_identity="webrtc_publisher",
            bypass_transcoding=False
        )
        
        print(f"WHIP Ingress создан:")
        print(f"  ID: {whip_ingress['ingress_id']}")
        print(f"  URL: {whip_ingress['url']}")
        print(f"  Использование: POST запрос с WebRTC offer на URL")
        
        # 3. URL Input Ingress - импорт из файлов/потоков
        print("\n3. Создание URL Input Ingress:")
        
        url_ingress = await self.ingress_service.create_url_input_ingress(
            name="file-import",
            room_name="import-room",
            participant_identity="file_player",
            url="https://example.com/sample.mp4"
        )
        
        print(f"URL Input Ingress создан:")
        print(f"  ID: {url_ingress['ingress_id']}")
        print(f"  Источник: https://example.com/sample.mp4")
        
        # 4. Список всех Ingress
        print("\n4. Список всех Ingress:")
        ingress_list = await self.ingress_service.list_ingress()
        for ingress in ingress_list:
            print(f"  {ingress.name} ({ingress.input_type}): {ingress.state}")
        
        # 5. Обновление Ingress
        print("\n5. Обновление Ingress:")
        await self.ingress_service.update_ingress(
            ingress_id=rtmp_ingress['ingress_id'],
            name="updated-obs-stream",
            room_name="updated-streaming-room"
        )
        print("Ingress обновлен")
        
        # 6. Удаление Ingress
        print("\n6. Удаление Ingress:")
        await self.ingress_service.delete_ingress(rtmp_ingress['ingress_id'])
        print("RTMP Ingress удален")
    
    async def monitoring_examples(self):
        """Примеры мониторинга системы."""
        print("\n=== Примеры мониторинга ===")
        
        # 1. Полная проверка здоровья системы
        print("\n1. Проверка здоровья системы:")
        health_status = await self.monitor.run_health_checks()
        
        print(f"Время проверки: {health_status['timestamp']}")
        for service, status in health_status['checks'].items():
            print(f"  {service}: {status['status']}")
            if 'latency_ms' in status:
                print(f"    Латентность: {status['latency_ms']}ms")
        
        # 2. Мониторинг производительности
        print("\n2. Метрики производительности:")
        performance = await self.monitor._check_performance()
        print(f"  Средняя латентность API: {performance['avg_api_latency_ms']}ms")
        print(f"  Активных комнат: {performance['active_rooms']}")
        print(f"  Активных участников: {performance['active_participants']}")
        print(f"  Процент ошибок: {performance['error_rate']:.2%}")
        
        # 3. Мониторинг ресурсов
        print("\n3. Использование ресурсов:")
        resources = await self.monitor.check_resource_usage()
        print(f"  CPU: {resources['cpu_percent']:.1f}%")
        print(f"  Memory: {resources['memory_percent']:.1f}%")
        print(f"  Disk: {resources['disk_percent']:.1f}%")
        
        # 4. Проверка качества соединений
        print("\n4. Качество соединений:")
        connection_quality = await self.monitor.check_connection_quality()
        print(f"  Успешных подключений: {connection_quality['successful_connections']}")
        print(f"  Неудачных подключений: {connection_quality['failed_connections']}")
        print(f"  Средняя задержка: {connection_quality['avg_latency_ms']}ms")
        
        # 5. Алерты и уведомления
        print("\n5. Система алертов:")
        from src.monitoring.livekit_alerting import LiveKitAlerting
        
        alerting = LiveKitAlerting()
        
        # Отправка тестового алерта
        await alerting.send_alert(
            level="info",
            message="Тестовый алерт системы мониторинга",
            details={"component": "monitoring", "test": True}
        )
        print("Тестовый алерт отправлен")
    
    async def security_examples(self):
        """Примеры работы с безопасностью."""
        print("\n=== Примеры безопасности ===")
        
        # 1. Валидация токенов
        print("\n1. Валидация токенов:")
        
        # Создаем токен для тестирования
        test_token = self.auth_manager.create_participant_token("test_user", "test_room")
        
        # Валидация токена
        is_valid = await self.security_manager.validate_token(test_token)
        print(f"Токен валиден: {is_valid}")
        
        # Проверка прав доступа
        permissions = await self.security_manager.check_permissions(test_token, "test_room")
        print(f"Права доступа: {permissions}")
        
        # 2. Аудит безопасности
        print("\n2. Аудит безопасности:")
        
        audit_results = await self.security_manager.run_security_audit()
        print(f"Результаты аудита:")
        for check, result in audit_results.items():
            status = "✓" if result['passed'] else "✗"
            print(f"  {status} {check}: {result['message']}")
        
        # 3. Мониторинг подозрительной активности
        print("\n3. Мониторинг активности:")
        
        # Симуляция подозрительной активности
        await self.security_manager.log_activity(
            user_id="suspicious_user",
            action="multiple_failed_logins",
            details={"attempts": 5, "ip": "192.168.1.100"}
        )
        
        # Проверка подозрительной активности
        suspicious_activity = await self.security_manager.check_suspicious_activity()
        print(f"Подозрительная активность обнаружена: {len(suspicious_activity)} событий")
        
        # 4. Ротация ключей
        print("\n4. Ротация ключей:")
        
        # Симуляция ротации (в реальности требует новые ключи)
        rotation_status = await self.security_manager.prepare_key_rotation()
        print(f"Статус подготовки к ротации: {rotation_status['ready']}")
        print(f"Активных токенов: {rotation_status['active_tokens']}")
        
        # 5. Защита от утечек
        print("\n5. Защита от утечек:")
        
        # Проверка логов на утечки ключей
        leak_check = await self.security_manager.check_for_key_leaks()
        if leak_check['found_leaks']:
            print(f"⚠️  Обнаружены потенциальные утечки: {len(leak_check['leaks'])}")
        else:
            print("✓ Утечки ключей не обнаружены")
    
    async def voice_ai_integration_examples(self):
        """Примеры интеграции с Voice AI."""
        print("\n=== Примеры интеграции с Voice AI ===")
        
        # 1. Создание Voice AI сессии
        print("\n1. Создание Voice AI сессии:")
        
        session = await self.voice_ai_integration.create_voice_session(
            caller_number="+1234567890",
            sip_call_id="call_123456"
        )
        
        print(f"Voice AI сессия создана:")
        print(f"  Room: {session['room_name']}")
        print(f"  Participant Token: {session['participant_token'][:50]}...")
        print(f"  Session ID: {session['session_id']}")
        
        # 2. Обработка SIP событий
        print("\n2. Обработка SIP событий:")
        
        # Симуляция входящего звонка
        sip_event = {
            "event_type": "call_started",
            "call_id": "call_123456",
            "caller_number": "+1234567890",
            "called_number": "+0987654321",
            "timestamp": datetime.now(UTC).isoformat()
        }
        
        await self.voice_ai_integration.handle_sip_event(sip_event)
        print("SIP событие обработано")
        
        # 3. Обработка аудио потоков
        print("\n3. Обработка аудио потоков:")
        
        # Симуляция аудио данных
        audio_data = b"fake_audio_data_for_example"
        
        # Обработка через STT
        stt_result = await self.voice_ai_integration.process_audio_input(
            session_id=session['session_id'],
            audio_data=audio_data
        )
        print(f"STT результат: {stt_result}")
        
        # Генерация ответа через LLM
        llm_response = await self.voice_ai_integration.generate_ai_response(
            session_id=session['session_id'],
            user_input=stt_result.get('text', 'Hello')
        )
        print(f"AI ответ: {llm_response}")
        
        # Синтез речи через TTS
        tts_audio = await self.voice_ai_integration.synthesize_speech(
            session_id=session['session_id'],
            text=llm_response
        )
        print(f"TTS аудио сгенерировано: {len(tts_audio)} байт")
        
        # 4. Управление состоянием разговора
        print("\n4. Управление состоянием разговора:")
        
        # Получение текущего состояния
        conversation_state = await self.voice_ai_integration.get_conversation_state(
            session['session_id']
        )
        print(f"Состояние разговора: {conversation_state['state']}")
        print(f"Количество сообщений: {len(conversation_state['messages'])}")
        
        # Обновление состояния
        await self.voice_ai_integration.update_conversation_state(
            session_id=session['session_id'],
            new_state="active",
            metadata={"last_activity": datetime.now(UTC).isoformat()}
        )
        print("Состояние разговора обновлено")
        
        # 5. Завершение сессии
        print("\n5. Завершение сессии:")
        
        session_summary = await self.voice_ai_integration.end_voice_session(
            session['session_id']
        )
        
        print(f"Сессия завершена:")
        print(f"  Длительность: {session_summary['duration_seconds']} сек")
        print(f"  Сообщений обработано: {session_summary['messages_processed']}")
        print(f"  Качество соединения: {session_summary['connection_quality']}")
    
    async def webhook_examples(self):
        """Примеры обработки webhook событий."""
        print("\n=== Примеры Webhook событий ===")
        
        # 1. Обработка событий комнаты
        print("\n1. События комнаты:")
        
        room_started_event = {
            "event": "room_started",
            "room": {
                "sid": "RM_123456",
                "name": "voice-ai-call-789",
                "empty_timeout": 300,
                "creation_time": int(datetime.now(UTC).timestamp())
            }
        }
        
        await self.voice_ai_integration.handle_webhook_event(room_started_event)
        print("Событие 'room_started' обработано")
        
        # 2. Обработка событий участников
        print("\n2. События участников:")
        
        participant_joined_event = {
            "event": "participant_joined",
            "room": {"name": "voice-ai-call-789"},
            "participant": {
                "sid": "PA_789012",
                "identity": "caller_+1234567890",
                "name": "Caller",
                "joined_at": int(datetime.now(UTC).timestamp())
            }
        }
        
        await self.voice_ai_integration.handle_webhook_event(participant_joined_event)
        print("Событие 'participant_joined' обработано")
        
        # 3. Обработка событий треков
        print("\n3. События треков:")
        
        track_published_event = {
            "event": "track_published",
            "room": {"name": "voice-ai-call-789"},
            "participant": {"identity": "caller_+1234567890"},
            "track": {
                "sid": "TR_345678",
                "type": "audio",
                "source": "microphone"
            }
        }
        
        await self.voice_ai_integration.handle_webhook_event(track_published_event)
        print("Событие 'track_published' обработано")
        
        # 4. Обработка событий записи
        print("\n4. События записи:")
        
        egress_started_event = {
            "event": "egress_started",
            "egress_info": {
                "egress_id": "EG_901234",
                "room_name": "voice-ai-call-789",
                "status": "EGRESS_STARTING"
            }
        }
        
        await self.voice_ai_integration.handle_webhook_event(egress_started_event)
        print("Событие 'egress_started' обработано")

async def main():
    """Главная функция для запуска всех примеров."""
    print("🚀 Запуск примеров использования LiveKit API")
    print("=" * 60)
    
    # Проверка переменных окружения
    required_vars = ['LIVEKIT_URL', 'LIVEKIT_API_KEY', 'LIVEKIT_API_SECRET']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"⚠️  Отсутствуют переменные окружения: {', '.join(missing_vars)}")
        print("Установите их в файле .env или экспортируйте в shell")
        return
    
    # Создание экземпляра примеров
    examples = LiveKitAPIExamples()
    
    try:
        # Запуск всех примеров
        await examples.authentication_examples()
        await examples.room_service_examples()
        await examples.participant_management_examples()
        await examples.egress_examples()
        await examples.ingress_examples()
        await examples.monitoring_examples()
        await examples.security_examples()
        await examples.voice_ai_integration_examples()
        await examples.webhook_examples()
        
        print("\n" + "=" * 60)
        print("✅ Все примеры выполнены успешно!")
        print("\nДля использования в production:")
        print("1. Настройте правильные переменные окружения")
        print("2. Адаптируйте примеры под ваши нужды")
        print("3. Добавьте proper error handling")
        print("4. Настройте логирование и мониторинг")
        
    except Exception as e:
        print(f"\n❌ Ошибка при выполнении примеров: {e}")
        print("Проверьте конфигурацию и доступность LiveKit сервера")

if __name__ == "__main__":
    # Запуск примеров
    asyncio.run(main())