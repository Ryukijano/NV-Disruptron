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

export type TacticalPanelKind =
  | "video"
  | "live"
  | "audio"
  | "hazard"
  | "station"
  | "route"
  | "disruption"
  | "detection";

export type ActivePanel = {
  kind: TacticalPanelKind;
  title: string;
  expiresAt: number;
};

type TacticalPanelContextValue = {
  activePanels: ActivePanel[];
  activeKind: TacticalPanelKind | null;
  pushPanel: (kind: TacticalPanelKind, title: string, ttlMs?: number) => void;
  dismissPanel: (kind: TacticalPanelKind) => void;
  clearAllPanels: () => void;
};

const TacticalPanelContext = createContext<TacticalPanelContextValue | null>(null);

export function TacticalPanelProvider({ children }: { children: ReactNode }) {
  const [activePanels, setActivePanels] = useState<ActivePanel[]>([]);
  const timers = useRef<Map<string, number>>(new Map());

  const dismissPanel = useCallback((kind: TacticalPanelKind) => {
    const timer = timers.current.get(kind);
    if (timer) {
      window.clearTimeout(timer);
      timers.current.delete(kind);
    }
    setActivePanels((prev) => prev.filter((p) => p.kind !== kind));
  }, []);

  const clearAllPanels = useCallback(() => {
    for (const timer of timers.current.values()) {
      window.clearTimeout(timer);
    }
    timers.current.clear();
    setActivePanels([]);
  }, []);

  const pushPanel = useCallback(
    (kind: TacticalPanelKind, title: string, ttlMs = 15000) => {
      // Dismiss existing timer for this kind
      const oldTimer = timers.current.get(kind);
      if (oldTimer) {
        window.clearTimeout(oldTimer);
      }
      timers.current.delete(kind);

      // Defensive: ensure ttlMs is a valid number
      const validTtlMs = typeof ttlMs === "number" && !isNaN(ttlMs) && ttlMs > 0 ? ttlMs : 15000;
      const expiresAt = Date.now() + validTtlMs;
      setActivePanels((prev) => {
        const rest = prev.filter((p) => p.kind !== kind);
        return [...rest, { kind, title, expiresAt }];
      });

      const timer = window.setTimeout(() => dismissPanel(kind), validTtlMs);
      timers.current.set(kind, timer);
    },
    [dismissPanel],
  );

  // TTL sweeper — auto-expire panels whose time is up
  useEffect(() => {
    const sweep = setInterval(() => {
      const now = Date.now();
      setActivePanels((prev) => {
        const expired = prev.filter((p) => p.expiresAt <= now);
        if (expired.length === 0) return prev;
        for (const p of expired) {
          const t = timers.current.get(p.kind);
          if (t) {
            window.clearTimeout(t);
            timers.current.delete(p.kind);
          }
        }
        return prev.filter((p) => p.expiresAt > now);
      });
    }, 1000);
    return () => clearInterval(sweep);
  }, []);

  useEffect(() => {
    const activeTimers = timers.current;
    return () => {
      for (const timer of activeTimers.values()) {
        window.clearTimeout(timer);
      }
      activeTimers.clear();
    };
  }, []);

  const activeKind = useMemo(
    () => (activePanels.length > 0 ? activePanels[activePanels.length - 1].kind : null),
    [activePanels],
  );

  const value = useMemo(
    () => ({ activePanels, activeKind, pushPanel, dismissPanel, clearAllPanels }),
    [activePanels, activeKind, pushPanel, dismissPanel, clearAllPanels],
  );

  return (
    <TacticalPanelContext.Provider value={value}>
      {children}
    </TacticalPanelContext.Provider>
  );
}

export function useTacticalPanels() {
  const ctx = useContext(TacticalPanelContext);
  if (!ctx) throw new Error("useTacticalPanels must be used within TacticalPanelProvider");
  return ctx;
}
