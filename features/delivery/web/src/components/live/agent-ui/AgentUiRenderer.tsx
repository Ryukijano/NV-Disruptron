import Box from "@mui/material/Box";
import { motion } from "framer-motion";
import type { AgentUiBlock } from "@/api/types";
import { BarChartBlock } from "./blocks/BarChartBlock";
import { MetricsBlock } from "./blocks/MetricsBlock";
import { RouteCardBlock } from "./blocks/RouteCardBlock";
import { StatusGridBlock } from "./blocks/StatusGridBlock";
import { TimelineBlock } from "./blocks/TimelineBlock";

const blockMotion = {
  hidden: { opacity: 0, y: 14, scale: 0.97 },
  show: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { type: "spring" as const, stiffness: 420, damping: 28 },
  },
};

export function AgentUiRenderer({ blocks }: { blocks: AgentUiBlock[] }) {
  return (
    <Box
      component={motion.div}
      initial="hidden"
      animate="show"
      variants={{
        show: { transition: { staggerChildren: 0.08, delayChildren: 0.05 } },
      }}
      sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}
    >
      {blocks.map((block, index) => {
        const key = `${block.type}-${index}`;
        const child = (() => {
          switch (block.type) {
            case "metrics":
              return <MetricsBlock items={block.items} />;
            case "bar-chart":
              return (
                <BarChartBlock title={block.title} unit={block.unit} items={block.items} />
              );
            case "timeline":
              return <TimelineBlock items={block.items} />;
            case "status-grid":
              return <StatusGridBlock items={block.items} />;
            case "route-card":
              return <RouteCardBlock route={block.route} />;
            default:
              return null;
          }
        })();
        if (!child) return null;
        return (
          <Box component={motion.div} key={key} variants={blockMotion}>
            {child}
          </Box>
        );
      })}
    </Box>
  );
}
