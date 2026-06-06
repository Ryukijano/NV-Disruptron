import { showAgentUi } from "@/api/agentUi";
import { AGENT_UI_SAMPLES } from "@/api/agentUiSamples";

type LiveDemoControlsProps = {
  onDemoActivity: () => void;
};

export function LiveDemoControls({ onDemoActivity }: LiveDemoControlsProps) {
  return (
    <div className="flex shrink-0 flex-wrap gap-1.5">
      <button
        type="button"
        onClick={onDemoActivity}
        className="rounded-lg border border-white/80 bg-white/90 px-2.5 py-1 text-xs text-slate-500 hover:text-slate-700"
      >
        Preview thinking
      </button>
      {(
        [
          ["Disruptions", AGENT_UI_SAMPLES.disruptions],
          ["Route", AGENT_UI_SAMPLES.route],
          ["Morning", AGENT_UI_SAMPLES.morning],
        ] as const
      ).map(([label, sample]) => (
        <button
          key={label}
          type="button"
          onClick={() => showAgentUi(sample)}
          className="rounded-lg border border-white/80 bg-white/90 px-2.5 py-1 text-xs text-slate-500 hover:text-slate-700"
        >
          Preview {label}
        </button>
      ))}
    </div>
  );
}
