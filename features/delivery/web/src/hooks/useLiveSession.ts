import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { showAgentUi } from "@/api/agentUi";
import type { ChatStreamEvent } from "@/api/types";
import { useApi } from "@/providers/ApiProvider";
import { useSession } from "@/providers/SessionProvider";
import { useSummaries } from "@/providers/SummariesProvider";
import { useMapState } from "@/providers/MapStateProvider";
import { useTacticalPanels } from "@/providers/TacticalPanelProvider";
import { useTtsPlayback } from "@/hooks/useTtsPlayback";
import { subscribeAgentStream } from "@/api/agentEvents";
import type { LiveSessionState } from "@/types/live";

export type ChatLine = {
  id: string;
  role: "user" | "assistant";
  text: string;
};

function isMorningSummary(text: string): boolean {
  const lower = text.toLowerCase();
  return lower.includes("morning briefing") || lower.includes("morning plan");
}

function toolStatusLabel(event: Extract<ChatStreamEvent, { type: "tool" }>): string {
  const short = event.tool.replace("disruptron_ops__", "").replace("openclaw:", "");
  if (event.status === "start") return `Running ${short}…`;
  if (event.status === "done") return event.detail ? `${short}: ${event.detail}` : `${short} complete`;
  return `${short} failed`;
}

export function useLiveSession() {
  const client = useApi();
  const navigate = useNavigate();
  const { triggerMapIntent, setRouteCoordinates, setIsRoutingActive, pushDetection } = useMapState();
  const { saveForToday } = useSummaries();
  const { messages, setMessages, refreshMessages } = useSession();
  const tts = useTtsPlayback();
  const { pushPanel, clearAllPanels } = useTacticalPanels();
  const [lines, setLines] = useState<ChatLine[]>([]);
  const [state, setState] = useState<LiveSessionState>("idle");
  const [statusText, setStatusText] = useState<string | null>(null);
  const [agentMode, setAgentMode] = useState<string | null>(null);
  const [agentId, setAgentId] = useState<string | null>(null);
  const speakingTimer = useRef<number | null>(null);
  const activityDemoTimer = useRef<number | null>(null);

  useEffect(() => {
    setLines(messages);
  }, [messages]);

  const clearActivityDemo = useCallback(() => {
    if (activityDemoTimer.current) {
      window.clearTimeout(activityDemoTimer.current);
      activityDemoTimer.current = null;
    }
  }, []);

  useEffect(
    () => () => {
      if (speakingTimer.current) window.clearTimeout(speakingTimer.current);
      clearActivityDemo();
    },
    [clearActivityDemo],
  );

  const handleStreamEvent = useCallback((event: ChatStreamEvent) => {
    if (event.type === "status") setStatusText(event.text);
    if (event.type === "mode") {
      setAgentMode(event.mode);
      setAgentId(event.agent_id);
      setStatusText(event.reason);
    }
    if (event.type === "tool") setStatusText(toolStatusLabel(event));
    if (event.type === "ui") {
      showAgentUi({
        title: event.title,
        variant: event.variant ?? "info",
        blocks: event.blocks,
      });
    }
    if (event.type === "panel") {
      pushPanel(event.kind as any, event.title, event.ttlMs);
    }
    if (event.type === "route") {
      setRouteCoordinates(event.coordinates);
      setIsRoutingActive(true);
    }
    if (event.type === "detection") {
      const ttlMs = typeof event.ttlMs === "number" ? event.ttlMs : 30000;
      pushDetection({
        cameraId: event.camera_id,
        cameraName: event.camera_name,
        lat: event.lat,
        lon: event.lon,
        imageUrl: event.image_url,
        detections: event.detections,
      }, ttlMs);
      // Also push a tactical panel for the detection
      pushPanel("detection", `${event.camera_name} — ${event.detections.length} objects`, ttlMs);
    }
  }, [pushPanel, setRouteCoordinates, setIsRoutingActive, pushDetection]);

  // Subscribe to proactive autonomous events (watcher loop, alerts, etc.)
  useEffect(() => {
    const unsub = subscribeAgentStream(handleStreamEvent);
    return unsub;
  }, [handleStreamEvent]);

  const send = useCallback(
    async (text: string, image?: File) => {
      const trimmed = text.trim();
      if (!trimmed || state === "thinking") return;

      clearAllPanels();
      const matched = triggerMapIntent(trimmed);
      if (matched) {
        navigate("/");
      }

      const userLine: ChatLine = {
        id: crypto.randomUUID(),
        role: "user",
        text: image ? `${trimmed} [image]` : trimmed,
      };
      setLines((prev) => [...prev, userLine]);
      setMessages((prev) => [...prev, userLine]);
      setState("thinking");
      setStatusText("Routing…");
      setAgentMode(null);

      try {
        let reply: string;
        if (image) {
          const response = await client.chatWithImage(trimmed, image);
          reply = response.reply;
        } else {
          reply = await client.chatStream({ text: trimmed }, handleStreamEvent);
        }
        setStatusText(null);
        const assistantLine: ChatLine = {
          id: crypto.randomUUID(),
          role: "assistant",
          text: reply,
        };
        setLines((prev) => [...prev, assistantLine]);
        void refreshMessages();

        if (isMorningSummary(reply)) {
          saveForToday("Morning London ops plan", reply);
          showAgentUi({
            title: "Morning plan saved",
            body: "Today's digest is in Summaries.",
            variant: "plan",
          });
        }

        setState("speaking");
        void tts.speak(reply);
        if (speakingTimer.current) window.clearTimeout(speakingTimer.current);
        speakingTimer.current = window.setTimeout(() => setState("idle"), 2500);
      } catch {
        setStatusText(null);
        const errorLine: ChatLine = {
          id: crypto.randomUUID(),
          role: "assistant",
          text: "Could not reach disruptron-api. Start the gateway and try again.",
        };
        setLines((prev) => [...prev, errorLine]);
        setState("idle");
      }
    },
    [client, clearAllPanels, handleStreamEvent, refreshMessages, saveForToday, setMessages, state, tts],
  );

  const setListening = useCallback((active: boolean) => {
    setState(active ? "listening" : "idle");
  }, []);

  const demoActivity = useCallback(() => {
    clearActivityDemo();
    if (speakingTimer.current) window.clearTimeout(speakingTimer.current);
    setState("thinking");
    setStatusText("Preview mode…");
    activityDemoTimer.current = window.setTimeout(() => {
      setStatusText(null);
      setState("speaking");
      activityDemoTimer.current = window.setTimeout(() => setState("idle"), 2000);
    }, 2200);
  }, [clearActivityDemo]);

  return {
    lines,
    state,
    statusText,
    agentMode,
    agentId,
    send,
    setListening,
    demoActivity,
    ttsEnabled: tts.enabled,
    toggleTts: tts.toggle,
  };
}
