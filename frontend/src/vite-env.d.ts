/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_YOUTUBE_AUDIO_SERVICE_URL?: string;
  readonly VITE_AUDIO_TEXT_SERVICE_URL?: string;
  readonly VITE_RAG_INDEXER_URL?: string;
  readonly VITE_CHAT_SERVICE_URL?: string;
  readonly VITE_DB_SERVICE_URL?: string;
  readonly VITE_DEFAULT_COLLECTION?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
