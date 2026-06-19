import { Map, ClipboardList, Bell, Camera } from "lucide-react";
import { useEffect, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { NotificationToasts } from "@/components/notifications/NotificationToasts";
import { getApiClient } from "@/api/client";
import type { IntegrationsResponse } from "@/api/types";

const navItems = [
  { key: "/app", label: "Map", icon: Map },
  { key: "/app/cctvs", label: "CCTVs", icon: Camera },
  { key: "/app/summaries", label: "Logs", icon: ClipboardList },
  { key: "/app/notifications", label: "Alerts", icon: Bell },
];

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

  const allHealthy =
    integrations?.nemotron?.status === "healthy" &&
    integrations?.locateanything?.status === "cached";

  const isMapPage = location.pathname === "/app";

  return (
    <div className="relative flex h-dvh flex-col overflow-hidden bg-[#0B0B0D] text-[#E8E8E8] font-sans">
      <NotificationToasts />

      <header className="relative z-30 shrink-0 border-b border-white/[0.04] bg-[#0B0B0D]/90 backdrop-blur-md px-5 py-2.5 flex items-center justify-between">
        {/* Brand */}
        <a
          href="https://ryukijano.github.io/NV-Disruptron/"
          className="flex items-center gap-3 transition-opacity hover:opacity-80"
        >
          <div className="h-2 w-2 rounded-full bg-[#0EA5E9]" />
          <span className="text-[13px] font-semibold tracking-tight text-white/90">
            NV Disruptron
          </span>
        </a>

        {/* Status */}
        <div className="hidden sm:flex items-center gap-2">
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              allHealthy ? "bg-[#10B981]" : "bg-[#F59E0B]"
            }`}
          />
          <span className="text-[11px] text-white/40 tracking-wide">
            {allHealthy ? "Systems normal" : "Degraded"}
          </span>
        </div>

        {/* Nav */}
        <nav className="flex items-center gap-1">
          {navItems.map((item) => {
            const active = location.pathname === item.key;
            const Icon = item.icon;
            return (
              <button
                key={item.key}
                onClick={() => navigate(item.key)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[11px] font-medium transition-all duration-200 ${
                  active
                    ? "bg-white/[0.06] text-white/90"
                    : "text-white/40 hover:text-white/70 hover:bg-white/[0.03]"
                }`}
              >
                <Icon size={13} strokeWidth={2} />
                <span className="hidden sm:inline">{item.label}</span>
              </button>
            );
          })}
        </nav>
      </header>

      <main
        className={`relative z-10 h-full flex-1 flex overflow-hidden w-full ${
          isMapPage ? "" : "max-w-3xl mx-auto"
        }`}
      >
        <Outlet />
      </main>
    </div>
  );
}
