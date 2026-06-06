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
import { registerAgentUiHandler } from "@/api/agentUi";
import type { AgentUiPayload } from "@/api/types";

const POPUP_MS = 7000;
const MAX_POPUPS = 2;

export type AgentUiPopup = AgentUiPayload & {
  id: string;
  timestamp: number;
};

type AgentUiContextValue = {
  popups: AgentUiPopup[];
  showAgentUi: (payload: AgentUiPayload) => void;
  dismissAgentUi: (id: string) => void;
};

const AgentUiContext = createContext<AgentUiContextValue | null>(null);

export function AgentUiProvider({ children }: { children: ReactNode }) {
  const [popups, setPopups] = useState<AgentUiPopup[]>([]);
  const timers = useRef<Map<string, number>>(new Map());

  const dismissAgentUi = useCallback((id: string) => {
    const timer = timers.current.get(id);
    if (timer) {
      window.clearTimeout(timer);
      timers.current.delete(id);
    }
    setPopups((prev) => prev.filter((p) => p.id !== id));
  }, []);

  const showAgentUi = useCallback(
    (payload: AgentUiPayload) => {
      const popup: AgentUiPopup = {
        ...payload,
        id: crypto.randomUUID(),
        timestamp: Date.now(),
        variant: payload.variant ?? "info",
      };
      setPopups((prev) => [...prev, popup].slice(-MAX_POPUPS));

      const timer = window.setTimeout(() => dismissAgentUi(popup.id), POPUP_MS);
      timers.current.set(popup.id, timer);
    },
    [dismissAgentUi],
  );

  useEffect(() => registerAgentUiHandler(showAgentUi), [showAgentUi]);

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
    () => ({ popups, showAgentUi, dismissAgentUi }),
    [popups, showAgentUi, dismissAgentUi],
  );

  return <AgentUiContext.Provider value={value}>{children}</AgentUiContext.Provider>;
}

export function useAgentUi() {
  const ctx = useContext(AgentUiContext);
  if (!ctx) throw new Error("useAgentUi must be used within AgentUiProvider");
  return ctx;
}
