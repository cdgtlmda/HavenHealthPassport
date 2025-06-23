#!/usr/bin/env python3
"""Quick verification of medical glossary population."""

import os
import psycopg2

# Database configuration from environment variables
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "haven_health")
DB_USER = os.getenv("DB_USER", "haven_user")
DB_PASSWORD = os.getenv("DB_PASSWORD")

if not DB_PASSWORD:
    print("❌ Error: DB_PASSWORD environment variable not set!")
    print("Please set the DB_PASSWORD environment variable")
    exit(1)

try:
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

    cursor = conn.cursor()

    # Total count
    cursor.execute("SELECT COUNT(*) FROM medical_glossary")
    total = cursor.fetchone()[0]
    print(f"✅ Medical glossary successfully populated with {total} terms!")

    # Show sample terms
    cursor.execute("""
        SELECT term_display, category, source
        FROM medical_glossary
        LIMIT 5
    """)

    print("\nSample terms:")
    for row in cursor.fetchall():
        print(f"  - {row[0]} ({row[1]}, source: {row[2]})")

    conn.close()

except Exception as e:
    print(f"❌ Error: {e}")
