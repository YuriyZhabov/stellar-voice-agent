"""Database connection management for Voice AI Agent."""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Optional, Dict, Any
from sqlalchemy import create_engine, event, pool, text
from sqlalchemy.ext.asyncio import (
    create_async_engine, 
    AsyncEngine, 
    AsyncSession, 
    async_sessionmaker
)
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from src.config import get_settings
from .models import Base

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages database connections and sessions for the Voice AI Agent.
    
    Provides both synchronous and asynchronous database access with
    proper connection pooling, error handling, and lifecycle management.
    """
    
    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize the database manager.
        
        Args:
            database_url: Optional database URL override
        """
        self.settings = get_settings()
        self.database_url = database_url or self.settings.database_url
        
        # Connection state
        self._async_engine: Optional[AsyncEngine] = None
        self._sync_engine = None
        self._async_session_factory: Optional[async_sessionmaker] = None
        self._sync_session_factory = None
        self._is_initialized = False
        
        logger.info(f"DatabaseManager initialized with URL: {self._mask_url(self.database_url)}")
    
    def _mask_url(self, url: str) -> str:
        """Mask sensitive information in database URL for logging."""
        if "://" in url:
            scheme, rest = url.split("://", 1)
            if "@" in rest:
                credentials, host_part = rest.split("@", 1)
                return f"{scheme}://***@{host_part}"
        return url
    
    def _get_engine_config(self) -> Dict[str, Any]:
        """Get engine configuration based on database type and environment."""
        config = {
            "echo": self.settings.debug and not self.settings.is_production,
            "future": True,
        }
        
        if self.settings.database_is_sqlite:
            # SQLite-specific configuration
            config.update({
                "poolclass": StaticPool,
                "connect_args": {
                    "check_same_thread": False,
                    "timeout": 30,
                    "isolation_level": None,  # Enable autocommit mode
                },
                "pool_pre_ping": True,
                "pool_recycle": 3600,  # 1 hour
            })
        else:
            # PostgreSQL/other database configuration
            config.update({
                "pool_size": self.settings.db_pool_size,
                "max_overflow": self.settings.db_pool_overflow,
                "pool_pre_ping": True,
                "pool_recycle": 3600,  # 1 hour
                "connect_args": {
                    "connect_timeout": 30,
                    "command_timeout": 60,
                }
            })
        
        return config
    
    async def initialize(self) -> None:
        """
        Initialize database connections and create tables if needed.
        
        Raises:
            Exception: If database initialization fails
        """
        if self._is_initialized:
            logger.warning("DatabaseManager already initialized")
            return
        
        try:
            logger.info("Initializing database connections...")
            
            # Create async engine
            engine_config = self._get_engine_config()
            
            # Convert sync URL to async URL for SQLite
            async_url = self.database_url
            if self.settings.database_is_sqlite:
                async_url = self.database_url.replace("sqlite://", "sqlite+aiosqlite://")
            
            self._async_engine = create_async_engine(async_url, **engine_config)
            
            # Create sync engine for migrations and admin tasks
            self._sync_engine = create_engine(self.database_url, **engine_config)
            
            # Create session factories
            self._async_session_factory = async_sessionmaker(
                bind=self._async_engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=True,
                autocommit=False
            )
            
            self._sync_session_factory = sessionmaker(
                bind=self._sync_engine,
                expire_on_commit=False,
                autoflush=True,
                autocommit=False
            )
            
            # Create database directory if using SQLite
            if self.settings.database_is_sqlite:
                db_path = Path(self.database_url.replace("sqlite:///", ""))
                db_path.parent.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created database directory: {db_path.parent}")
            
            # Test connections
            await self._test_connections()
            
            self._is_initialized = True
            logger.info("Database connections initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            await self.cleanup()
            raise
    
    async def _test_connections(self) -> None:
        """Test database connections."""
        try:
            # Test async connection
            async with self._async_engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            
            # Test sync connection
            with self._sync_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            logger.info("Database connection tests passed")
            
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            raise
    
    async def create_tables(self) -> None:
        """
        Create all database tables.
        
        Raises:
            Exception: If table creation fails
        """
        if not self._is_initialized:
            await self.initialize()
        
        try:
            logger.info("Creating database tables...")
            
            async with self._async_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            
            logger.info("Database tables created successfully")
            
        except Exception as e:
            logger.error(f"Failed to create database tables: {e}")
            raise
    
    async def drop_tables(self) -> None:
        """
        Drop all database tables.
        
        WARNING: This will delete all data!
        
        Raises:
            Exception: If table dropping fails
        """
        if not self._is_initialized:
            await self.initialize()
        
        try:
            logger.warning("Dropping all database tables...")
            
            async with self._async_engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
            
            logger.info("Database tables dropped successfully")
            
        except Exception as e:
            logger.error(f"Failed to drop database tables: {e}")
            raise
    
    @asynccontextmanager
    async def get_async_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get an async database session with automatic cleanup.
        
        Yields:
            AsyncSession: Database session
            
        Raises:
            Exception: If session creation fails
        """
        if not self._is_initialized:
            await self.initialize()
        
        if not self._async_session_factory:
            raise RuntimeError("Async session factory not initialized")
        
        session = self._async_session_factory()
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()
    
    def get_sync_session(self) -> Session:
        """
        Get a synchronous database session.
        
        Returns:
            Session: Database session
            
        Raises:
            Exception: If session creation fails
        """
        if not self._sync_session_factory:
            raise RuntimeError("Sync session factory not initialized")
        
        return self._sync_session_factory()
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform database health check.
        
        Returns:
            Dict containing health status information
        """
        health_status = {
            "status": "unknown",
            "initialized": self._is_initialized,
            "database_type": "sqlite" if self.settings.database_is_sqlite else "postgresql",
            "url_masked": self._mask_url(self.database_url),
            "error": None
        }
        
        if not self._is_initialized:
            health_status["status"] = "not_initialized"
            return health_status
        
        try:
            # Test async connection
            async with self.get_async_session() as session:
                result = await session.execute(text("SELECT 1 as test"))
                test_value = result.scalar()
                
                if test_value == 1:
                    health_status["status"] = "healthy"
                else:
                    health_status["status"] = "unhealthy"
                    health_status["error"] = "Unexpected test query result"
                    
        except Exception as e:
            health_status["status"] = "unhealthy"
            health_status["error"] = str(e)
            logger.error(f"Database health check failed: {e}")
        
        return health_status
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        Get database statistics.
        
        Returns:
            Dict containing database statistics
        """
        if not self._is_initialized:
            return {"error": "Database not initialized"}
        
        try:
            async with self.get_async_session() as session:
                # Get table counts
                from .models import Call, Conversation, Message, SystemEvent
                
                calls_count = await session.execute(text("SELECT COUNT(*) FROM calls"))
                conversations_count = await session.execute(text("SELECT COUNT(*) FROM conversations"))
                messages_count = await session.execute(text("SELECT COUNT(*) FROM messages"))
                events_count = await session.execute(text("SELECT COUNT(*) FROM system_events"))
                
                return {
                    "tables": {
                        "calls": calls_count.scalar(),
                        "conversations": conversations_count.scalar(),
                        "messages": messages_count.scalar(),
                        "system_events": events_count.scalar()
                    },
                    "database_type": "sqlite" if self.settings.database_is_sqlite else "postgresql",
                    "pool_size": self.settings.db_pool_size if not self.settings.database_is_sqlite else "N/A"
                }
                
        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            return {"error": str(e)}
    
    async def cleanup(self) -> None:
        """Clean up database connections and resources."""
        logger.info("Cleaning up database connections...")
        
        try:
            if self._async_engine:
                await self._async_engine.dispose()
                self._async_engine = None
            
            if self._sync_engine:
                self._sync_engine.dispose()
                self._sync_engine = None
            
            self._async_session_factory = None
            self._sync_session_factory = None
            self._is_initialized = False
            
            logger.info("Database cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during database cleanup: {e}")


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


def get_database_manager() -> DatabaseManager:
    """
    Get the global database manager instance.
    
    Returns:
        DatabaseManager: The global database manager
    """
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


async def init_database() -> DatabaseManager:
    """
    Initialize the global database manager and create tables.
    
    Returns:
        DatabaseManager: The initialized database manager
    """
    db_manager = get_database_manager()
    await db_manager.initialize()
    await db_manager.create_tables()
    return db_manager


async def cleanup_database() -> None:
    """Clean up the global database manager."""
    global _db_manager
    if _db_manager:
        await _db_manager.cleanup()
        _db_manager = None