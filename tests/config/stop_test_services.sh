#!/bin/bash
# Stop Real Test Services

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

echo "Stopping test services..."

# Navigate to project root
cd "$PROJECT_ROOT"

# Stop docker services
docker-compose -f docker-compose.test.yml down -v

# Stop ganache if running
if [ -f "$SCRIPT_DIR/.ganache.pid" ]; then
    GANACHE_PID=$(cat "$SCRIPT_DIR/.ganache.pid")
    if ps -p $GANACHE_PID > /dev/null 2>&1; then
        echo "Stopping Ganache (PID: $GANACHE_PID)..."
        kill $GANACHE_PID || true
    fi
    rm "$SCRIPT_DIR/.ganache.pid"
fi

# Additional cleanup
pkill -f ganache || true

echo "All test services stopped."
