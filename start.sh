#!/bin/bash

# Markly - Quick Start Script
# Usage: ./start.sh

cd "$(dirname "$0")"

echo "🚀 Starting Markly..."

# Kill any existing processes on ports 5000 and 5173
lsof -ti:5000 | xargs kill -9 2>/dev/null
lsof -ti:5173 | xargs kill -9 2>/dev/null

# Start backend
echo "📦 Starting backend on http://localhost:5050..."
cd backend
FLASK_APP=app:create_app ../.venv/bin/flask run --port 5050 &
BACKEND_PID=$!
cd ..

# Wait for backend to start
sleep 2

# Start frontend
echo "🎨 Starting frontend on http://localhost:5173..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "✅ Markly is running!"
echo "   Frontend: http://localhost:5173"
echo "   Backend:  http://localhost:5050"
echo ""
echo "Press Ctrl+C to stop both servers"

# Wait for Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo ''; echo '👋 Stopped Markly'; exit" INT
wait
