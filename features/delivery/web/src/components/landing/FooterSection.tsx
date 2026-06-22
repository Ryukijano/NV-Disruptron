export function FooterSection() {
  return (
    <footer className="relative z-10 border-t border-white/[0.06] bg-surface/50 px-6 py-16 backdrop-blur-sm">
      <div className="mx-auto max-w-6xl">
        <div className="flex flex-col items-center justify-between gap-6 md:flex-row">
          <div className="text-center md:text-left">
            <h3 className="font-heading text-2xl font-bold text-text-primary">
              <span className="bg-gradient-to-r from-electric-cyan to-neon-green bg-clip-text text-transparent">
                NV-Disruptron
              </span>
            </h3>
            <p className="mt-1 text-sm text-text-secondary">
              Optimistic cyberpunk mobility intelligence for London.
            </p>
          </div>

          <div className="flex items-center gap-6 text-sm text-text-secondary">
            <a
              href="https://github.com/Ryukijano/NV-Disruptron"
              target="_blank"
              rel="noopener noreferrer"
              className="transition-colors hover:text-electric-cyan"
            >
              GitHub
            </a>
            <a
              href="https://huggingface.co/spaces/Ryukijano/gyanateet-portfolio"
              target="_blank"
              rel="noopener noreferrer"
              className="transition-colors hover:text-electric-cyan"
            >
              Hugging Face
            </a>
            <a
              href="https://www.nvidia.com/en-us/events/hackathons/"
              target="_blank"
              rel="noopener noreferrer"
              className="transition-colors hover:text-electric-cyan"
            >
              NVIDIA Hack for Impact
            </a>
          </div>
        </div>

        <div className="mt-10 text-center text-xs text-text-secondary/60">
          Built for the NVIDIA Hack for Impact — London, Jun 5–7 2026.
        </div>
      </div>
    </footer>
  );
}
