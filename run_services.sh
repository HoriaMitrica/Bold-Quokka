#!/bin/bash

# Remove any existing Qdrant container
docker rm -f qdrant 2>/dev/null || true

# Create Qdrant volume if it doesn't exist
docker volume create qdrant_data 2>/dev/null || true

# Kill any existing processes on the ports we need
echo "Killing existing processes..."
kill $(lsof -t -i:8001) 2>/dev/null || true
kill $(lsof -t -i:8002) 2>/dev/null || true
kill $(lsof -t -i:8003) 2>/dev/null || true
kill $(lsof -t -i:8004) 2>/dev/null || true
kill $(lsof -t -i:8005) 2>/dev/null || true
kill $(lsof -t -i:8006) 2>/dev/null || true
kill $(lsof -t -i:8007) 2>/dev/null || true

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

# Start the rag-indexer service
echo "Starting RAG Indexer service..."
cd rag-indexer
uvicorn app.main:app --host 0.0.0.0 --port 8005 --reload &
cd ..

# Start the chat service
echo "Starting Chat service..."
cd chat-service
uvicorn app.main:app --host 0.0.0.0 --port 8006 --reload &
cd ..

# # Start the frontend service
# echo "Starting frontend service..."
# cd frontend
# npm run dev &
# cd ..

# Start Qdrant vector database
echo "Starting Qdrant vector database..."
docker run -d --name qdrant -p 6333:6333 -v qdrant_data:/qdrant/storage qdrant/qdrant:latest

# Start Qdrant Admin service
echo "Starting Qdrant Admin service..."
cd qdrant-admin
uvicorn app.main:app --host 0.0.0.0 --port 8007 --reload &
cd ..

echo "All services started!"
echo "Database service: http://localhost:8001"
echo "Audio-text service: http://localhost:8002"
echo "Youtube-audio service: http://localhost:8003"
echo "RAG Indexer service: http://localhost:8005"
echo "Chat service: http://localhost:8006"
echo "Qdrant Admin service: http://localhost:8007"
# echo "Frontend: http://localhost:8004"

# Wait for all background processes
wait