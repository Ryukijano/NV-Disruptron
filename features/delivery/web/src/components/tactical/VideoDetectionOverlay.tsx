import { useEffect, useRef, useState } from "react";

interface BBox {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

interface VideoEventDetail {
  event_id: string;
  category: string;
  label: string;
  duration_sec: number;
  avg_confidence: number;
  frame_count: number;
  bbox_history: BBox[];
  lat: number | null;
  lon: number | null;
  timestamp: string;
}

const CATEGORY_COLORS: Record<string, string> = {
  pavement_obstruction: "#EF4444",
  broken_lift: "#F59E0B",
  missing_dropped_kerb: "#8B5CF6",
  flooding: "#0EA5E9",
  illegal_parking: "#EC4899",
  broken_ev_charger: "#10B981",
  missing_tactile_paving: "#F97316",
};

function drawSyntheticFrame(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number
) {
  // Dark synthetic video frame background
  ctx.fillStyle = "#0B0B0D";
  ctx.fillRect(0, 0, width, height);

  // Subtle grid lines (like a street scene)
  ctx.strokeStyle = "rgba(255,255,255,0.04)";
  ctx.lineWidth = 1;
  for (let x = 0; x < width; x += 40) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, height);
    ctx.stroke();
  }
  for (let y = 0; y < height; y += 40) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(width, y);
    ctx.stroke();
  }

  // Vignette
  const grad = ctx.createRadialGradient(
    width / 2, height / 2, width * 0.3,
    width / 2, height / 2, width * 0.7
  );
  grad.addColorStop(0, "rgba(0,0,0,0)");
  grad.addColorStop(1, "rgba(0,0,0,0.5)");
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, width, height);
}

function drawBBox(
  ctx: CanvasRenderingContext2D,
  bbox: BBox,
  width: number,
  height: number,
  color: string,
  alpha: number,
  label: string
) {
  const x = bbox.x1 * width;
  const y = bbox.y1 * height;
  const w = (bbox.x2 - bbox.x1) * width;
  const h = (bbox.y2 - bbox.y1) * height;

  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.globalAlpha = alpha;
  ctx.strokeRect(x, y, w, h);

  // Fill
  ctx.fillStyle = color;
  ctx.globalAlpha = alpha * 0.12;
  ctx.fillRect(x, y, w, h);

  // Label tag
  ctx.globalAlpha = alpha;
  ctx.fillStyle = color;
  const text = `${label}`;
  ctx.font = "10px sans-serif";
  const textW = ctx.measureText(text).width + 8;
  ctx.fillRect(x, Math.max(0, y - 16), textW, 16);
  ctx.fillStyle = "#000";
  ctx.fillText(text, x + 4, Math.max(12, y - 4));

  ctx.globalAlpha = 1;
}

export function VideoDetectionOverlay({ eventId }: { eventId: string }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [event, setEvent] = useState<VideoEventDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const rafRef = useRef(0);
  const frameIdxRef = useRef(0);

  useEffect(() => {
    fetch(`/api/v1/video/events/${encodeURIComponent(eventId)}`)
      .then((r) => r.json())
      .then((data) => {
        if (data.error) {
          setError(data.error);
        } else {
          setEvent(data);
        }
      })
      .catch(() => setError("Failed to load detection data"));
  }, [eventId]);

  useEffect(() => {
    if (!event || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const bboxes = event.bbox_history || [];
    const color = CATEGORY_COLORS[event.category] || "#0EA5E9";
    const totalFrames = Math.max(bboxes.length, 1);

    const animate = () => {
      if (!canvasRef.current) return;
      const w = rect.width;
      const h = rect.height;
      drawSyntheticFrame(ctx, w, h);

      // Show current bbox with a fade trail of previous frames
      const currentIdx = frameIdxRef.current % totalFrames;
      for (let trail = 0; trail < 3; trail++) {
        const idx = (currentIdx - trail + totalFrames) % totalFrames;
        const bbox = bboxes[idx];
        if (!bbox) continue;
        const alpha = trail === 0 ? 0.95 : trail === 1 ? 0.5 : 0.2;
        drawBBox(ctx, bbox, w, h, color, alpha, event.label);
      }

      // Frame indicator
      ctx.fillStyle = "rgba(255,255,255,0.5)";
      ctx.font = "10px monospace";
      ctx.fillText(
        `Frame ${currentIdx + 1}/${totalFrames}  |  ${event.duration_sec.toFixed(1)}s`,
        8,
        h - 8
      );

      // Confidence bar
      const barW = w - 16;
      const conf = event.avg_confidence;
      ctx.fillStyle = "rgba(255,255,255,0.08)";
      ctx.fillRect(8, h - 28, barW, 4);
      ctx.fillStyle = conf > 0.7 ? "#10B981" : conf > 0.4 ? "#F59E0B" : "#EF4444";
      ctx.fillRect(8, h - 28, barW * conf, 4);

      frameIdxRef.current += 0.15; // Slow advance for visibility
      rafRef.current = requestAnimationFrame(animate);
    };

    animate();
    return () => cancelAnimationFrame(rafRef.current);
  }, [event]);

  if (error) {
    return (
      <div className="rounded-lg border border-[#EF4444]/20 bg-[#EF4444]/5 p-3 text-[11px] text-[#EF4444]">
        {error}
      </div>
    );
  }

  if (!event) {
    return (
      <div className="flex items-center gap-2 text-[11px] text-white/40">
        <span className="h-2 w-2 rounded-full bg-[#0EA5E9] animate-pulse" />
        Loading detection data…
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-[10px] text-white/40">
        <span className="capitalize">{event.category.replace("_", " ")}</span>
        <span>{event.frame_count} frames</span>
      </div>
      <canvas
        ref={canvasRef}
        className="w-full rounded-lg border border-white/5"
        style={{ aspectRatio: "16/9", background: "#0B0B0D" }}
      />
      <div className="flex justify-between text-[10px] text-white/30">
        <span>Confidence: {(event.avg_confidence * 100).toFixed(0)}%</span>
        <span>{event.duration_sec.toFixed(1)}s</span>
      </div>
    </div>
  );
}
