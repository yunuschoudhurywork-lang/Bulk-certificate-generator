"""
Pytest configuration and shared fixtures.
"""

import pytest
import pytest_asyncio
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import event

from app.core.config import settings


# Create a test-specific engine
test_engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    poolclass=None,  # Use NullPool to avoid connection pool issues across tests
)


@pytest.fixture(scope="session")
def event_loop():
    """
    Create a session-scoped event loop.
    
    This ensures all tests share the same event loop, which is required
    for asyncpg connections to work properly across multiple tests.
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncSession:
    """
    Provide an async database session for tests with transaction isolation.
    
    Uses nested transactions (SAVEPOINT) to ensure each test is isolated:
    - A new connection is created for each test
    - An outer transaction is started
    - A nested transaction (SAVEPOINT) allows services to call commit()
    - After each service commit(), a new savepoint is created automatically
    - After the test, the outer transaction is rolled back
    - No test data persists to the database
    
    This approach allows services to call commit() and refresh() normally
    while ensuring complete test isolation.
    
    NOTE: This fixture only isolates data created within the test.
    If the database contains pre-existing data from integration tests or
    manual testing, it will be visible to tests. For a clean test environment,
    ensure the test database is empty before running tests, or use database
    migrations to reset state.
    """
    # Get a connection from the engine
    connection = await test_engine.connect()
    
    # Start an outer transaction
    transaction = await connection.begin()
    
    # Create a session bound to this connection
    session = AsyncSession(bind=connection, expire_on_commit=False)
    
    # Start a nested transaction (savepoint)
    nested = await connection.begin_nested()
    
    # Hook to recreate savepoint after each commit
    @event.listens_for(session.sync_session, "after_transaction_end")
    def restart_savepoint(sess, trans):
        # Only recreate savepoint for nested transaction commits
        # not for the outer transaction or already-nested transactions
        if trans.nested and not trans._parent.nested:
            # Check if connection is still active
            if connection.sync_connection.in_transaction():
                connection.sync_connection.begin_nested()
    
    try:
        yield session
    finally:
        # Remove the event listener
        event.remove(session.sync_session, "after_transaction_end", restart_savepoint)
        
        # Clean up
        await session.close()
        # Roll back the outer transaction (discards all test changes)
        await transaction.rollback()
        await connection.close()