"""Database migration system for Voice AI Agent."""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional
from sqlalchemy import text, inspect
from sqlalchemy.ext.asyncio import AsyncEngine

from .connection import DatabaseManager
from .models import Base

logger = logging.getLogger(__name__)


class Migration:
    """Represents a single database migration."""
    
    def __init__(
        self,
        version: str,
        description: str,
        up_sql: str,
        down_sql: Optional[str] = None
    ):
        """
        Initialize a migration.
        
        Args:
            version: Migration version (e.g., "001", "002")
            description: Human-readable description
            up_sql: SQL to apply the migration
            down_sql: SQL to rollback the migration (optional)
        """
        self.version = version
        self.description = description
        self.up_sql = up_sql
        self.down_sql = down_sql
        self.timestamp = datetime.now(timezone.utc)
    
    def __repr__(self) -> str:
        return f"<Migration(version='{self.version}', description='{self.description}')>"


class MigrationManager:
    """
    Manages database schema migrations for the Voice AI Agent.
    
    Provides functionality to apply, rollback, and track database
    schema changes in a controlled manner.
    """
    
    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize the migration manager.
        
        Args:
            db_manager: Database manager instance
        """
        self.db_manager = db_manager
        self.migrations: List[Migration] = []
        self._load_migrations()
    
    def _load_migrations(self) -> None:
        """Load all available migrations."""
        # Migration 001: Create initial schema version tracking table
        self.migrations.append(Migration(
            version="001",
            description="Create schema version tracking table",
            up_sql="""CREATE TABLE IF NOT EXISTS schema_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    version VARCHAR(50) NOT NULL UNIQUE,
                    description TEXT NOT NULL,
                    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    applied_by VARCHAR(100) DEFAULT 'system'
                )""",
            down_sql="DROP TABLE IF EXISTS schema_versions"
        ))
        
        # Migration 002: Add schema version indexes
        self.migrations.append(Migration(
            version="002",
            description="Add schema version indexes",
            up_sql="CREATE INDEX IF NOT EXISTS idx_schema_versions_version ON schema_versions(version)",
            down_sql="DROP INDEX IF EXISTS idx_schema_versions_version"
        ))
        
        # Migration 003: Add schema version applied_at index
        self.migrations.append(Migration(
            version="003",
            description="Add schema version applied_at index",
            up_sql="CREATE INDEX IF NOT EXISTS idx_schema_versions_applied_at ON schema_versions(applied_at)",
            down_sql="DROP INDEX IF EXISTS idx_schema_versions_applied_at"
        ))
        
        # Migration 004: Add performance optimization indexes
        self.migrations.append(Migration(
            version="004",
            description="Add performance optimization indexes",
            up_sql="CREATE INDEX IF NOT EXISTS idx_calls_caller_number_start_time ON calls(caller_number, start_time)",
            down_sql="DROP INDEX IF EXISTS idx_calls_caller_number_start_time"
        ))
        
        # Migration 005: Create data retention policy table
        self.migrations.append(Migration(
            version="005",
            description="Create data retention policy table",
            up_sql="""CREATE TABLE IF NOT EXISTS data_retention_policies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    table_name VARCHAR(100) NOT NULL,
                    retention_days INTEGER NOT NULL,
                    archive_before_delete BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )""",
            down_sql="DROP TABLE IF EXISTS data_retention_policies"
        ))
        
        logger.info(f"Loaded {len(self.migrations)} migrations")
    
    async def _ensure_main_tables_exist(self) -> None:
        """
        Ensure main application tables exist before applying migrations.
        
        This method checks if the main tables exist and creates them if not.
        This is necessary because some migrations depend on main tables existing.
        """
        try:
            async with self.db_manager.get_async_session() as session:
                # Check if main tables exist
                result = await session.execute(text("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name IN ('calls', 'conversations', 'messages', 'system_events', 'conversation_metrics')
                """))
                existing_tables = {row[0] for row in result.fetchall()}
                
                expected_tables = {'calls', 'conversations', 'messages', 'system_events', 'conversation_metrics'}
                missing_tables = expected_tables - existing_tables
                
                if missing_tables:
                    logger.info(f"Creating missing main tables: {missing_tables}")
                    await self.db_manager.create_tables()
                    
        except Exception as e:
            logger.warning(f"Could not ensure main tables exist: {e}")
            # Continue anyway - migrations will fail if tables are truly missing
    
    async def initialize_schema_tracking(self) -> None:
        """Initialize the schema version tracking system."""
        async with self.db_manager.get_async_session() as session:
            # Check if schema_versions table exists
            result = await session.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='schema_versions'
            """))
            
            if not result.fetchone():
                logger.info("Initializing schema version tracking...")
                
                # Apply the first migration to create the tracking table
                first_migration = self.migrations[0]
                await session.execute(text(first_migration.up_sql))
                
                # Record the migration
                await session.execute(text("""
                    INSERT INTO schema_versions (version, description) 
                    VALUES (:version, :description)
                """), {
                    "version": first_migration.version,
                    "description": first_migration.description
                })
                
                logger.info("Schema version tracking initialized")
    
    async def get_current_version(self) -> Optional[str]:
        """
        Get the current database schema version.
        
        Returns:
            Optional[str]: Current version or None if no migrations applied
        """
        try:
            async with self.db_manager.get_async_session() as session:
                result = await session.execute(text("""
                    SELECT version FROM schema_versions 
                    ORDER BY applied_at DESC, version DESC LIMIT 1
                """))
                row = result.fetchone()
                return row[0] if row else None
        except Exception as e:
            logger.warning(f"Could not get current version: {e}")
            return None
    
    async def get_applied_migrations(self) -> List[Dict[str, Any]]:
        """
        Get list of applied migrations.
        
        Returns:
            List[Dict]: List of applied migration records
        """
        try:
            async with self.db_manager.get_async_session() as session:
                result = await session.execute(text("""
                    SELECT version, description, applied_at, applied_by
                    FROM schema_versions 
                    ORDER BY applied_at ASC
                """))
                
                return [
                    {
                        "version": row[0],
                        "description": row[1],
                        "applied_at": row[2],
                        "applied_by": row[3]
                    }
                    for row in result.fetchall()
                ]
        except Exception as e:
            logger.error(f"Could not get applied migrations: {e}")
            return []
    
    async def get_pending_migrations(self) -> List[Migration]:
        """
        Get list of pending migrations.
        
        Returns:
            List[Migration]: List of migrations that haven't been applied
        """
        applied_migrations = await self.get_applied_migrations()
        applied_versions = {m["version"] for m in applied_migrations}
        
        return [
            migration for migration in self.migrations
            if migration.version not in applied_versions
        ]
    
    async def apply_migration(self, migration: Migration) -> bool:
        """
        Apply a single migration.
        
        Args:
            migration: Migration to apply
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info(f"Applying migration {migration.version}: {migration.description}")
            
            async with self.db_manager.get_async_session() as session:
                # Apply the migration SQL
                await session.execute(text(migration.up_sql))
                
                # Record the migration
                await session.execute(text("""
                    INSERT INTO schema_versions (version, description) 
                    VALUES (:version, :description)
                """), {
                    "version": migration.version,
                    "description": migration.description
                })
                
                logger.info(f"Successfully applied migration {migration.version}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to apply migration {migration.version}: {e}")
            return False
    
    async def rollback_migration(self, version: str) -> bool:
        """
        Rollback a specific migration.
        
        Args:
            version: Version to rollback
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Find the migration
        migration = next((m for m in self.migrations if m.version == version), None)
        if not migration:
            logger.error(f"Migration {version} not found")
            return False
        
        if not migration.down_sql:
            logger.error(f"Migration {version} has no rollback SQL")
            return False
        
        try:
            logger.info(f"Rolling back migration {version}: {migration.description}")
            
            async with self.db_manager.get_async_session() as session:
                # Apply the rollback SQL
                await session.execute(text(migration.down_sql))
                
                # Remove the migration record
                await session.execute(text("""
                    DELETE FROM schema_versions WHERE version = :version
                """), {"version": version})
                
                logger.info(f"Successfully rolled back migration {version}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to rollback migration {version}: {e}")
            return False
    
    async def migrate_to_latest(self) -> bool:
        """
        Apply all pending migrations to bring database to latest version.
        
        Returns:
            bool: True if all migrations successful, False otherwise
        """
        try:
            # Initialize schema tracking if needed
            await self.initialize_schema_tracking()
            
            # Check if main application tables exist, create them if not
            await self._ensure_main_tables_exist()
            
            # Get pending migrations
            pending = await self.get_pending_migrations()
            
            if not pending:
                logger.info("Database is already at the latest version")
                return True
            
            logger.info(f"Applying {len(pending)} pending migrations...")
            
            # Apply each migration
            for migration in pending:
                success = await self.apply_migration(migration)
                if not success:
                    logger.error(f"Migration failed at version {migration.version}")
                    return False
            
            current_version = await self.get_current_version()
            logger.info(f"Database migrated to version {current_version}")
            return True
            
        except Exception as e:
            logger.error(f"Migration to latest failed: {e}")
            return False
    
    async def create_tables_if_not_exist(self) -> bool:
        """
        Create all tables using SQLAlchemy models if they don't exist.
        
        This is used for initial setup and as a fallback.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info("Creating tables from SQLAlchemy models...")
            await self.db_manager.create_tables()
            
            # Initialize schema tracking
            await self.initialize_schema_tracking()
            
            # Mark all migrations as applied since we created from models
            for migration in self.migrations[1:]:  # Skip first migration (schema tracking)
                async with self.db_manager.get_async_session() as session:
                    # Check if migration is already recorded
                    result = await session.execute(text("""
                        SELECT COUNT(*) FROM schema_versions WHERE version = :version
                    """), {"version": migration.version})
                    
                    if result.scalar() == 0:
                        await session.execute(text("""
                            INSERT INTO schema_versions (version, description) 
                            VALUES (:version, :description)
                        """), {
                            "version": migration.version,
                            "description": migration.description
                        })
            
            logger.info("Tables created and migrations marked as applied")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create tables: {e}")
            return False
    
    async def get_migration_status(self) -> Dict[str, Any]:
        """
        Get comprehensive migration status information.
        
        Returns:
            Dict containing migration status details
        """
        try:
            current_version = await self.get_current_version()
            applied_migrations = await self.get_applied_migrations()
            pending_migrations = await self.get_pending_migrations()
            
            return {
                "current_version": current_version,
                "total_migrations": len(self.migrations),
                "applied_count": len(applied_migrations),
                "pending_count": len(pending_migrations),
                "applied_migrations": applied_migrations,
                "pending_migrations": [
                    {
                        "version": m.version,
                        "description": m.description
                    }
                    for m in pending_migrations
                ],
                "is_up_to_date": len(pending_migrations) == 0
            }
            
        except Exception as e:
            logger.error(f"Failed to get migration status: {e}")
            return {
                "error": str(e),
                "current_version": None,
                "is_up_to_date": False
            }