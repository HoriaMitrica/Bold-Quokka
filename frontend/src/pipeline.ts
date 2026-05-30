import { api, ApiError } from "./api";
import type { ExtractAudioResponse, VideoRecord } from "./types";

export function videoToExtractResponse(video: VideoRecord): ExtractAudioResponse {
  return {
    status: "success",
    skipped: true,
    video_id: video.video_id,
    title: video.title,
    audio_file: video.audio_file_path,
    duration: video.duration,
  };
}

export async function resolveVideoForUrl(youtubeUrl: string): Promise<VideoRecord | null> {
  const videoId = api.extractVideoId(youtubeUrl);
  if (!videoId) {
    return null;
  }
  return api.getVideo(videoId);
}

export async function extractOrRecover(
  youtubeUrl: string,
  existingVideo: VideoRecord | null
): Promise<ExtractAudioResponse> {
  if (existingVideo?.audio_file_path) {
    return videoToExtractResponse(existingVideo);
  }

  const videoIdHint = api.extractVideoId(youtubeUrl);

  try {
    return await api.extractAudio(youtubeUrl);
  } catch (error) {
    if (videoIdHint) {
      const recovered = await api.getVideo(videoIdHint);
      if (recovered?.audio_file_path) {
        return videoToExtractResponse(recovered);
      }
    }
    throw error;
  }
}

export async function refreshVideoState(videoId: string): Promise<VideoRecord | null> {
  return api.getVideo(videoId);
}

export function shouldSkipTranscribe(video: VideoRecord | null): boolean {
  return video?.text_status === "TEXT";
}

export function formatStepStatus(
  status: "idle" | "running" | "success" | "failed",
  skipped?: boolean
): string {
  if (skipped && status === "success") {
    return "skipped";
  }
  return status;
}

export { ApiError };
