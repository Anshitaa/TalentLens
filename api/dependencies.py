import os
from typing import Generator

import psycopg2
import psycopg2.extras
from fastapi import HTTPException

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://talentlens:talentlens@localhost:5434/talentlens",
)


def get_db() -> Generator:
    """
    psycopg2 connection context manager for FastAPI dependency injection.
    Yields a psycopg2 connection with RealDictCursor as the cursor factory,
    so rows come back as dicts. Closes connection after request completes.
    """
    conn = None
    try:
        conn = psycopg2.connect(
            DATABASE_URL,
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
        yield conn
    except psycopg2.OperationalError as e:
        raise HTTPException(status_code=500, detail=f"Database connection error: {e}")
    finally:
        if conn is not None:
            conn.close()
