#!/usr/bin/env python3
"""
Специализированная валидация требований безопасности LiveKit системы.
Проверяет все критические аспекты безопасности согласно требованиям.
"""

import os
import re
import ssl
import socket
import asyncio
import logging
import json
import time
from typing import Dict, Any, List
from pathlib import Path
import jwt
from urllib.parse import urlparse

class SecurityValidator:
    """Валидатор безопасности LiveKit системы."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.project_root = Path(__file__).parent.parent
        self.security_issues = []
        self.security_warnings = []
    
    async def run_comprehensive_security_audit(self) -> Dict[str, Any]:
        """Запуск комплексного аудита безопасности."""
        print("🔒 Начало аудита безопасности системы...")
        
        audit_results = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "checks": {}
        }
        
        # Проверка защиты API ключей
        audit_results["checks"]["api_keys_protection"] = await self._check_api_keys_protection()
        
        # Проверка использования WSS соединений
        audit_results["checks"]["wss_connections"] = await self._check_wss_connections()
        
        # Проверка JWT токенов
        audit_results["checks"]["jwt_security"] = await self._check_jwt_security()
        
        # Проверка валидации прав доступа
        audit_results["checks"]["permissions_validation"] = await self._check_permissions_validation()
        
        # Проверка конфигурационных файлов
        audit_results["checks"]["config_security"] = await self._check_config_security()
        
        # Проверка логирования
        audit_results["checks"]["logging_security"] = await self._check_logging_security()
        
        # Проверка сетевой безопасности
        audit_results["checks"]["network_security"] = await self._check_network_security()
        
        # Общая оценка безопасности
        audit_results["overall_assessment"] = self._assess_overall_security(audit_results["checks"])
        audit_results["security_issues"] = self.security_issues
        audit_results["security_warnings"] = self.security_warnings
        
        return audit_results
    
    async def _check_api_keys_protection(self) -> Dict[str, Any]:
        """Проверка защиты API ключей от утечки."""
        print("  🔑 Проверка защиты API ключей...")
        
        issues = []
        warnings = []
        
        # Проверка переменных окружения
        api_key = os.getenv('LIVEKIT_API_KEY')
        api_secret = os.getenv('LIVEKIT_API_SECRET')
        
        if not api_key or not api_secret:
            issues.append("API ключи не настроены в переменных окружения")
        
        # Проверка файлов на наличие хардкодных ключей
        source_files = list(self.project_root.rglob("*.py"))
        source_files.extend(list(self.project_root.rglob("*.yaml")))
        source_files.extend(list(self.project_root.rglob("*.yml")))
        
        hardcoded_patterns = [
            r'LIVEKIT_API_KEY\s*=\s*["\'][^"\']+["\']',
            r'LIVEKIT_API_SECRET\s*=\s*["\'][^"\']+["\']',
            r'api_key\s*:\s*["\'][^"\']+["\']',
            r'api_secret\s*:\s*["\'][^"\']+["\']'
        ]
        
        for file_path in source_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                for pattern in hardcoded_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        issues.append(f"Возможно хардкодный ключ в файле: {file_path}")
                        break
                        
            except Exception:
                continue
        
        # Проверка .env файла
        env_file = self.project_root / ".env"
        if env_file.exists():
            try:
                with open(env_file, 'r') as f:
                    env_content = f.read()
                    if "LIVEKIT_API_KEY=" in env_content and "LIVEKIT_API_SECRET=" in env_content:
                        # Проверка что файл не в git
                        gitignore_file = self.project_root / ".gitignore"
                        if gitignore_file.exists():
                            with open(gitignore_file, 'r') as gf:
                                gitignore_content = gf.read()
                                if ".env" not in gitignore_content:
                                    warnings.append(".env файл может не быть исключен из git")
            except Exception:
                pass
        
        self.security_issues.extend(issues)
        self.security_warnings.extend(warnings)
        
        return {
            "status": "FAIL" if issues else "PASS",
            "issues": issues,
            "warnings": warnings,
            "api_keys_in_env": bool(api_key and api_secret),
            "hardcoded_keys_found": len([i for i in issues if "хардкодный ключ" in i])
        }   
 async def _check_wss_connections(self) -> Dict[str, Any]:
        """Проверка использования WSS соединений."""
        print("  🔐 Проверка WSS соединений...")
        
        issues = []
        warnings = []
        
        # Проверка URL LiveKit
        livekit_url = os.getenv('LIVEKIT_URL', '')
        
        if livekit_url:
            parsed_url = urlparse(livekit_url)
            if parsed_url.scheme not in ['https', 'wss']:
                issues.append(f"LiveKit URL использует небезопасный протокол: {parsed_url.scheme}")
            
            # Проверка SSL сертификата
            if parsed_url.scheme in ['https', 'wss']:
                try:
                    hostname = parsed_url.hostname
                    port = parsed_url.port or (443 if parsed_url.scheme == 'https' else 443)
                    
                    context = ssl.create_default_context()
                    with socket.create_connection((hostname, port), timeout=10) as sock:
                        with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                            cert = ssock.getpeercert()
                            # Проверка срока действия сертификата
                            import datetime
                            not_after = datetime.datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
                            if not_after < datetime.datetime.now():
                                issues.append("SSL сертификат истек")
                            elif (not_after - datetime.datetime.now()).days < 30:
                                warnings.append("SSL сертификат истекает в течение 30 дней")
                                
                except Exception as e:
                    warnings.append(f"Не удалось проверить SSL сертификат: {e}")
        else:
            issues.append("LIVEKIT_URL не настроен")
        
        # Проверка конфигурационных файлов на использование HTTP
        config_files = list(self.project_root.rglob("*.yaml"))
        config_files.extend(list(self.project_root.rglob("*.yml")))
        config_files.extend(list(self.project_root.rglob("*.py")))
        
        for file_path in config_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if re.search(r'http://[^/\s]+', content):
                        warnings.append(f"Найдены HTTP URL в файле: {file_path}")
            except Exception:
                continue
        
        self.security_issues.extend(issues)
        self.security_warnings.extend(warnings)
        
        return {
            "status": "FAIL" if issues else "PASS",
            "issues": issues,
            "warnings": warnings,
            "livekit_url_secure": livekit_url.startswith(('https://', 'wss://')) if livekit_url else False
        }
    
    async def _check_jwt_security(self) -> Dict[str, Any]:
        """Проверка безопасности JWT токенов."""
        print("  🎫 Проверка безопасности JWT токенов...")
        
        issues = []
        warnings = []
        
        try:
            # Проверка наличия auth модуля
            auth_file = self.project_root / "src" / "auth" / "livekit_auth.py"
            if not auth_file.exists():
                issues.append("Модуль аутентификации не найден")
                return {
                    "status": "FAIL",
                    "issues": issues,
                    "warnings": warnings
                }
            
            # Анализ кода аутентификации
            with open(auth_file, 'r', encoding='utf-8') as f:
                auth_content = f.read()
                
                # Проверка использования правильного алгоритма
                if 'HS256' not in auth_content and 'algorithm=' not in auth_content:
                    warnings.append("Не указан алгоритм подписи JWT")
                
                # Проверка времени жизни токенов
                if 'timedelta' in auth_content:
                    # Поиск настроек времени жизни
                    ttl_matches = re.findall(r'timedelta\([^)]+\)', auth_content)
                    for match in ttl_matches:
                        if 'hours' in match:
                            hours_match = re.search(r'hours=(\d+)', match)
                            if hours_match and int(hours_match.group(1)) > 24:
                                warnings.append("Слишком долгое время жизни токена (>24 часов)")
                        elif 'days' in match:
                            warnings.append("Время жизни токена указано в днях - может быть слишком долго")
                
                # Проверка обязательных полей
                required_fields = ['iss', 'sub', 'iat', 'exp', 'video']
                for field in required_fields:
                    if field not in auth_content:
                        warnings.append(f"Возможно отсутствует обязательное поле JWT: {field}")
        
        except Exception as e:
            issues.append(f"Ошибка анализа JWT безопасности: {e}")
        
        self.security_issues.extend(issues)
        self.security_warnings.extend(warnings)
        
        return {
            "status": "FAIL" if issues else ("WARNING" if warnings else "PASS"),
            "issues": issues,
            "warnings": warnings,
            "auth_module_exists": auth_file.exists()
        }
    
    async def _check_permissions_validation(self) -> Dict[str, Any]:
        """Проверка валидации прав доступа."""
        print("  👮 Проверка валидации прав доступа...")
        
        issues = []
        warnings = []
        
        # Проверка наличия системы валидации прав
        security_files = [
            self.project_root / "src" / "security" / "livekit_security.py",
            self.project_root / "src" / "auth" / "livekit_auth.py"
        ]
        
        validation_found = False
        for file_path in security_files:
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if any(keyword in content.lower() for keyword in ['permission', 'grant', 'validate', 'authorize']):
                            validation_found = True
                            break
                except Exception:
                    continue
        
        if not validation_found:
            issues.append("Система валидации прав доступа не найдена")
        
        # Проверка использования VideoGrants
        auth_file = self.project_root / "src" / "auth" / "livekit_auth.py"
        if auth_file.exists():
            try:
                with open(auth_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if 'VideoGrants' not in content:
                        warnings.append("VideoGrants может не использоваться")
                    
                    # Проверка основных прав
                    required_grants = ['room_join', 'can_publish', 'can_subscribe']
                    for grant in required_grants:
                        if grant not in content:
                            warnings.append(f"Право доступа {grant} может не проверяться")
            except Exception:
                pass
        
        self.security_issues.extend(issues)
        self.security_warnings.extend(warnings)
        
        return {
            "status": "FAIL" if issues else ("WARNING" if warnings else "PASS"),
            "issues": issues,
            "warnings": warnings,
            "validation_system_found": validation_found
        }    async d
ef _check_config_security(self) -> Dict[str, Any]:
        """Проверка безопасности конфигурационных файлов."""
        print("  📋 Проверка безопасности конфигурации...")
        
        issues = []
        warnings = []
        
        # Проверка прав доступа к файлам
        sensitive_files = [
            ".env",
            "config/security.yaml",
            "livekit-sip-correct.yaml"
        ]
        
        for file_name in sensitive_files:
            file_path = self.project_root / file_name
            if file_path.exists():
                try:
                    stat_info = file_path.stat()
                    # Проверка прав доступа (должны быть ограничены)
                    mode = oct(stat_info.st_mode)[-3:]
                    if mode != '600' and mode != '644':
                        warnings.append(f"Файл {file_name} имеет слишком открытые права доступа: {mode}")
                except Exception:
                    pass
        
        # Проверка наличия секретов в конфигурации
        config_files = list(self.project_root.rglob("*.yaml"))
        config_files.extend(list(self.project_root.rglob("*.yml")))
        
        for file_path in config_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                    # Поиск потенциальных секретов
                    secret_patterns = [
                        r'password\s*:\s*["\'][^"\']{8,}["\']',
                        r'secret\s*:\s*["\'][^"\']{8,}["\']',
                        r'key\s*:\s*["\'][^"\']{8,}["\']'
                    ]
                    
                    for pattern in secret_patterns:
                        if re.search(pattern, content, re.IGNORECASE):
                            # Проверка что это не переменная окружения
                            if not re.search(r'\$\{[^}]+\}', content):
                                warnings.append(f"Возможный хардкодный секрет в файле: {file_path}")
                                break
            except Exception:
                continue
        
        self.security_warnings.extend(warnings)
        
        return {
            "status": "WARNING" if warnings else "PASS",
            "issues": issues,
            "warnings": warnings,
            "sensitive_files_checked": len(sensitive_files)
        }
    
    async def _check_logging_security(self) -> Dict[str, Any]:
        """Проверка безопасности логирования."""
        print("  📝 Проверка безопасности логирования...")
        
        issues = []
        warnings = []
        
        # Проверка файлов на логирование секретов
        source_files = list(self.project_root.rglob("*.py"))
        
        dangerous_logging_patterns = [
            r'log.*api_key',
            r'log.*api_secret',
            r'log.*password',
            r'log.*token',
            r'print.*api_key',
            r'print.*api_secret',
            r'print.*password'
        ]
        
        for file_path in source_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                    for pattern in dangerous_logging_patterns:
                        if re.search(pattern, content, re.IGNORECASE):
                            warnings.append(f"Возможное логирование секретов в файле: {file_path}")
                            break
            except Exception:
                continue
        
        # Проверка настроек логирования
        logging_config_files = [
            self.project_root / "config" / "logging.yaml",
            self.project_root / "src" / "monitoring" / "livekit_logging.py"
        ]
        
        logging_configured = any(f.exists() for f in logging_config_files)
        if not logging_configured:
            warnings.append("Специализированная конфигурация логирования не найдена")
        
        self.security_warnings.extend(warnings)
        
        return {
            "status": "WARNING" if warnings else "PASS",
            "issues": issues,
            "warnings": warnings,
            "logging_configured": logging_configured
        }
    
    async def _check_network_security(self) -> Dict[str, Any]:
        """Проверка сетевой безопасности."""
        print("  🌐 Проверка сетевой безопасности...")
        
        issues = []
        warnings = []
        
        # Проверка настроек SIP безопасности
        sip_config_file = self.project_root / "livekit-sip-correct.yaml"
        if sip_config_file.exists():
            try:
                with open(sip_config_file, 'r', encoding='utf-8') as f:
                    sip_content = f.read()
                    
                    # Проверка allowed_addresses
                    if "0.0.0.0/0" in sip_content:
                        warnings.append("SIP конфигурация разрешает подключения с любых IP адресов")
                    
                    # Проверка аутентификации
                    if "auth_required: false" in sip_content:
                        issues.append("SIP аутентификация отключена")
                    
                    # Проверка транспорта
                    if "transport: UDP" in sip_content:
                        warnings.append("Используется UDP транспорт для SIP (менее безопасен чем TLS)")
                        
            except Exception:
                pass
        
        # Проверка настроек Redis безопасности
        redis_url = os.getenv('REDIS_URL', '')
        if redis_url:
            if not redis_url.startswith('rediss://'):
                warnings.append("Redis подключение не использует SSL/TLS")
            
            # Проверка аутентификации Redis
            if '@' not in redis_url:
                warnings.append("Redis подключение может не использовать аутентификацию")
        
        self.security_issues.extend(issues)
        self.security_warnings.extend(warnings)
        
        return {
            "status": "FAIL" if issues else ("WARNING" if warnings else "PASS"),
            "issues": issues,
            "warnings": warnings,
            "sip_config_exists": sip_config_file.exists(),
            "redis_configured": bool(redis_url)
        }
    
    def _assess_overall_security(self, checks: Dict[str, Any]) -> Dict[str, Any]:
        """Общая оценка безопасности системы."""
        
        critical_failures = sum(1 for check in checks.values() if check.get("status") == "FAIL")
        warnings_count = sum(1 for check in checks.values() if check.get("status") == "WARNING")
        total_checks = len(checks)
        
        if critical_failures > 0:
            overall_status = "CRITICAL"
            risk_level = "HIGH"
        elif warnings_count > total_checks // 2:
            overall_status = "NEEDS_ATTENTION"
            risk_level = "MEDIUM"
        elif warnings_count > 0:
            overall_status = "ACCEPTABLE"
            risk_level = "LOW"
        else:
            overall_status = "SECURE"
            risk_level = "MINIMAL"
        
        recommendations = []
        
        if critical_failures > 0:
            recommendations.append("Немедленно устраните критические проблемы безопасности")
        
        if len(self.security_issues) > 0:
            recommendations.append("Исправьте все выявленные проблемы безопасности")
        
        if len(self.security_warnings) > 0:
            recommendations.append("Рассмотрите устранение предупреждений безопасности")
        
        if not recommendations:
            recommendations.append("Система соответствует требованиям безопасности")
        
        return {
            "overall_status": overall_status,
            "risk_level": risk_level,
            "critical_failures": critical_failures,
            "warnings_count": warnings_count,
            "total_checks": total_checks,
            "security_score": max(0, 100 - (critical_failures * 30) - (warnings_count * 10)),
            "recommendations": recommendations
        }

async def main():
    """Главная функция запуска аудита безопасности."""
    print("🔒 Запуск комплексного аудита безопасности LiveKit системы")
    print("=" * 60)
    
    validator = SecurityValidator()
    
    try:
        audit_results = await validator.run_comprehensive_security_audit()
        
        print("\n" + "=" * 60)
        print("🛡️  ОТЧЕТ ПО БЕЗОПАСНОСТИ")
        print("=" * 60)
        
        assessment = audit_results["overall_assessment"]
        print(f"Общий статус: {assessment['overall_status']}")
        print(f"Уровень риска: {assessment['risk_level']}")
        print(f"Оценка безопасности: {assessment['security_score']}/100")
        print(f"Критические проблемы: {assessment['critical_failures']}")
        print(f"Предупреждения: {assessment['warnings_count']}")
        
        print("\n📋 РЕКОМЕНДАЦИИ:")
        for i, rec in enumerate(assessment["recommendations"], 1):
            print(f"{i}. {rec}")
        
        if audit_results["security_issues"]:
            print("\n❌ КРИТИЧЕСКИЕ ПРОБЛЕМЫ:")
            for i, issue in enumerate(audit_results["security_issues"], 1):
                print(f"{i}. {issue}")
        
        if audit_results["security_warnings"]:
            print("\n⚠️  ПРЕДУПРЕЖДЕНИЯ:")
            for i, warning in enumerate(audit_results["security_warnings"], 1):
                print(f"{i}. {warning}")
        
        # Сохранение отчета
        report_file = f"security_audit_report_{int(time.time())}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(audit_results, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 Полный отчет сохранен в {report_file}")
        
        # Возврат кода выхода
        if assessment['overall_status'] == "CRITICAL":
            sys.exit(1)
        elif assessment['overall_status'] in ["NEEDS_ATTENTION", "ACCEPTABLE"]:
            sys.exit(2)
        else:
            sys.exit(0)
            
    except Exception as e:
        print(f"❌ Критическая ошибка аудита безопасности: {e}")
        sys.exit(1)

if __name__ == "__main__":
    import sys
    asyncio.run(main())