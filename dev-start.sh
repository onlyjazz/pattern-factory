#!/bin/bash

# Start the backend uvicorn server in the background
echo "Starting backend server on http://0.0.0.0:8000..."
uvicorn backend.services.api:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Give the backend a moment to start
sleep 2

# Start the frontend development server
echo "Starting frontend server..."
npm run dev

# Cleanup: kill backend when frontend stops
trap "kill $BACKEND_PID" EXIT
