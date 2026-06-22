import { BookOpen, ExternalLink } from "lucide-react";
import { GlowCard } from "./GlowCard";
import { SectionHeading } from "./SectionHeading";

const HuggingFaceIcon = () => (
  <svg className="h-7 w-7" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2Zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8Z" />
    <circle cx="9" cy="10" r="1.5" />
    <circle cx="15" cy="10" r="1.5" />
    <path d="M8 14c1 2 3 2 4 2s3 0 4-2" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
  </svg>
);

const links = [
  {
    title: "Hugging Face Space",
    description: "Try the live backend demo running Nemotron-3-Nano-4B.",
    href: "https://huggingface.co/spaces/Ryukijano/gyanateet-portfolio",
    icon: HuggingFaceIcon,
    glow: "amber" as const,
  },
  {
    title: "NVIDIA Developer Blog",
    description: "Read the official write-up on the hackathon project.",
    href: "https://developer.nvidia.com/blog",
    icon: BookOpen,
    glow: "green" as const,
  },
  {
    title: "GitHub Repository",
    description: "Forks, issues, and contributions welcome.",
    href: "https://github.com/Ryukijano/NV-Disruptron",
    icon: ExternalLink,
    glow: "cyan" as const,
  },
];

export function CommunitySection() {
  return (
    <section className="relative z-10 px-6 py-24">
      <div className="mx-auto max-w-6xl">
        <SectionHeading
          eyebrow="Community"
          title="Share, fork, and build on it"
        />

        <div className="grid gap-6 md:grid-cols-3">
          {links.map((link, index) => (
            <GlowCard key={link.title} glow={link.glow} delay={index * 0.1} className="h-full">
              <a
                href={link.href}
                target="_blank"
                rel="noopener noreferrer"
                className="flex h-full flex-col"
              >
                <div className="mb-4 inline-flex rounded-xl bg-white/[0.06] p-3 text-electric-cyan">
                  <link.icon size={28} />
                </div>
                <h3 className="mb-2 font-heading text-xl font-semibold text-text-primary">
                  {link.title}
                </h3>
                <p className="text-text-secondary">{link.description}</p>
              </a>
            </GlowCard>
          ))}
        </div>
      </div>
    </section>
  );
}
