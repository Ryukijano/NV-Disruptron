import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import type { AgentChartItem } from "@/api/types";

export function BarChartBlock({
  title,
  unit,
  items,
}: {
  title?: string;
  unit?: string;
  items: AgentChartItem[];
}) {
  const max = Math.max(...items.map((i) => i.value), 1);

  return (
    <Box>
      {title ? (
        <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>
          {title}
          {unit ? ` · ${unit}` : ""}
        </Typography>
      ) : null}
      <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
        {items.map((item) => (
          <Box key={item.label}>
            <Box sx={{ display: "flex", justifyContent: "space-between", mb: 0.25 }}>
              <Typography variant="caption" color="text.secondary">
                {item.label}
              </Typography>
              <Typography variant="caption" sx={{ fontWeight: 600 }}>
                {item.value}
              </Typography>
            </Box>
            <Box
              sx={{
                height: 8,
                borderRadius: 99,
                bgcolor: "rgba(15,23,42,0.06)",
                overflow: "hidden",
              }}
            >
              <Box
                sx={{
                  height: "100%",
                  width: `${(item.value / max) * 100}%`,
                  borderRadius: 99,
                  background: `linear-gradient(90deg, ${item.color ?? "#0891b2"}, ${item.color ?? "#10b981"}99)`,
                  transition: "width 0.8s cubic-bezier(0.22, 1, 0.36, 1)",
                }}
              />
            </Box>
          </Box>
        ))}
      </Box>
    </Box>
  );
}
