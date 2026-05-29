export type HealthStatus = "healthy" | "degraded" | "unhealthy" | "unknown";

export interface ExtractAudioResponse {
  status: string;
  video_id: string;
  title: string;
  audio_file: string;
  duration?: number;
}

export interface ProcessAudioResponse {
  status: string;
  message: string;
  video_id: string;
  audio_path: string;
}

export interface IndexByVideoIdResponse {
  status: string;
  chunks_indexed: number;
}

export interface CollectionInfo {
  name: string;
  points_count?: number;
}

export interface CollectionsResponse {
  collections: CollectionInfo[];
}

export interface ChatSource {
  video_id: string;
  title: string;
  chunk_index: number;
  score: number;
  text_preview: string;
}

export interface ChatResponse {
  answer: string;
  sources: ChatSource[];
  question: string;
}

export interface PipelineRun {
  id: string;
  startedAt: string;
  youtubeUrl: string;
  collection: string;
  videoId?: string;
  title?: string;
  extractStatus: "idle" | "running" | "success" | "failed";
  transcribeStatus: "idle" | "running" | "success" | "failed";
  indexStatus: "idle" | "running" | "success" | "failed";
  error?: string;
}

export interface ServiceHealthItem {
  name: string;
  status: HealthStatus;
  detail?: string;
}
