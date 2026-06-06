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

export type AgentEvent = {
  id: string;
  title: string;
  body?: string;
  timestamp: number;
};

export type ApiConfig = {
  baseUrl: string;
  sessionId: string;
  userId: string;
};
