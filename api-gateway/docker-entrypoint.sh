#!/bin/sh
set -eu

export CORS_ALLOW_ORIGIN="${CORS_ALLOW_ORIGIN:-https://bold-quokka.mitrisoft.ro}"
export DB_SERVICE_PORT="${DB_SERVICE_PORT:-8001}"
export AUDIO_TEXT_SERVICE_PORT="${AUDIO_TEXT_SERVICE_PORT:-8002}"
export YOUTUBE_AUDIO_SERVICE_PORT="${YOUTUBE_AUDIO_SERVICE_PORT:-8003}"
export RAG_INDEXER_PORT="${RAG_INDEXER_PORT:-8005}"
export CHAT_SERVICE_PORT="${CHAT_SERVICE_PORT:-8006}"

envsubst '${CORS_ALLOW_ORIGIN} ${DB_SERVICE_PORT} ${AUDIO_TEXT_SERVICE_PORT} ${YOUTUBE_AUDIO_SERVICE_PORT} ${RAG_INDEXER_PORT} ${CHAT_SERVICE_PORT}' \
  < /etc/nginx/templates/nginx.conf.template \
  > /etc/nginx/conf.d/default.conf

exec nginx -g 'daemon off;'
