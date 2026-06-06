import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { subscribeAgentEvents } from "@/api/agentEvents";
import type { NotificationRecord } from "@/types/live";

const STORAGE_KEY = "disruptron.notifications";

function loadNotifications(): NotificationRecord[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as NotificationRecord[]) : [];
  } catch {
    return [];
  }
}

type NotificationsContextValue = {
  items: NotificationRecord[];
  addFromBackend: (title: string, body?: string) => void;
};

const NotificationsContext = createContext<NotificationsContextValue | null>(null);

export function NotificationsProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<NotificationRecord[]>(() => loadNotifications());

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items.slice(0, 100)));
  }, [items]);

  const addFromBackend = useCallback((title: string, body?: string) => {
    const record: NotificationRecord = {
      id: crypto.randomUUID(),
      title,
      body: body ?? "",
      timestamp: Date.now(),
    };
    setItems((prev) => [record, ...prev]);
  }, []);

  useEffect(() => {
    return subscribeAgentEvents((event) => {
      addFromBackend(event.title, event.body);
    });
  }, [addFromBackend]);

  const value = useMemo(() => ({ items, addFromBackend }), [items, addFromBackend]);

  return (
    <NotificationsContext.Provider value={value}>{children}</NotificationsContext.Provider>
  );
}

export function useNotifications() {
  const ctx = useContext(NotificationsContext);
  if (!ctx) throw new Error("useNotifications must be used within NotificationsProvider");
  return ctx;
}
