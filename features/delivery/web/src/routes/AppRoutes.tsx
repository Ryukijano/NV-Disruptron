import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { CCTVPage } from "@/pages/CCTVPage";
import { LandingPage } from "@/pages/LandingPage";
import { MapPage } from "@/pages/MapPage";
import { NotificationsPage } from "@/pages/NotificationsPage";
import { SummariesPage } from "@/pages/SummariesPage";

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="app" element={<AppShell />}>
        <Route index element={<MapPage />} />
        <Route path="cctvs" element={<CCTVPage />} />
        <Route path="summaries" element={<SummariesPage />} />
        <Route path="notifications" element={<NotificationsPage />} />
        <Route path="*" element={<Navigate to="/app" replace />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
