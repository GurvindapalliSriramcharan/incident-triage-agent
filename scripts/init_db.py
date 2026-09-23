#!/usr/bin/env python3
"""
Initialize PostgreSQL database schema and required extensions (vector, uuid-ossp).
Run directly: python scripts/init_db.py
"""

import sys
import os

# Add root directory to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.connection import run_schema_migration, is_database_connected
from app.config import settings


def main():
    print(f"[*] Initializing database for Incident Triage Agent...")
    print(f"[*] Target Database URL: {settings.DATABASE_URL or 'None (DATABASE_URL not set)'}")

    if not settings.DATABASE_URL:
        print("[!] Warning: DATABASE_URL is not set. Set it in .env or environment to initialize a PostgreSQL database.")
        sys.exit(1)

    if not is_database_connected():
        print("[X] Error: Could not connect to PostgreSQL. Please verify your connection string and ensure the database server is running.")
        sys.exit(1)

    print("[*] Connection successful. Applying schema and extensions (vector, uuid)...")
    success = run_schema_migration()
    if success:
        print("[+] Database schema, tables (incidents, incident_events, incident_docs), and indexes initialized successfully!")
    else:
        print("[X] Failed to apply database schema.")
        sys.exit(1)


if __name__ == "__main__":
    main()
