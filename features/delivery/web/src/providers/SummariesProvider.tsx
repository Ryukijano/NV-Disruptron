import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { DailySummary } from "@/types/live";

const STORAGE_KEY = "disruptron.summaries";

function todayKey() {
  return new Date().toISOString().slice(0, 10);
}

function loadSummaries(): DailySummary[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as DailySummary[]) : [];
  } catch {
    return [];
  }
}

type SummariesContextValue = {
  summaries: DailySummary[];
  saveForToday: (title: string, body: string) => void;
};

const SummariesContext = createContext<SummariesContextValue | null>(null);

export function SummariesProvider({ children }: { children: ReactNode }) {
  const [summaries, setSummaries] = useState<DailySummary[]>(() => loadSummaries());

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(summaries));
  }, [summaries]);

  const saveForToday = useCallback((title: string, body: string) => {
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
  }, []);

  const value = useMemo(() => ({ summaries, saveForToday }), [summaries, saveForToday]);

  return <SummariesContext.Provider value={value}>{children}</SummariesContext.Provider>;
}

export function useSummaries() {
  const ctx = useContext(SummariesContext);
  if (!ctx) throw new Error("useSummaries must be used within SummariesProvider");
  return ctx;
}
