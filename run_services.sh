#!/bin/bash

# Kill any existing processes on the ports we need
echo "Killing existing processes..."
kill $(lsof -t -i:8001) 2>/dev/null || true
kill $(lsof -t -i:8002) 2>/dev/null || true
kill $(lsof -t -i:8003) 2>/dev/null || true
kill $(lsof -t -i:8004) 2>/dev/null || true

# Create necessary directories
echo "Creating directories..."
mkdir -p downloaded_audio downloaded_text

# Initialize database
echo "Initializing database..."
cd db-service
python init_db.py
cd ..

# Start the database service
echo "Starting database service..."
cd db-service
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload &
cd ..

# Wait for database service to start
echo "Waiting for database service to start..."
sleep 5

# Start the audio-text service
echo "Starting audio-text service..."
cd audio-text-service
uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload &
cd ..

# Start the youtube-audio service
echo "Starting youtube-audio service..."
cd youtube-audio-service
uvicorn app.main:app --host 0.0.0.0 --port 8003 --reload &
cd ..

# Start the frontend service
echo "Starting frontend service..."
cd frontend
npm run dev &
cd ..

echo "All services started!"
echo "Database service: http://localhost:8001"
echo "Audio-text service: http://localhost:8002"
echo "Youtube-audio service: http://localhost:8003"
echo "Frontend: http://localhost:8004"

# Wait for all background processes
wait