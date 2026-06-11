import { useState } from "react";

export type Detection = {
  label: string;
  category?: string;
  bbox: [number, number, number, number]; // [x1, y1, x2, y2] normalized 0-1
  confidence: number;
};

const CATEGORY_COLORS: Record<string, string> = {
  // Hazard categories
  pavement_obstruction: "#EF4444",
  broken_lift: "#F59E0B",
  missing_dropped_kerb: "#F97316",
  flooding: "#3B82F6",
  illegal_parking: "#8B5CF6",
  broken_ev_charger: "#10B981",
  missing_tactile_paving: "#EC4899",
  // Traffic / object categories
  car: "#0EA5E9",
  bus: "#8B5CF6",
  person: "#10B981",
  bicycle: "#F59E0B",
  truck: "#EC4899",
  van: "#6366F1",
  motorcycle: "#F97316",
  unknown: "#9CA3AF",
};

export function DetectionOverlay({
  imageUrl,
  detections,
}: {
  imageUrl: string;
  detections: Detection[];
}) {
  const [imgSize, setImgSize] = useState({ w: 0, h: 0 });

  return (
    <div className="relative inline-block w-full">
      <img
        src={imageUrl}
        alt="Camera snapshot"
        className="w-full rounded-lg bg-black/40 object-contain max-h-[400px]"
        onLoad={(e) => {
          const el = e.currentTarget;
          setImgSize({ w: el.clientWidth, h: el.clientHeight });
        }}
      />
      {imgSize.w > 0 &&
        detections.map((det, i) => {
          const [x1, y1, x2, y2] = det.bbox;
          const left = x1 * 100;
          const top = y1 * 100;
          const width = (x2 - x1) * 100;
          const height = (y2 - y1) * 100;
          const color = CATEGORY_COLORS[det.category || det.label] || CATEGORY_COLORS[det.label] || CATEGORY_COLORS.unknown;
          return (
            <div
              key={i}
              className="absolute pointer-events-none"
              style={{
                left: `${left}%`,
                top: `${top}%`,
                width: `${width}%`,
                height: `${height}%`,
                border: `2px solid ${color}`,
                borderRadius: 4,
                boxShadow: `0 0 8px ${color}66`,
              }}
            >
              <span
                className="absolute -top-5 left-0 px-1 py-[1px] text-[9px] font-semibold rounded-sm whitespace-nowrap"
                style={{ background: color, color: "#fff" }}
              >
                {det.label} ({Math.round(det.confidence * 100)}%)
              </span>
            </div>
          );
        })}
    </div>
  );
}
