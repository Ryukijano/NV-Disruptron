import { GlowCard } from "./GlowCard";
import { SectionHeading } from "./SectionHeading";

const techStack = [
  {
    name: "Nemotron",
    tag: "Local LLM",
    description: "NVIDIA Nemotron-3-Nano-4B runs locally on the HF Space A10G for tool-calling chat.",
    glow: "green" as const,
  },
  {
    name: "RAPIDS",
    tag: "GPU acceleration",
    description: "cuDF, cuSpatial, and cuGraph power the geospatial analytics pipeline on DGX Spark.",
    glow: "cyan" as const,
  },
  {
    name: "cuOpt",
    tag: "Routing",
    description: "GPU-accelerated hazard-response routing and alternative journey planning.",
    glow: "amber" as const,
  },
  {
    name: "LocateAnything",
    tag: "Vision",
    description: "On-demand visual hazard detection from live TfL JamCams on DGX Spark.",
    glow: "purple" as const,
  },
  {
    name: "NeMo Toolkit",
    tag: "Agent orchestration",
    description: "Agent workflows and guardrails keep the assistant factual and safe.",
    glow: "cyan" as const,
  },
  {
    name: "Riva",
    tag: "Voice",
    description: "Optional ASR/TTS voice mode for hands-free interaction with the agent.",
    glow: "green" as const,
  },
];

export function TechStackSection() {
  return (
    <section className="relative z-10 px-6 py-24">
      <div className="mx-auto max-w-6xl">
        <SectionHeading
          eyebrow="Built with NVIDIA"
          title="A full-stack NVIDIA AI stack, from GPU to browser"
        />

        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {techStack.map((tech, index) => (
            <GlowCard key={tech.name} glow={tech.glow} delay={index * 0.1}>
              <div className="mb-3 flex items-center justify-between">
                <h3 className="font-heading text-2xl font-bold text-text-primary">{tech.name}</h3>
                <span className="rounded-full bg-white/[0.06] px-3 py-1 text-xs font-medium text-electric-cyan">
                  {tech.tag}
                </span>
              </div>
              <p className="text-text-secondary">{tech.description}</p>
            </GlowCard>
          ))}
        </div>
      </div>
    </section>
  );
}
