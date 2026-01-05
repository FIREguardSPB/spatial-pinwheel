#!/bin/bash
set -e

# P1: Dev Environment Unification

echo "--> Starting Docker Dependencies (Mock Profile)..."
# Ensure we use the correct compose file
docker compose -f backend/infra/docker-compose.yml --profile mock up -d postgres redis

echo "--> Docker services started."

echo "--> Starting Backend (Uvicorn :3000)..."
# Run in background
(cd backend && uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 3000) &
BACKEND_PID=$!

echo "--> Starting Frontend (Vite :5173)..."
npm run dev &
FRONTEND_PID=$!

echo "==================================================="
echo "   Dev Environment Running"
echo "   Backend:  http://localhost:3000"
echo "   Frontend: http://localhost:5173"
echo "   Press Ctrl+C to stop all services"
echo "==================================================="

# Trap cleanup
cleanup() {
    echo "Stopping services..."
    kill $BACKEND_PID
    kill $FRONTEND_PID
    docker compose -f backend/infra/docker-compose.yml stop
    exit
}

trap cleanup SIGINT

wait
