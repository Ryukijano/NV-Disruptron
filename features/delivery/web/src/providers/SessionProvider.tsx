import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  bootstrapWebSession,
  getStoredSessionId,
  toDailySummaries,
  toNotifications,
  toSubscriptionPrefs,
} from "@/api/session";
import type { WebSessionBootstrapResponse } from "@/api/types";
import type { DailySummary, NotificationRecord, SubscriptionPrefs } from "@/types/live";
import type { ChatLine } from "@/hooks/useLiveSession";

type SessionContextValue = {
  ready: boolean;
  sessionId: string | null;
  messages: ChatLine[];
  summaries: DailySummary[];
  notifications: NotificationRecord[];
  subscriptions: SubscriptionPrefs;
  setMessages: React.Dispatch<React.SetStateAction<ChatLine[]>>;
  setSummaries: React.Dispatch<React.SetStateAction<DailySummary[]>>;
  setNotifications: React.Dispatch<React.SetStateAction<NotificationRecord[]>>;
  setSubscriptions: React.Dispatch<React.SetStateAction<SubscriptionPrefs>>;
  refreshMessages: () => Promise<void>;
};

const SessionContext = createContext<SessionContextValue | null>(null);

function mapMessages(items: WebSessionBootstrapResponse["messages"]): ChatLine[] {
  return items
    .filter((m) => m.role === "user" || m.role === "assistant")
    .map((m) => ({
      id: m.id,
      role: m.role as "user" | "assistant",
      text: m.text,
    }));
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(getStoredSessionId());
  const [messages, setMessages] = useState<ChatLine[]>([]);
  const [summaries, setSummaries] = useState<DailySummary[]>([]);
  const [notifications, setNotifications] = useState<NotificationRecord[]>([]);
  const [subscriptions, setSubscriptions] = useState<SubscriptionPrefs>({
    alerts: false,
    daily: false,
  });

  const refreshMessages = useCallback(async () => {
    const sid = getStoredSessionId();
    if (!sid) return;
    const response = await fetch(
      `/api/v1/web/messages?session_id=${encodeURIComponent(sid)}&limit=100`,
    );
    if (!response.ok) return;
    const data = (await response.json()) as WebSessionBootstrapResponse["messages"];
    setMessages(mapMessages(data));
  }, []);

  useEffect(() => {
    let cancelled = false;
    bootstrapWebSession()
      .then((data) => {
        if (cancelled) return;
        setSessionId(data.session_id);
        setMessages(mapMessages(data.messages));
        setSummaries(toDailySummaries(data.summaries));
        setNotifications(toNotifications(data.notifications));
        setSubscriptions(toSubscriptionPrefs(data.subscriptions));
        setReady(true);
      })
      .catch(() => {
        if (!cancelled) setReady(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const value = useMemo(
    () => ({
      ready,
      sessionId,
      messages,
      summaries,
      notifications,
      subscriptions,
      setMessages,
      setSummaries,
      setNotifications,
      setSubscriptions,
      refreshMessages,
    }),
    [
      ready,
      sessionId,
      messages,
      summaries,
      notifications,
      subscriptions,
      refreshMessages,
    ],
  );

  if (!ready) {
    return (
      <div className="flex h-dvh items-center justify-center bg-obsidian text-sm text-cyan-neon font-mono tracking-widest uppercase">
        <span className="animate-neon-pulse">Loading session…</span>
      </div>
    );
  }

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used within SessionProvider");
  return ctx;
}
