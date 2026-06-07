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
    <div className="flex min-h-0 flex-1 flex-col rounded-2xl border-2 border-white/80 bg-white shadow-lg overflow-hidden ring-1 ring-slate-200/60">
      <div className="border-b border-slate-100 px-4 py-2 text-xs font-medium uppercase tracking-wide text-slate-500 bg-white">
        Live chat
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-3 py-3 space-y-3 bg-white">
        {lines.length === 0 && !agentActive && !userActive ? (
          <p className="text-sm text-slate-400 text-center py-8">
            Ask about London transport — tube, roads, charging, or ward impact.
          </p>
        ) : (
          lines.map((line) => (
            <div
              key={line.id}
              className={`flex ${line.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[88%] rounded-xl px-3 py-2 text-sm leading-relaxed border ${
                  line.role === "user"
                    ? "bg-cyan-50/80 border-cyan-100 text-slate-800"
                    : "bg-emerald-50/80 border-emerald-100 text-slate-800"
                }`}
              >
                <span className="block text-[10px] uppercase tracking-wider opacity-50 mb-0.5">
                  {line.role === "user" ? "You" : "Agent"}
                </span>
                {line.text}
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
