export type SttMode = "api" | "browser" | "auto";

export function getSttMode(): SttMode {
  const raw = import.meta.env.VITE_STT_MODE?.trim().toLowerCase();
  if (raw === "api" || raw === "browser" || raw === "auto") return raw;
  return "auto";
}

export function prefersApiTranscription(): boolean {
  const mode = getSttMode();
  return mode === "api" || mode === "auto";
}
