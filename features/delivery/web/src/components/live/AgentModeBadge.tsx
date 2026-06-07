type AgentModeBadgeProps = {
  mode: string | null;
  agentId: string | null;
};

const labels: Record<string, string> = {
  interactive: "Interactive",
  autonomous: "Autonomous",
  digest: "Morning digest",
};

export function AgentModeBadge({ mode, agentId }: AgentModeBadgeProps) {
  if (!mode) return null;
  const label = labels[mode] ?? mode;
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full border border-cyan-200/80 bg-white/90 px-2.5 py-0.5 text-[10px] font-medium uppercase tracking-wider text-cyan-700 shadow-sm"
      title={agentId ? `Agent: ${agentId}` : undefined}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
      {label}
    </span>
  );
}
