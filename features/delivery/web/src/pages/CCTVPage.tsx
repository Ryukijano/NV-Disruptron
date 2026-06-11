import { useEffect, useState } from "react";
import { getApiConfig } from "@/api/config";
import { DetectionOverlay, type Detection } from "@/components/vision/DetectionOverlay";
import { Activity, AlertTriangle, CheckCircle, Loader2, MapPin } from "lucide-react";

const BASE = getApiConfig().baseUrl;

type Camera = {
  id: string;
  name: string;
  lat: number;
  lon: number;
  image_url: string;
  video_url?: string;
  available?: boolean;
};

type AnalyzeResult = {
  camera_id: string;
  camera_name: string;
  image_url: string;
  detections: Detection[];
  detection_count: number;
  model: string;
};

export function CCTVPage() {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCamera, setSelectedCamera] = useState<Camera | null>(null);
  const [analyzeResult, setAnalyzeResult] = useState<AnalyzeResult | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${BASE}/v1/livefeed/cameras?limit=60`)
      .then((r) => r.json())
      .then((data: Camera[]) => {
        setCameras(data);
        setLoading(false);
      })
      .catch(() => {
        setError("Failed to load cameras");
        setLoading(false);
      });
  }, []);

  const handleAnalyze = async (camera: Camera) => {
    setSelectedCamera(camera);
    setAnalyzing(true);
    setAnalyzeResult(null);
    setError(null);
    try {
      const res = await fetch(`${BASE}/v1/livefeed/cameras/${camera.id}/analyze`, {
        method: "POST",
      });
      if (!res.ok) throw new Error("Analysis failed");
      const data: AnalyzeResult = await res.json();
      setAnalyzeResult(data);
    } catch {
      setError("Analysis failed — model may be warming up or camera offline.");
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <div className="h-full overflow-y-auto px-5 py-4 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-[14px] font-semibold text-white/90 flex items-center gap-2">
          <Activity size={15} className="text-[#0EA5E9]" />
          TfL JamCam Network
        </h1>
        <span className="text-[11px] text-white/30">
          {cameras.length} cameras
        </span>
      </div>

      {loading && (
        <div className="flex items-center justify-center py-12 text-white/30 text-[12px]">
          <Loader2 size={16} className="animate-spin mr-2" />
          Loading camera registry…
        </div>
      )}

      {error && !selectedCamera && (
        <div className="glass-panel p-3 text-[12px] text-red-300 flex items-center gap-2">
          <AlertTriangle size={14} />
          {error}
        </div>
      )}

      {/* Camera grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
        {cameras.map((cam) => (
          <button
            key={cam.id}
            onClick={() => {
              setSelectedCamera(cam);
              setAnalyzeResult(null);
              setError(null);
            }}
            className={`text-left glass-panel p-2 rounded-lg transition-all hover:bg-white/[0.04] ${
              selectedCamera?.id === cam.id ? "ring-1 ring-[#0EA5E9]" : ""
            }`}
          >
            <div className="relative rounded-md overflow-hidden bg-black/40 aspect-video mb-2">
              <img
                src={cam.image_url + "?t=" + Date.now()}
                alt={cam.name}
                className="w-full h-full object-cover"
                loading="lazy"
                onError={(e) => {
                  (e.target as HTMLImageElement).style.display = "none";
                }}
              />
              <div className="absolute top-1 right-1">
                {cam.available !== false ? (
                  <span className="flex items-center gap-1 px-1 py-[2px] rounded bg-green-500/20 text-green-300 text-[8px] font-medium">
                    <CheckCircle size={8} /> Live
                  </span>
                ) : (
                  <span className="flex items-center gap-1 px-1 py-[2px] rounded bg-red-500/20 text-red-300 text-[8px] font-medium">
                    <AlertTriangle size={8} /> Offline
                  </span>
                )}
              </div>
            </div>
            <div className="text-[10px] text-white/70 truncate font-medium">
              {cam.name}
            </div>
            <div className="text-[9px] text-white/30 flex items-center gap-1 mt-0.5">
              <MapPin size={8} />
              {cam.lat?.toFixed(4)}, {cam.lon?.toFixed(4)}
            </div>
          </button>
        ))}
      </div>

      {/* Detail panel */}
      {selectedCamera && (
        <div className="glass-panel p-4 rounded-xl space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-[13px] font-medium text-white/90">
                {selectedCamera.name}
              </h2>
              <p className="text-[10px] text-white/30 mt-0.5">
                {selectedCamera.id}
              </p>
            </div>
            <button
              onClick={() => {
                setSelectedCamera(null);
                setAnalyzeResult(null);
              }}
              className="text-white/30 hover:text-white/60 text-[11px]"
            >
              Close
            </button>
          </div>

          {!analyzing && !analyzeResult && !error && (
            <button
              onClick={() => handleAnalyze(selectedCamera)}
              className="w-full py-2 rounded-lg bg-[#0EA5E9]/20 hover:bg-[#0EA5E9]/30 text-[#0EA5E9] text-[12px] font-medium transition-all flex items-center justify-center gap-2"
            >
              <Activity size={14} />
              Run LocateAnything-3B Analysis
            </button>
          )}

          {analyzing ? (
            <div className="flex items-center justify-center py-8 text-white/30 text-[12px]">
              <Loader2 size={16} className="animate-spin mr-2" />
              Running LocateAnything-3B detection…
            </div>
          ) : analyzeResult ? (
            <div className="space-y-3">
              <DetectionOverlay
                imageUrl={analyzeResult.image_url + "?t=" + Date.now()}
                detections={analyzeResult.detections}
              />
              <div className="flex items-center gap-2 text-[10px] text-white/40">
                <span className="px-1.5 py-0.5 rounded bg-white/[0.04]">
                  {analyzeResult.model}
                </span>
                <span>
                  {analyzeResult.detection_count} detection
                  {analyzeResult.detection_count !== 1 ? "s" : ""}
                </span>
              </div>
              {analyzeResult.detections.length > 0 && (
                <div className="space-y-1">
                  {analyzeResult.detections.map((det, i) => (
                    <div
                      key={i}
                      className="flex items-center justify-between text-[11px] px-2 py-1 rounded bg-white/[0.03]"
                    >
                      <span className="text-white/70">{det.label}</span>
                      <span className="text-white/40">
                        {Math.round(det.confidence * 100)}% · {det.category}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : error ? (
            <div className="text-[12px] text-red-300 flex items-center gap-2 py-4">
              <AlertTriangle size={14} />
              {error}
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
