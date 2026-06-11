import { NextUIProvider } from "@nextui-org/react";
import { BrowserRouter } from "react-router-dom";
import { AgentUiProvider } from "@/providers/AgentUiProvider";
import { ApiProvider } from "@/providers/ApiProvider";
import { NotificationsProvider } from "@/providers/NotificationsProvider";
import { SessionProvider } from "@/providers/SessionProvider";
import { SubscriptionsProvider } from "@/providers/SubscriptionsProvider";
import { SummariesProvider } from "@/providers/SummariesProvider";
import { MapStateProvider } from "@/providers/MapStateProvider";
import { TacticalPanelProvider } from "@/providers/TacticalPanelProvider";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { AppRoutes } from "@/routes/AppRoutes";

export default function App() {
  return (
    <NextUIProvider>
      <SessionProvider>
        <ApiProvider>
          <SummariesProvider>
            <NotificationsProvider>
              <SubscriptionsProvider>
                <AgentUiProvider>
                  <MapStateProvider>
                    <TacticalPanelProvider>
                      <BrowserRouter>
                        <ErrorBoundary>
                          <AppRoutes />
                        </ErrorBoundary>
                      </BrowserRouter>
                    </TacticalPanelProvider>
                  </MapStateProvider>
                </AgentUiProvider>
              </SubscriptionsProvider>
            </NotificationsProvider>
          </SummariesProvider>
        </ApiProvider>
      </SessionProvider>
    </NextUIProvider>
  );
}
