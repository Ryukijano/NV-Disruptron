import { AnimatePresence } from "framer-motion";
import { useEffect, useRef } from "react";
import type { ChatLine } from "@/hooks/useLiveSession";
import type { LiveSessionState } from "@/types/live";
import { AgentActivityIndicator } from "./AgentActivityIndicator";
import { UserListeningIndicator } from "./UserListeningIndicator";

type ChatBoxProps = {
  lines: ChatLine[];
  state: LiveSessionState;
  statusText?: string | null;
  userListening?: boolean;
  userTranscribing?: boolean;
  userInterim?: string;
};

export function ChatBox({
  lines,
  state,
  statusText,
  userListening,
  userTranscribing,
  userInterim,
}: ChatBoxProps) {
  const endRef = useRef<HTMLDivElement>(null);
  const agentActive = state === "thinking" || state === "speaking";
  const userActive = Boolean(userListening || userTranscribing);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [lines, agentActive, userActive, userInterim]);

  return (
    <div className="flex min-h-0 flex-1 flex-col glass-panel border border-white/5 shadow-lg overflow-hidden">
      <div className="border-b border-white/5 px-4 py-2 text-[11px] font-mono uppercase tracking-widest text-cyan-neon bg-[#0d1117]/40">
        // NEURAL LINK SESSION ACTIVE
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3 space-y-4 bg-transparent scrollbar-thin scrollbar-thumb-white/10">
        {lines.length === 0 && !agentActive && !userActive ? (
          <p className="text-xs font-mono text-muted text-center py-12">
            STANDBY FOR COGNITIVE COMMANDS. ASK ABOUT TfL ROUTING, STATION STATUS, ACCESSIBILITY OR EV CHARGER INFRASTRUCTURE.
          </p>
        ) : (
          lines.map((line) => (
            <div
              key={line.id}
              className={`flex ${line.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[85%] rounded-sm px-3.5 py-2 text-sm leading-relaxed border ${
                  line.role === "user"
                    ? "bg-[#0d1117]/80 border-cyan-neon/20 text-cyan-neon shadow-[0_0_10px_rgba(102,252,241,0.08)]"
                    : "bg-matrix border-emerald/20 text-emerald shadow-[0_0_10px_rgba(0,250,154,0.08)]"
                }`}
              >
                <span className="block text-[10px] font-mono uppercase tracking-wider opacity-60 mb-1">
                  {line.role === "user" ? "▶ NODE_OPERATOR" : "◀ SYS_NEURAL_CORE"}
                </span>
                <span className="font-sans text-text font-normal">{line.text}</span>
              </div>
            </div>
          ))
        )}
        <AnimatePresence>
          {userActive ? (
            <UserListeningIndicator
              key="user-listening"
              interim={userInterim}
              transcribing={userTranscribing}
            />
          ) : null}
          {state === "thinking" || state === "speaking" ? (
            <AgentActivityIndicator key={state} state={state} statusText={statusText} />
          ) : null}
        </AnimatePresence>
        <div ref={endRef} />
      </div>
    </div>
  );
}
