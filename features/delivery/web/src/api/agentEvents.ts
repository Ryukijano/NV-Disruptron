import { getStoredSessionId } from "./session";
import type { AgentEvent, ChatStreamEvent } from "./types";

export type AgentEventsHandler = (event: AgentEvent) => void;
export type AgentStreamHandler = (event: ChatStreamEvent) => void;

export function subscribeAgentEvents(onEvent: AgentEventsHandler): () => void {
  const sessionId = getStoredSessionId();
  if (!sessionId) return () => {};

  const url = `/api/v1/events/stream?session_id=${encodeURIComponent(sessionId)}`;
  const source = new EventSource(url);

  source.onmessage = (message) => {
    try {
      const data = JSON.parse(message.data) as AgentEvent & { type?: string };
      if (data.type === "connected") return;
      onEvent({
        id: data.id,
        title: data.title,
        body: data.body,
        timestamp: data.timestamp,
        kind: data.kind,
      });
    } catch {
      // Ignore malformed events.
    }
  };

  return () => source.close();
}

export function subscribeAgentStream(onEvent: AgentStreamHandler): () => void {
  const sessionId = getStoredSessionId();
  if (!sessionId) return () => {};

  const url = `/api/v1/events/stream?session_id=${encodeURIComponent(sessionId)}`;
  const source = new EventSource(url);

  source.onmessage = (message) => {
    try {
      const data = JSON.parse(message.data) as ChatStreamEvent & { type?: string };
      if ((data as any).type === "connected") return;
      onEvent(data as ChatStreamEvent);
    } catch {
      // Ignore malformed events.
    }
  };

  return () => source.close();
}
