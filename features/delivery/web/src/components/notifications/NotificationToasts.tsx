import { Bell } from "@deemlol/next-icons";
import { AnimatePresence, motion } from "framer-motion";
import { useNotifications } from "@/providers/NotificationsProvider";

function formatWhen(ts: number) {
  return new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(ts));
}

export function NotificationToasts() {
  const { toasts, dismissToast } = useNotifications();

  return (
    <div className="pointer-events-none fixed right-4 top-4 z-50 flex w-full max-w-sm flex-col gap-2">
      <AnimatePresence mode="popLayout">
        {toasts.map((toast) => (
          <motion.div
            key={toast.id}
            layout
            initial={{ opacity: 0, x: 48, scale: 0.96 }}
            animate={{ opacity: 1, x: 0, scale: 1 }}
            exit={{ opacity: 0, x: 48, scale: 0.96 }}
            transition={{ type: "spring", stiffness: 420, damping: 32 }}
            className="pointer-events-auto rounded-2xl border-2 border-white/90 bg-white/95 p-3 shadow-xl ring-1 ring-cyan-100/80 backdrop-blur-md"
          >
            <div className="flex items-start gap-2.5">
              <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-cyan-500 to-emerald-500 text-white">
                <Bell size={16} strokeWidth={1.75} color="#ffffff" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-start justify-between gap-2">
                  <p className="text-sm font-semibold text-slate-800">{toast.title}</p>
                  <button
                    type="button"
                    onClick={() => dismissToast(toast.id)}
                    className="shrink-0 text-xs text-slate-400 hover:text-slate-600"
                    aria-label="Dismiss notification"
                  >
                    ✕
                  </button>
                </div>
                {toast.body ? (
                  <p className="mt-0.5 text-sm text-slate-600 leading-snug">{toast.body}</p>
                ) : null}
                <p className="mt-1 text-[10px] uppercase tracking-wide text-slate-400">
                  {formatWhen(toast.timestamp)}
                </p>
              </div>
            </div>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
