import type { ApiConfig } from "./types";

const SESSION_KEY = "disruptron.web.session";

function sessionId(): string {
  const existing = sessionStorage.getItem(SESSION_KEY);
  if (existing) return existing;
  const id = `web-${crypto.randomUUID().slice(0, 8)}`;
  sessionStorage.setItem(SESSION_KEY, id);
  return id;
}

export function getApiConfig(): ApiConfig {
  return {
    baseUrl: "/api",
    sessionId: sessionId(),
    userId: "web-user",
  };
}
