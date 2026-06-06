import type { AgentUiPayload } from "./types";

export const AGENT_UI_SAMPLES: Record<string, AgentUiPayload> = {
  disruptions: {
    title: "Live disruption snapshot",
    body: "Central London network — updated just now",
    variant: "alert",
    blocks: [
      {
        type: "metrics",
        items: [
          { label: "Lines delayed", value: "4", delta: "+2", tone: "down" },
          { label: "Avg delay", value: "11m", delta: "-3m", tone: "up" },
          { label: "Road closures", value: "7", tone: "neutral" },
        ],
      },
      {
        type: "bar-chart",
        title: "Passenger impact by line",
        unit: "k journeys/hr",
        items: [
          { label: "Central", value: 42, color: "#f59e0b" },
          { label: "District", value: 28, color: "#0891b2" },
          { label: "Northern", value: 19, color: "#10b981" },
          { label: "Jubilee", value: 12, color: "#6366f1" },
        ],
      },
      {
        type: "status-grid",
        items: [
          { line: "Central", status: "minor", detail: "Eastbound delays Liverpool St → Stratford" },
          { line: "District", status: "good", detail: "Good service" },
          { line: "Northern", status: "severe", detail: "Part suspension Bank branch" },
          { line: "Elizabeth", status: "good", detail: "Good service" },
        ],
      },
    ],
  },
  route: {
    title: "Recommended route",
    body: "Fastest option avoiding ULEZ surcharge",
    variant: "plan",
    blocks: [
      {
        type: "route-card",
        route: {
          from: "Shoreditch High St",
          to: "City of London Ward",
          duration: "18 min",
          mode: "Tube + walk",
          charge: "£0 ULEZ",
          delay: "+4 min vs usual",
        },
      },
      {
        type: "timeline",
        items: [
          { time: "08:12", title: "Walk to Liverpool Street", status: "ok" },
          { time: "08:18", title: "Central line → Bank", status: "warn", detail: "Minor delay" },
          { time: "08:31", title: "Arrive Leadenhall", status: "ok" },
        ],
      },
    ],
  },
  morning: {
    title: "Morning ops digest",
    body: "Priority items for today's ward briefing",
    variant: "plan",
    blocks: [
      {
        type: "metrics",
        items: [
          { label: "Active incidents", value: "12", tone: "neutral" },
          { label: "Resolved overnight", value: "8", delta: "+3", tone: "up" },
          { label: "Ward alerts", value: "3", tone: "down" },
        ],
      },
      {
        type: "timeline",
        items: [
          { time: "06:00", title: "Night tube ended — standard service", status: "ok" },
          { time: "07:15", title: "Bishopsgate lane closure", status: "warn", detail: "Until 18:00" },
          { time: "09:00", title: "Council transport committee", status: "ok", detail: "Agenda item: ULEZ" },
        ],
      },
    ],
  },
};
