import { motion } from "framer-motion";
import { ArrowRight, Rocket } from "lucide-react";
import { useNavigate } from "react-router-dom";

export function HeroSection() {
  const navigate = useNavigate();

  return (
    <section className="relative z-10 flex min-h-screen flex-col items-center justify-center px-6 py-24 text-center">
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, ease: "easeOut" }}
        className="max-w-5xl"
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.1, duration: 0.6 }}
          className="mb-6 inline-flex items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.03] px-4 py-2 text-sm text-text-secondary backdrop-blur-sm"
        >
          <span className="h-2 w-2 rounded-full bg-neon-green animate-pulse" />
          NVIDIA AI Hack for Impact — London 2026
        </motion.div>

        <h1 className="mb-6 font-heading text-6xl font-bold leading-tight tracking-tight text-text-primary md:text-8xl">
          <span className="bg-gradient-to-r from-electric-cyan via-nvidia to-neon-green bg-clip-text text-transparent">
            NV-Disruptron
          </span>
        </h1>

        <p className="mx-auto mb-10 max-w-2xl text-xl leading-relaxed text-text-secondary md:text-2xl">
          An optimistic, AI-powered mobility brain for London. Live transport intelligence,
          equity-aware routing, and agentic assistance — running on local NVIDIA GPUs.
        </p>

        <div className="flex flex-col items-center justify-center gap-4 sm:flex-row">
          <motion.button
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.98 }}
            onClick={() => navigate("/app")}
            className="inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-electric-cyan to-neon-green px-8 py-4 font-semibold text-canvas shadow-lg shadow-electric-cyan/20 transition-shadow hover:shadow-electric-cyan/40"
          >
            <Rocket size={20} />
            Launch Live Demo
            <ArrowRight size={20} />
          </motion.button>

          <motion.a
            href="https://github.com/Ryukijano/NV-Disruptron"
            target="_blank"
            rel="noopener noreferrer"
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.98 }}
            className="inline-flex items-center gap-2 rounded-full border border-white/[0.12] bg-white/[0.03] px-8 py-4 font-semibold text-text-primary backdrop-blur-sm transition-colors hover:bg-white/[0.06]"
          >
            <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M12 0C5.37 0 0 5.373 0 12c0 5.303 3.438 9.8 8.205 11.387.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61-.546-1.387-1.333-1.756-1.333-1.756-1.09-.745.083-.729.083-.729 1.205.085 1.84 1.237 1.84 1.237 1.07 1.835 2.807 1.305 3.492.998.108-.776.42-1.305.763-1.605-2.665-.305-5.467-1.334-5.467-5.93 0-1.31.468-2.382 1.235-3.22-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.3 1.23A11.51 11.51 0 0 1 12 5.803c1.02.005 2.047.138 3.006.404 2.29-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.838 1.233 1.91 1.233 3.22 0 4.61-2.807 5.625-5.48 5.92.43.372.814 1.103.814 2.222 0 1.606-.014 2.898-.014 3.293 0 .32.218.694.824.576C20.565 21.795 24 17.298 24 12c0-6.627-5.373-12-12-12Z" />
            </svg>
            View on GitHub
          </motion.a>
        </div>

        {/* Floating stat badges */}
        <div className="mt-14 flex flex-wrap items-center justify-center gap-4">
          {[
            { label: "Local LLM", value: "Nemotron 4B" },
            { label: "GPU memory", value: "128 GB" },
            { label: "Live cameras", value: "200+" },
          ].map((stat, index) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.6 + index * 0.15, duration: 0.5 }}
              whileHover={{ y: -4 }}
              className="rounded-xl border border-white/[0.06] bg-white/[0.03] px-5 py-3 backdrop-blur-sm"
            >
              <div className="text-lg font-bold text-electric-cyan">{stat.value}</div>
              <div className="text-xs uppercase tracking-wider text-text-secondary">{stat.label}</div>
            </motion.div>
          ))}
        </div>
      </motion.div>

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1, duration: 1 }}
        className="absolute bottom-10 left-1/2 -translate-x-1/2 text-text-secondary"
      >
        <div className="flex flex-col items-center gap-2 text-sm">
          <span>Scroll to explore</span>
          <motion.div
            animate={{ y: [0, 8, 0] }}
            transition={{ duration: 1.5, repeat: Infinity }}
            className="h-6 w-4 rounded-full border border-white/20 p-1"
          >
            <div className="h-1.5 w-full rounded-full bg-electric-cyan" />
          </motion.div>
        </div>
      </motion.div>
    </section>
  );
}
