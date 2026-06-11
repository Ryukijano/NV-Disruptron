import { motion } from "framer-motion";
import type { LiveSessionState } from "@/types/live";

type GeminiVisualizerProps = {
  state: LiveSessionState;
};

export function GeminiVisualizer({ state }: GeminiVisualizerProps) {
  // Define dynamic gradients based on the agent's state
  const getGradientClass = () => {
    switch (state) {
      case "listening":
        return "from-cyan-400 via-blue-500 to-indigo-500";
      case "thinking":
        return "from-purple-500 via-pink-500 to-amber-400 animate-pulse";
      case "speaking":
        return "from-emerald-400 via-cyan-500 to-blue-500";
      case "idle":
      default:
        return "from-blue-500 via-cyan-400 to-emerald-400";
    }
  };

  return (
    <div className="relative flex flex-col items-center justify-center py-6 px-4">
      {/* Decorative ambient background blur */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <motion.div
          layout
          className={`h-40 w-40 rounded-full bg-gradient-to-tr ${getGradientClass()} opacity-25 blur-3xl`}
          animate={{
            scale: state === "listening" ? [1, 1.25, 1] : state === "thinking" ? [1, 0.9, 1.1, 1] : state === "speaking" ? [1, 1.15, 1] : [1, 1.05, 1],
          }}
          transition={{
            duration: state === "thinking" ? 1.5 : 3,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        />
      </div>

      {/* Main expressive orb or wave */}
      <div className="relative z-10 flex h-24 items-center justify-center w-full">
        {state === "idle" && (
          <motion.div
            key="idle"
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.8, opacity: 0 }}
            className="relative flex items-center justify-center"
          >
            {/* Pulsing outer ring */}
            <motion.div
              className="absolute h-16 w-16 rounded-full border-2 border-cyan-400/30"
              animate={{ scale: [1, 1.4, 1], opacity: [0.6, 0.1, 0.6] }}
              transition={{ duration: 2.5, repeat: Infinity, ease: "easeInOut" }}
            />
            {/* Morphing inner orb */}
            <motion.div
              className="h-12 w-12 bg-gradient-to-tr from-cyan-400 via-blue-500 to-emerald-400 shadow-[0_0_20px_rgba(34,211,238,0.4)]"
              animate={{
                borderRadius: [
                  "42% 58% 70% 30% / 45% 45% 55% 55%",
                  "70% 30% 52% 48% / 60% 40% 60% 40%",
                  "42% 58% 70% 30% / 45% 45% 55% 55%",
                ],
                rotate: 360,
              }}
              transition={{
                borderRadius: { duration: 6, repeat: Infinity, ease: "easeInOut" },
                rotate: { duration: 12, repeat: Infinity, ease: "linear" },
              }}
            />
          </motion.div>
        )}

        {state === "listening" && (
          <motion.div
            key="listening"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="flex items-center gap-1.5 h-12"
          >
            {/* Gemini Live style voice listening waves */}
            {[...Array(9)].map((_, i) => {
              // Delay wave animation for standard sound wave effect
              const delay = i * 0.08;
              const baseHeight = [16, 28, 48, 60, 48, 28, 16][i % 7];
              return (
                <motion.span
                  key={i}
                  className="w-1.5 rounded-full bg-gradient-to-t from-blue-500 via-cyan-400 to-indigo-500 shadow-[0_0_8px_rgba(6,182,212,0.4)]"
                  animate={{
                    height: [
                      `${baseHeight * 0.3}px`,
                      `${baseHeight * 1.1}px`,
                      `${baseHeight * 0.5}px`,
                      `${baseHeight * 0.9}px`,
                      `${baseHeight * 0.3}px`,
                    ],
                  }}
                  transition={{
                    duration: 0.85,
                    repeat: Infinity,
                    ease: "easeInOut",
                    delay: delay,
                  }}
                />
              );
            })}
          </motion.div>
        )}

        {state === "thinking" && (
          <motion.div
            key="thinking"
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.8, opacity: 0 }}
            className="relative h-16 w-16"
          >
            {/* Spinning colorful vortex */}
            <motion.div
              className="absolute inset-0 rounded-full"
              style={{
                background: "conic-gradient(from 0deg, #a78bfa, #ec4899, #f59e0b, #3b82f6, #a78bfa)",
                filter: "blur(4px)",
              }}
              animate={{ rotate: 360 }}
              transition={{ duration: 1.8, repeat: Infinity, ease: "linear" }}
            />
            {/* Floating particle/core effect */}
            <motion.div
              className="absolute inset-2 rounded-full bg-white flex items-center justify-center shadow-inner"
              animate={{ scale: [0.9, 1.05, 0.9] }}
              transition={{ duration: 1.2, repeat: Infinity, ease: "easeInOut" }}
            >
              <div className="h-6 w-6 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 animate-pulse" />
            </motion.div>
          </motion.div>
        )}

        {state === "speaking" && (
          <motion.div
            key="speaking"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="flex items-center justify-center w-full max-w-xs px-4"
          >
            {/* CSS-animated speaking wave bars */}
            <div className="flex items-center gap-1 h-12">
              {[...Array(7)].map((_, i) => (
                <motion.span
                  key={i}
                  className="w-1.5 rounded-full bg-gradient-to-t from-emerald-400 via-cyan-400 to-blue-500 shadow-[0_0_8px_rgba(34,211,238,0.4)]"
                  animate={{
                    height: ["12px", "32px", "18px", "40px", "14px"],
                  }}
                  transition={{
                    duration: 0.9,
                    repeat: Infinity,
                    ease: "easeInOut",
                    delay: i * 0.1,
                  }}
                />
              ))}
            </div>
          </motion.div>
        )}
      </div>

      {/* State label */}
      <span className="mt-3 text-xs uppercase tracking-widest font-semibold bg-gradient-to-r from-slate-400 via-slate-600 to-slate-400 bg-clip-text text-transparent">
        {state === "idle" && "NV-Disruptron Standby"}
        {state === "listening" && "Listening to user..."}
        {state === "thinking" && "Computing London Transit Grid..."}
        {state === "speaking" && "Broadcasting response..."}
      </span>
    </div>
  );
}
