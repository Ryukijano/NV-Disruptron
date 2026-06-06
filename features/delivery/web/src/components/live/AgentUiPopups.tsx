import { ThemeProvider } from "@mui/material/styles";
import { AnimatePresence } from "framer-motion";
import { useAgentUi } from "@/providers/AgentUiProvider";
import { agentMuiTheme } from "@/theme/agentMuiTheme";
import { AgentExpressiveSurface } from "./agent-ui/AgentExpressiveSurface";

export function AgentUiPopups() {
  const { popups, dismissAgentUi } = useAgentUi();
  if (popups.length === 0) return null;

  return (
    <ThemeProvider theme={agentMuiTheme}>
      <div className="pointer-events-none absolute inset-x-2 bottom-2 z-20 flex max-h-[48%] flex-col gap-2 overflow-y-auto overscroll-contain">
        <AnimatePresence mode="popLayout">
          {popups.map((popup) => (
            <AgentExpressiveSurface key={popup.id} payload={popup} onDismiss={dismissAgentUi} />
          ))}
        </AnimatePresence>
      </div>
    </ThemeProvider>
  );
}
