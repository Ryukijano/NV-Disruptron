export type LiveSessionState = "idle" | "listening" | "thinking" | "speaking";

export type DailySummary = {
  date: string;
  title: string;
  body: string;
  updatedAt: number;
};

export type NotificationRecord = {
  id: string;
  title: string;
  body: string;
  timestamp: number;
};

export type SubscriptionPrefs = {
  alerts: boolean;
  daily: boolean;
};
