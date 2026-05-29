#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ ! -f ".env" ]]; then
  echo "No .env file found. Copy env.example to .env first."
  exit 1
fi

set -a
source .env
set +a

echo "Running health checks..."
curl -fsS "http://localhost:${DB_SERVICE_PORT}/api/v1/health" >/dev/null
curl -fsS "http://localhost:${YOUTUBE_AUDIO_SERVICE_PORT}/api/v1/health" >/dev/null
curl -fsS "http://localhost:${AUDIO_TEXT_SERVICE_PORT}/api/v1/health" >/dev/null
curl -fsS "http://localhost:${RAG_INDEXER_PORT}/health" >/dev/null
curl -fsS "http://localhost:${CHAT_SERVICE_PORT}/health" >/dev/null
curl -fsS "http://localhost:${QDRANT_ADMIN_PORT:-8007}/health" >/dev/null

echo "Health checks passed."

if [[ "${1:-}" == "--full" ]]; then
  if [[ -z "${2:-}" ]]; then
    echo "Usage: ./scripts/smoke_test.sh --full <youtube_url>"
    exit 1
  fi

  YT_URL="$2"
  COLLECTION="${3:-batem-palma}"

  echo "Extracting audio..."
  EXTRACT_RESPONSE="$(
    curl -fsS -X POST "http://localhost:${YOUTUBE_AUDIO_SERVICE_PORT}/api/v1/extract-audio" \
      -H "Content-Type: application/json" \
      -d "{\"url\":\"${YT_URL}\"}"
  )"

  VIDEO_ID="$(python -c "import json,sys; print(json.loads(sys.argv[1])['video_id'])" "${EXTRACT_RESPONSE}")"
  TITLE="$(python -c "import json,sys; print(json.loads(sys.argv[1]).get('title', 'Unknown'))" "${EXTRACT_RESPONSE}")"
  echo "Extracted video id: ${VIDEO_ID} (${TITLE})"

  echo "Transcribing audio..."
  curl -fsS -X POST "http://localhost:${AUDIO_TEXT_SERVICE_PORT}/api/v1/process-audio/${VIDEO_ID}" >/dev/null

  echo "Indexing transcript into collection '${COLLECTION}'..."
  curl -fsS -X POST "http://localhost:${RAG_INDEXER_PORT}/index-by-video-id?space=${COLLECTION}" \
    -H "Content-Type: application/json" \
    -d "{\"video_id\":\"${VIDEO_ID}\"}" >/dev/null

  echo "Running chat query..."
  CHAT_RESPONSE="$(
    curl -fsS -X POST "http://localhost:${CHAT_SERVICE_PORT}/chat" \
      -H "Content-Type: application/json" \
      -d "{\"question\":\"Cine a fost concurentul principal?\",\"collection\":\"${COLLECTION}\",\"max_results\":5}"
  )"
  python -c "import json,sys; d=json.loads(sys.argv[1]); print('Answer:\\n', d.get('answer','<empty>'))" "${CHAT_RESPONSE}"
fi
