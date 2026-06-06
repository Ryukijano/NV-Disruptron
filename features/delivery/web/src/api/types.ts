export type HealthResponse = {
  status: string;
  service: string;
};

export type ChatRequest = {
  text: string;
  session_id?: string;
  user_id?: string;
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
