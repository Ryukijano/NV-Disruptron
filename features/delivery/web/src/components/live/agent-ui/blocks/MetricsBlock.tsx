import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import type { AgentMetric } from "@/api/types";

const toneColor = {
  up: "#10b981",
  down: "#ef4444",
  neutral: "#64748b",
} as const;

export function MetricsBlock({ items }: { items: AgentMetric[] }) {
  return (
    <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
      {items.map((item) => (
        <Box
          key={item.label}
          sx={{
            flex: "1 1 88px",
            minWidth: 88,
            p: 1.25,
            borderRadius: 2,
            bgcolor: "rgba(8,145,178,0.06)",
            border: "1px solid rgba(8,145,178,0.12)",
          }}
        >
          <Typography variant="caption" color="text.secondary">
            {item.label}
          </Typography>
          <Typography variant="h6" sx={{ fontWeight: 700, lineHeight: 1.2 }}>
            {item.value}
          </Typography>
          {item.delta ? (
            <Typography variant="caption" sx={{ color: toneColor[item.tone ?? "neutral"] }}>
              {item.delta}
            </Typography>
          ) : null}
        </Box>
      ))}
    </Box>
  );
}
