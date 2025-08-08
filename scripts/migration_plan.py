#!/usr/bin/env python3
"""
Migration Plan for LiveKit System Configuration
Создание плана миграции с существующей конфигурации
Requirements: 1.1, 2.1, 3.1
"""

import os
import json
import yaml
import shutil
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LiveKitMigrationPlan:
    """План миграции LiveKit системы с существующей конфигурации."""
    
    def __init__(self, backup_dir: str = "backups/migration"):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        
    def analyze_current_configuration(self) -> Dict[str, Any]:
        """Анализ текущей конфигурации системы."""
        logger.info("Analyzing current LiveKit configuration...")
        
        analysis = {
            "timestamp": self.timestamp,
            "current_files": {},
            "migration_needed": [],
            "backup_required": [],
            "risks": [],
            "recommendations": []
        }
        
        # Анализ существующих конфигурационных файлов
        config_files = [
            ".env",
            "livekit-sip.yaml",
            "livekit-sip-correct.yaml",
            "docker-compose.yml",
            "docker-compose.prod.yml",
            "src/livekit_integration.py",
            "src/webhooks.py",
            "src/voice_ai_agent.py"
        ]
        
        for file_path in config_files:
            if os.path.exists(file_path):
                analysis["current_files"][file_path] = {
                    "exists": True,
                    "size": os.path.getsize(file_path),
                    "modified": datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
                }
                analysis["backup_required"].append(file_path)
            else:
                analysis["current_files"][file_path] = {"exists": False}
        
        # Определение необходимых миграций
        migration_tasks = [
            {
                "task": "Update JWT authentication",
                "files": ["src/auth/livekit_auth.py", "config/livekit_auth.yaml"],
                "risk": "medium",
                "description": "Migrate to proper JWT token structure"
            },
            {
                "task": "Update API client endpoints",
                "files": ["src/clients/livekit_api_client.py"],
                "risk": "high",
                "description": "Switch to correct Twirp endpoints"
            },
            {
                "task": "Update SIP configuration",
                "files": ["livekit-sip-correct.yaml"],
                "risk": "high",
                "description": "Replace existing SIP config with correct version"
            },
            {
                "task": "Update webhook handlers",
                "files": ["src/webhooks.py"],
                "risk": "medium",
                "description": "Integrate with new LiveKit events"
            },
            {
                "task": "Update environment variables",
                "files": [".env"],
                "risk": "low",
                "description": "Add new required environment variables"
            }
        ]
        
        analysis["migration_needed"] = migration_tasks
        
        # Оценка рисков
        risks = [
            "Service downtime during migration",
            "Potential authentication failures",
            "SIP call interruptions",
            "Webhook delivery failures",
            "Configuration rollback complexity"
        ]
        analysis["risks"] = risks
        
        # Рекомендации
        recommendations = [
            "Perform migration during low-traffic hours",
            "Test all components in staging first",
            "Keep backup of working configuration",
            "Monitor system health during migration",
            "Have rollback plan ready"
        ]
        analysis["recommendations"] = recommendations
        
        return analysis
    
    def create_backup(self, files: List[str]) -> str:
        """Создание резервной копии текущих файлов."""
        backup_path = self.backup_dir / f"pre_migration_{self.timestamp}"
        backup_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Creating backup in {backup_path}")
        
        backed_up_files = []
        for file_path in files:
            if os.path.exists(file_path):
                dest_path = backup_path / file_path
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file_path, dest_path)
                backed_up_files.append(file_path)
                logger.info(f"Backed up: {file_path}")
        
        # Создание манифеста резервной копии
        manifest = {
            "timestamp": self.timestamp,
            "files": backed_up_files,
            "total_files": len(backed_up_files),
            "backup_path": str(backup_path)
        }
        
        with open(backup_path / "backup_manifest.json", "w") as f:
            json.dump(manifest, f, indent=2)
        
        logger.info(f"Backup completed: {len(backed_up_files)} files")
        return str(backup_path)
    
    def generate_migration_steps(self) -> List[Dict[str, Any]]:
        """Генерация пошаговых инструкций миграции."""
        steps = [
            {
                "step": 1,
                "title": "Pre-migration backup",
                "description": "Create backup of current configuration",
                "commands": [
                    "python scripts/migration_plan.py --backup",
                    "docker-compose down"
                ],
                "validation": "Verify backup files exist",
                "rollback": "N/A - this is the backup step"
            },
            {
                "step": 2,
                "title": "Update authentication system",
                "description": "Deploy new JWT authentication",
                "commands": [
                    "cp src/auth/livekit_auth.py src/auth/livekit_auth.py.new",
                    "cp config/livekit_auth.yaml config/livekit_auth.yaml.new"
                ],
                "validation": "Test JWT token generation",
                "rollback": "Restore original auth files"
            },
            {
                "step": 3,
                "title": "Update API client",
                "description": "Deploy new API client with correct endpoints",
                "commands": [
                    "cp src/clients/livekit_api_client.py src/clients/livekit_api_client.py.new"
                ],
                "validation": "Test API connectivity",
                "rollback": "Restore original API client"
            },
            {
                "step": 4,
                "title": "Update SIP configuration",
                "description": "Deploy correct SIP configuration",
                "commands": [
                    "cp livekit-sip-correct.yaml livekit-sip.yaml"
                ],
                "validation": "Test SIP trunk connectivity",
                "rollback": "Restore original SIP config"
            },
            {
                "step": 5,
                "title": "Update environment variables",
                "description": "Add new required environment variables",
                "commands": [
                    "python scripts/update_env_vars.py"
                ],
                "validation": "Verify all variables are set",
                "rollback": "Restore original .env file"
            },
            {
                "step": 6,
                "title": "Start services",
                "description": "Start updated services",
                "commands": [
                    "docker-compose up -d"
                ],
                "validation": "Check service health",
                "rollback": "Stop services and restore backup"
            },
            {
                "step": 7,
                "title": "Validate migration",
                "description": "Run comprehensive validation tests",
                "commands": [
                    "python scripts/validate_migration.py"
                ],
                "validation": "All tests pass",
                "rollback": "Full system rollback"
            }
        ]
        
        return steps
    
    def save_migration_plan(self, analysis: Dict[str, Any], steps: List[Dict[str, Any]]) -> str:
        """Сохранение плана миграции в файл."""
        plan_file = f"migration_plan_{self.timestamp}.json"
        
        migration_plan = {
            "metadata": {
                "created": self.timestamp,
                "version": "1.0",
                "description": "LiveKit System Migration Plan"
            },
            "analysis": analysis,
            "steps": steps,
            "rollback_procedures": self._generate_rollback_procedures()
        }
        
        with open(plan_file, "w") as f:
            json.dump(migration_plan, f, indent=2)
        
        logger.info(f"Migration plan saved to: {plan_file}")
        return plan_file
    
    def _generate_rollback_procedures(self) -> Dict[str, Any]:
        """Генерация процедур отката."""
        return {
            "emergency_rollback": {
                "description": "Emergency rollback to previous configuration",
                "steps": [
                    "Stop all services: docker-compose down",
                    "Restore backup files from backup directory",
                    "Restart services: docker-compose up -d",
                    "Validate system health"
                ]
            },
            "partial_rollback": {
                "description": "Rollback specific components",
                "components": {
                    "auth": "Restore src/auth/ directory from backup",
                    "api_client": "Restore src/clients/ directory from backup",
                    "sip_config": "Restore livekit-sip.yaml from backup",
                    "env_vars": "Restore .env file from backup"
                }
            },
            "validation_commands": [
                "python scripts/validate_system_health.py",
                "python scripts/test_sip_connectivity.py",
                "python scripts/test_api_endpoints.py"
            ]
        }

def main():
    """Основная функция для выполнения плана миграции."""
    import argparse
    
    parser = argparse.ArgumentParser(description="LiveKit Migration Plan")
    parser.add_argument("--analyze", action="store_true", help="Analyze current configuration")
    parser.add_argument("--backup", action="store_true", help="Create backup of current files")
    parser.add_argument("--generate-plan", action="store_true", help="Generate migration plan")
    
    args = parser.parse_args()
    
    migration = LiveKitMigrationPlan()
    
    if args.analyze:
        analysis = migration.analyze_current_configuration()
        print(json.dumps(analysis, indent=2))
    
    elif args.backup:
        files_to_backup = [
            ".env", "livekit-sip.yaml", "docker-compose.yml", "docker-compose.prod.yml",
            "src/livekit_integration.py", "src/webhooks.py", "src/voice_ai_agent.py"
        ]
        backup_path = migration.create_backup(files_to_backup)
        print(f"Backup created: {backup_path}")
    
    elif args.generate_plan:
        analysis = migration.analyze_current_configuration()
        steps = migration.generate_migration_steps()
        plan_file = migration.save_migration_plan(analysis, steps)
        print(f"Migration plan generated: {plan_file}")
    
    else:
        # Выполнить полный анализ и создание плана
        analysis = migration.analyze_current_configuration()
        steps = migration.generate_migration_steps()
        plan_file = migration.save_migration_plan(analysis, steps)
        
        print("Migration Plan Summary:")
        print(f"- Configuration files analyzed: {len(analysis['current_files'])}")
        print(f"- Migration tasks identified: {len(analysis['migration_needed'])}")
        print(f"- Migration steps: {len(steps)}")
        print(f"- Plan saved to: {plan_file}")

if __name__ == "__main__":
    main()