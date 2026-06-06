import { createTheme } from "@mui/material/styles";

export const agentMuiTheme = createTheme({
  palette: {
    mode: "light",
    primary: { main: "#0891b2" },
    secondary: { main: "#10b981" },
    warning: { main: "#f59e0b" },
    error: { main: "#ef4444" },
    background: { default: "#ffffff", paper: "#ffffff" },
    text: { primary: "#0f172a", secondary: "#475569" },
  },
  shape: { borderRadius: 14 },
  typography: {
    fontFamily: '"Inter", system-ui, sans-serif',
    subtitle2: { fontWeight: 600, letterSpacing: "0.04em", textTransform: "uppercase" },
  },
  components: {
    MuiCard: {
      styleOverrides: {
        root: {
          backgroundImage: "none",
        },
      },
    },
  },
});
