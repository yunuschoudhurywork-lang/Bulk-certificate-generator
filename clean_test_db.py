"""
Clean test database by truncating all tables.
Run this script to remove persisted test data.
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.core.config import settings


async def clean_database():
    """Truncate all tables in the test database."""
    engine = create_async_engine(settings.database_url)
    
    try:
        async with engine.begin() as conn:
            await conn.execute(text('TRUNCATE generation_jobs, certificate_records CASCADE'))
            print('[SUCCESS] Database tables truncated successfully')
    except Exception as e:
        print(f'[ERROR] Error cleaning database: {e}')
        raise
    finally:
        await engine.dispose()


if __name__ == '__main__':
    asyncio.run(clean_database())
