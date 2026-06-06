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
import { subscribeAgentEvents } from "@/api/agentEvents";
import type { NotificationRecord } from "@/types/live";

const STORAGE_KEY = "disruptron.notifications";
const TOAST_MS = 6000;
const MAX_TOASTS = 3;

function loadNotifications(): NotificationRecord[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as NotificationRecord[]) : [];
  } catch {
    return [];
  }
}

type PushOptions = {
  toast?: boolean;
};

type NotificationsContextValue = {
  items: NotificationRecord[];
  toasts: NotificationRecord[];
  pushNotification: (title: string, body?: string, options?: PushOptions) => void;
  dismissToast: (id: string) => void;
};

const NotificationsContext = createContext<NotificationsContextValue | null>(null);

export function NotificationsProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<NotificationRecord[]>(() => loadNotifications());
  const [toasts, setToasts] = useState<NotificationRecord[]>([]);
  const timers = useRef<Map<string, number>>(new Map());

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items.slice(0, 100)));
  }, [items]);

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
      setItems((prev) => [record, ...prev]);
      if (options?.toast !== false) {
        showToast(record);
      }
    },
    [showToast],
  );

  useEffect(() => {
    return subscribeAgentEvents((event) => {
      pushNotification(event.title, event.body, { toast: true });
    });
  }, [pushNotification]);

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
    () => ({ items, toasts, pushNotification, dismissToast }),
    [items, toasts, pushNotification, dismissToast],
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
