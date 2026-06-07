import type {
  DailySummary,
  NotificationRecord,
  SubscriptionPrefs,
} from "@/types/live";
import type { WebSessionBootstrapResponse } from "./types";

const SESSION_KEY = "disruptron.web.session";

export function getStoredSessionId(): string | null {
  return sessionStorage.getItem(SESSION_KEY);
}

export function setStoredSessionId(sessionId: string): void {
  sessionStorage.setItem(SESSION_KEY, sessionId);
}

export async function bootstrapWebSession(): Promise<WebSessionBootstrapResponse> {
  const existing = getStoredSessionId();
  const response = await fetch("/api/v1/web/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: existing ?? undefined,
      user_id: "web-user",
    }),
  });
  if (!response.ok) {
    throw new Error(`Session bootstrap failed (${response.status})`);
  }
  const data = (await response.json()) as WebSessionBootstrapResponse;
  setStoredSessionId(data.session_id);
  return data;
}

export function toDailySummaries(
  items: WebSessionBootstrapResponse["summaries"],
): DailySummary[] {
  return items.map((s) => ({
    date: s.date,
    title: s.title,
    body: s.body,
    updatedAt: s.updated_at,
  }));
}

export function toNotifications(
  items: WebSessionBootstrapResponse["notifications"],
): NotificationRecord[] {
  return items.map((n) => ({
    id: n.id,
    title: n.title,
    body: n.body,
    timestamp: n.timestamp,
  }));
}

export function toSubscriptionPrefs(
  sub: WebSessionBootstrapResponse["subscriptions"],
): SubscriptionPrefs {
  return { alerts: sub.alerts, daily: sub.daily };
}
