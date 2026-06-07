export type HealthResponse = {
  status: string;
  service: string;
};

export type ChatRequest = {
  text: string;
  session_id?: string;
  user_id?: string;
  image_path?: string;
};

export type ChatResponse = {
  reply: string;
};

export type TranscribeResponse = {
  text: string;
};

export type AgentEvent = {
  id: string;
  title: string;
  body?: string;
  timestamp: number;
  kind?: string;
};

export type ChatStreamEvent =
  | { type: "status"; text: string }
  | { type: "done"; reply: string }
  | { type: "error"; message: string }
  | { type: "mode"; mode: string; agent_id: string; reason: string }
  | { type: "tool"; tool: string; status: string; detail?: string }
  | {
      type: "ui";
      title: string;
      variant?: "info" | "alert" | "plan";
      blocks: AgentUiBlock[];
    };

export type UserPreferences = {
  session_id: string;
  tube_lines: string[];
  areas: string[];
  ev_enabled: boolean;
  commute_morning: string;
  commute_evening: string;
  onboarding_complete: boolean;
};

export type WebSubscriptionResponse = {
  session_id: string;
  alerts: boolean;
  daily: boolean;
};

export type WebSessionMessage = {
  id: string;
  role: "user" | "assistant" | string;
  text: string;
  created_at?: string;
};

export type WebSessionBootstrapResponse = {
  session_id: string;
  messages: WebSessionMessage[];
  summaries: Array<{
    date: string;
    title: string;
    body: string;
    updated_at: number;
  }>;
  notifications: Array<{
    id: string;
    title: string;
    body: string;
    kind: string;
    timestamp: number;
  }>;
  subscriptions: WebSubscriptionResponse;
};

export type IntegrationsResponse = {
  telegram: { mode: string; recommended: string; description: string; warning: string };
  calendar: Record<string, unknown>;
  google_maps?: Record<string, unknown>;
  elevenlabs?: Record<string, unknown>;
  scheduler: { enabled: boolean; daily_digest: string };
  agent: {
    local: boolean;
    chat_mode: string;
    interactive_agent_id?: string;
    autonomous_agent_id?: string;
    timeout_s: number;
  };
};

export type AgentMetric = {
  label: string;
  value: string;
  delta?: string;
  tone?: "up" | "down" | "neutral";
};

export type AgentChartItem = {
  label: string;
  value: number;
  color?: string;
};

export type AgentTimelineItem = {
  time: string;
  title: string;
  detail?: string;
  status?: "ok" | "warn" | "bad";
};

export type AgentStatusItem = {
  line: string;
  status: "good" | "minor" | "severe";
  detail?: string;
};

export type AgentRouteData = {
  from: string;
  to: string;
  duration: string;
  mode: string;
  charge?: string;
  delay?: string;
};

export type AgentUiBlock =
  | { type: "metrics"; items: AgentMetric[] }
  | { type: "bar-chart"; title?: string; unit?: string; items: AgentChartItem[] }
  | { type: "timeline"; items: AgentTimelineItem[] }
  | { type: "status-grid"; items: AgentStatusItem[] }
  | { type: "route-card"; route: AgentRouteData };

export type AgentUiPayload = {
  title: string;
  body?: string;
  variant?: "info" | "alert" | "plan";
  blocks?: AgentUiBlock[];
};

export type ApiConfig = {
  baseUrl: string;
  sessionId: string;
  userId: string;
};
