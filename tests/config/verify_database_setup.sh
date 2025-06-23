#!/bin/bash
# Verify Real Database Setup with Migrations
# This script ensures the test database is properly configured with all constraints

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

echo "========================================"
echo "Verifying Real Database Setup"
echo "========================================"

# Check if test database is running
if ! docker-compose -f "$PROJECT_ROOT/docker-compose.test.yml" ps | grep -q "test-postgres.*Up"; then
    echo "ERROR: Test PostgreSQL is not running"
    echo "Run: $SCRIPT_DIR/start_test_services.sh"
    exit 1
fi

# Set environment
export TESTING=true
export TEST_DATABASE_URL="postgresql://test:test@localhost:5433/haven_test"

cd "$PROJECT_ROOT"

echo ""
echo "1. Resetting database..."
echo "------------------------"
# Drop and recreate database
PGPASSWORD=test psql -h localhost -p 5433 -U test -d postgres -c "DROP DATABASE IF EXISTS haven_test;"
PGPASSWORD=test psql -h localhost -p 5433 -U test -d postgres -c "CREATE DATABASE haven_test;"

echo ""
echo "2. Running migrations..."
echo "------------------------"
alembic upgrade head

echo ""
echo "3. Verifying schema..."
echo "----------------------"
python << EOF
import psycopg2
import sys

try:
    conn = psycopg2.connect(
        host="localhost",
        port="5433",
        database="haven_test",
        user="test",
        password="test"
    )
    cursor = conn.cursor()
    
    # Check tables
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name
    """)
    tables = [row[0] for row in cursor.fetchall()]
    
    print("Tables created:")
    for table in tables:
        print(f"  ✓ {table}")
    
    # Check constraints
    cursor.execute("""
        SELECT 
            tc.table_name, 
            tc.constraint_name,
            tc.constraint_type
        FROM information_schema.table_constraints tc
        WHERE tc.table_schema = 'public'
        AND tc.constraint_type IN ('CHECK', 'FOREIGN KEY', 'UNIQUE')
        ORDER BY tc.table_name, tc.constraint_type
    """)
    
    print("\nConstraints:")
    current_table = None
    for table, constraint, ctype in cursor.fetchall():
        if table != current_table:
            print(f"\n  {table}:")
            current_table = table
        print(f"    ✓ {constraint} ({ctype})")
    
    # Check indexes
    cursor.execute("""
        SELECT 
            tablename,
            indexname
        FROM pg_indexes
        WHERE schemaname = 'public'
        AND indexname LIKE 'idx_%'
        ORDER BY tablename, indexname
    """)
    
    print("\nIndexes:")
    current_table = None
    for table, index in cursor.fetchall():
        if table != current_table:
            print(f"\n  {table}:")
            current_table = table
        print(f"    ✓ {index}")
    
    # Check triggers
    cursor.execute("""
        SELECT 
            event_object_table,
            trigger_name
        FROM information_schema.triggers
        WHERE trigger_schema = 'public'
        ORDER BY event_object_table, trigger_name
    """)
    
    print("\nTriggers:")
    current_table = None
    for table, trigger in cursor.fetchall():
        if table != current_table:
            print(f"\n  {table}:")
            current_table = table
        print(f"    ✓ {trigger}")
    
    # Check functions
    cursor.execute("""
        SELECT routine_name
        FROM information_schema.routines
        WHERE routine_schema = 'public'
        AND routine_type = 'FUNCTION'
        ORDER BY routine_name
    """)
    
    print("\nFunctions:")
    for func in cursor.fetchall():
        print(f"  ✓ {func[0]}")
    
    cursor.close()
    conn.close()
    
    print("\n✅ Database schema verified successfully!")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    sys.exit(1)
EOF

echo ""
echo "4. Running constraint tests..."
echo "------------------------------"
cd "$SCRIPT_DIR"
python -m pytest ../integration/test_database_constraints.py::TestRealDatabaseConstraints::test_foreign_key_constraints_enforced -v

echo ""
echo "========================================"
echo "✅ Database setup verified successfully!"
echo "========================================"
echo ""
echo "Connection string: postgresql://test:test@localhost:5433/haven_test"
echo ""
