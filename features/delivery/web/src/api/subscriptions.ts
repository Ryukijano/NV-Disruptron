import type { SubscriptionPrefs } from "@/types/live";

const STORAGE_KEY = "disruptron.subscriptions";

export function loadSubscriptionPrefs(): SubscriptionPrefs {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { alerts: false, daily: false };
    return JSON.parse(raw) as SubscriptionPrefs;
  } catch {
    return { alerts: false, daily: false };
  }
}

export function saveSubscriptionPrefs(prefs: SubscriptionPrefs): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
}

export async function syncSubscriptionPrefs(prefs: SubscriptionPrefs): Promise<void> {
  // Stub: POST /v1/subscriptions when API exposes web subscribe endpoints.
  saveSubscriptionPrefs(prefs);
  void prefs;
}
