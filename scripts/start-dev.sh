#!/bin/bash

# Haven Health Passport - Start Development Environment
# This script starts both backend and frontend services

echo "🚀 Starting Haven Health Passport Development Environment"
echo "======================================================="

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop first."
    exit 1
fi

# Start Docker services
echo "📦 Starting Docker services..."
docker-compose up -d

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 10

# Start backend in background
echo "🔧 Starting Backend API (port 8000)..."
source venv/bin/activate 2>/dev/null || {
    echo "⚠️  Virtual environment not found. Creating one..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
}

# Start backend in background
python app.py &
BACKEND_PID=$!
echo "✅ Backend started with PID: $BACKEND_PID"

# Start frontend
echo "🎨 Starting Frontend Web Portal (port 3000)..."
cd web

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    npm install
fi

# Create .env.local if it doesn't exist
if [ ! -f ".env.local" ]; then
    echo "📝 Creating .env.local from .env.example..."
    cp .env.example .env.local
fi

# Start frontend
npm start &
FRONTEND_PID=$!
echo "✅ Frontend started with PID: $FRONTEND_PID"

echo ""
echo "🎉 Haven Health Passport is running!"
echo "====================================="
echo "📱 Web Portal: http://localhost:3000"
echo "🔧 Backend API: http://localhost:8000"
echo "📚 API Docs: http://localhost:8000/api/docs"
echo "🚀 GraphQL: http://localhost:8000/graphql"
echo ""
echo "Press Ctrl+C to stop all services"

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down services..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    docker-compose down
    echo "✅ All services stopped"
    exit 0
}

# Set trap to cleanup on Ctrl+C
trap cleanup INT

# Keep script running
wait
