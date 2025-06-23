#!/usr/bin/env python3
"""Check current symptom descriptions in the glossary."""

import psycopg2

# Database configuration
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "haven_health"
DB_USER = "haven_user"
DB_PASSWORD = "haven_password"

try:
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    cursor = conn.cursor()
    
    # Check for symptom terms
    cursor.execute("""
        SELECT COUNT(*) FROM medical_glossary 
        WHERE category IN ('symptoms_signs', 'symptom')
    """)
    
    count = cursor.fetchone()[0]
    print(f"Current symptom terms in glossary: {count}")
    
    conn.close()
    
except Exception as e:
    print(f"Error: {e}")
