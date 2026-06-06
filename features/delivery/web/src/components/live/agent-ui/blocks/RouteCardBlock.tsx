import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Typography from "@mui/material/Typography";
import type { AgentRouteData } from "@/api/types";

export function RouteCardBlock({ route }: { route: AgentRouteData }) {
  return (
    <Box
      sx={{
        p: 1.5,
        borderRadius: 2.5,
        background: "linear-gradient(135deg, rgba(8,145,178,0.12), rgba(16,185,129,0.1))",
        border: "1px solid rgba(8,145,178,0.18)",
      }}
    >
      <Box
        sx={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          gap: 1,
        }}
      >
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="caption" color="text.secondary">
            {route.from}
          </Typography>
          <Typography variant="body2" sx={{ fontWeight: 700 }}>
            → {route.to}
          </Typography>
        </Box>
        <Chip size="small" label={route.duration} color="primary" />
      </Box>
      <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.75, mt: 1 }}>
        <Chip size="small" variant="outlined" label={route.mode} />
        {route.charge ? <Chip size="small" variant="outlined" label={route.charge} color="success" /> : null}
        {route.delay ? <Chip size="small" variant="outlined" label={route.delay} color="warning" /> : null}
      </Box>
    </Box>
  );
}
