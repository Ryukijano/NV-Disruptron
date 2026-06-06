import { motion } from "framer-motion";

type UserListeningIndicatorProps = {
  interim?: string;
  transcribing?: boolean;
};

export function UserListeningIndicator({ interim, transcribing }: UserListeningIndicatorProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 4 }}
      className="flex justify-end"
    >
      <div className="flex max-w-[88%] items-center gap-2.5 rounded-xl border border-cyan-200 bg-cyan-50/90 px-3 py-2 shadow-sm">
        <div className="relative h-8 w-8 shrink-0">
          <motion.div
            className="absolute inset-0 rounded-full bg-cyan-400/30"
            animate={{ scale: [1, 1.35, 1], opacity: [0.55, 0.15, 0.55] }}
            transition={{ duration: 1.4, repeat: Infinity, ease: "easeInOut" }}
          />
          <motion.div
            className="absolute inset-1 rounded-full bg-gradient-to-br from-cyan-400 to-blue-500"
            animate={{ scale: transcribing ? [0.95, 1.05, 0.95] : [1, 1.08, 1] }}
            transition={{ duration: transcribing ? 0.8 : 1.2, repeat: Infinity, ease: "easeInOut" }}
          />
        </div>
        <div className="min-w-0">
          <span className="block text-[10px] uppercase tracking-wider text-cyan-700/80">
            {transcribing ? "Transcribing" : "You"}
          </span>
          <div className="flex items-center gap-2">
            <span className="text-sm text-slate-700">
              {interim || (transcribing ? "Processing audio…" : "Listening…")}
            </span>
            {!transcribing ? (
              <div className="flex h-4 items-end gap-0.5">
                {[0, 1, 2, 3].map((i) => (
                  <motion.span
                    key={i}
                    className="w-0.5 rounded-full bg-cyan-500"
                    animate={{ height: ["20%", "100%", "35%", "80%", "20%"] }}
                    transition={{
                      duration: 0.9,
                      repeat: Infinity,
                      ease: "easeInOut",
                      delay: i * 0.1,
                    }}
                  />
                ))}
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </motion.div>
  );
}
