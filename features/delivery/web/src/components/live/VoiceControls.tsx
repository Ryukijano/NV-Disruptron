import { Mic, MicOff } from "@deemlol/next-icons";
import { motion } from "framer-motion";

type VoiceControlsProps = {
  supported: boolean;
  listening: boolean;
  disabled?: boolean;
  onToggleMic: () => void;
};

export function VoiceControls({ supported, listening, disabled, onToggleMic }: VoiceControlsProps) {
  const Icon = listening ? MicOff : Mic;

  return (
    <motion.button
      type="button"
      disabled={!supported || disabled}
      onClick={onToggleMic}
      whileTap={{ scale: 0.94 }}
      className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-full border-2 transition-all disabled:opacity-40 ${
        listening
          ? "border-cyan-400 bg-white text-cyan-600 shadow-md"
          : "border-emerald-300 bg-white text-emerald-600 shadow-sm"
      }`}
      aria-label={listening ? "Stop listening" : "Voice input"}
    >
      <Icon size={20} strokeWidth={1.75} color="currentColor" />
    </motion.button>
  );
}
