import { isDemoEnabled } from "@/config/demo";
import { useLiveSession } from "@/hooks/useLiveSession";
import { useVoiceInput } from "@/hooks/useVoiceInput";
import { AgentUiPopups } from "./AgentUiPopups";
import { ChatBox } from "./ChatBox";
import { LiveDemoControls } from "./LiveDemoControls";
import { TextInputBar } from "./TextInputBar";
import { VoiceControls } from "./VoiceControls";

export function LiveView() {
  const { lines, state, send, setListening, demoActivity } = useLiveSession();
  const busy = state === "thinking" || state === "speaking";

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

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 px-4 py-3">
      <div className="relative flex min-h-0 flex-1 flex-col">
        <ChatBox
          lines={lines}
          state={state}
          userListening={voice.listening}
          userTranscribing={voice.transcribing}
          userInterim={voice.interim}
        />
        <AgentUiPopups />
      </div>
      {isDemoEnabled() ? <LiveDemoControls onDemoActivity={demoActivity} /> : null}
      <div className="flex items-center gap-2 shrink-0">
        <VoiceControls
          supported={voice.supported}
          listening={voice.listening || voice.transcribing}
          disabled={busy}
          onToggleMic={onToggleMic}
        />
        <div className="flex-1 min-w-0">
          <TextInputBar disabled={busy || voice.listening || voice.transcribing} onSend={send} />
        </div>
      </div>
    </div>
  );
}
