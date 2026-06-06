import type { AgentEvent } from "./types";

export type AgentEventsHandler = (event: AgentEvent) => void;

export function subscribeAgentEvents(_onEvent: AgentEventsHandler): () => void {
  // Stub: wire to backend push/SSE when disruptron-api exposes agent events.
  // Example future shape:
  //   GET /v1/events/stream  (SSE)
  //   or WebSocket /v1/events
  return () => {};
}
