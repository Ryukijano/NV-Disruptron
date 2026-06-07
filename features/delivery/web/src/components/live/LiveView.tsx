import { Volume2, VolumeX } from "@deemlol/next-icons";
import { Button } from "@nextui-org/react";
import { isDemoEnabled } from "@/config/demo";
import { useLiveSession } from "@/hooks/useLiveSession";
import { useVoiceInput } from "@/hooks/useVoiceInput";
import { useEffect, useState } from "react";
import { useApi } from "@/providers/ApiProvider";
import { AgentModeBadge } from "./AgentModeBadge";
import { AgentUiPopups } from "./AgentUiPopups";
import { ChatBox } from "./ChatBox";
import { LiveDemoControls } from "./LiveDemoControls";
import { VoiceControls } from "./VoiceControls";
import { TextInputBar } from "./TextInputBar";
import { OnboardingDialog } from "@/components/onboarding/OnboardingDialog";
import { GeminiVisualizer } from "./GeminiVisualizer";

export function LiveView() {
  const {
    lines,
    state,
    statusText,
    send,
    setListening,
    demoActivity,
    agentMode,
    agentId,
    ttsEnabled,
    toggleTts,
  } = useLiveSession();
  const client = useApi();
  const [onboardingOpen, setOnboardingOpen] = useState(false);
  const busy = state === "thinking" || state === "speaking";

  useEffect(() => {
    client
      .getPreferences()
      .then((p) => {
        if (!p.onboarding_complete) setOnboardingOpen(true);
      })
      .catch(() => {});
  }, [client]);

  const voice = useVoiceInput((text) => {
    setListening(false);
    send(text);
  });

  const onToggleMic = () => {
    if (voice.listening || voice.transcribing) {
      voice.stop();
      setListening(false);
    } else {
      setListening(true);
      voice.toggle();
    }
  };

  // Determine active visualizer state (e.g. override state to "listening" when mic is recording)
  const activeState = voice.listening || voice.transcribing ? "listening" : state;

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 px-4 py-3">
      {/* Top Controls Header */}
      <div className="flex items-center justify-between gap-2 shrink-0 bg-white/40 backdrop-blur-md px-3 py-1.5 rounded-2xl border border-white/60">
        <AgentModeBadge mode={agentMode} agentId={agentId} />
        <Button
          size="sm"
          variant="light"
          className="text-slate-500 min-w-0"
          onPress={toggleTts}
          startContent={
            ttsEnabled ? (
              <Volume2 size={16} strokeWidth={1.75} />
            ) : (
              <VolumeX size={16} strokeWidth={1.75} />
            )
          }
        >
          Voice out
        </Button>
      </div>

      {/* Expressive Neural Visualizer */}
      <div className="shrink-0 bg-white/60 backdrop-blur-md rounded-2xl border border-white/80 shadow-md">
        <GeminiVisualizer state={activeState} />
      </div>

      {/* Chat Container */}
      <div className="relative flex min-h-0 flex-1 flex-col">
        <ChatBox
          lines={lines}
          state={state}
          statusText={statusText}
          userListening={voice.listening}
          userTranscribing={voice.transcribing}
          userInterim={voice.interim}
        />
        <AgentUiPopups />
      </div>

      {isDemoEnabled() ? <LiveDemoControls onDemoActivity={demoActivity} /> : null}

      {/* Bottom Input Area */}
      <div className="flex items-center gap-2 shrink-0 bg-white/50 backdrop-blur-md p-2 rounded-2xl border border-white/60">
        <VoiceControls
          supported={voice.supported}
          listening={voice.listening || voice.transcribing}
          disabled={busy}
          onToggleMic={onToggleMic}
        />
        <TextInputBar disabled={busy || voice.listening || voice.transcribing} onSend={send} />
      </div>

      <OnboardingDialog open={onboardingOpen} onComplete={() => setOnboardingOpen(false)} />
    </div>
  );
}

