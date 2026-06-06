import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Typography from "@mui/material/Typography";
import type { AgentStatusItem } from "@/api/types";

const statusMeta = {
  good: { label: "Good", color: "success" as const },
  minor: { label: "Minor", color: "warning" as const },
  severe: { label: "Severe", color: "error" as const },
};

export function StatusGridBlock({ items }: { items: AgentStatusItem[] }) {
  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
      {items.map((item) => {
        const meta = statusMeta[item.status];
        return (
          <Box
            key={item.line}
            sx={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 1,
              p: 1,
              borderRadius: 2,
              bgcolor: "rgba(15,23,42,0.03)",
              border: "1px solid rgba(15,23,42,0.06)",
            }}
          >
            <Box sx={{ minWidth: 0 }}>
              <Typography variant="body2" sx={{ fontWeight: 600 }}>
                {item.line}
              </Typography>
              {item.detail ? (
                <Typography variant="caption" color="text.secondary" noWrap>
                  {item.detail}
                </Typography>
              ) : null}
            </Box>
            <Chip size="small" label={meta.label} color={meta.color} variant="outlined" />
          </Box>
        );
      })}
    </Box>
  );
}
