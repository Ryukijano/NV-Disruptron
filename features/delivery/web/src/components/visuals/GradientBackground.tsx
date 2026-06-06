import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo } from "react";
import * as THREE from "three";

const TOUCH_SIZE = 64;
const TOUCH_MAX_AGE = 80;
const TOUCH_RADIUS = 0.22 * TOUCH_SIZE;

type TouchPoint = {
  x: number;
  y: number;
  age: number;
  force: number;
  vx: number;
  vy: number;
};

class TouchTexture {
  readonly texture: THREE.CanvasTexture;
  private readonly canvas: HTMLCanvasElement;
  private readonly ctx: CanvasRenderingContext2D;
  private readonly trail: TouchPoint[] = [];
  private last: { x: number; y: number } | null = null;

  constructor() {
    this.canvas = document.createElement("canvas");
    this.canvas.width = TOUCH_SIZE;
    this.canvas.height = TOUCH_SIZE;
    const ctx = this.canvas.getContext("2d");
    if (!ctx) throw new Error("2d context unavailable");
    this.ctx = ctx;
    this.texture = new THREE.CanvasTexture(this.canvas);
    this.texture.minFilter = THREE.LinearFilter;
    this.texture.magFilter = THREE.LinearFilter;
  }

  addTouch(nx: number, ny: number) {
    const x = nx * TOUCH_SIZE;
    const y = (1 - ny) * TOUCH_SIZE;
    let force = 0;
    let vx = 0;
    let vy = 0;

    if (this.last) {
      const dx = x - this.last.x;
      const dy = y - this.last.y;
      if (dx === 0 && dy === 0) return;
      const d = Math.sqrt(dx * dx + dy * dy);
      vx = dx / d;
      vy = dy / d;
      force = Math.min(d * d * 12000, 1.4);
    }

    this.last = { x, y };
    this.trail.push({ x, y, age: 0, force, vx, vy });
  }

  update() {
    this.ctx.fillStyle = "rgba(0,0,0,1)";
    this.ctx.fillRect(0, 0, TOUCH_SIZE, TOUCH_SIZE);

    for (let i = this.trail.length - 1; i >= 0; i--) {
      const p = this.trail[i];
      p.age += 1;
      if (p.age > TOUCH_MAX_AGE) {
        this.trail.splice(i, 1);
        continue;
      }

      p.x += p.vx * p.force * 0.6;
      p.y += p.vy * p.force * 0.6;
      const life = 1 - p.age / TOUCH_MAX_AGE;
      const intensity = life * life * p.force * 0.55;
      const r = TOUCH_RADIUS * (0.6 + p.force * 0.4);

      const g = this.ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, r);
      g.addColorStop(0, `rgba(255,255,255,${intensity})`);
      g.addColorStop(0.4, `rgba(255,255,255,${intensity * 0.35})`);
      g.addColorStop(1, "rgba(255,255,255,0)");
      this.ctx.fillStyle = g;
      this.ctx.beginPath();
      this.ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
      this.ctx.fill();
    }

    this.texture.needsUpdate = true;
  }

  dispose() {
    this.texture.dispose();
  }
}

const vertexShader = `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const fragmentShader = `
  varying vec2 vUv;
  uniform float uTime;
  uniform vec2 uResolution;
  uniform vec3 uColor1;
  uniform vec3 uColor2;
  uniform vec3 uColor3;
  uniform float uSpeed;
  uniform float uIntensity;
  uniform sampler2D uTouchTexture;
  uniform float uGrainIntensity;

  float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
  }

  vec2 rotate(vec2 uv, float angle) {
    float s = sin(angle);
    float c = cos(angle);
    mat2 m = mat2(c, -s, s, c);
    return m * (uv - 0.5) + 0.5;
  }

  float field(vec2 uv, vec2 center, float radius) {
    float d = distance(uv, center);
    return smoothstep(radius, radius * 0.15, d);
  }

  void main() {
    vec2 touch = texture2D(uTouchTexture, vUv).rg;
    vec2 uv = vUv;
    uv += (touch - 0.5) * 0.06;
    uv = rotate(uv, sin(uTime * 0.08) * 0.12);

    float t = uTime * uSpeed;

    vec2 c1 = vec2(0.28 + sin(t * 0.31) * 0.14, 0.62 + cos(t * 0.27) * 0.12);
    vec2 c2 = vec2(0.72 + cos(t * 0.24) * 0.13, 0.38 + sin(t * 0.29) * 0.14);
    vec2 c3 = vec2(0.5 + sin(t * 0.19) * 0.18, 0.5 + cos(t * 0.22) * 0.16);
    vec2 c4 = vec2(0.18 + cos(t * 0.17) * 0.1, 0.28 + sin(t * 0.21) * 0.11);
    vec2 c5 = vec2(0.82 + sin(t * 0.15) * 0.09, 0.72 + cos(t * 0.18) * 0.1);

    float f1 = field(uv, c1, 0.55);
    float f2 = field(uv, c2, 0.52);
    float f3 = field(uv, c3, 0.48);
    float f4 = field(uv, c4, 0.45);
    float f5 = field(uv, c5, 0.42);

    vec3 deepBlue = uColor1;
    vec3 cyan = uColor2;
    vec3 emerald = uColor3;

    vec3 col = mix(deepBlue, cyan, f1);
    col = mix(col, emerald, f2 * 0.85);
    col = mix(col, cyan, f3 * 0.7);
    col = mix(col, deepBlue, f4 * 0.5);
    col = mix(col, emerald, f5 * 0.6);

    col = mix(col, cyan, smoothstep(0.0, 1.0, uv.y) * 0.25);
    col = mix(col, deepBlue, smoothstep(1.0, 0.0, uv.x) * 0.15);
    col *= uIntensity;

    float grain = (hash(uv * uResolution + uTime * 0.02) - 0.5) * uGrainIntensity;
    col += grain;

    gl_FragColor = vec4(col, 1.0);
  }
`;

function LiquidGradient() {
  const { size, viewport } = useThree();
  const touch = useMemo(() => new TouchTexture(), []);
  const mat = useMemo(
    () =>
      new THREE.ShaderMaterial({
        uniforms: {
          uTime: { value: 0 },
          uResolution: { value: new THREE.Vector2(size.width, size.height) },
          uColor1: { value: new THREE.Vector3(0.1, 0.38, 0.72) },
          uColor2: { value: new THREE.Vector3(0.18, 0.72, 0.82) },
          uColor3: { value: new THREE.Vector3(0.2, 0.78, 0.58) },
          uSpeed: { value: 0.28 },
          uIntensity: { value: 1.05 },
          uTouchTexture: { value: touch.texture },
          uGrainIntensity: { value: 0.035 },
        },
        vertexShader,
        fragmentShader,
        depthWrite: false,
        depthTest: false,
      }),
    [size.height, size.width, touch.texture],
  );

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      touch.addTouch(e.clientX / window.innerWidth, e.clientY / window.innerHeight);
    };
    const onTouch = (e: TouchEvent) => {
      const t = e.touches[0];
      if (!t) return;
      touch.addTouch(t.clientX / window.innerWidth, t.clientY / window.innerHeight);
    };
    window.addEventListener("mousemove", onMove, { passive: true });
    window.addEventListener("touchmove", onTouch, { passive: true });
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("touchmove", onTouch);
      touch.dispose();
    };
  }, [touch]);

  useFrame((_, delta) => {
    mat.uniforms.uTime.value += Math.min(delta, 0.1);
    mat.uniforms.uResolution.value.set(size.width, size.height);
    touch.update();
  });

  return (
    <mesh scale={[viewport.width, viewport.height, 1]}>
      <planeGeometry args={[1, 1]} />
      <primitive object={mat} attach="material" />
    </mesh>
  );
}

export function GradientBackground() {
  return (
    <div className="pointer-events-none absolute inset-0 -z-0 overflow-hidden">
      <Canvas
        orthographic
        camera={{ zoom: 1, position: [0, 0, 1], near: 0.1, far: 10 }}
        dpr={[1, 1.5]}
        gl={{
          antialias: true,
          alpha: false,
          powerPreference: "high-performance",
          stencil: false,
          depth: false,
        }}
        style={{ width: "100%", height: "100%" }}
      >
        <LiquidGradient />
      </Canvas>
    </div>
  );
}
