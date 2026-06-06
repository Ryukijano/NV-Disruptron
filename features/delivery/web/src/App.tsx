import { NextUIProvider } from "@nextui-org/react";
import { BrowserRouter } from "react-router-dom";
import { ApiProvider } from "@/providers/ApiProvider";
import { NotificationsProvider } from "@/providers/NotificationsProvider";
import { SubscriptionsProvider } from "@/providers/SubscriptionsProvider";
import { SummariesProvider } from "@/providers/SummariesProvider";
import { AppRoutes } from "@/routes/AppRoutes";

export default function App() {
  return (
    <NextUIProvider>
      <ApiProvider>
        <SummariesProvider>
          <NotificationsProvider>
            <SubscriptionsProvider>
              <BrowserRouter>
                <AppRoutes />
              </BrowserRouter>
            </SubscriptionsProvider>
          </NotificationsProvider>
        </SummariesProvider>
      </ApiProvider>
    </NextUIProvider>
  );
}
