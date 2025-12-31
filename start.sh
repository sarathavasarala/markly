#!/bin/bash

# Markly - Quick Start Script
# Usage: ./start.sh

cd "$(dirname "$0")"

ENV=${1:-prod}
echo "🚀 Starting Markly in $ENV mode..."

# Kill any existing processes on ports 5050 and 5173
lsof -ti:5050 | xargs kill -9 2>/dev/null
lsof -ti:5173 | xargs kill -9 2>/dev/null

# Start backend
echo "📦 Starting backend on http://localhost:5050..."
npm run backend:$ENV &
BACKEND_PID=$!

# Wait for backend to start
sleep 2

# Start frontend
echo "🎨 Starting frontend on http://localhost:5173..."
npm run frontend:$ENV &
FRONTEND_PID=$!

echo ""
echo "✅ Markly is running!"
echo "   Frontend: http://localhost:5173"
echo "   Backend:  http://localhost:5050"
echo ""
echo "Press Ctrl+C to stop both servers"

# Wait for Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo ''; echo '👋 Stopped Markly'; exit" INT
wait
