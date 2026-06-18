import { Cpu, MemoryStick, Server } from "lucide-react";
import { GlowCard } from "./GlowCard";
import { SectionHeading } from "./SectionHeading";

const specs = [
  {
    icon: Server,
    title: "DGX Spark",
    detail: "NVIDIA GB10 Grace Blackwell Superchip",
    glow: "green" as const,
  },
  {
    icon: MemoryStick,
    title: "Unified memory",
    detail: "128 GB shared CPU/GPU memory",
    glow: "cyan" as const,
  },
  {
    icon: Cpu,
    title: "Hugging Face Space",
    detail: "A10G GPU · 24 GB VRAM · 48 GB RAM · 12 vCPU cores",
    glow: "purple" as const,
  },
];

export function HardwareSection() {
  return (
    <section className="relative z-10 px-6 py-24">
      <div className="mx-auto max-w-6xl">
        <SectionHeading
          eyebrow="Hardware"
          title="Built for real hardware, not just slides"
        />

        <div className="grid gap-6 md:grid-cols-3">
          {specs.map((spec, index) => (
            <GlowCard key={spec.title} glow={spec.glow} delay={index * 0.1}>
              <div className="mb-4 inline-flex rounded-xl bg-white/[0.06] p-3 text-electric-cyan">
                <spec.icon size={28} />
              </div>
              <h3 className="mb-1 font-heading text-xl font-semibold text-text-primary">
                {spec.title}
              </h3>
              <p className="text-text-secondary">{spec.detail}</p>
            </GlowCard>
          ))}
        </div>
      </div>
    </section>
  );
}
