import { motion } from "framer-motion";
import { ArrowRight, Play } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { GlowCard } from "./GlowCard";
import { SectionHeading } from "./SectionHeading";

export function DemoSection() {
  const navigate = useNavigate();

  return (
    <section className="relative z-10 px-6 py-24">
      <div className="mx-auto max-w-6xl">
        <SectionHeading
          eyebrow="Live demo"
          title="See the map, chat with the agent, explore TfL data"
        />

        <GlowCard glow="cyan" className="p-0">
          <div className="relative aspect-video w-full overflow-hidden rounded-2xl bg-surface">
            {/* Placeholder for the live app screenshot/video */}
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-4">
              <div className="rounded-2xl border border-white/[0.06] bg-white/[0.03] p-8 text-center backdrop-blur-md">
                <div className="mb-4 inline-flex rounded-full bg-electric-cyan/10 p-4 text-electric-cyan">
                  <Play size={32} />
                </div>
                <p className="text-lg font-medium text-text-primary">
                  Interactive demo placeholder
                </p>
                <p className="text-sm text-text-secondary">
                  Replace with a screenshot or screen recording in docs/screenshots/
                </p>
              </div>
            </div>

            {/* Gradient overlay at bottom */}
            <div className="absolute inset-x-0 bottom-0 h-32 bg-gradient-to-t from-canvas to-transparent" />
          </div>
        </GlowCard>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.2, duration: 0.6 }}
          className="mt-8 flex justify-center"
        >
          <button
            onClick={() => navigate("/app")}
            className="inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-electric-cyan to-neon-green px-8 py-4 font-semibold text-canvas shadow-lg shadow-electric-cyan/20 transition-shadow hover:shadow-electric-cyan/40"
          >
            Try it now
            <ArrowRight size={20} />
          </button>
        </motion.div>
      </div>
    </section>
  );
}
