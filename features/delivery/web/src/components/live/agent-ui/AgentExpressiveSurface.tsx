import CloseIcon from "@mui/icons-material/Close";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import IconButton from "@mui/material/IconButton";
import Typography from "@mui/material/Typography";
import { motion } from "framer-motion";
import type { AgentUiPayload } from "@/api/types";
import { AgentUiRenderer } from "./AgentUiRenderer";

const variantMeta = {
  info: { label: "Insight", color: "primary" as const },
  alert: { label: "Alert", color: "warning" as const },
  plan: { label: "Plan", color: "success" as const },
};

const variantMotion = {
  info: {
    initial: { opacity: 0, x: 28, rotate: 1.5, scale: 0.94 },
    animate: { opacity: 1, x: 0, rotate: 0, scale: 1 },
    exit: { opacity: 0, x: 20, scale: 0.96 },
    transition: { type: "spring" as const, stiffness: 380, damping: 26, mass: 0.9 },
  },
  alert: {
    initial: { opacity: 0, y: 24, scale: 0.92 },
    animate: { opacity: 1, y: 0, scale: 1 },
    exit: { opacity: 0, y: 16, scale: 0.95 },
    transition: { type: "spring" as const, stiffness: 520, damping: 24, mass: 0.85 },
  },
  plan: {
    initial: { opacity: 0, y: 18, scale: 0.9 },
    animate: { opacity: 1, y: 0, scale: 1 },
    exit: { opacity: 0, y: 12, scale: 0.94 },
    transition: { type: "spring" as const, stiffness: 340, damping: 22, mass: 1 },
  },
};

type AgentExpressiveSurfaceProps = {
  payload: AgentUiPayload & { id: string };
  onDismiss: (id: string) => void;
};

export function AgentExpressiveSurface({ payload, onDismiss }: AgentExpressiveSurfaceProps) {
  const variant = payload.variant ?? "info";
  const meta = variantMeta[variant];
  const motionProps = variantMotion[variant];

  return (
    <Box
      component={motion.div}
      layout
      initial={motionProps.initial}
      animate={motionProps.animate}
      exit={motionProps.exit}
      transition={motionProps.transition}
      whileHover={{ y: -2, transition: { type: "spring", stiffness: 500, damping: 30 } }}
      sx={{
        pointerEvents: "auto",
        position: "relative",
        overflow: "hidden",
        borderRadius: 3,
        bgcolor: "background.paper",
        boxShadow:
          variant === "alert"
            ? "0 20px 48px rgba(245,158,11,0.18)"
            : "0 18px 42px rgba(8,145,178,0.16)",
        border: "1px solid rgba(255,255,255,0.92)",
        "&::before": {
          content: '""',
          position: "absolute",
          inset: 0,
          padding: "1.5px",
          borderRadius: "inherit",
          background:
            variant === "alert"
              ? "linear-gradient(135deg, #fbbf24, #f97316, #ef4444)"
              : variant === "plan"
                ? "linear-gradient(135deg, #34d399, #22d3ee, #3b82f6)"
                : "linear-gradient(135deg, #22d3ee, #34d399, #3b82f6)",
          WebkitMask: "linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)",
          WebkitMaskComposite: "xor",
          maskComposite: "exclude",
          pointerEvents: "none",
        },
      }}
    >
      <Box
        component={motion.div}
        animate={{
          x: variant === "alert" ? [0, 2, -2, 0] : 0,
          opacity: [0.5, 0.75, 0.5],
        }}
        transition={{
          x: { duration: 0.45, repeat: variant === "alert" ? 2 : 0 },
          opacity: { duration: 3, repeat: Infinity, ease: "easeInOut" },
        }}
        sx={{
          position: "absolute",
          inset: "-35% -15% auto auto",
          width: 200,
          height: 200,
          borderRadius: "50%",
          background:
            variant === "plan"
              ? "radial-gradient(circle, rgba(52,211,153,0.22), transparent 70%)"
              : "radial-gradient(circle, rgba(34,211,238,0.2), transparent 70%)",
          pointerEvents: "none",
        }}
      />
      <Box sx={{ p: 1.75, position: "relative", display: "flex", flexDirection: "column", gap: 1.25 }}>
        <Box sx={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 1 }}>
          <Box sx={{ minWidth: 0 }}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 0.75, mb: 0.5 }}>
              <Typography variant="subtitle2" color="secondary.main">
                Agent
              </Typography>
              <Chip size="small" label={meta.label} color={meta.color} variant="outlined" />
            </Box>
            <Typography variant="subtitle1" sx={{ fontWeight: 700, lineHeight: 1.25 }}>
              {payload.title}
            </Typography>
            {payload.body ? (
              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.25 }}>
                {payload.body}
              </Typography>
            ) : null}
          </Box>
          <IconButton
            size="small"
            aria-label="Dismiss agent update"
            onClick={() => onDismiss(payload.id)}
            sx={{ mt: -0.5, mr: -0.5 }}
          >
            <CloseIcon fontSize="small" />
          </IconButton>
        </Box>

        {payload.blocks?.length ? <AgentUiRenderer blocks={payload.blocks} /> : null}
      </Box>
    </Box>
  );
}
