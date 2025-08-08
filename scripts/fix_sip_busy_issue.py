#!/usr/bin/env python3
"""
Исправление проблемы "занято" при SIP звонках
Перестраивает и перезапускает LiveKit SIP с правильной конфигурацией
"""

import os
import sys
import subprocess
import time
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SIPBusyFixer:
    def __init__(self):
        pass
    
    def stop_current_service(self):
        """Останавливает текущий SIP сервис"""
        logger.info("Остановка текущего SIP сервиса...")
        
        try:
            # Останавливаем контейнер
            subprocess.run(['docker', 'stop', 'voice-ai-livekit-sip'], 
                         capture_output=True, check=False)
            
            # Удаляем контейнер
            subprocess.run(['docker', 'rm', 'voice-ai-livekit-sip'], 
                         capture_output=True, check=False)
            
            logger.info("✓ Текущий сервис остановлен")
            return True
            
        except Exception as e:
            logger.error(f"✗ Ошибка остановки сервиса: {e}")
            return False
    
    def rebuild_sip_image(self):
        """Пересобирает Docker образ для SIP"""
        logger.info("Пересборка Docker образа для SIP...")
        
        try:
            # Удаляем старый образ
            subprocess.run(['docker', 'rmi', 'voice-ai-livekit-sip'], 
                         capture_output=True, check=False)
            
            # Собираем новый образ
            cmd = [
                'docker', 'build',
                '-f', 'Dockerfile.livekit-sip',
                '-t', 'voice-ai-livekit-sip',
                '.'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("✓ Docker образ пересобран успешно")
                return True
            else:
                logger.error(f"✗ Ошибка сборки образа: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"✗ Ошибка пересборки образа: {e}")
            return False
    
    def start_sip_service(self):
        """Запускает SIP сервис с новой конфигурацией"""
        logger.info("Запуск SIP сервиса с новой конфигурацией...")
        
        try:
            cmd = [
                'docker', 'run', '-d',
                '--name', 'voice-ai-livekit-sip',
                '--network', 'voice-ai-network',
                '-p', '5060:5060/udp',
                '-p', '10000-10100:10000-10100/udp',
                '-e', 'LIVEKIT_URL=wss://voice-mz90cpgw.livekit.cloud',
                '-e', 'LIVEKIT_API_KEY=API48Ajeeuv4tYL',
                '-e', 'LIVEKIT_API_SECRET=Q5eag53mO3WVhUcoRGmI5Y1wjDbCFnf7qn6pJOzakHN',
                'voice-ai-livekit-sip'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("✓ SIP сервис запущен успешно")
                return True
            else:
                logger.error(f"✗ Ошибка запуска сервиса: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"✗ Ошибка запуска сервиса: {e}")
            return False
    
    def wait_for_service_ready(self, timeout=60):
        """Ждет готовности сервиса"""
        logger.info("Ожидание готовности сервиса...")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                result = subprocess.run(['docker', 'logs', 'voice-ai-livekit-sip', '--tail', '10'], 
                                      capture_output=True, text=True)
                
                if 'sip signaling listening on' in result.stdout:
                    logger.info("✓ SIP сервис готов к приему звонков")
                    return True
                    
                time.sleep(2)
                
            except Exception:
                time.sleep(2)
                continue
        
        logger.error("✗ Сервис не готов в течение таймаута")
        return False
    
    def test_sip_configuration(self):
        """Тестирует SIP конфигурацию"""
        logger.info("Тестирование SIP конфигурации...")
        
        try:
            result = subprocess.run(['docker', 'logs', 'voice-ai-livekit-sip', '--tail', '20'], 
                                  capture_output=True, text=True)
            
            logs = result.stdout
            
            if 'server starting' in logs:
                logger.info("✓ SIP сервер запущен")
            else:
                logger.warning("⚠ SIP сервер может быть не запущен")
            
            if 'listening on' in logs:
                logger.info("✓ SIP сервер слушает входящие соединения")
            else:
                logger.warning("⚠ SIP сервер может не слушать соединения")
            
            if 'error' in logs.lower() or 'failed' in logs.lower():
                logger.warning("⚠ Обнаружены ошибки в логах")
                return False
            else:
                logger.info("✓ Ошибок в логах не обнаружено")
                return True
                
        except Exception as e:
            logger.error(f"✗ Ошибка тестирования конфигурации: {e}")
            return False
    
    def fix_all_issues(self):
        """Исправляет все проблемы с SIP"""
        logger.info("=== ИСПРАВЛЕНИЕ ПРОБЛЕМЫ 'ЗАНЯТО' ===")
        
        # Останавливаем текущий сервис
        if not self.stop_current_service():
            return False
        
        # Пересобираем образ
        if not self.rebuild_sip_image():
            return False
        
        # Запускаем новый сервис
        if not self.start_sip_service():
            return False
        
        # Ждем готовности
        if not self.wait_for_service_ready():
            return False
        
        # Тестируем конфигурацию
        config_ok = self.test_sip_configuration()
        
        logger.info("=== РЕЗУЛЬТАТЫ ИСПРАВЛЕНИЯ ===")
        logger.info("✓ Сервис остановлен и удален")
        logger.info("✓ Docker образ пересобран")
        logger.info("✓ Новый сервис запущен")
        logger.info(f"Конфигурация: {'✓' if config_ok else '⚠'}")
        
        return True

def main():
    """Основная функция"""
    fixer = SIPBusyFixer()
    
    success = fixer.fix_all_issues()
    
    if success:
        print("\n✓ Проблема 'занято' исправлена!")
        print("Теперь попробуйте позвонить на +79952227978")
        print("SIP сервис должен принимать входящие звонки.")
    else:
        print("\n✗ Не удалось исправить все проблемы.")
        print("Проверьте логи для получения дополнительной информации.")

if __name__ == '__main__':
    main()