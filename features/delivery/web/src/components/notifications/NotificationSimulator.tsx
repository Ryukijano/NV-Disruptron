import { useEffect } from "react";
import { startDevNotificationSimulation } from "@/api/simulateNotifications";
import { isDemoEnabled } from "@/config/demo";
import { useNotifications } from "@/providers/NotificationsProvider";
import { useSubscriptions } from "@/providers/SubscriptionsProvider";

export function NotificationSimulator() {
  const { prefs } = useSubscriptions();
  const { pushNotification } = useNotifications();

  useEffect(() => {
    if (!isDemoEnabled() || !prefs.alerts) return;
    return startDevNotificationSimulation((event) => {
      pushNotification(event.title, event.body, { toast: true });
    });
  }, [prefs.alerts, pushNotification]);

  return null;
}
