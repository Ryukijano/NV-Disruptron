import { NextUIProvider } from "@nextui-org/react";
import { BrowserRouter } from "react-router-dom";
import { AgentUiProvider } from "@/providers/AgentUiProvider";
import { ApiProvider } from "@/providers/ApiProvider";
import { NotificationsProvider } from "@/providers/NotificationsProvider";
import { SessionProvider } from "@/providers/SessionProvider";
import { SubscriptionsProvider } from "@/providers/SubscriptionsProvider";
import { SummariesProvider } from "@/providers/SummariesProvider";
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
                  <BrowserRouter>
                    <AppRoutes />
                  </BrowserRouter>
                </AgentUiProvider>
              </SubscriptionsProvider>
            </NotificationsProvider>
          </SummariesProvider>
        </ApiProvider>
      </SessionProvider>
    </NextUIProvider>
  );
}
