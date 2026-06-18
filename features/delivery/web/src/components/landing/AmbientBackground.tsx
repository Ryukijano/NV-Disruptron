import { useEffect, useRef } from "react";

export function AmbientBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (prefersReducedMotion) {
      // Static gradient background
      canvas.style.background =
        "radial-gradient(circle at 20% 20%, rgba(0, 212, 255, 0.08), transparent 40%), " +
        "radial-gradient(circle at 80% 80%, rgba(118, 185, 0, 0.08), transparent 40%), " +
        "#0a0e1a";
      return;
    }

    let animationId: number;
    let width = window.innerWidth;
    let height = window.innerHeight;

    const resize = () => {
      width = window.innerWidth;
      height = window.innerHeight;
      canvas.width = width;
      canvas.height = height;
    };
    resize();
    window.addEventListener("resize", resize);

    const blobs = [
      { x: 0.2, y: 0.3, r: 0.4, color: "rgba(0, 212, 255, 0.18)", phase: 0, speed: 0.0003 },
      { x: 0.8, y: 0.7, r: 0.35, color: "rgba(118, 185, 0, 0.16)", phase: 2, speed: 0.00025 },
      { x: 0.5, y: 0.5, r: 0.3, color: "rgba(168, 85, 247, 0.12)", phase: 4, speed: 0.0002 },
    ];

    const draw = (time: number) => {
      ctx.fillStyle = "#0a0e1a";
      ctx.fillRect(0, 0, width, height);

      for (const blob of blobs) {
        const dx = Math.sin(time * blob.speed + blob.phase) * width * 0.08;
        const dy = Math.cos(time * blob.speed * 0.7 + blob.phase) * height * 0.06;
        const cx = blob.x * width + dx;
        const cy = blob.y * height + dy;
        const radius = blob.r * Math.min(width, height);

        const gradient = ctx.createRadialGradient(cx, cy, 0, cx, cy, radius);
        gradient.addColorStop(0, blob.color);
        gradient.addColorStop(1, "rgba(0,0,0,0)");
        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.arc(cx, cy, radius, 0, Math.PI * 2);
        ctx.fill();
      }

      // Subtle grid overlay
      ctx.strokeStyle = "rgba(0, 212, 255, 0.03)";
      ctx.lineWidth = 1;
      const gridSize = 60;
      for (let x = 0; x < width; x += gridSize) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
      }
      for (let y = 0; y < height; y += gridSize) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
      }

      animationId = requestAnimationFrame(draw);
    };

    animationId = requestAnimationFrame(draw);
    return () => {
      cancelAnimationFrame(animationId);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="pointer-events-none fixed inset-0 z-0 h-full w-full"
      aria-hidden="true"
    />
  );
}
