import { Activity, Heart, MapPin } from "lucide-react";
import { GlowCard } from "./GlowCard";
import { SectionHeading } from "./SectionHeading";

export function ProblemSection() {
  return (
    <section className="relative z-10 px-6 py-24">
      <div className="mx-auto max-w-6xl">
        <SectionHeading
          eyebrow="The challenge"
          title="London moves 8 million people every day. When it breaks, who pays the price?"
          subtitle="Disruptions hit vulnerable communities hardest. NV-Disruptron combines live TfL data, open demographics, and local AI to surface the right action at the right time."
        />

        <div className="grid gap-6 md:grid-cols-3">
          <GlowCard glow="amber" delay={0.1}>
            <div className="mb-4 inline-flex rounded-xl bg-amber-500/10 p-3 text-amber-400">
              <Activity size={28} />
            </div>
            <h3 className="mb-2 font-heading text-xl font-semibold text-text-primary">
              Real-time disruptions
            </h3>
            <p className="text-text-secondary">
              Tube, road, and accessibility alerts from live TfL feeds — no stale data.
            </p>
          </GlowCard>

          <GlowCard glow="purple" delay={0.2}>
            <div className="mb-4 inline-flex rounded-xl bg-purple-500/10 p-3 text-purple-400">
              <Heart size={28} />
            </div>
            <h3 className="mb-2 font-heading text-xl font-semibold text-text-primary">
              Equity-aware
            </h3>
            <p className="text-text-secondary">
              Impact scoring considers step-free access, deprivation indices, and mobility needs.
            </p>
          </GlowCard>

          <GlowCard glow="cyan" delay={0.3}>
            <div className="mb-4 inline-flex rounded-xl bg-cyan-400/10 p-3 text-cyan-400">
              <MapPin size={28} />
            </div>
            <h3 className="mb-2 font-heading text-xl font-semibold text-text-primary">
              Agentic assistance
            </h3>
            <p className="text-text-secondary">
              Ask questions, get route alternatives, and receive proactive alerts from a local AI agent.
            </p>
          </GlowCard>
        </div>
      </div>
    </section>
  );
}
