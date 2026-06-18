import { motion } from "framer-motion";
import type { ReactNode } from "react";

interface GlowCardProps {
  children: ReactNode;
  glow?: "cyan" | "green" | "purple" | "amber";
  className?: string;
  delay?: number;
}

const glowColors = {
  cyan: "from-cyan-400/30 to-cyan-400/0",
  green: "from-nvidia/30 to-nvidia/0",
  purple: "from-purple-500/30 to-purple-500/0",
  amber: "from-amber-500/30 to-amber-500/0",
};

export function GlowCard({ children, glow = "cyan", className = "", delay = 0 }: GlowCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.6, delay, ease: "easeOut" }}
      className={`group relative overflow-hidden rounded-2xl border border-white/[0.06] bg-white/[0.03] backdrop-blur-md ${className}`}
    >
      {/* Ambient glow halo */}
      <div
        className={`absolute -inset-px rounded-2xl bg-gradient-radial ${glowColors[glow]} opacity-0 blur-2xl transition-opacity duration-500 group-hover:opacity-100`}
        aria-hidden="true"
      />
      <div className="relative z-10 h-full p-6">{children}</div>
    </motion.div>
  );
}
