import type { AgentEvent } from "./types";

export const DEMO_ALERTS: Array<{ title: string; body: string }> = [
  {
    title: "Central Line delay",
    body: "Minor delays eastbound between Liverpool Street and Stratford.",
  },
  {
    title: "Road closure — Bishopsgate",
    body: "Lane restrictions near Leadenhall Street until 18:00.",
  },
  {
    title: "District Line update",
    body: "Good service restored on all branches.",
  },
  {
    title: "ULEZ boundary check",
    body: "Your route crosses the charging zone — £12.50 daily charge applies.",
  },
  {
    title: "Bus diversion — Route 15",
    body: "Diverted via London Bridge due to roadworks on Cannon Street.",
  },
  {
    title: "Thameslink advisory",
    body: "Reduced frequency between Blackfriars and St Pancras this evening.",
  },
];

export function startDevNotificationSimulation(
  onEvent: (event: AgentEvent) => void,
): () => void {
  let index = 0;

  const emit = () => {
    const sample = DEMO_ALERTS[index % DEMO_ALERTS.length];
    index += 1;
    onEvent({
      id: crypto.randomUUID(),
      title: sample.title,
      body: sample.body,
      timestamp: Date.now(),
    });
  };

  const first = window.setTimeout(emit, 2500);
  const interval = window.setInterval(emit, 14000);

  return () => {
    window.clearTimeout(first);
    window.clearInterval(interval);
  };
}
