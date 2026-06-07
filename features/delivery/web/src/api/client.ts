import { getApiConfig } from "./config";
import { getStoredSessionId } from "./session";
import type {
  ChatRequest,
  ChatResponse,
  ChatStreamEvent,
  HealthResponse,
  IntegrationsResponse,
  TranscribeResponse,
  UserPreferences,
  WebSubscriptionResponse,
} from "./types";

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

  integrations(): Promise<IntegrationsResponse> {
    return this.request<IntegrationsResponse>("/v1/integrations");
  }

  chat(body: ChatRequest): Promise<ChatResponse> {
    return this.request<ChatResponse>("/v1/chat", {
      method: "POST",
      body: JSON.stringify({
        text: body.text,
        session_id: body.session_id ?? getStoredSessionId() ?? this.config.sessionId,
        user_id: body.user_id ?? this.config.userId,
      }),
    });
  }

  async chatStream(
    body: ChatRequest,
    onEvent: (event: ChatStreamEvent) => void,
  ): Promise<string> {
    const response = await fetch(`${this.config.baseUrl}/v1/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: body.text,
        session_id: body.session_id ?? getStoredSessionId() ?? this.config.sessionId,
        user_id: body.user_id ?? this.config.userId,
        image_path: body.image_path,
      }),
    });
    if (!response.ok || !response.body) {
      throw new Error(`Stream failed (${response.status})`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let reply = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() ?? "";
      for (const part of parts) {
        const line = part
          .split("\n")
          .find((l) => l.startsWith("data: "))
          ?.slice(6);
        if (!line) continue;
        const event = JSON.parse(line) as ChatStreamEvent;
        onEvent(event);
        if (event.type === "done") reply = event.reply;
      }
    }
    return reply;
  }

  getWebSubscriptions(): Promise<WebSubscriptionResponse> {
    const sessionId = getStoredSessionId() ?? this.config.sessionId;
    return this.request<WebSubscriptionResponse>(
      `/v1/web/subscriptions?session_id=${encodeURIComponent(sessionId)}`,
    );
  }

  putWebSubscriptions(prefs: { alerts?: boolean; daily?: boolean }): Promise<WebSubscriptionResponse> {
    return this.request<WebSubscriptionResponse>("/v1/web/subscriptions", {
      method: "PUT",
      body: JSON.stringify({
        session_id: getStoredSessionId() ?? this.config.sessionId,
        alerts: prefs.alerts,
        daily: prefs.daily,
      }),
    });
  }

  putWebSummary(body: { date: string; title: string; body: string }): Promise<void> {
    const sessionId = getStoredSessionId() ?? this.config.sessionId;
    return this.request("/v1/web/summaries", {
      method: "PUT",
      body: JSON.stringify({ session_id: sessionId, ...body }),
    });
  }

  postWebNotification(body: {
    title: string;
    body?: string;
    kind?: string;
    id?: string;
  }): Promise<void> {
    const sessionId = getStoredSessionId() ?? this.config.sessionId;
    return this.request("/v1/web/notifications", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId, ...body }),
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

  async chatWithImage(text: string, image: File, sessionId?: string): Promise<ChatResponse> {
    const sid = sessionId ?? getStoredSessionId() ?? this.config.sessionId;
    const form = new FormData();
    form.append("image", image);
    const params = new URLSearchParams({ text, session_id: sid });
    const response = await fetch(`${this.config.baseUrl}/v1/chat/image?${params}`, {
      method: "POST",
      body: form,
    });
    if (!response.ok) throw new Error(`Image chat failed (${response.status})`);
    return response.json() as Promise<ChatResponse>;
  }

  getPreferences(): Promise<UserPreferences> {
    const sessionId = getStoredSessionId() ?? this.config.sessionId;
    return this.request<UserPreferences>(
      `/v1/web/preferences?session_id=${encodeURIComponent(sessionId)}`,
    );
  }

  putPreferences(prefs: Partial<UserPreferences>): Promise<UserPreferences> {
    return this.request<UserPreferences>("/v1/web/preferences", {
      method: "PUT",
      body: JSON.stringify({
        session_id: getStoredSessionId() ?? this.config.sessionId,
        ...prefs,
      }),
    });
  }

  async synthesizeSpeech(text: string): Promise<Blob> {
    const response = await fetch(`${this.config.baseUrl}/v1/tts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!response.ok) throw new Error(`TTS failed (${response.status})`);
    return response.blob();
  }
}

let singleton: DisruptronApiClient | null = null;

export function getApiClient(): DisruptronApiClient {
  if (!singleton) singleton = new DisruptronApiClient();
  return singleton;
}
