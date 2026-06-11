import { Bell } from "@deemlol/next-icons";
import { Card, CardBody, Switch } from "@nextui-org/react";
import { useNotifications } from "@/providers/NotificationsProvider";
import { useSubscriptions } from "@/providers/SubscriptionsProvider";

function formatWhen(ts: number) {
  return new Intl.DateTimeFormat("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(ts));
}

export function NotificationsView() {
  const { items } = useNotifications();
  const { prefs, setAlerts } = useSubscriptions();

  return (
    <div className="h-full min-h-0 overflow-y-auto px-4 py-3 space-y-3">
      <div className="flex items-center gap-2">
        <Bell size={22} strokeWidth={1.75} color="#0891b2" />
        <div>
          <h1 className="text-lg font-semibold text-slate-800">Notifications</h1>
          <p className="text-sm text-slate-500">
            Live pop-ups when disruption alerts are on. History is kept here.
          </p>
        </div>
      </div>

      <Card className="border-2 border-white/80 bg-white/90 shadow-sm backdrop-blur-sm">
        <CardBody className="flex flex-row items-center justify-between gap-4 py-4">
          <div>
            <p className="font-medium text-slate-800">Disruption alerts</p>
            <p className="text-sm text-slate-500">Push when transport conditions change.</p>
          </div>
          <Switch isSelected={prefs.alerts} onValueChange={setAlerts} color="primary" />
        </CardBody>
      </Card>

      {items.length === 0 ? (
        <Card className="border-2 border-white/80 bg-white/90 shadow-sm">
          <CardBody className="text-sm text-slate-500 py-8 text-center">
            No notifications yet. They will appear here when the backend pushes agent events.
          </CardBody>
        </Card>
      ) : (
        items.map((item) => (
          <Card key={item.id} className="border-2 border-white/80 bg-white/90 shadow-sm">
            <CardBody className="gap-1">
              <div className="flex items-center justify-between gap-2">
                <p className="font-medium text-slate-800">{item.title}</p>
                <span className="text-xs text-slate-400">{formatWhen(item.timestamp)}</span>
              </div>
              {item.body ? (
                <p className="text-sm text-slate-600 whitespace-pre-wrap">{item.body}</p>
              ) : null}
            </CardBody>
          </Card>
        ))
      )}
    </div>
  );
}
