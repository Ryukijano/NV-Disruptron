import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  type ReactNode,
} from "react";
import { useApi } from "@/providers/ApiProvider";
import { useSession } from "@/providers/SessionProvider";
import type { DailySummary } from "@/types/live";

function todayKey() {
  return new Date().toISOString().slice(0, 10);
}

type SummariesContextValue = {
  summaries: DailySummary[];
  saveForToday: (title: string, body: string) => void;
};

const SummariesContext = createContext<SummariesContextValue | null>(null);

export function SummariesProvider({ children }: { children: ReactNode }) {
  const client = useApi();
  const { summaries, setSummaries } = useSession();

  const saveForToday = useCallback(
    (title: string, body: string) => {
      const date = todayKey();
      const entry: DailySummary = {
        date,
        title,
        body,
        updatedAt: Date.now(),
      };
      setSummaries((prev) => {
        const rest = prev.filter((s) => s.date !== date);
        return [entry, ...rest].sort((a, b) => b.date.localeCompare(a.date));
      });
      void client.putWebSummary({ date, title, body }).catch(() => {});
    },
    [client, setSummaries],
  );

  const value = useMemo(() => ({ summaries, saveForToday }), [summaries, saveForToday]);

  return <SummariesContext.Provider value={value}>{children}</SummariesContext.Provider>;
}

export function useSummaries() {
  const ctx = useContext(SummariesContext);
  if (!ctx) throw new Error("useSummaries must be used within SummariesProvider");
  return ctx;
}
