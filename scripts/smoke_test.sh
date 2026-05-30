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

USE_GATEWAY=false
FULL_TEST=false
YT_URL=""
COLLECTION="batem-palma"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --gateway)
      USE_GATEWAY=true
      shift
      ;;
    --full)
      FULL_TEST=true
      shift
      if [[ $# -gt 0 && "$1" != --* ]]; then
        YT_URL="$1"
        shift
      fi
      if [[ $# -gt 0 && "$1" != --* ]]; then
        COLLECTION="$1"
        shift
      fi
      ;;
    *)
      echo "Unknown argument: $1"
      echo "Usage: ./scripts/smoke_test.sh [--gateway] [--full <youtube_url> [collection]]"
      exit 1
      ;;
  esac
done

if [[ "${USE_GATEWAY}" == "true" ]]; then
  BASE_URL="http://localhost:${API_GATEWAY_PORT:-8082}"
  echo "Running health checks via API gateway (${BASE_URL})..."
  curl -fsS "${BASE_URL}/db/api/v1/health" >/dev/null
  curl -fsS "${BASE_URL}/youtube/api/v1/health" >/dev/null
  curl -fsS "${BASE_URL}/audio/api/v1/health" >/dev/null
  curl -fsS "${BASE_URL}/rag/health" >/dev/null
  curl -fsS "${BASE_URL}/chat/health" >/dev/null
else
  echo "Running health checks..."
  curl -fsS "http://localhost:${DB_SERVICE_PORT}/api/v1/health" >/dev/null
  curl -fsS "http://localhost:${YOUTUBE_AUDIO_SERVICE_PORT}/api/v1/health" >/dev/null
  curl -fsS "http://localhost:${AUDIO_TEXT_SERVICE_PORT}/api/v1/health" >/dev/null
  curl -fsS "http://localhost:${RAG_INDEXER_PORT}/health" >/dev/null
  curl -fsS "http://localhost:${CHAT_SERVICE_PORT}/health" >/dev/null
  curl -fsS "http://localhost:${QDRANT_ADMIN_PORT:-8007}/health" >/dev/null
fi

echo "Health checks passed."

if [[ "${FULL_TEST}" == "true" ]]; then
  if [[ -z "${YT_URL}" ]]; then
    echo "Usage: ./scripts/smoke_test.sh [--gateway] --full <youtube_url> [collection]"
    exit 1
  fi

  if [[ "${USE_GATEWAY}" == "true" ]]; then
    YOUTUBE_BASE="${BASE_URL}/youtube"
    AUDIO_BASE="${BASE_URL}/audio"
    RAG_BASE="${BASE_URL}/rag"
    CHAT_BASE="${BASE_URL}/chat"
  else
    YOUTUBE_BASE="http://localhost:${YOUTUBE_AUDIO_SERVICE_PORT}"
    AUDIO_BASE="http://localhost:${AUDIO_TEXT_SERVICE_PORT}"
    RAG_BASE="http://localhost:${RAG_INDEXER_PORT}"
    CHAT_BASE="http://localhost:${CHAT_SERVICE_PORT}"
  fi

  echo "Extracting audio..."
  EXTRACT_RESPONSE="$(
    curl -fsS -X POST "${YOUTUBE_BASE}/api/v1/extract-audio" \
      -H "Content-Type: application/json" \
      -d "{\"url\":\"${YT_URL}\"}"
  )"

  VIDEO_ID="$(python -c "import json,sys; print(json.loads(sys.argv[1])['video_id'])" "${EXTRACT_RESPONSE}")"
  TITLE="$(python -c "import json,sys; print(json.loads(sys.argv[1]).get('title', 'Unknown'))" "${EXTRACT_RESPONSE}")"
  echo "Extracted video id: ${VIDEO_ID} (${TITLE})"

  echo "Transcribing audio..."
  curl -fsS -X POST "${AUDIO_BASE}/api/v1/process-audio/${VIDEO_ID}" >/dev/null

  echo "Indexing transcript into collection '${COLLECTION}'..."
  curl -fsS -X POST "${RAG_BASE}/index-by-video-id?space=${COLLECTION}" \
    -H "Content-Type: application/json" \
    -d "{\"video_id\":\"${VIDEO_ID}\"}" >/dev/null

  echo "Running chat query..."
  CHAT_RESPONSE="$(
    curl -fsS -X POST "${CHAT_BASE}/chat" \
      -H "Content-Type: application/json" \
      -d "{\"question\":\"Cine a fost concurentul principal?\",\"collection\":\"${COLLECTION}\",\"max_results\":5}"
  )"
  python -c "import json,sys; d=json.loads(sys.argv[1]); print('Answer:\\n', d.get('answer','<empty>'))" "${CHAT_RESPONSE}"
fi
