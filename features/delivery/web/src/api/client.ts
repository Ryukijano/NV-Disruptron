import { getApiConfig } from "./config";
import type { ChatRequest, ChatResponse, HealthResponse, TranscribeResponse } from "./types";

export class DisruptronApiClient {
  private config = getApiConfig();

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${this.config.baseUrl}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...init?.headers,
      },
    });
    if (!response.ok) {
      throw new Error(`Request failed (${response.status})`);
    }
    return response.json() as Promise<T>;
  }

  health(): Promise<HealthResponse> {
    return this.request<HealthResponse>("/health");
  }

  chat(body: ChatRequest): Promise<ChatResponse> {
    return this.request<ChatResponse>("/v1/chat", {
      method: "POST",
      body: JSON.stringify({
        text: body.text,
        session_id: body.session_id ?? this.config.sessionId,
        user_id: body.user_id ?? this.config.userId,
      }),
    });
  }

  async transcribe(audio: Blob, filename = "recording.webm"): Promise<TranscribeResponse> {
    const form = new FormData();
    form.append("audio", audio, filename);
    const response = await fetch(`${this.config.baseUrl}/v1/transcribe`, {
      method: "POST",
      body: form,
    });
    if (!response.ok) {
      throw new Error(`Transcription failed (${response.status})`);
    }
    return response.json() as Promise<TranscribeResponse>;
  }
}

let singleton: DisruptronApiClient | null = null;

export function getApiClient(): DisruptronApiClient {
  if (!singleton) singleton = new DisruptronApiClient();
  return singleton;
}
