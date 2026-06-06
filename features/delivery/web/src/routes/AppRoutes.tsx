import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { LivePage } from "@/pages/LivePage";
import { NotificationsPage } from "@/pages/NotificationsPage";
import { SummariesPage } from "@/pages/SummariesPage";

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<LivePage />} />
        <Route path="summaries" element={<SummariesPage />} />
        <Route path="notifications" element={<NotificationsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
