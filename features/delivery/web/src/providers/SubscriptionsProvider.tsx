import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  type ReactNode,
} from "react";
import { useApi } from "@/providers/ApiProvider";
import { useSession } from "@/providers/SessionProvider";
import type { SubscriptionPrefs } from "@/types/live";

type SubscriptionsContextValue = {
  prefs: SubscriptionPrefs;
  setAlerts: (enabled: boolean) => Promise<void>;
  setDaily: (enabled: boolean) => Promise<void>;
};

const SubscriptionsContext = createContext<SubscriptionsContextValue | null>(null);

export function SubscriptionsProvider({ children }: { children: ReactNode }) {
  const client = useApi();
  const { subscriptions, setSubscriptions } = useSession();

  const apply = useCallback(
    async (next: SubscriptionPrefs) => {
      setSubscriptions(next);
      try {
        await client.putWebSubscriptions({ alerts: next.alerts, daily: next.daily });
      } catch {
        // Server sync failed; local session state still updated.
      }
    },
    [client, setSubscriptions],
  );

  const setAlerts = useCallback(
    (enabled: boolean) => apply({ ...subscriptions, alerts: enabled }),
    [apply, subscriptions],
  );

  const setDaily = useCallback(
    (enabled: boolean) => apply({ ...subscriptions, daily: enabled }),
    [apply, subscriptions],
  );

  const value = useMemo(
    () => ({ prefs: subscriptions, setAlerts, setDaily }),
    [subscriptions, setAlerts, setDaily],
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
