import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import type { AgentTimelineItem } from "@/api/types";

const statusColor = {
  ok: "#10b981",
  warn: "#f59e0b",
  bad: "#ef4444",
} as const;

export function TimelineBlock({ items }: { items: AgentTimelineItem[] }) {
  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 1.25 }}>
      {items.map((item, index) => (
        <Box key={`${item.time}-${item.title}`} sx={{ display: "flex", gap: 1.25 }}>
          <Box
            sx={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              width: 14,
            }}
          >
            <Box
              sx={{
                width: 10,
                height: 10,
                borderRadius: "50%",
                bgcolor: statusColor[item.status ?? "ok"],
                boxShadow: `0 0 0 4px ${statusColor[item.status ?? "ok"]}22`,
              }}
            />
            {index < items.length - 1 ? (
              <Box sx={{ flex: 1, width: 2, bgcolor: "rgba(15,23,42,0.08)", mt: 0.5 }} />
            ) : null}
          </Box>
          <Box sx={{ flex: 1, pb: index < items.length - 1 ? 0.5 : 0 }}>
            <Typography variant="caption" color="text.secondary">
              {item.time}
            </Typography>
            <Typography variant="body2" sx={{ fontWeight: 600 }}>
              {item.title}
            </Typography>
            {item.detail ? (
              <Typography variant="caption" color="text.secondary">
                {item.detail}
              </Typography>
            ) : null}
          </Box>
        </Box>
      ))}
    </Box>
  );
}
