import { Card, CardBody, Switch } from "@nextui-org/react";
import { useSummaries } from "@/providers/SummariesProvider";
import { useSubscriptions } from "@/providers/SubscriptionsProvider";

function formatDate(date: string) {
  return new Intl.DateTimeFormat("en-GB", {
    weekday: "long",
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(`${date}T12:00:00`));
}

export function SummariesView() {
  const { summaries } = useSummaries();
  const { prefs, setDaily } = useSubscriptions();

  return (
    <div className="h-full min-h-0 overflow-y-auto px-4 py-3 space-y-3">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold text-slate-800">Morning summaries</h1>
          <p className="text-sm text-slate-500">One digest per day, kept in history.</p>
        </div>
      </div>

      <Card className="border-2 border-white/80 bg-white/90 shadow-sm backdrop-blur-sm">
        <CardBody className="flex flex-row items-center justify-between gap-4 py-4">
          <div>
            <p className="font-medium text-slate-800">Morning plan</p>
            <p className="text-sm text-slate-500">Receive the daily London ops digest.</p>
          </div>
          <Switch isSelected={prefs.daily} onValueChange={setDaily} color="secondary" />
        </CardBody>
      </Card>

      {summaries.length === 0 ? (
        <Card className="border-2 border-white/80 bg-white/90 shadow-sm">
          <CardBody className="text-sm text-slate-500 py-8 text-center">
            No morning summaries yet. Ask the agent for today&apos;s plan on Live.
          </CardBody>
        </Card>
      ) : (
        summaries.map((item) => (
          <Card key={item.date} className="border-2 border-white/80 bg-white/90 shadow-sm">
            <CardBody className="gap-2">
              <div className="flex items-center justify-between gap-2">
                <p className="font-medium text-slate-800">{item.title}</p>
                <span className="text-xs text-slate-400">{formatDate(item.date)}</span>
              </div>
              <p className="text-sm text-slate-600 whitespace-pre-wrap line-clamp-8">{item.body}</p>
            </CardBody>
          </Card>
        ))
      )}
    </div>
  );
}
