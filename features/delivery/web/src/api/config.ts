import { getStoredSessionId } from "./session";
import type { ApiConfig } from "./types";

export function getApiConfig(): ApiConfig {
  return {
    baseUrl: "/api",
    sessionId: getStoredSessionId() ?? "web-pending",
    userId: "web-user",
  };
}
