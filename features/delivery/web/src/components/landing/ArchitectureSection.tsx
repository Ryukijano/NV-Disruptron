import { motion } from "framer-motion";
import { Brain, Database, Eye, MessageSquare, Route, Shield } from "lucide-react";
import { GlowCard } from "./GlowCard";
import { SectionHeading } from "./SectionHeading";

const steps = [
  { icon: MessageSquare, label: "User asks", color: "text-electric-cyan" },
  { icon: Brain, label: "Nemotron plans", color: "text-nvidia" },
  { icon: Database, label: "Live TfL data", color: "text-electric-cyan" },
  { icon: Eye, label: "LocateAnything", color: "text-purple-400" },
  { icon: Route, label: "cuOpt routing", color: "text-amber-400" },
  { icon: Shield, label: "Equity scoring", color: "text-neon-green" },
];

export function ArchitectureSection() {
  return (
    <section className="relative z-10 px-6 py-24">
      <div className="mx-auto max-w-6xl">
        <SectionHeading
          eyebrow="Architecture"
          title="Agent loop: from question to action"
        />

        <div className="flex flex-wrap items-center justify-center gap-4 md:gap-8">
          {steps.map((step, index) => (
            <motion.div
              key={step.label}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: index * 0.1, duration: 0.5 }}
              className="flex items-center gap-4"
            >
              <GlowCard glow={index % 2 === 0 ? "cyan" : "green"} className="min-w-[140px]">
                <div className={`mb-3 ${step.color}`}>
                  <step.icon size={28} />
                </div>
                <p className="font-heading text-sm font-semibold text-text-primary">{step.label}</p>
              </GlowCard>
              {index < steps.length - 1 && (
                <div className="hidden text-text-secondary md:block">→</div>
              )}
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
