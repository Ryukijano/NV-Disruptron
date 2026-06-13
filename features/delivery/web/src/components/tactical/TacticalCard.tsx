import { motion, AnimatePresence } from "framer-motion";
import type { TacticalPanelKind } from "@/providers/TacticalPanelProvider";

// Softer, WCAG-friendly accent colors for dark mode — easy on the eyes
const KIND_COLORS: Record<TacticalPanelKind, string> = {
  video: "#818CF8",    // soft indigo
  live: "#F59E0B",      // warm amber
  audio: "#F472B6",     // soft rose
  hazard: "#EF4444",    // standard red
  station: "#06B6D4",   // teal
  route: "#10B981",     // emerald
  disruption: "#F97316", // warm orange
  detection: "#22D3EE", // cyan — camera detection popup
};

const KIND_LABELS: Record<TacticalPanelKind, string> = {
  video: "Vision Analysis",
  live: "Live TfL Feed",
  audio: "Acoustic Analysis",
  hazard: "Hazard Detection",
  station: "Station Access",
  route: "Route Planning",
  disruption: "Live Disruptions",
  detection: "Camera Detection",
};

export function TacticalCard({
  kind,
  title,
  children,
}: {
  kind: TacticalPanelKind;
  title: string;
  children?: React.ReactNode;
}) {
  const accent = KIND_COLORS[kind];

  return (
    <motion.div
      key={kind}
      initial={{ opacity: 0, x: 24, scale: 0.97 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, x: 20, scale: 0.97 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      className="glass-panel border border-white/8 shadow-xl flex flex-col p-4 overflow-y-auto rounded-xl backdrop-blur-xl bg-[#121214]/80 max-h-[340px]"
      style={{ borderLeft: `3px solid ${accent}` }}
    >
      {/* Clean header bar */}
      <div className="flex items-center justify-between border-b border-white/6 pb-2.5 mb-2.5">
        <span className="text-[11px] font-medium tracking-wide flex items-center gap-2" style={{ color: accent }}>
          <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: accent }} />
          {KIND_LABELS[kind]}
        </span>
        <span className="text-[10px] text-muted/70 tracking-normal">
          {title}
        </span>
      </div>

      <div>
        {children}
      </div>
    </motion.div>
  );
}

export function TacticalCardStack({ panels }: { panels: { kind: TacticalPanelKind; title: string; children?: React.ReactNode }[] }) {
  return (
    <AnimatePresence>
      {panels.map((p) => (
        <TacticalCard key={p.kind} kind={p.kind} title={p.title}>
          {p.children}
        </TacticalCard>
      ))}
    </AnimatePresence>
  );
}
