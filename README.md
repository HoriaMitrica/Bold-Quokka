# Bold-Quokka

Microservice-based pipeline for YouTube audio extraction, transcription, RAG indexing, and chat Q&A with Ollama.

## Services

- `db-service` (`8001`): metadata and transcript registry on Postgres
- `youtube-audio-service` (`8003`): download/extract WAV from YouTube
- `audio-text-service` (`8002`): Whisper-based transcription
- `rag-indexer` (`8005`): chunking + embeddings + Qdrant ingestion
- `chat-service` (`8006`): retrieval + response generation via Ollama
- `qdrant-admin` (`8007`): Qdrant inspection API
- `db` (`5432`): PostgreSQL
- `qdrant` (`6333`): vector database
- `pgadmin` (`5050`): Postgres UI
- `prometheus` (`9090`): metrics scraping
- `grafana` (`3001`): dashboards
- `frontend` (`8080`): user UI (guided pipeline + chat + health)

## Quick Start

1. Create env file:
   - `cp env.example .env`
2. Adjust credentials and host-specific values in `.env`.
3. Start all containers:
   - `docker compose up -d --build`
4. Validate compose:
   - `docker compose ps`
   - `./scripts/smoke_test.sh`

## Health Endpoints

- `http://localhost:8001/api/v1/health`
- `http://localhost:8002/api/v1/health`
- `http://localhost:8003/api/v1/health`
- `http://localhost:8005/health`
- `http://localhost:8006/health`
- `http://localhost:8007/health`

## Monitoring Endpoints

- pgAdmin: `http://localhost:5050`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3001`
- Metrics (each service): `http://localhost:<service_port>/metrics`

## UI (Frontend)

- App URL: `http://localhost:8080`
- The UI supports:
  - guided flow (extract -> transcribe -> index),
  - chat against selected collection,
  - service health panel.
- Frontend API base URLs are configured through `.env` using:
  - `VITE_YOUTUBE_AUDIO_SERVICE_URL`
  - `VITE_AUDIO_TEXT_SERVICE_URL`
  - `VITE_RAG_INDEXER_URL`
  - `VITE_CHAT_SERVICE_URL`
  - `VITE_DB_SERVICE_URL`
  - `VITE_DEFAULT_COLLECTION`
- If you change any `VITE_*` value, rebuild frontend image:
  - `docker compose up -d --build frontend`

## Full End-to-End Smoke Test

Run health-only checks:

- `./scripts/smoke_test.sh`

Run full ingest -> transcribe -> index -> chat flow:

- `./scripts/smoke_test.sh --full \"https://www.youtube.com/watch?v=<video_id>\"`

Optional third argument sets Qdrant collection name:

- `./scripts/smoke_test.sh --full \"https://www.youtube.com/watch?v=<video_id>\" my-collection`

## Notes for Server Testing with Ollama

- Ensure Ollama is reachable from `chat-service` via `OLLAMA_URL`.
- Ensure the configured `OLLAMA_MODEL` is already pulled on the Ollama host.
- If Ollama is on a different machine than Docker host, use a routable URL (not `localhost`).