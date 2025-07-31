"""Tests for database connection management."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, AsyncMock
from sqlalchemy import text

from src.database.connection import DatabaseManager, get_database_manager, init_database
from src.config import Settings, Environment


@pytest.fixture
def temp_db_path():
    """Create a temporary database file path."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    
    yield f"sqlite:///{db_path}"
    
    # Cleanup
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def test_settings(temp_db_path):
    """Create test settings with temporary database."""
    return Settings(
        environment=Environment.TESTING,
        database_url=temp_db_path,
        debug=True
    )


class TestDatabaseManager:
    """Test the DatabaseManager class."""
    
    @pytest.mark.asyncio
    async def test_initialization(self, test_settings, temp_db_path):
        """Test database manager initialization."""
        with patch('src.database.connection.get_settings', return_value=test_settings):
            db_manager = DatabaseManager()
            
            assert not db_manager._is_initialized
            assert db_manager.database_url == temp_db_path
            
            await db_manager.initialize()
            
            assert db_manager._is_initialized
            assert db_manager._async_engine is not None
            assert db_manager._sync_engine is not None
            assert db_manager._async_session_factory is not None
            assert db_manager._sync_session_factory is not None
            
            await db_manager.cleanup()
    
    @pytest.mark.asyncio
    async def test_double_initialization(self, test_settings, temp_db_path):
        """Test that double initialization is handled gracefully."""
        with patch('src.database.connection.get_settings', return_value=test_settings):
            db_manager = DatabaseManager()
            
            await db_manager.initialize()
            assert db_manager._is_initialized
            
            # Second initialization should not fail
            await db_manager.initialize()
            assert db_manager._is_initialized
            
            await db_manager.cleanup()
    
    @pytest.mark.asyncio
    async def test_create_tables(self, test_settings, temp_db_path):
        """Test table creation."""
        with patch('src.database.connection.get_settings', return_value=test_settings):
            db_manager = DatabaseManager()
            await db_manager.initialize()
            await db_manager.create_tables()
            
            # Verify tables exist by trying to query them
            async with db_manager.get_async_session() as session:
                result = await session.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
                tables = [row[0] for row in result.fetchall()]
                
                expected_tables = ['calls', 'conversations', 'messages', 'conversation_metrics', 'system_events']
                for table in expected_tables:
                    assert table in tables
            
            await db_manager.cleanup()
    
    @pytest.mark.asyncio
    async def test_async_session_context_manager(self, test_settings, temp_db_path):
        """Test async session context manager."""
        with patch('src.database.connection.get_settings', return_value=test_settings):
            db_manager = DatabaseManager()
            await db_manager.initialize()
            await db_manager.create_tables()
            
            # Test successful session usage
            async with db_manager.get_async_session() as session:
                result = await session.execute(text("SELECT 1 as test"))
                assert result.scalar() == 1
            
            await db_manager.cleanup()
    
    @pytest.mark.asyncio
    async def test_async_session_rollback_on_error(self, test_settings, temp_db_path):
        """Test that async session rolls back on error."""
        with patch('src.database.connection.get_settings', return_value=test_settings):
            db_manager = DatabaseManager()
            await db_manager.initialize()
            await db_manager.create_tables()
            
            # Test session rollback on error
            with pytest.raises(Exception):
                async with db_manager.get_async_session() as session:
                    await session.execute(text("SELECT * FROM nonexistent_table"))
            
            # Session should still work after error
            async with db_manager.get_async_session() as session:
                result = await session.execute(text("SELECT 1 as test"))
                assert result.scalar() == 1
            
            await db_manager.cleanup()
    
    @pytest.mark.asyncio
    async def test_health_check_healthy(self, test_settings, temp_db_path):
        """Test health check when database is healthy."""
        with patch('src.database.connection.get_settings', return_value=test_settings):
            db_manager = DatabaseManager()
            await db_manager.initialize()
            
            health_status = await db_manager.health_check()
            
            assert health_status["status"] == "healthy"
            assert health_status["initialized"] is True
            assert health_status["database_type"] == "sqlite"
            assert health_status["error"] is None
            
            await db_manager.cleanup()
    
    @pytest.mark.asyncio
    async def test_health_check_not_initialized(self, test_settings):
        """Test health check when database is not initialized."""
        with patch('src.database.connection.get_settings', return_value=test_settings):
            db_manager = DatabaseManager()
            
            health_status = await db_manager.health_check()
            
            assert health_status["status"] == "not_initialized"
            assert health_status["initialized"] is False
    
    @pytest.mark.asyncio
    async def test_get_stats(self, test_settings, temp_db_path):
        """Test getting database statistics."""
        with patch('src.database.connection.get_settings', return_value=test_settings):
            db_manager = DatabaseManager()
            await db_manager.initialize()
            await db_manager.create_tables()
            
            stats = await db_manager.get_stats()
            
            assert "tables" in stats
            assert "calls" in stats["tables"]
            assert "conversations" in stats["tables"]
            assert "messages" in stats["tables"]
            assert "system_events" in stats["tables"]
            assert stats["database_type"] == "sqlite"
            
            # All counts should be 0 for empty database
            assert stats["tables"]["calls"] == 0
            assert stats["tables"]["conversations"] == 0
            assert stats["tables"]["messages"] == 0
            assert stats["tables"]["system_events"] == 0
            
            await db_manager.cleanup()
    
    @pytest.mark.asyncio
    async def test_cleanup(self, test_settings, temp_db_path):
        """Test database cleanup."""
        with patch('src.database.connection.get_settings', return_value=test_settings):
            db_manager = DatabaseManager()
            await db_manager.initialize()
            
            assert db_manager._is_initialized
            assert db_manager._async_engine is not None
            
            await db_manager.cleanup()
            
            assert not db_manager._is_initialized
            assert db_manager._async_engine is None
            assert db_manager._sync_engine is None
    
    def test_mask_url(self, test_settings):
        """Test URL masking for logging."""
        with patch('src.database.connection.get_settings', return_value=test_settings):
            db_manager = DatabaseManager()
            
            # Test SQLite URL (no masking needed)
            sqlite_url = "sqlite:///./data/test.db"
            masked = db_manager._mask_url(sqlite_url)
            assert masked == sqlite_url
            
            # Test PostgreSQL URL with credentials
            pg_url = "postgresql://user:password@localhost:5432/dbname"
            masked = db_manager._mask_url(pg_url)
            assert masked == "postgresql://***@localhost:5432/dbname"
            assert "password" not in masked
    
    def test_get_engine_config_sqlite(self, test_settings):
        """Test engine configuration for SQLite."""
        with patch('src.database.connection.get_settings', return_value=test_settings):
            db_manager = DatabaseManager()
            config = db_manager._get_engine_config()
            
            assert "poolclass" in config
            assert "connect_args" in config
            assert config["connect_args"]["check_same_thread"] is False
            assert "timeout" in config["connect_args"]
    
    def test_get_engine_config_postgresql(self, test_settings):
        """Test engine configuration for PostgreSQL."""
        # Mock PostgreSQL settings
        pg_settings = Settings(
            environment=Environment.TESTING,
            database_url="postgresql://user:pass@localhost/db",
            db_pool_size=5,
            db_pool_overflow=10
        )
        
        with patch('src.database.connection.get_settings', return_value=pg_settings):
            db_manager = DatabaseManager()
            config = db_manager._get_engine_config()
            
            assert config["pool_size"] == 5
            assert config["max_overflow"] == 10
            assert "connect_args" in config
            assert "connect_timeout" in config["connect_args"]


class TestGlobalFunctions:
    """Test global database functions."""
    
    @pytest.mark.asyncio
    async def test_get_database_manager_singleton(self):
        """Test that get_database_manager returns singleton."""
        # Clear any existing global instance
        import src.database.connection
        src.database.connection._db_manager = None
        
        manager1 = get_database_manager()
        manager2 = get_database_manager()
        
        assert manager1 is manager2
    
    @pytest.mark.asyncio
    async def test_init_database(self, test_settings, temp_db_path):
        """Test init_database function."""
        with patch('src.database.connection.get_settings', return_value=test_settings):
            # Clear any existing global instance
            import src.database.connection
            src.database.connection._db_manager = None
            
            db_manager = await init_database()
            
            assert db_manager._is_initialized
            
            # Verify tables were created
            async with db_manager.get_async_session() as session:
                result = await session.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
                tables = [row[0] for row in result.fetchall()]
                assert 'calls' in tables
            
            await db_manager.cleanup()


class TestErrorHandling:
    """Test error handling in database operations."""
    
    @pytest.mark.asyncio
    async def test_initialization_failure(self):
        """Test handling of initialization failure."""
        # Use invalid database URL
        invalid_settings = Settings(
            environment=Environment.TESTING,
            database_url="invalid://invalid/url"
        )
        
        with patch('src.database.connection.get_settings', return_value=invalid_settings):
            db_manager = DatabaseManager()
            
            with pytest.raises(Exception):
                await db_manager.initialize()
            
            # Manager should not be marked as initialized
            assert not db_manager._is_initialized
    
    @pytest.mark.asyncio
    async def test_session_without_initialization(self, test_settings):
        """Test getting session without initialization."""
        with patch('src.database.connection.get_settings', return_value=test_settings):
            db_manager = DatabaseManager()
            
            # Should initialize automatically
            async with db_manager.get_async_session() as session:
                result = await session.execute(text("SELECT 1"))
                assert result.scalar() == 1
            
            await db_manager.cleanup()
    
    @pytest.mark.asyncio
    async def test_health_check_with_error(self, test_settings, temp_db_path):
        """Test health check when database has errors."""
        with patch('src.database.connection.get_settings', return_value=test_settings):
            db_manager = DatabaseManager()
            await db_manager.initialize()
            
            # Mock a database error
            with patch.object(db_manager, 'get_async_session') as mock_session:
                mock_session.side_effect = Exception("Database connection failed")
                
                health_status = await db_manager.health_check()
                
                assert health_status["status"] == "unhealthy"
                assert "Database connection failed" in health_status["error"]
            
            await db_manager.cleanup()
    
    @pytest.mark.asyncio
    async def test_stats_with_error(self, test_settings, temp_db_path):
        """Test getting stats when database has errors."""
        with patch('src.database.connection.get_settings', return_value=test_settings):
            db_manager = DatabaseManager()
            await db_manager.initialize()
            
            # Mock a database error
            with patch.object(db_manager, 'get_async_session') as mock_session:
                mock_session.side_effect = Exception("Query failed")
                
                stats = await db_manager.get_stats()
                
                assert "error" in stats
                assert "Query failed" in stats["error"]
            
            await db_manager.cleanup()