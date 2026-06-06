export function isDemoEnabled(): boolean {
  return import.meta.env.VITE_ENABLE_DEMO !== "false";
}
