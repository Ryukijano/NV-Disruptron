import { getStoredSessionId } from "./session";
import type { ApiConfig } from "./types";

export function getApiConfig(): ApiConfig {
  return {
    baseUrl: import.meta.env.VITE_API_BASE_URL || "/api",
    sessionId: getStoredSessionId() ?? "web-pending",
    userId: "web-user",
  };
}
