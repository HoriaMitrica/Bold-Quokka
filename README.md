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
- `api-gateway` (`8082`): reverse proxy for public API access with CORS

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

Direct (local):

- `http://localhost:8001/api/v1/health`
- `http://localhost:8002/api/v1/health`
- `http://localhost:8003/api/v1/health`
- `http://localhost:8005/health`
- `http://localhost:8006/health`
- `http://localhost:8007/health`

Via API gateway (`API_GATEWAY_PORT`, default `8082`):

- `http://localhost:8082/db/api/v1/health`
- `http://localhost:8082/youtube/api/v1/health`
- `http://localhost:8082/audio/api/v1/health`
- `http://localhost:8082/rag/health`
- `http://localhost:8082/chat/health`

## Monitoring Endpoints

Local ports:

- pgAdmin: `http://localhost:5050`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3001`
- Metrics (each service): `http://localhost:<service_port>/metrics`

Via frontend reverse proxy (when `PUBLIC_URL` is set, e.g. Cloudflare):

- Grafana: `https://bold-quokka.mitrisoft.ro/grafana/`
- pgAdmin: `https://bold-quokka.mitrisoft.ro/pgadmin/`
- Prometheus: `https://bold-quokka.mitrisoft.ro/prometheus/`
- Qdrant dashboard: `https://bold-quokka.mitrisoft.ro/qdrant/dashboard`

## Public Deployment (Cloudflare Tunnel)

1. **UI**: tunnel `bold-quokka.mitrisoft.ro` → `http://<host>:${FRONTEND_PORT}`
2. **API**: tunnel `bold-quokka-api.mitrisoft.ro` → `http://<host>:${API_GATEWAY_PORT}`
3. Set in `.env`:
   - `PUBLIC_URL=https://bold-quokka.mitrisoft.ro`
   - `CORS_ALLOW_ORIGIN=https://bold-quokka.mitrisoft.ro`
   - `VITE_*` URLs pointing at `https://bold-quokka-api.mitrisoft.ro/...`
4. Rebuild and restart:
   - `docker compose up -d --build api-gateway frontend grafana prometheus`

CORS is handled by the API gateway nginx — no backend service rebuild needed for CORS.

## UI (Frontend)

- App URL: `http://localhost:8080` (or `FRONTEND_PORT`)
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
- `./scripts/smoke_test.sh --gateway`

Run full ingest -> transcribe -> index -> chat flow:

- `./scripts/smoke_test.sh --full \"https://www.youtube.com/watch?v=<video_id>\"`
- `./scripts/smoke_test.sh --gateway --full \"https://www.youtube.com/watch?v=<video_id>\"`

Optional third argument sets Qdrant collection name:

- `./scripts/smoke_test.sh --full \"https://www.youtube.com/watch?v=<video_id>\" my-collection`

CORS preflight check (after gateway is up):

```bash
curl -i -X OPTIONS "http://localhost:8082/chat/health" \
  -H "Origin: https://bold-quokka.mitrisoft.ro" \
  -H "Access-Control-Request-Method: GET"
```

## Notes for Server Testing with Ollama

- Ensure Ollama is reachable from `chat-service` via `OLLAMA_URL`.
- Ensure the configured `OLLAMA_MODEL` is already pulled on the Ollama host.
- If Ollama is on a different machine than Docker host, use a routable URL (not `localhost`).