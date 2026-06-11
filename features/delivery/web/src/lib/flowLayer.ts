import type maplibregl from "maplibre-gl";

// London congestion corridors with approximate polyline coordinates [lon, lat]
// Ordered from start to end for directional flow
export const FLOW_PATHS: Array<{
  id: string;
  name: string;
  severity: "serious" | "moderate" | "good";
  coords: [number, number][];
}> = [
  {
    id: "a12",
    name: "A12",
    severity: "serious",
    coords: [
      [-0.089, 51.505], [-0.06, 51.51], [-0.03, 51.52], [-0.01, 51.535], [0.005, 51.545], [0.02, 51.555],
    ],
  },
  {
    id: "a13",
    name: "A13",
    severity: "serious",
    coords: [
      [-0.025, 51.52], [-0.015, 51.525], [0.0, 51.53], [0.015, 51.535], [0.03, 51.54],
    ],
  },
  {
    id: "a23",
    name: "A23",
    severity: "serious",
    coords: [
      [-0.18, 51.48], [-0.16, 51.485], [-0.14, 51.49], [-0.12, 51.495], [-0.1, 51.505], [-0.08, 51.51],
    ],
  },
  {
    id: "a3",
    name: "A3",
    severity: "serious",
    coords: [
      [-0.37, 51.54], [-0.32, 51.52], [-0.28, 51.505], [-0.24, 51.495], [-0.2, 51.49], [-0.16, 51.485], [-0.12, 51.48],
    ],
  },
  {
    id: "a40",
    name: "A40",
    severity: "serious",
    coords: [
      [-0.28, 51.515], [-0.24, 51.51], [-0.2, 51.505], [-0.16, 51.5], [-0.12, 51.495], [-0.08, 51.49],
    ],
  },
  {
    id: "a406",
    name: "A406 North Circular",
    severity: "serious",
    coords: [
      [-0.22, 51.555], [-0.16, 51.56], [-0.1, 51.565], [-0.04, 51.57], [0.0, 51.575], [0.04, 51.57], [0.08, 51.56],
    ],
  },
  {
    id: "inner_ring",
    name: "Inner Ring Road",
    severity: "serious",
    coords: [
      [-0.18, 51.515], [-0.14, 51.51], [-0.1, 51.505], [-0.06, 51.505], [-0.02, 51.51], [0.0, 51.515], [0.02, 51.52], [0.0, 51.525], [-0.04, 51.525], [-0.08, 51.52], [-0.12, 51.515], [-0.16, 51.515],
    ],
  },
  {
    id: "bishopsgate",
    name: "Bishopsgate",
    severity: "serious",
    coords: [
      [-0.08, 51.51], [-0.06, 51.515], [-0.04, 51.52], [-0.02, 51.525],
    ],
  },
  {
    id: "jubilee_tube",
    name: "Jubilee Line (示意)",
    severity: "moderate",
    coords: [
      [-0.2, 51.52], [-0.16, 51.515], [-0.12, 51.51], [-0.08, 51.505], [-0.04, 51.505], [0.0, 51.51], [0.02, 51.52],
    ],
  },
  {
    id: "central_tube",
    name: "Central Line (示意)",
    severity: "moderate",
    coords: [
      [-0.3, 51.515], [-0.24, 51.51], [-0.18, 51.505], [-0.12, 51.5], [-0.06, 51.5], [0.0, 51.505], [0.04, 51.51], [0.08, 51.515],
    ],
  },
];

interface Particle {
  pathIndex: number;
  segIndex: number;
  t: number; // 0..1 along current segment
  speed: number;
  size: number;
  alpha: number;
  life: number;
}

function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}

function projectPath(
  map: maplibregl.Map,
  coords: [number, number][]
): Array<{ x: number; y: number }> {
  return coords.map((c) => {
    const p = map.project(c);
    return { x: p.x, y: p.y };
  });
}

export class FlowParticleLayer {
  private canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D;
  private particles: Particle[] = [];
  private rafId = 0;
  private map: maplibregl.Map;
  private active = false;

  constructor(map: maplibregl.Map) {
    this.map = map;
    this.canvas = document.createElement("canvas");
    this.canvas.style.position = "absolute";
    this.canvas.style.top = "0";
    this.canvas.style.left = "0";
    this.canvas.style.pointerEvents = "none";
    this.canvas.style.width = "100%";
    this.canvas.style.height = "100%";
    this.canvas.style.zIndex = "5";
    const container = map.getContainer();
    container.appendChild(this.canvas);
    this.ctx = this.canvas.getContext("2d")!;
    this.resize();

    map.on("resize", this.resize);
    map.on("move", this.resize);
    map.on("moveend", this.resize);
  }

  private resize = () => {
    const rect = this.map.getContainer().getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    this.canvas.width = rect.width * dpr;
    this.canvas.height = rect.height * dpr;
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.canvas.style.width = `${rect.width}px`;
    this.canvas.style.height = `${rect.height}px`;
  };

  start() {
    if (this.active) return;
    this.active = true;
    this.spawnParticles();
    this.animate();
  }

  stop() {
    this.active = false;
    if (this.rafId) cancelAnimationFrame(this.rafId);
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    this.particles = [];
  }

  destroy() {
    this.stop();
    this.canvas.remove();
    this.map.off("resize", this.resize);
    this.map.off("move", this.resize);
    this.map.off("moveend", this.resize);
  }

  private spawnParticles() {
    if (!this.active) return;
    // Maintain ~150 particles total
    const target = 150;
    while (this.particles.length < target) {
      const pathIdx = Math.floor(Math.random() * FLOW_PATHS.length);
      const path = FLOW_PATHS[pathIdx];
      const segIdx = Math.floor(Math.random() * Math.max(1, path.coords.length - 1));
      const severitySpeed = path.severity === "serious" ? 0.3 : path.severity === "moderate" ? 0.6 : 1.0;
      this.particles.push({
        pathIndex: pathIdx,
        segIndex: segIdx,
        t: Math.random(),
        speed: (0.003 + Math.random() * 0.004) * severitySpeed,
        size: 1.2 + Math.random() * 1.5,
        alpha: 0.4 + Math.random() * 0.5,
        life: 1.0,
      });
    }
  }

  private animate = () => {
    if (!this.active) return;
    const ctx = this.ctx;
    const rect = this.map.getContainer().getBoundingClientRect();
    ctx.clearRect(0, 0, rect.width, rect.height);

    // Update and draw particles
    for (let i = this.particles.length - 1; i >= 0; i--) {
      const p = this.particles[i];
      const path = FLOW_PATHS[p.pathIndex];
      const segments = projectPath(this.map, path.coords);
      if (segments.length < 2) continue;

      p.t += p.speed;
      if (p.t >= 1) {
        p.segIndex++;
        p.t = 0;
        if (p.segIndex >= segments.length - 1) {
          // Respawn on same path at start
          p.segIndex = 0;
          p.t = 0;
        }
      }

      const seg = segments[p.segIndex];
      const next = segments[p.segIndex + 1];
      if (!seg || !next) continue;

      const x = lerp(seg.x, next.x, p.t);
      const y = lerp(seg.y, next.y, p.t);

      // Trail: draw a short line behind
      const dx = next.x - seg.x;
      const dy = next.y - seg.y;
      const len = Math.sqrt(dx * dx + dy * dy) || 1;
      const tailLen = 8 + p.size * 4;
      const tx = x - (dx / len) * tailLen;
      const ty = y - (dy / len) * tailLen;

      const color =
        path.severity === "serious"
          ? `rgba(239,68,68,${p.alpha})` // red
          : path.severity === "moderate"
          ? `rgba(245,158,11,${p.alpha})` // amber
          : `rgba(16,185,129,${p.alpha})`; // green

      ctx.beginPath();
      ctx.moveTo(tx, ty);
      ctx.lineTo(x, y);
      ctx.strokeStyle = color;
      ctx.lineWidth = p.size;
      ctx.lineCap = "round";
      ctx.stroke();

      // Head dot
      ctx.beginPath();
      ctx.arc(x, y, p.size * 1.2, 0, Math.PI * 2);
      ctx.fillStyle = color.replace(/[\d\.]+\)$/, "0.85)");
      ctx.fill();
    }

    this.spawnParticles();
    this.rafId = requestAnimationFrame(this.animate);
  };
}
