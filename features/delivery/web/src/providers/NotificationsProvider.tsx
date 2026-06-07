import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { showAgentUi } from "@/api/agentUi";
import { subscribeAgentEvents } from "@/api/agentEvents";
import { useApi } from "@/providers/ApiProvider";
import { useSession } from "@/providers/SessionProvider";
import type { NotificationRecord } from "@/types/live";
import { useSummaries } from "./SummariesProvider";

const TOAST_MS = 6000;
const MAX_TOASTS = 3;

type PushOptions = {
  toast?: boolean;
  persist?: boolean;
};

type NotificationsContextValue = {
  items: NotificationRecord[];
  toasts: NotificationRecord[];
  pushNotification: (title: string, body?: string, options?: PushOptions) => void;
  dismissToast: (id: string) => void;
};

const NotificationsContext = createContext<NotificationsContextValue | null>(null);

export function NotificationsProvider({ children }: { children: ReactNode }) {
  const client = useApi();
  const { saveForToday } = useSummaries();
  const { notifications, setNotifications } = useSession();
  const [toasts, setToasts] = useState<NotificationRecord[]>([]);
  const timers = useRef<Map<string, number>>(new Map());

  const dismissToast = useCallback((id: string) => {
    const timer = timers.current.get(id);
    if (timer) {
      window.clearTimeout(timer);
      timers.current.delete(id);
    }
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const showToast = useCallback(
    (record: NotificationRecord) => {
      setToasts((prev) => [...prev, record].slice(-MAX_TOASTS));
      const timer = window.setTimeout(() => dismissToast(record.id), TOAST_MS);
      timers.current.set(record.id, timer);
    },
    [dismissToast],
  );

  const pushNotification = useCallback(
    (title: string, body?: string, options?: PushOptions) => {
      const record: NotificationRecord = {
        id: crypto.randomUUID(),
        title,
        body: body ?? "",
        timestamp: Date.now(),
      };
      setNotifications((prev) => [record, ...prev].slice(0, 100));
      if (options?.persist !== false) {
        void client
          .postWebNotification({
            id: record.id,
            title: record.title,
            body: record.body,
          })
          .catch(() => {});
      }
      if (options?.toast !== false) {
        showToast(record);
      }
    },
    [client, setNotifications, showToast],
  );

  useEffect(() => {
    return subscribeAgentEvents((event) => {
      const record: NotificationRecord = {
        id: event.id,
        title: event.title,
        body: event.body ?? "",
        timestamp: event.timestamp,
      };
      setNotifications((prev) => {
        if (prev.some((p) => p.id === record.id)) return prev;
        return [record, ...prev].slice(0, 100);
      });
      showToast(record);
      if (event.kind === "daily" && event.body) {
        saveForToday(event.title, event.body);
        showAgentUi({
          title: "Morning plan received",
          body: "Saved to Summaries.",
          variant: "plan",
        });
      }
    });
  }, [saveForToday, setNotifications, showToast]);

  useEffect(() => {
    const activeTimers = timers.current;
    return () => {
      for (const timer of activeTimers.values()) {
        window.clearTimeout(timer);
      }
      activeTimers.clear();
    };
  }, []);

  const value = useMemo(
    () => ({ items: notifications, toasts, pushNotification, dismissToast }),
    [notifications, toasts, pushNotification, dismissToast],
  );

  return (
    <NotificationsContext.Provider value={value}>{children}</NotificationsContext.Provider>
  );
}

export function useNotifications() {
  const ctx = useContext(NotificationsContext);
  if (!ctx) throw new Error("useNotifications must be used within NotificationsProvider");
  return ctx;
}
