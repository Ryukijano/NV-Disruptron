import { motion } from "framer-motion";
import type { LiveSessionState } from "@/types/live";

type AgentActivityIndicatorProps = {
  state: Extract<LiveSessionState, "thinking" | "speaking">;
};

const copy = {
  thinking: "Thinking",
  speaking: "Responding",
} as const;

function WaveBars() {
  return (
    <div className="flex h-4 items-end gap-0.5">
      {[0, 1, 2, 3, 4].map((i) => (
        <motion.span
          key={i}
          className="w-0.5 rounded-full bg-gradient-to-t from-cyan-500 to-emerald-400"
          animate={{ height: ["30%", "100%", "45%", "85%", "30%"] }}
          transition={{
            duration: 1.1,
            repeat: Infinity,
            ease: "easeInOut",
            delay: i * 0.12,
          }}
        />
      ))}
    </div>
  );
}

function NeuralOrb({ active }: { active: boolean }) {
  return (
    <div className="relative h-9 w-9 shrink-0">
      <motion.div
        className="absolute inset-0 rounded-full opacity-70 blur-md"
        style={{
          background:
            "conic-gradient(from 0deg, #22d3ee, #34d399, #3b82f6, #a78bfa, #22d3ee)",
        }}
        animate={{ rotate: 360, scale: active ? [1, 1.08, 1] : 1 }}
        transition={{
          rotate: { duration: 4, repeat: Infinity, ease: "linear" },
          scale: { duration: 2.2, repeat: Infinity, ease: "easeInOut" },
        }}
      />
      <motion.div
        className="absolute inset-1 rounded-full"
        style={{
          background: "radial-gradient(circle at 35% 35%, #ffffff 0%, #22d3ee 35%, #10b981 70%, #3b82f6 100%)",
        }}
        animate={{ scale: active ? [0.92, 1, 0.92] : 1 }}
        transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="absolute inset-2 rounded-full bg-white/25 backdrop-blur-[1px]"
        animate={{ opacity: [0.35, 0.65, 0.35] }}
        transition={{ duration: 1.8, repeat: Infinity, ease: "easeInOut" }}
      />
    </div>
  );
}

export function AgentActivityIndicator({ state }: AgentActivityIndicatorProps) {
  const label = copy[state];

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 4 }}
      className="flex justify-start"
    >
      <div className="flex max-w-[88%] items-center gap-3 rounded-xl border border-emerald-100 bg-emerald-50/60 px-3 py-2.5">
        <NeuralOrb active={state === "thinking"} />
        <div className="min-w-0">
          <span className="block text-[10px] uppercase tracking-wider text-emerald-700/70 mb-0.5">
            Agent
          </span>
          <div className="flex items-center gap-2">
            <motion.span
              className="bg-gradient-to-r from-cyan-600 via-emerald-600 to-blue-600 bg-clip-text text-sm font-medium text-transparent"
              style={{ backgroundSize: "200% 100%" }}
              animate={{ backgroundPosition: ["0% 50%", "100% 50%", "0% 50%"] }}
              transition={{ duration: 2.4, repeat: Infinity, ease: "linear" }}
            >
              {label}
            </motion.span>
            {state === "thinking" ? (
              <motion.span
                className="flex gap-1"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
              >
                {[0, 1, 2].map((i) => (
                  <motion.span
                    key={i}
                    className="h-1 w-1 rounded-full bg-emerald-500"
                    animate={{ opacity: [0.25, 1, 0.25], y: [0, -2, 0] }}
                    transition={{
                      duration: 1.2,
                      repeat: Infinity,
                      ease: "easeInOut",
                      delay: i * 0.2,
                    }}
                  />
                ))}
              </motion.span>
            ) : (
              <WaveBars />
            )}
          </div>
        </div>
      </div>
    </motion.div>
  );
}
