import type { AgentUiPayload } from "./types";

type AgentUiHandler = (payload: AgentUiPayload) => void;

let handler: AgentUiHandler | null = null;

export function registerAgentUiHandler(fn: AgentUiHandler): () => void {
  handler = fn;
  return () => {
    if (handler === fn) handler = null;
  };
}

export function showAgentUi(payload: AgentUiPayload): void {
  if (!handler) {
    if (import.meta.env.DEV) {
      console.warn("[agentUi] showAgentUi called before UI mounted", payload);
    }
    return;
  }
  handler(payload);
}
