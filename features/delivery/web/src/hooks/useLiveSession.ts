import { useCallback, useEffect, useRef, useState } from "react";
import { useApi } from "@/providers/ApiProvider";
import { useSummaries } from "@/providers/SummariesProvider";
import type { LiveSessionState } from "@/types/live";

export type ChatLine = {
  id: string;
  role: "user" | "assistant";
  text: string;
};

function isMorningSummary(text: string): boolean {
  const lower = text.toLowerCase();
  return lower.includes("daily plan") || lower.includes("morning briefing");
}

export function useLiveSession() {
  const client = useApi();
  const { saveForToday } = useSummaries();
  const [lines, setLines] = useState<ChatLine[]>([]);
  const [state, setState] = useState<LiveSessionState>("idle");
  const speakingTimer = useRef<number | null>(null);

  useEffect(
    () => () => {
      if (speakingTimer.current) window.clearTimeout(speakingTimer.current);
    },
    [],
  );

  const send = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || state === "thinking") return;

      setLines((prev) => [...prev, { id: crypto.randomUUID(), role: "user", text: trimmed }]);
      setState("thinking");

      try {
        const { reply } = await client.chat({ text: trimmed });
        setLines((prev) => [...prev, { id: crypto.randomUUID(), role: "assistant", text: reply }]);

        if (isMorningSummary(reply)) {
          saveForToday("Morning London ops plan", reply);
        }

        setState("speaking");
        if (speakingTimer.current) window.clearTimeout(speakingTimer.current);
        speakingTimer.current = window.setTimeout(() => setState("idle"), 2000);
      } catch {
        setLines((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: "assistant",
            text: "Could not reach disruptron-api. Start the gateway and try again.",
          },
        ]);
        setState("idle");
      }
    },
    [client, saveForToday, state],
  );

  const setListening = useCallback((active: boolean) => {
    setState(active ? "listening" : "idle");
  }, []);

  return { lines, state, send, setListening };
}
