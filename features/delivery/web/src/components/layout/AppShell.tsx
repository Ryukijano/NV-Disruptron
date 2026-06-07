import { Bell } from "@deemlol/next-icons";
import { Tab, Tabs } from "@nextui-org/react";
import { useEffect, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { NotificationSimulator } from "@/components/notifications/NotificationSimulator";
import { NotificationToasts } from "@/components/notifications/NotificationToasts";
import { GradientBackground } from "@/components/visuals/GradientBackground";
import { isDemoEnabled } from "@/config/demo";
import { getApiClient } from "@/api/client";
import type { IntegrationsResponse } from "@/api/types";

const tabs = [
  { key: "/", label: "Live" },
  { key: "/summaries", label: "Summaries" },
  { key: "/notifications", label: "Notifications", icon: Bell },
];

function IntegrationPill({ label, ok }: { label: string; ok: boolean }) {
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-[10px] ${
        ok ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"
      }`}
    >
      {label}
    </span>
  );
}

export function AppShell() {
  const location = useLocation();
  const navigate = useNavigate();
  const [integrations, setIntegrations] = useState<IntegrationsResponse | null>(null);

  useEffect(() => {
    getApiClient()
      .integrations()
      .then(setIntegrations)
      .catch(() => {});
  }, []);

  const calendarOk = integrations?.calendar?.status === "healthy";
  const mapsOk = integrations?.google_maps?.status === "configured";
  const ttsOk = integrations?.elevenlabs?.status === "configured";

  return (
    <div className="relative flex h-dvh flex-col overflow-hidden">
      <GradientBackground />
      <NotificationToasts />
      {isDemoEnabled() ? <NotificationSimulator /> : null}

      <header className="relative z-10 shrink-0 border-b border-white/60 bg-white/75 backdrop-blur-md px-4 py-3">
        <p className="text-center text-xs uppercase tracking-[0.2em] text-cyan-600 mb-1">
          NV Disruptron
        </p>
        {integrations ? (
          <div className="flex flex-wrap justify-center gap-1.5 mb-2">
            <IntegrationPill label="Calendar" ok={Boolean(calendarOk)} />
            <IntegrationPill label="Maps" ok={Boolean(mapsOk)} />
            <IntegrationPill label="TTS" ok={Boolean(ttsOk)} />
          </div>
        ) : null}
        <Tabs
          selectedKey={location.pathname}
          onSelectionChange={(key) => navigate(String(key))}
          variant="underlined"
          classNames={{
            base: "w-full",
            tabList: "w-full max-w-xl mx-auto justify-center gap-4",
            tab: "text-slate-500",
            cursor: "bg-gradient-to-r from-cyan-500 to-emerald-500",
            tabContent: "group-data-[selected=true]:text-slate-800 font-medium",
          }}
        >
          {tabs.map((tab) => (
            <Tab
              key={tab.key}
              title={
                tab.icon ? (
                  <span className="inline-flex items-center gap-1.5">
                    <tab.icon size={16} strokeWidth={1.75} color="currentColor" />
                    {tab.label}
                  </span>
                ) : (
                  tab.label
                )
              }
            />
          ))}
        </Tabs>
      </header>

      <main className="relative z-10 min-h-0 flex-1 overflow-hidden max-w-3xl w-full mx-auto">
        <Outlet />
      </main>
    </div>
  );
}
