import { useCallback, useRef, useState } from "react";
import { getApiClient } from "@/api/client";

const TTS_KEY = "disruptron-tts-enabled";

export function isTtsEnabled(): boolean {
  return localStorage.getItem(TTS_KEY) === "1";
}

export function setTtsEnabled(on: boolean): void {
  localStorage.setItem(TTS_KEY, on ? "1" : "0");
}

export function useTtsPlayback() {
  const [enabled, setEnabled] = useState(isTtsEnabled());
  const [speaking, setSpeaking] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const toggle = useCallback(() => {
    setEnabled((prev) => {
      const next = !prev;
      setTtsEnabled(next);
      return next;
    });
  }, []);

  const speak = useCallback(
    async (text: string) => {
      if (!enabled || !text.trim()) return;
      try {
        setSpeaking(true);
        const blob = await getApiClient().synthesizeSpeech(text);
        if (audioRef.current) {
          URL.revokeObjectURL(audioRef.current.src);
        }
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        audioRef.current = audio;
        audio.onended = () => {
          setSpeaking(false);
          URL.revokeObjectURL(url);
        };
        audio.onerror = () => setSpeaking(false);
        await audio.play();
      } catch {
        setSpeaking(false);
      }
    },
    [enabled],
  );

  const stop = useCallback(() => {
    audioRef.current?.pause();
    setSpeaking(false);
  }, []);

  return { enabled, speaking, toggle, speak, stop };
}
