import logging
import os
from contextlib import contextmanager
from typing import Generator, Optional
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from app.config import settings

logger = logging.getLogger(__name__)

_pool: Optional[ConnectionPool] = None
_warned_no_db: bool = False


def get_db_pool() -> Optional[ConnectionPool]:
    """Get or initialize the global PostgreSQL connection pool."""
    global _pool, _warned_no_db
    if _pool is not None:
        return _pool

    db_url = settings.DATABASE_URL
    if not db_url:
        if not _warned_no_db:
            logger.warning("DATABASE_URL is not set. Database features will operate in fallback mode.")
            _warned_no_db = True
        return None

    try:
        # Initialize connection pool with dict_row factory and disable prepared statements for PgBouncer / Supabase
        _pool = ConnectionPool(
            conninfo=db_url,
            min_size=1,
            max_size=10,
            timeout=10.0,
            open=True,
            kwargs={
                "row_factory": dict_row,
                "autocommit": True,
                "prepare_threshold": None
            }
        )
        logger.info("PostgreSQL connection pool initialized successfully.")
        return _pool
    except Exception as e:
        logger.error(f"Failed to initialize PostgreSQL connection pool: {e}")
        return None


@contextmanager
def get_db_connection() -> Generator[Optional[psycopg.Connection], None, None]:
    """Context manager for acquiring a database connection from the pool."""
    pool = get_db_pool()
    if pool is None:
        yield None
        return

    try:
        with pool.connection() as conn:
            yield conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        yield None


def is_database_connected() -> bool:
    """Check whether a live connection to PostgreSQL can be established."""
    try:
        with get_db_connection() as conn:
            if conn is None:
                return False
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                return cur.fetchone() is not None
    except Exception as e:
        logger.debug(f"Database health check failed: {e}")
        return False


def run_schema_migration() -> bool:
    """Execute schema.sql to ensure all required tables and extensions exist."""
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    if not os.path.exists(schema_path):
        logger.error(f"Schema file not found at {schema_path}")
        return False

    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    try:
        with get_db_connection() as conn:
            if conn is None:
                logger.warning("Cannot run schema migration: No database connection.")
                return False
            with conn.cursor() as cur:
                cur.execute(schema_sql)
            logger.info("Database schema applied successfully.")
            return True
    except Exception as e:
        logger.error(f"Failed to execute schema migration: {e}")
        return False
