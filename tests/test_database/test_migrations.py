"""Tests for database migration system."""

import pytest
from unittest.mock import patch, AsyncMock
from sqlalchemy import text

from src.database.connection import DatabaseManager
from src.database.migrations import MigrationManager, Migration
from src.config import Settings, Environment


@pytest.fixture
async def db_manager():
    """Create a test database manager with in-memory SQLite."""
    settings = Settings(
        environment=Environment.TESTING,
        database_url="sqlite:///:memory:",
        debug=True
    )
    
    with patch('src.database.connection.get_settings', return_value=settings):
        manager = DatabaseManager()
        await manager.initialize()
        yield manager
        await manager.cleanup()


@pytest.fixture
async def migration_manager(db_manager):
    """Create a migration manager."""
    return MigrationManager(db_manager)


class TestMigration:
    """Test the Migration class."""
    
    def test_migration_creation(self):
        """Test creating a migration."""
        migration = Migration(
            version="001",
            description="Create test table",
            up_sql="CREATE TABLE test (id INTEGER PRIMARY KEY);",
            down_sql="DROP TABLE test;"
        )
        
        assert migration.version == "001"
        assert migration.description == "Create test table"
        assert migration.up_sql == "CREATE TABLE test (id INTEGER PRIMARY KEY);"
        assert migration.down_sql == "DROP TABLE test;"
        assert migration.timestamp is not None
    
    def test_migration_without_down_sql(self):
        """Test creating a migration without rollback SQL."""
        migration = Migration(
            version="002",
            description="Add index",
            up_sql="CREATE INDEX idx_test ON test(id);"
        )
        
        assert migration.version == "002"
        assert migration.down_sql is None
    
    def test_migration_repr(self):
        """Test migration string representation."""
        migration = Migration(
            version="001",
            description="Test migration",
            up_sql="SELECT 1;"
        )
        
        repr_str = repr(migration)
        assert "Migration" in repr_str
        assert "001" in repr_str
        assert "Test migration" in repr_str


class TestMigrationManager:
    """Test the MigrationManager class."""
    
    def test_migration_manager_initialization(self, migration_manager):
        """Test migration manager initialization."""
        assert migration_manager.db_manager is not None
        assert len(migration_manager.migrations) > 0
        
        # Check that migrations are loaded
        versions = [m.version for m in migration_manager.migrations]
        assert "001" in versions  # Schema tracking migration
        assert "002" in versions  # Performance indexes
        assert "003" in versions  # Data retention
    
    @pytest.mark.asyncio
    async def test_initialize_schema_tracking(self, migration_manager):
        """Test initializing schema version tracking."""
        await migration_manager.initialize_schema_tracking()
        
        # Check that schema_versions table exists
        async with migration_manager.db_manager.get_async_session() as session:
            result = await session.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='schema_versions'
            """))
            assert result.fetchone() is not None
            
            # Check that first migration is recorded
            result = await session.execute(text("""
                SELECT version FROM schema_versions WHERE version = '001'
            """))
            assert result.fetchone() is not None
    
    @pytest.mark.asyncio
    async def test_get_current_version_none(self, migration_manager):
        """Test getting current version when no migrations applied."""
        version = await migration_manager.get_current_version()
        assert version is None
    
    @pytest.mark.asyncio
    async def test_get_current_version_after_init(self, migration_manager):
        """Test getting current version after initialization."""
        await migration_manager.initialize_schema_tracking()
        
        version = await migration_manager.get_current_version()
        assert version == "001"
    
    @pytest.mark.asyncio
    async def test_get_applied_migrations(self, migration_manager):
        """Test getting list of applied migrations."""
        await migration_manager.initialize_schema_tracking()
        
        applied = await migration_manager.get_applied_migrations()
        assert len(applied) == 1
        assert applied[0]["version"] == "001"
        assert applied[0]["description"] == "Create schema version tracking table"
        assert applied[0]["applied_at"] is not None
        assert applied[0]["applied_by"] == "system"
    
    @pytest.mark.asyncio
    async def test_get_pending_migrations(self, migration_manager):
        """Test getting list of pending migrations."""
        # Before initialization - all migrations are pending
        pending = await migration_manager.get_pending_migrations()
        assert len(pending) == len(migration_manager.migrations)
        
        # After initialization - first migration is applied
        await migration_manager.initialize_schema_tracking()
        pending = await migration_manager.get_pending_migrations()
        assert len(pending) == len(migration_manager.migrations) - 1
        
        # Check that version 001 is not in pending
        pending_versions = [m.version for m in pending]
        assert "001" not in pending_versions
        assert "002" in pending_versions
        assert "003" in pending_versions
    
    @pytest.mark.asyncio
    async def test_apply_migration(self, migration_manager):
        """Test applying a single migration."""
        await migration_manager.initialize_schema_tracking()
        
        # Find migration 002 (performance indexes)
        migration_002 = next(m for m in migration_manager.migrations if m.version == "002")
        
        # Apply the migration
        success = await migration_manager.apply_migration(migration_002)
        assert success is True
        
        # Check that migration is recorded
        async with migration_manager.db_manager.get_async_session() as session:
            result = await session.execute(text("""
                SELECT version FROM schema_versions WHERE version = '002'
            """))
            assert result.fetchone() is not None
        
        # Check current version
        current_version = await migration_manager.get_current_version()
        assert current_version == "002"
    
    @pytest.mark.asyncio
    async def test_apply_migration_failure(self, migration_manager):
        """Test handling migration application failure."""
        await migration_manager.initialize_schema_tracking()
        
        # Create a migration with invalid SQL
        bad_migration = Migration(
            version="999",
            description="Bad migration",
            up_sql="INVALID SQL STATEMENT;"
        )
        
        success = await migration_manager.apply_migration(bad_migration)
        assert success is False
        
        # Check that migration is not recorded
        async with migration_manager.db_manager.get_async_session() as session:
            result = await session.execute(text("""
                SELECT version FROM schema_versions WHERE version = '999'
            """))
            assert result.fetchone() is None
    
    @pytest.mark.asyncio
    async def test_rollback_migration(self, migration_manager):
        """Test rolling back a migration."""
        await migration_manager.initialize_schema_tracking()
        
        # Apply migration 002 first
        migration_002 = next(m for m in migration_manager.migrations if m.version == "002")
        await migration_manager.apply_migration(migration_002)
        
        # Rollback the migration
        success = await migration_manager.rollback_migration("002")
        assert success is True
        
        # Check that migration record is removed
        async with migration_manager.db_manager.get_async_session() as session:
            result = await session.execute(text("""
                SELECT version FROM schema_versions WHERE version = '002'
            """))
            assert result.fetchone() is None
        
        # Current version should be back to 001
        current_version = await migration_manager.get_current_version()
        assert current_version == "001"
    
    @pytest.mark.asyncio
    async def test_rollback_nonexistent_migration(self, migration_manager):
        """Test rolling back a migration that doesn't exist."""
        success = await migration_manager.rollback_migration("999")
        assert success is False
    
    @pytest.mark.asyncio
    async def test_rollback_migration_without_down_sql(self, migration_manager):
        """Test rolling back a migration without down SQL."""
        # Create migration without down SQL
        migration_manager.migrations.append(Migration(
            version="998",
            description="No rollback",
            up_sql="SELECT 1;"
        ))
        
        success = await migration_manager.rollback_migration("998")
        assert success is False
    
    @pytest.mark.asyncio
    async def test_migrate_to_latest(self, migration_manager):
        """Test migrating to latest version."""
        success = await migration_manager.migrate_to_latest()
        assert success is True
        
        # Check that all migrations are applied
        applied = await migration_manager.get_applied_migrations()
        assert len(applied) == len(migration_manager.migrations)
        
        # Check that no migrations are pending
        pending = await migration_manager.get_pending_migrations()
        assert len(pending) == 0
        
        # Check current version is the latest
        current_version = await migration_manager.get_current_version()
        latest_version = migration_manager.migrations[-1].version
        assert current_version == latest_version
    
    @pytest.mark.asyncio
    async def test_migrate_to_latest_already_up_to_date(self, migration_manager):
        """Test migrating when already at latest version."""
        # First migration to latest
        await migration_manager.migrate_to_latest()
        
        # Second migration should succeed but do nothing
        success = await migration_manager.migrate_to_latest()
        assert success is True
    
    @pytest.mark.asyncio
    async def test_migrate_to_latest_with_failure(self, migration_manager):
        """Test migrate to latest with a failing migration."""
        # Add a bad migration
        bad_migration = Migration(
            version="999",
            description="Bad migration",
            up_sql="INVALID SQL;"
        )
        migration_manager.migrations.append(bad_migration)
        
        success = await migration_manager.migrate_to_latest()
        assert success is False
        
        # Should stop at the failing migration
        current_version = await migration_manager.get_current_version()
        assert current_version != "999"
    
    @pytest.mark.asyncio
    async def test_create_tables_if_not_exist(self, migration_manager):
        """Test creating tables from SQLAlchemy models."""
        success = await migration_manager.create_tables_if_not_exist()
        assert success is True
        
        # Check that tables exist
        async with migration_manager.db_manager.get_async_session() as session:
            result = await session.execute(text("""
                SELECT name FROM sqlite_master WHERE type='table'
            """))
            tables = [row[0] for row in result.fetchall()]
            
            expected_tables = ['calls', 'conversations', 'messages', 'conversation_metrics', 'system_events']
            for table in expected_tables:
                assert table in tables
        
        # Check that migrations are marked as applied
        applied = await migration_manager.get_applied_migrations()
        assert len(applied) == len(migration_manager.migrations)
    
    @pytest.mark.asyncio
    async def test_get_migration_status(self, migration_manager):
        """Test getting comprehensive migration status."""
        # Before any migrations
        status = await migration_manager.get_migration_status()
        assert status["current_version"] is None
        assert status["applied_count"] == 0
        assert status["pending_count"] == len(migration_manager.migrations)
        assert status["is_up_to_date"] is False
        
        # After initialization
        await migration_manager.initialize_schema_tracking()
        status = await migration_manager.get_migration_status()
        assert status["current_version"] == "001"
        assert status["applied_count"] == 1
        assert status["pending_count"] == len(migration_manager.migrations) - 1
        assert status["is_up_to_date"] is False
        
        # After migrating to latest
        await migration_manager.migrate_to_latest()
        status = await migration_manager.get_migration_status()
        assert status["applied_count"] == len(migration_manager.migrations)
        assert status["pending_count"] == 0
        assert status["is_up_to_date"] is True
    
    @pytest.mark.asyncio
    async def test_get_migration_status_with_error(self, migration_manager):
        """Test getting migration status when there's an error."""
        # Mock an error in get_current_version
        with patch.object(migration_manager, 'get_current_version', side_effect=Exception("DB Error")):
            status = await migration_manager.get_migration_status()
            
            assert "error" in status
            assert "DB Error" in status["error"]
            assert status["current_version"] is None
            assert status["is_up_to_date"] is False


class TestMigrationSQL:
    """Test that migration SQL is valid and works correctly."""
    
    @pytest.mark.asyncio
    async def test_migration_001_sql(self, migration_manager):
        """Test that migration 001 SQL creates the correct schema."""
        migration_001 = next(m for m in migration_manager.migrations if m.version == "001")
        
        # Apply the migration
        success = await migration_manager.apply_migration(migration_001)
        assert success is True
        
        # Check that schema_versions table exists with correct structure
        async with migration_manager.db_manager.get_async_session() as session:
            # Check table exists
            result = await session.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='schema_versions'
            """))
            assert result.fetchone() is not None
            
            # Check table structure
            result = await session.execute(text("PRAGMA table_info(schema_versions)"))
            columns = {row[1]: row[2] for row in result.fetchall()}
            
            assert 'id' in columns
            assert 'version' in columns
            assert 'description' in columns
            assert 'applied_at' in columns
            assert 'applied_by' in columns
            
            # Check that only the unique constraint index exists (created automatically by SQLite)
            result = await session.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='index' AND tbl_name='schema_versions'
            """))
            indexes = [row[0] for row in result.fetchall()]
            # Migration 001 only creates the table, indexes are created in later migrations
            # SQLite automatically creates an index for the UNIQUE constraint on version
            assert len(indexes) >= 1  # At least the unique constraint index
    
    @pytest.mark.asyncio
    async def test_migration_002_sql(self, migration_manager):
        """Test that migration 002 SQL creates schema version indexes."""
        # First create the main tables
        await migration_manager.db_manager.create_tables()
        await migration_manager.initialize_schema_tracking()
        
        # Apply migration 002
        migration_002 = next(m for m in migration_manager.migrations if m.version == "002")
        success = await migration_manager.apply_migration(migration_002)
        assert success is True
        
        # Check that schema version index was created
        async with migration_manager.db_manager.get_async_session() as session:
            result = await session.execute(text("""
                SELECT name FROM sqlite_master WHERE type='index' AND name='idx_schema_versions_version'
            """))
            assert result.fetchone() is not None
    
    @pytest.mark.asyncio
    async def test_migration_003_sql(self, migration_manager):
        """Test that migration 003 SQL adds schema version applied_at index."""
        # First create the main tables and apply previous migrations
        await migration_manager.db_manager.create_tables()
        await migration_manager.initialize_schema_tracking()
        
        migration_002 = next(m for m in migration_manager.migrations if m.version == "002")
        await migration_manager.apply_migration(migration_002)
        
        # Apply migration 003
        migration_003 = next(m for m in migration_manager.migrations if m.version == "003")
        success = await migration_manager.apply_migration(migration_003)
        assert success is True
        
        # Check that applied_at index was created
        async with migration_manager.db_manager.get_async_session() as session:
            result = await session.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='index' AND name='idx_schema_versions_applied_at'
            """))
            assert result.fetchone() is not None
    
    @pytest.mark.asyncio
    async def test_migration_rollback_sql(self, migration_manager):
        """Test that migration rollback SQL works correctly."""
        # Create tables and apply migrations
        await migration_manager.db_manager.create_tables()
        await migration_manager.initialize_schema_tracking()
        
        # Apply migration 002
        migration_002 = next(m for m in migration_manager.migrations if m.version == "002")
        await migration_manager.apply_migration(migration_002)
        
        # Verify index exists
        async with migration_manager.db_manager.get_async_session() as session:
            result = await session.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='index' AND name='idx_schema_versions_version'
            """))
            assert result.fetchone() is not None
        
        # Rollback migration 002
        success = await migration_manager.rollback_migration("002")
        assert success is True
        
        # Verify index is removed
        async with migration_manager.db_manager.get_async_session() as session:
            result = await session.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='index' AND name='idx_schema_versions_version'
            """))
            assert result.fetchone() is None


class TestMigrationIntegration:
    """Test migration system integration with the database manager."""
    
    @pytest.mark.asyncio
    async def test_full_migration_cycle(self, migration_manager):
        """Test complete migration cycle from empty database to latest."""
        # Start with empty database
        assert await migration_manager.get_current_version() is None
        
        # Migrate to latest
        success = await migration_manager.migrate_to_latest()
        assert success is True
        
        # Verify all tables exist and work
        async with migration_manager.db_manager.get_async_session() as session:
            # Test inserting data into all main tables
            from src.database.models import Call, Conversation, Message, SystemEvent
            
            # Insert test call
            await session.execute(text("""
                INSERT INTO calls (call_id, status, start_time, created_at, updated_at, error_count) 
                VALUES ('test-call', 'active', datetime('now'), datetime('now'), datetime('now'), 0)
            """))
            
            # Insert test conversation
            await session.execute(text("""
                INSERT INTO conversations (call_id, conversation_id, status, start_time, created_at, updated_at) 
                VALUES (1, 'test-conv', 'active', datetime('now'), datetime('now'), datetime('now'))
            """))
            
            # Insert test message
            await session.execute(text("""
                INSERT INTO messages (conversation_id, message_id, sequence_number, role, content, created_at, updated_at, retry_count) 
                VALUES (1, 'test-msg', 1, 'user', 'Hello', datetime('now'), datetime('now'), 0)
            """))
            
            # Insert test system event
            await session.execute(text("""
                INSERT INTO system_events (event_id, event_type, severity, message, timestamp, created_at) 
                VALUES ('test-event', 'test', 'INFO', 'Test message', datetime('now'), datetime('now'))
            """))
            
            # Verify data was inserted
            result = await session.execute(text("SELECT COUNT(*) FROM calls"))
            assert result.scalar() == 1
            
            result = await session.execute(text("SELECT COUNT(*) FROM conversations"))
            assert result.scalar() == 1
            
            result = await session.execute(text("SELECT COUNT(*) FROM messages"))
            assert result.scalar() == 1
            
            result = await session.execute(text("SELECT COUNT(*) FROM system_events"))
            assert result.scalar() == 1
        
        # Verify migration status
        status = await migration_manager.get_migration_status()
        assert status["is_up_to_date"] is True
        assert status["pending_count"] == 0