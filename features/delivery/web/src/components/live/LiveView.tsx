import { useLiveSession } from "@/hooks/useLiveSession";
import { useVoiceInput } from "@/hooks/useVoiceInput";
import { ChatBox } from "./ChatBox";
import { TextInputBar } from "./TextInputBar";
import { VoiceControls } from "./VoiceControls";

export function LiveView() {
  const { lines, state, send, setListening } = useLiveSession();
  const busy = state === "thinking" || state === "speaking";

  const voice = useVoiceInput((text) => {
    setListening(false);
    send(text);
  });

  const onToggleMic = () => {
    if (voice.listening) {
      voice.stop();
      setListening(false);
    } else {
      setListening(true);
      voice.toggle();
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 px-4 py-3">
      <ChatBox lines={lines} thinking={state === "thinking"} />
      {voice.interim ? (
        <p className="text-xs text-slate-500 italic shrink-0 px-1">Hearing: “{voice.interim}”</p>
      ) : null}
      <div className="flex items-center gap-2 shrink-0">
        <VoiceControls
          supported={voice.supported}
          listening={voice.listening}
          disabled={busy}
          onToggleMic={onToggleMic}
        />
        <div className="flex-1 min-w-0">
          <TextInputBar disabled={busy || voice.listening} onSend={send} />
        </div>
      </div>
    </div>
  );
}
