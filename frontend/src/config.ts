const required = (value: string | undefined, fallback: string): string =>
  value && value.trim().length > 0 ? value : fallback;

export const config = {
  youtubeServiceUrl: required(
    import.meta.env.VITE_YOUTUBE_AUDIO_SERVICE_URL,
    "http://localhost:8003"
  ),
  audioTextServiceUrl: required(
    import.meta.env.VITE_AUDIO_TEXT_SERVICE_URL,
    "http://localhost:8002"
  ),
  ragIndexerUrl: required(
    import.meta.env.VITE_RAG_INDEXER_URL,
    "http://localhost:8005"
  ),
  chatServiceUrl: required(
    import.meta.env.VITE_CHAT_SERVICE_URL,
    "http://localhost:8006"
  ),
  dbServiceUrl: required(
    import.meta.env.VITE_DB_SERVICE_URL,
    "http://localhost:8001"
  ),
  defaultCollection: required(import.meta.env.VITE_DEFAULT_COLLECTION, "batem-palma"),
};
