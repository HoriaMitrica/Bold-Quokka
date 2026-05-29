import { config } from "./config";
import type {
  ChatResponse,
  CollectionsResponse,
  ExtractAudioResponse,
  IndexByVideoIdResponse,
  ProcessAudioResponse,
} from "./types";

class ApiError extends Error {
  status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(
  url: string,
  init?: RequestInit,
  timeoutMs = 120000
): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(url, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
      signal: controller.signal,
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new ApiError(errorText || "Request failed", response.status);
    }

    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }

    if (error instanceof Error && error.name === "AbortError") {
      throw new ApiError("Request timeout");
    }

    throw new ApiError(error instanceof Error ? error.message : "Unknown error");
  } finally {
    clearTimeout(timeout);
  }
}

export const api = {
  extractAudio(youtubeUrl: string): Promise<ExtractAudioResponse> {
    return request(`${config.youtubeServiceUrl}/api/v1/extract-audio`, {
      method: "POST",
      body: JSON.stringify({ url: youtubeUrl }),
    });
  },

  processAudio(videoId: string): Promise<ProcessAudioResponse> {
    return request(`${config.audioTextServiceUrl}/api/v1/process-audio/${videoId}`, {
      method: "POST",
    });
  },

  indexByVideoId(videoId: string, collection: string): Promise<IndexByVideoIdResponse> {
    const safeCollection = encodeURIComponent(collection);
    return request(`${config.ragIndexerUrl}/index-by-video-id?space=${safeCollection}`, {
      method: "POST",
      body: JSON.stringify({ video_id: videoId }),
    });
  },

  getCollections(): Promise<CollectionsResponse> {
    return request(`${config.chatServiceUrl}/collections`, undefined, 15000);
  },

  chat(question: string, collection: string, maxResults = 5): Promise<ChatResponse> {
    return request(`${config.chatServiceUrl}/chat`, {
      method: "POST",
      body: JSON.stringify({
        question,
        collection,
        max_results: maxResults,
      }),
    });
  },

  async getServiceHealth(
    name: string,
    url: string
  ): Promise<{ name: string; status: string; detail?: string }> {
    try {
      const health = await request<{ status?: string; error?: string }>(url, undefined, 8000);
      return {
        name,
        status: health.status ?? "unknown",
        detail: health.error,
      };
    } catch (error) {
      return {
        name,
        status: "unhealthy",
        detail: error instanceof Error ? error.message : "Health check failed",
      };
    }
  },
};

export { ApiError };
