import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { loadSubscriptionPrefs, syncSubscriptionPrefs } from "@/api/subscriptions";
import type { SubscriptionPrefs } from "@/types/live";

type SubscriptionsContextValue = {
  prefs: SubscriptionPrefs;
  setAlerts: (enabled: boolean) => Promise<void>;
  setDaily: (enabled: boolean) => Promise<void>;
};

const SubscriptionsContext = createContext<SubscriptionsContextValue | null>(null);

export function SubscriptionsProvider({ children }: { children: ReactNode }) {
  const [prefs, setPrefs] = useState<SubscriptionPrefs>(() => loadSubscriptionPrefs());

  const apply = useCallback(async (next: SubscriptionPrefs) => {
    setPrefs(next);
    await syncSubscriptionPrefs(next);
  }, []);

  const setAlerts = useCallback(
    (enabled: boolean) => apply({ ...prefs, alerts: enabled }),
    [apply, prefs],
  );

  const setDaily = useCallback(
    (enabled: boolean) => apply({ ...prefs, daily: enabled }),
    [apply, prefs],
  );

  const value = useMemo(
    () => ({ prefs, setAlerts, setDaily }),
    [prefs, setAlerts, setDaily],
  );

  return (
    <SubscriptionsContext.Provider value={value}>{children}</SubscriptionsContext.Provider>
  );
}

export function useSubscriptions() {
  const ctx = useContext(SubscriptionsContext);
  if (!ctx) throw new Error("useSubscriptions must be used within SubscriptionsProvider");
  return ctx;
}
