import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { AnimatePresence, motion } from "framer-motion";
import { Button } from "@nextui-org/react";
import { Volume2, VolumeX } from "@deemlol/next-icons";
import { useMapState } from "@/providers/MapStateProvider";
import { useLiveSession } from "@/hooks/useLiveSession";
import { useVoiceInput } from "@/hooks/useVoiceInput";
import { VoiceControls } from "@/components/live/VoiceControls";
import { TextInputBar } from "@/components/live/TextInputBar";
import { GeminiVisualizer } from "@/components/live/GeminiVisualizer";
import { TacticalCard } from "@/components/tactical/TacticalCard";
import { VideoDetectionOverlay } from "@/components/tactical/VideoDetectionOverlay";
import { DetectionOverlay } from "@/components/vision/DetectionOverlay";
import { useTacticalPanels, type TacticalPanelKind } from "@/providers/TacticalPanelProvider";
import { FlowParticleLayer } from "@/lib/flowLayer";

// Dark, dramatic 3D map style with building extrusions, sky, and fog
// Uses OpenFreeMap vector tiles which contain real OSM building height data
const DARK_3D_STYLE = {
  version: 8 as const,
  sources: {
    carto: {
      type: "raster" as const,
      tiles: [
        "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png",
        "https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png",
        "https://c.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png",
      ],
      tileSize: 256,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>',
    },
    openfreemap: {
      type: "vector" as const,
      url: "https://tiles.openfreemap.org/planet",
    },
    terrainSource: {
      type: "raster-dem" as const,
      url: "https://demotiles.maplibre.org/terrain-tiles/tiles.json",
      tileSize: 256,
    },
  },
  layers: [
    {
      id: "carto-dark",
      type: "raster" as const,
      source: "carto",
      minzoom: 0,
      maxzoom: 22,
    },
    {
      id: "3d-buildings",
      type: "fill-extrusion" as const,
      source: "openfreemap",
      "source-layer": "building",
      minzoom: 12,
      filter: ["!=", ["get", "hide_3d"], true],
      paint: {
        "fill-extrusion-color": [
          "interpolate",
          ["linear"],
          ["get", "render_height"],
          0, "#0B1220",
          30, "#1a2744",
          80, "#2d4a6f",
          200, "#4a7ab8",
        ],
        "fill-extrusion-height": [
          "interpolate",
          ["linear"],
          ["zoom"],
          14, 0,
          15.5, ["get", "render_height"],
        ],
        "fill-extrusion-base": ["coalesce", ["get", "render_min_height"], 0],
        "fill-extrusion-opacity": 0.92,
        "fill-extrusion-vertical-gradient": true,
      },
    },
    {
      id: "building-edges",
      type: "line" as const,
      source: "openfreemap",
      "source-layer": "building",
      minzoom: 14,
      filter: ["!=", ["get", "hide_3d"], true],
      paint: {
        "line-color": "#0EA5E9",
        "line-width": 0.5,
        "line-opacity": 0.15,
      },
    },
  ],
};

const COMPUTE_LABELS: Record<string, string> = {
  hazard: "hazard density",
  disruption: "disruption heatmap",
  video: "vision detections",
  live: "live camera feed",
  audio: "acoustic signals",
  station: "station accessibility",
  route: "step-free route",
};

export function MapPage() {
  const mapContainer = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const chatEndRef = useRef<HTMLDivElement | null>(null);
  const flowLayerRef = useRef<FlowParticleLayer | null>(null);
  
  const [loading, setLoading] = useState(true);
  const [hazardCount, setHazardCount] = useState(0);
  const [viewMode, setViewMode] = useState<"3d" | "flat">("3d");
  
  // Local overlay panel visibility state
  const [isAssistantExpanded, setIsAssistantExpanded] = useState(false);
  const [filterType, setFilterType] = useState<"lifts" | "escalators" | "toilets">("lifts");

  // Shared global navigation states from MapStateProvider
  const {
    isRoutingActive,
    setIsRoutingActive,
    setSearchQuery,
    selectedStation,
    setSelectedStation,
    showDisruptionAlert,
    setShowDisruptionAlert,
    routeCoordinates,
    setRouteCoordinates,
    detectionFeed,
  } = useMapState();

  // Active AI Link session hooks
  const {
    lines,
    state: activeState,
    send,
    setListening,
    ttsEnabled,
    toggleTts,
  } = useLiveSession();

  // Agent-driven tactical panels
  const { activePanels, activeKind } = useTacticalPanels();

  // Visualization compute state — shows "computing" before overlays render
  const [computingKind, setComputingKind] = useState<TacticalPanelKind | null>(null);

  // Capture MapLibre errors for visible debug overlay
  const [mapErrors, setMapErrors] = useState<string[]>([]);

  // Voice recording integration
  const voice = useVoiceInput((text) => {
    setListening(false);
    send(text);
  });

  const onToggleMic = () => {
    if (voice.listening || voice.transcribing) {
      voice.stop();
      setListening(false);
    } else {
      setListening(true);
      voice.toggle();
    }
  };

  // Video upload state
  const [videoUploading, setVideoUploading] = useState(false);
  const [videoEvents, setVideoEvents] = useState<Array<{
    event_id: string;
    category: string;
    label: string;
    duration_sec: number;
    lat: number | null;
    lon: number | null;
    timestamp: string;
  }>>([]);
  const [selectedVideoEvent, setSelectedVideoEvent] = useState<string | null>(null);

  // Live TfL JamCam feed state
  const [liveFeedRunning, setLiveFeedRunning] = useState(false);
  const [liveObservations, setLiveObservations] = useState<Array<{
    observation_id: string;
    camera_name: string;
    crowd_density: string;
    step_free_access: string;
    platform_condition: string;
    mobility_impact: string;
    recommended_action: string;
    confidence: number;
    timestamp: string;
  }>>([]);

  // Audio ingestion state
  // Camera popup state
  const [cameraPopup, setCameraPopup] = useState<{
    camera_id: string;
    camera_name: string;
    lat: number;
    lon: number;
    image_url?: string;
    video_url?: string;
  } | null>(null);

  const [audioRecording, setAudioRecording] = useState(false);
  const [audioAnalyzing, setAudioAnalyzing] = useState(false);
  const [audioObservations, setAudioObservations] = useState<Array<{
    observation_id: string;
    soundscape_type: string;
    crowd_level: string;
    detected_sounds: string[];
    accessibility_relevance: string;
    incident_indicators: string[];
    environment_assessment: string;
    recommended_action: string;
    confidence: number;
    timestamp: string;
  }>>([]);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  const startAudioRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];
      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };
      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: "audio/webm" });
        setAudioAnalyzing(true);
        try {
          const formData = new FormData();
          formData.append("audio", audioBlob, "recording.webm");
          const res = await fetch("/api/v1/audio/analyze", { method: "POST", body: formData });
          const obs = await res.json();
          if (obs.observation_id) {
            setAudioObservations((prev) => [obs, ...prev]);
            fetch("/api/v1/geo/audio-observations")
              .then((r) => r.json())
              .then((geojson) => {
                const map = mapRef.current;
                if (!map) return;
                if (map.getSource("audio-observations")) {
                  (map.getSource("audio-observations") as maplibregl.GeoJSONSource).setData(geojson);
                }
              });
          }
        } catch (err) {
          console.error("Audio analysis failed:", err);
        } finally {
          setAudioAnalyzing(false);
        }
        stream.getTracks().forEach((t) => t.stop());
      };
      mediaRecorder.start();
      setAudioRecording(true);
    } catch (err) {
      console.error("Microphone access failed:", err);
    }
  };

  const stopAudioRecording = () => {
    mediaRecorderRef.current?.stop();
    setAudioRecording(false);
  };

  const handleRunLiveFeed = async () => {
    setLiveFeedRunning(true);
    try {
      const res = await fetch("/api/v1/livefeed/run", { method: "POST" });
      const observations = await res.json();
      if (Array.isArray(observations) && observations.length > 0) {
        setLiveObservations(observations);
        // Refresh map layer
        fetch("/api/v1/geo/live-observations")
          .then((r) => r.json())
          .then((geojson) => {
            const map = mapRef.current;
            if (!map) return;
            if (map.getSource("live-observations")) {
              (map.getSource("live-observations") as maplibregl.GeoJSONSource).setData(geojson);
            }
          });
      }
    } catch (err) {
      console.error("Live feed run failed:", err);
    } finally {
      setLiveFeedRunning(false);
    }
  };

  const handleVideoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setVideoUploading(true);
    try {
      const formData = new FormData();
      formData.append("video", file);
      const res = await fetch("/api/v1/video/upload", {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      if (data.persistent_events > 0) {
        // Refresh video events layer
        fetch("/api/v1/geo/video-events")
          .then((r) => r.json())
          .then((geojson) => {
            const map = mapRef.current;
            if (!map) return;
            if (map.getSource("video-events")) {
              (map.getSource("video-events") as maplibregl.GeoJSONSource).setData(geojson);
            }
          });
        // Also refresh list
        fetch("/api/v1/video/events?limit=20")
          .then((r) => r.json())
          .then((events) => setVideoEvents(events));
      }
    } catch (err) {
      console.error("Video upload failed:", err);
    } finally {
      setVideoUploading(false);
    }
  };

  const busy = activeState === "thinking" || activeState === "speaking";
  const visualizerState = voice.listening || voice.transcribing ? "listening" : activeState;

  // Auto-scroll chat console messages to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [lines]);

  useEffect(() => {
    console.log("[MapPage] mount effect running");
    if (!mapContainer.current || mapRef.current) {
      console.log("[MapPage] skipping: no container or map already exists");
      return;
    }

    try {
      const map = new maplibregl.Map({
        container: mapContainer.current,
        style: DARK_3D_STYLE as any,
        center: [-0.1276, 51.5074],
        zoom: 13,
        pitch: 60,
        bearing: -30,
        attributionControl: false,
      });

      mapRef.current = map;
      console.log("[MapPage] MapLibre instance created");

      map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");
      map.addControl(
        new maplibregl.NavigationControl({ visualizePitch: true }),
        "top-right"
      );

      // Fallback: if load takes too long, clear spinner anyway
      const loadTimeout = window.setTimeout(() => {
        console.warn("[MapPage] Load timeout — clearing spinner");
        setLoading(false);
      }, 8000);

      map.on("load", () => {
        console.log("[MapPage] Map loaded");
        window.clearTimeout(loadTimeout);
        setLoading(false);

        // Dramatic sky + fog atmosphere
        try {
          map.setSky({
            "sky-color": "#0B1220",
            "sky-horizon-blend": 0.6,
            "horizon-color": "#1a2744",
            "horizon-fog-blend": 0.4,
            "fog-color": "#08090C",
            "fog-ground-blend": 0.6,
            "atmosphere-blend": ["interpolate", ["linear"], ["zoom"], 0, 1, 10, 1, 12, 0],
          });
        } catch (skyErr) {
          console.warn("[MapPage] setSky failed:", skyErr);
        }

        // Terrain — add dynamically after load so a missing DEM doesn't block the map
        if (map.getSource("terrainSource")) {
          try {
            map.setTerrain({ source: "terrainSource", exaggeration: 1.2 });
            map.addControl(
              new maplibregl.TerrainControl({ source: "terrainSource", exaggeration: 1.2 })
            );
          } catch (terrErr) {
            console.warn("[MapPage] Terrain setup failed:", terrErr);
          }
        }

        // Initialize heatflow particle layer (starts on demand)
        flowLayerRef.current = new FlowParticleLayer(map);

        // Camera popup on live observation marker click
        map.on("click", "live-obs-marker", (e) => {
          const feat = e.features?.[0];
          if (!feat) return;
          const props = feat.properties || {};
          const camId = props.camera_id || "";
          setCameraPopup({
            camera_id: camId,
            camera_name: props.camera_name || "TfL Camera",
            lat: (feat.geometry as any).coordinates[1],
            lon: (feat.geometry as any).coordinates[0],
          });
          // Fetch camera details with image/video URLs
          if (camId) {
            fetch(`/api/v1/livefeed/cameras/${encodeURIComponent(camId)}`)
              .then((r) => r.json())
              .then((data) => {
                if (data.image_url || data.video_url) {
                  setCameraPopup((prev) =>
                    prev && prev.camera_id === camId
                      ? { ...prev, image_url: data.image_url, video_url: data.video_url }
                      : prev
                  );
                }
              })
              .catch(() => {});
          }
        });
      });

      map.on("error", (e) => {
        const extract = (x: any): string => {
          if (x instanceof Error) return x.message;
          if (typeof x === "string") return x;
          if (x && typeof x === "object") {
            const msg = x.message || x.error?.message || x.reason || JSON.stringify(x);
            return msg;
          }
          return String(x);
        };
        const msg = extract(e?.error ?? e);
        console.error("[MapPage] MapLibre error:", msg);
        setMapErrors((prev) => [...prev.slice(-4), msg]);
      });

      return () => {
        console.log("[MapPage] cleanup: removing map");
        flowLayerRef.current?.destroy();
        flowLayerRef.current = null;
        map.remove();
        mapRef.current = null;
      };
    } catch (err) {
      console.error("[MapPage] Failed to create map:", err);
      setLoading(false);
    }
  }, []);

  // Toggle between 3D isometric and flat 2D
  useEffect(() => {
    const map = mapRef.current;
    if (!map || loading || !map.isStyleLoaded() || !map.getLayer("3d-buildings")) {
      return;
    }
    if (viewMode === "3d") {
      map.easeTo({ pitch: 60, bearing: -30, duration: 1200 });
      map.setLayoutProperty("3d-buildings", "visibility", "visible");
      map.setLayoutProperty("building-edges", "visibility", "visible");
      if (map.getSource("terrainSource")) {
        map.setTerrain({ source: "terrainSource", exaggeration: 1.2 });
      }
      map.setSky({
        "sky-color": "#0B1220",
        "sky-horizon-blend": 0.6,
        "horizon-color": "#1a2744",
        "horizon-fog-blend": 0.4,
        "fog-color": "#08090C",
        "fog-ground-blend": 0.6,
      });
    } else {
      map.easeTo({ pitch: 0, bearing: 0, duration: 1200 });
      map.setLayoutProperty("3d-buildings", "visibility", "none");
      map.setLayoutProperty("building-edges", "visibility", "none");
      map.setTerrain(null);
      map.setSky({ "sky-color": "#000000", "sky-horizon-blend": 0, "horizon-color": "#000000", "horizon-fog-blend": 0, "fog-color": "#000000", "fog-ground-blend": 0 });
    }
  }, [viewMode, loading]);

  // Reactive Effect: Handle Routing Layer and Panning
  useEffect(() => {
    const map = mapRef.current;
    if (!map || loading) return;

    if (isRoutingActive && routeCoordinates.length > 0) {
      // Draw routing pathway dynamically using GeoJSON source from backend TfL data
      const routeGeoJSON = {
        type: "Feature" as const,
        properties: {},
        geometry: {
          type: "LineString" as const,
          coordinates: routeCoordinates,
        },
      };

      if (map.getSource("active-route")) {
        (map.getSource("active-route") as maplibregl.GeoJSONSource).setData(routeGeoJSON);
      } else {
        map.addSource("active-route", { type: "geojson", data: routeGeoJSON });
        
        // Core line
        map.addLayer({
          id: "active-route-core",
          type: "line",
          source: "active-route",
          paint: {
            "line-color": "#10B981",
            "line-width": 3,
            "line-opacity": 1,
          },
        });

        // Mid glow
        map.addLayer({
          id: "active-route-mid",
          type: "line",
          source: "active-route",
          paint: {
            "line-color": "#10B981",
            "line-width": 8,
            "line-opacity": 0.5,
            "line-blur": 2,
          },
        });

        // Outer bloom
        map.addLayer({
          id: "active-route-bloom",
          type: "line",
          source: "active-route",
          paint: {
            "line-color": "#10B981",
            "line-width": 18,
            "line-opacity": 0.15,
            "line-blur": 8,
          },
        });

        // Animated flowing particles along route (small dashes)
        map.addLayer({
          id: "active-route-flow",
          type: "line",
          source: "active-route",
          paint: {
            "line-color": "#ffffff",
            "line-width": 2,
            "line-opacity": 0.7,
            "line-dasharray": [0.3, 1.5],
          },
        });
      }

      // Zoom and orient map to fit routing perspective
      map.flyTo({
        center: [-0.0733, 51.5249],
        zoom: 13.5,
        pitch: 45,
        bearing: 15,
        duration: 1500
      });
    } else {
      if (map.getSource("active-route")) {
        try {
          ["active-route-core", "active-route-mid", "active-route-bloom", "active-route-flow"].forEach((id) => {
            if (map.getLayer(id)) map.removeLayer(id);
          });
          map.removeSource("active-route");
        } catch (e) {
          // ignore
        }
      }
    }
  }, [isRoutingActive, routeCoordinates, loading]);

  // Reactive Effect: Zoom to selected station for Deep Dive
  useEffect(() => {
    const map = mapRef.current;
    if (!map || loading || !selectedStation) return;

    let coords: [number, number] = [-0.1276, 51.5074];
    if (selectedStation.includes("Bank")) {
      coords = [-0.1256, 51.5084];
    } else if (selectedStation.includes("Stratford")) {
      coords = [-0.0210, 51.5414];
    } else if (selectedStation.includes("London Bridge")) {
      coords = [-0.0874, 51.5048];
    }

    map.flyTo({
      center: coords,
      zoom: 16.5,
      pitch: 70,
      bearing: 45,
      duration: 1500
    });
  }, [selectedStation, loading]);

  // Reactive Effect: Pan map to active disruption zone
  useEffect(() => {
    const map = mapRef.current;
    if (!map || loading || !showDisruptionAlert) return;

    map.flyTo({
      center: [-0.1256, 51.5084], // Central zone/Bank
      zoom: 15.5,
      pitch: 65,
      bearing: -45,
      duration: 1200
    });
  }, [showDisruptionAlert, loading]);

  // Detection popups: render markers + popups on map for each detection in feed
  const detectionMarkersRef = useRef<Record<string, maplibregl.Marker>>({});
  useEffect(() => {
    const map = mapRef.current;
    if (!map || loading) return;
    const now = Date.now();
    const active = detectionFeed.filter((d) => d.expiresAt > now);
    const currentIds = new Set(active.map((d) => d.cameraId));

    // Remove expired markers
    for (const [id, marker] of Object.entries(detectionMarkersRef.current)) {
      if (!currentIds.has(id)) {
        marker.remove();
        delete detectionMarkersRef.current[id];
      }
    }

    for (const d of active) {
      if (detectionMarkersRef.current[d.cameraId]) continue;
      const el = document.createElement("div");
      el.className = "detection-marker";
      el.style.cssText = "width:14px;height:14px;border-radius:50%;background:#22D3EE;border:2px solid #fff;box-shadow:0 0 8px #22D3EE;cursor:pointer;";
      const marker = new maplibregl.Marker({ element: el }).setLngLat([d.lon, d.lat]).addTo(map);
      // Build popup HTML with bounding boxes
      const bboxOverlays = d.detections.map((det: any) => {
        const [x1, y1, x2, y2] = det.bbox;
        const left = x1 * 100;
        const top = y1 * 100;
        const width = (x2 - x1) * 100;
        const height = (y2 - y1) * 100;
        const colors: Record<string, string> = {
          car: "#0EA5E9", bus: "#8B5CF6", person: "#10B981", bicycle: "#F59E0B",
          truck: "#EC4899", van: "#6366F1", motorcycle: "#F97316", unknown: "#9CA3AF",
        };
        const color = colors[det.label] || colors.unknown;
        return `<div style="position:absolute;left:${left}%;top:${top}%;width:${width}%;height:${height}%;border:2px solid ${color};border-radius:2px;box-shadow:0 0 4px ${color}66;">
          <span style="position:absolute;top:-14px;left:0;background:${color};color:#fff;font-size:8px;padding:1px 3px;border-radius:2px;white-space:nowrap;">${det.label}</span>
        </div>`;
      }).join("");

      const popup = new maplibregl.Popup({ maxWidth: "280px" }).setHTML(
        `<div style="font-family:sans-serif;font-size:11px;color:#eee;background:#121214;border-radius:8px;padding:8px;">
          <div style="font-weight:600;margin-bottom:4px;color:#22D3EE;">${d.cameraName}</div>
          <div style="position:relative;width:240px;border-radius:6px;overflow:hidden;margin-bottom:6px;">
            <img src="${d.imageUrl}" style="width:100%;height:auto;display:block;" />
            ${bboxOverlays}
          </div>
          <div style="display:flex;gap:4px;flex-wrap:wrap;">
            ${d.detections.map((det: any) => `<span style="background:#1E293B;border-radius:4px;padding:2px 6px;font-size:10px;">${det.label}</span>`).join("")}
          </div>
          <div style="margin-top:4px;font-size:10px;color:#94A3B8;">${d.detections.length} objects detected</div>
        </div>`
      );
      marker.setPopup(popup);
      marker.getElement().addEventListener("click", () => popup.addTo(map));
      detectionMarkersRef.current[d.cameraId] = marker;
    }

    // Fly to newest detection
    if (active.length > 0) {
      const newest = active[active.length - 1];
      map.flyTo({
        center: [newest.lon, newest.lat],
        zoom: 15.5,
        pitch: 55,
        bearing: -20,
        duration: 1200,
      });
    }
  }, [detectionFeed, loading]);

  // Agent-driven camera panning: when tactical panel changes, fly camera to relevant zone
  useEffect(() => {
    const map = mapRef.current;
    if (!map || loading || !activeKind) return;

    // Only pan for agent-triggered kinds (not manual user interactions)
    if (activeKind === "station") {
      map.flyTo({
        center: [-0.1276, 51.5074], // Central London
        zoom: 14.5,
        pitch: 55,
        bearing: -20,
        duration: 1500,
      });
    } else if (activeKind === "disruption" || activeKind === "hazard") {
      map.flyTo({
        center: [-0.1256, 51.5084], // Bank / central disruption zone
        zoom: 14,
        pitch: 50,
        bearing: -30,
        duration: 1500,
      });
    } else if (activeKind === "route") {
      // Route panning is handled by the isRoutingActive effect above
    }
  }, [activeKind, loading]);

  // Start/stop heatflow particle animation - always active for congestion visualization
  useEffect(() => {
    if (!flowLayerRef.current || loading) return;
    // Always show heatflows for congestion visualization
    flowLayerRef.current.start();
  }, [loading]);

  // Auto-run live feed when the live panel appears with no data
  useEffect(() => {
    if (activeKind === "live" && liveObservations.length === 0 && !liveFeedRunning) {
      handleRunLiveFeed();
    }
  }, [activeKind, liveObservations.length, liveFeedRunning]);

  // Agent-gated visualization: hide everything, run compute, then reveal with transitions
  useEffect(() => {
    const map = mapRef.current;
    if (!map || loading) return;

    const allLayers = [
      "ward-fill", "ward-line", "station-markers",
      "hazard-glow", "hazard-core",
      "video-event-markers", "video-event-glow",
      "live-obs-marker", "live-obs-glow",
      "audio-obs-marker", "audio-obs-glow",
      "density-heatmap",
      "active-route-core", "active-route-mid", "active-route-bloom", "active-route-flow",
    ];
    const visibleByKind: Record<string, string[]> = {
      hazard: ["density-heatmap", "hazard-glow", "hazard-core"],
      disruption: ["density-heatmap", "hazard-glow", "hazard-core"],
      video: ["video-event-glow", "video-event-markers"],
      live: ["live-obs-glow", "live-obs-marker"],
      audio: ["audio-obs-glow", "audio-obs-marker"],
      station: ["ward-fill", "ward-line", "station-markers"],
      route: ["active-route-bloom", "active-route-mid", "active-route-core", "active-route-flow"],
    };

    // Hide every overlay layer immediately (base map stays clean)
    const hideAll = () => {
      for (const id of allLayers) {
        if (map.getLayer(id)) {
          try { map.setLayoutProperty(id, "visibility", "none"); } catch {}
        }
      }
    };

    const animateOpacity = (id: string, paintProp: string, target: number, durationMs: number) => {
      const start = performance.now();
      const step = (now: number) => {
        if (!map.getLayer(id)) return;
        const progress = Math.max(0, Math.min((now - start) / durationMs, 1));
        const eased = progress < 1 ? progress * (2 - progress) : 1;
        try {
          map.setPaintProperty(id, paintProp, Math.max(0, Math.min(target * eased, 1)));
        } catch {
          return;
        }
        if (progress < 1) {
          requestAnimationFrame(step);
        }
      };
      try {
        map.setPaintProperty(id, paintProp, 0);
      } catch {
        return;
      }
      requestAnimationFrame(step);
    };

    // Reveal a single layer with a type-appropriate fade/pop transition
    const revealLayer = (id: string) => {
      const layer = map.getLayer(id);
      if (!layer) return;
      try {
        map.setLayoutProperty(id, "visibility", "visible");
        if (layer.type === "heatmap") {
          animateOpacity(id, "heatmap-opacity", 0.6, 700);
        } else if (layer.type === "line") {
          const target = id === "active-route-core" ? 1 : id === "active-route-mid" ? 0.5 : 0.15;
          animateOpacity(id, "line-opacity", target, 650);
        } else if (layer.type === "circle") {
          const isGlow = id.includes("glow");
          animateOpacity(id, "circle-opacity", isGlow ? 0.1 : 1, 550);
        }
      } catch {}
    };

    // No active panel → clean base map
    if (!activeKind) {
      hideAll();
      setComputingKind(null);
      return;
    }

    let cancelled = false;
    hideAll();
    setComputingKind(activeKind);

    (async () => {
      // Brief compute window (represents agent tool-call + GPU calculation)
      await new Promise((r) => setTimeout(r, 750));
      if (cancelled) return;

      if (activeKind === "hazard" || activeKind === "disruption") {
        await loadHeatmapLayer(map);
        await loadHazardLayer(map);
      } else if (activeKind === "video") {
        await loadVideoEventsLayer(map);
      } else if (activeKind === "live") {
        await loadLiveObservationsLayer(map);
      } else if (activeKind === "audio") {
        await loadAudioObservationsLayer(map);
      } else if (activeKind === "station") {
        await loadWardLayer(map);
        await loadTfLStations(map);
      } else if (activeKind === "route" && !isRoutingActive) {
        setIsRoutingActive(true);
      }
      if (cancelled) return;

      setComputingKind(null);
      // Reveal only the layers for this kind, staggered for a sequential build-in
      const layers = visibleByKind[activeKind] || [];
      layers.forEach((id, i) => {
        window.setTimeout(() => {
          if (!cancelled) revealLayer(id);
        }, i * 120);
      });
    })();

    return () => {
      cancelled = true;
    };
  }, [activeKind, isRoutingActive, loading, setIsRoutingActive]);

  async function loadHazardLayer(map: maplibregl.Map) {
    try {
      const res = await fetch("/api/v1/geo/hazards");
      const geojson = await res.json();
      setHazardCount(geojson.features?.length || 0);

      if (!map.getSource("hazards")) {
        map.addSource("hazards", { type: "geojson", data: geojson });

        // Outer glow ring (static)
        map.addLayer({
          id: "hazard-glow",
          type: "circle",
          source: "hazards",
          paint: {
            "circle-radius": 22,
            "circle-color": "#EF4444",
            "circle-opacity": 0.08,
            "circle-stroke-width": 0,
          },
        });

        // Core marker
        map.addLayer({
          id: "hazard-core",
          type: "circle",
          source: "hazards",
          paint: {
            "circle-radius": 7,
            "circle-color": "#EF4444",
            "circle-stroke-width": 2,
            "circle-stroke-color": "#08090C",
          },
        });

        // Animated pulsing ring via rAF
        let hazardPulseTime = 0;
        const animateHazardPulse = () => {
          if (!map.getLayer("hazard-glow")) return;
          hazardPulseTime += 0.04;
          const radius = 18 + Math.sin(hazardPulseTime) * 6;
          const opacity = 0.06 + Math.sin(hazardPulseTime) * 0.04;
          map.setPaintProperty("hazard-glow", "circle-radius", radius);
          map.setPaintProperty("hazard-glow", "circle-opacity", opacity);
          requestAnimationFrame(animateHazardPulse);
        };
        requestAnimationFrame(animateHazardPulse);

        map.on("click", "hazard-core", (e) => {
          // Trigger disruption outbreak UI state
          setShowDisruptionAlert(true);
          setSelectedStation(null); // Close deep dive if open
          
          // Pan map to disruption zone
          map.flyTo({
            center: e.lngLat,
            zoom: 15.5,
            pitch: 65,
            bearing: -45,
            duration: 1200
          });
        });

        map.on("mouseenter", "hazard-core", () => {
          map.getCanvas().style.cursor = "pointer";
        });
        map.on("mouseleave", "hazard-core", () => {
          map.getCanvas().style.cursor = "";
        });
      } else {
        (map.getSource("hazards") as maplibregl.GeoJSONSource).setData(geojson);
      }
    } catch {
      // Graceful
    }
  }

  async function loadVideoEventsLayer(map: maplibregl.Map) {
    try {
      const res = await fetch("/api/v1/geo/video-events");
      const geojson = await res.json();
      if (!map.getSource("video-events")) {
        map.addSource("video-events", { type: "geojson", data: geojson });

        // Video event markers — diamond shape for temporal events
        map.addLayer({
          id: "video-event-markers",
          type: "circle",
          source: "video-events",
          paint: {
            "circle-radius": 7,
            "circle-color": "#A78BFA", // Violet for video-derived
            "circle-stroke-width": 2,
            "circle-stroke-color": "#08090C",
          },
        });

        map.addLayer({
          id: "video-event-glow",
          type: "circle",
          source: "video-events",
          paint: {
            "circle-radius": 20,
            "circle-color": "#A78BFA",
            "circle-opacity": 0.12,
            "circle-stroke-width": 0,
          },
        });

        let videoPulseTime = 0;
        const animateVideoPulse = () => {
          if (!map.getLayer("video-event-glow")) return;
          videoPulseTime += 0.035;
          map.setPaintProperty("video-event-glow", "circle-radius", 16 + Math.sin(videoPulseTime) * 5);
          map.setPaintProperty("video-event-glow", "circle-opacity", 0.08 + Math.sin(videoPulseTime) * 0.05);
          requestAnimationFrame(animateVideoPulse);
        };
        requestAnimationFrame(animateVideoPulse);

        // Click handler: open detection overlay for video event
        map.on("click", "video-event-markers", (e) => {
          const feat = e.features?.[0];
          if (!feat) return;
          const props = feat.properties || {};
          const eventId = props.event_id;
          if (eventId) {
            setSelectedVideoEvent(eventId);
          }
        });
        map.on("mouseenter", "video-event-markers", () => {
          map.getCanvas().style.cursor = "pointer";
        });
        map.on("mouseleave", "video-event-markers", () => {
          map.getCanvas().style.cursor = "";
        });
      } else {
        (map.getSource("video-events") as maplibregl.GeoJSONSource).setData(geojson);
      }
    } catch {
      // Graceful
    }
  }

  async function loadLiveObservationsLayer(map: maplibregl.Map) {
    try {
      const res = await fetch("/api/v1/geo/live-observations");
      const geojson = await res.json();
      if (!map.getSource("live-observations")) {
        map.addSource("live-observations", { type: "geojson", data: geojson });

        map.addLayer({
          id: "live-obs-marker",
          type: "circle",
          source: "live-observations",
          paint: {
            "circle-radius": 8,
            "circle-color": "#FBBF24", // Amber for live feed
            "circle-stroke-width": 2,
            "circle-stroke-color": "#08090C",
          },
        });

        map.addLayer({
          id: "live-obs-glow",
          type: "circle",
          source: "live-observations",
          paint: {
            "circle-radius": 22,
            "circle-color": "#FBBF24",
            "circle-opacity": 0.1,
            "circle-stroke-width": 0,
          },
        });

        let livePulseTime = 0;
        const animateLivePulse = () => {
          if (!map.getLayer("live-obs-glow")) return;
          livePulseTime += 0.03;
          map.setPaintProperty("live-obs-glow", "circle-radius", 18 + Math.sin(livePulseTime) * 6);
          map.setPaintProperty("live-obs-glow", "circle-opacity", 0.07 + Math.sin(livePulseTime) * 0.04);
          requestAnimationFrame(animateLivePulse);
        };
        requestAnimationFrame(animateLivePulse);
      } else {
        (map.getSource("live-observations") as maplibregl.GeoJSONSource).setData(geojson);
      }
    } catch {
      // Graceful
    }
  }

  async function loadAudioObservationsLayer(map: maplibregl.Map) {
    try {
      const res = await fetch("/api/v1/geo/audio-observations");
      const geojson = await res.json();
      if (!map.getSource("audio-observations")) {
        map.addSource("audio-observations", { type: "geojson", data: geojson });

        map.addLayer({
          id: "audio-obs-marker",
          type: "circle",
          source: "audio-observations",
          paint: {
            "circle-radius": 8,
            "circle-color": "#EC4899", // Pink for audio
            "circle-stroke-width": 2,
            "circle-stroke-color": "#08090C",
          },
        });

        map.addLayer({
          id: "audio-obs-glow",
          type: "circle",
          source: "audio-observations",
          paint: {
            "circle-radius": 22,
            "circle-color": "#EC4899",
            "circle-opacity": 0.1,
            "circle-stroke-width": 0,
          },
        });

        let audioPulseTime = 0;
        const animateAudioPulse = () => {
          if (!map.getLayer("audio-obs-glow")) return;
          audioPulseTime += 0.045;
          map.setPaintProperty("audio-obs-glow", "circle-radius", 18 + Math.sin(audioPulseTime) * 5);
          map.setPaintProperty("audio-obs-glow", "circle-opacity", 0.07 + Math.sin(audioPulseTime) * 0.04);
          requestAnimationFrame(animateAudioPulse);
        };
        requestAnimationFrame(animateAudioPulse);
      } else {
        (map.getSource("audio-observations") as maplibregl.GeoJSONSource).setData(geojson);
      }
    } catch {
      // Graceful
    }
  }

  async function loadWardLayer(map: maplibregl.Map) {
    try {
      const res = await fetch("/api/v1/geo/wards");
      const geojson = await res.json();
      if (geojson.features && geojson.features.length > 0) {
        if (!map.getSource("wards")) {
          map.addSource("wards", { type: "geojson", data: geojson });
          map.addLayer({
            id: "ward-fill",
            type: "fill",
            source: "wards",
            paint: {
              "fill-color": "#0EA5E9",
              "fill-opacity": 0.05,
            },
          });
          map.addLayer({
            id: "ward-line",
            type: "line",
            source: "wards",
            paint: {
              "line-color": "#0EA5E9",
              "line-width": 1,
              "line-opacity": 0.25,
            },
          });
        }
      }
    } catch {
      // Graceful
    }
  }

  async function loadTfLStations(map: maplibregl.Map) {
    try {
      const res = await fetch("/api/v1/geo/nearest-step-free?lat=51.5074&lon=-0.1278&radius=5000");
      const data = await res.json();
      const stations = data.stations || [];
      if (!stations.length) return;

      const features = stations.map((s: Record<string, unknown>) => ({
        type: "Feature" as const,
        geometry: {
          type: "Point" as const,
          coordinates: [s.lon, s.lat],
        },
        properties: {
          name: s.name,
          step_free: s.step_free ? "Yes" : "No",
        },
      }));

      map.addSource("stations", {
        type: "geojson",
        data: { type: "FeatureCollection" as const, features },
      });

      map.addLayer({
        id: "station-markers",
        type: "circle",
        source: "stations",
        paint: {
          "circle-radius": 7,
          "circle-color": [
            "case",
            ["==", ["get", "step_free"], "Yes"],
            "#10B981",
            "#F59E0B",
          ],
          "circle-stroke-width": 2,
          "circle-stroke-color": "#08090C",
        },
      });

      // Handle station click for Deep Dive Mode
      map.on("click", "station-markers", (e) => {
        const feat = e.features?.[0];
        if (!feat) return;
        const name = feat.properties?.name || "Transit Station Hub";
        
        setSelectedStation(name);
        setShowDisruptionAlert(false); // Close disruption alert if open
      });

      map.on("mouseenter", "station-markers", () => {
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", "station-markers", () => {
        map.getCanvas().style.cursor = "";
      });
    } catch {
      // Graceful
    }
  }

  async function loadHeatmapLayer(map: maplibregl.Map) {
    try {
      // Heatmap for disruption density using hazard + live data points
      const res = await fetch("/api/v1/geo/hazards");
      const geojson = await res.json();
      if (!map.getSource("density-heatmap")) {
        map.addSource("density-heatmap", { type: "geojson", data: geojson });
        map.addLayer({
          id: "density-heatmap",
          type: "heatmap",
          source: "density-heatmap",
          paint: {
            "heatmap-weight": 1,
            "heatmap-intensity": ["interpolate", ["linear"], ["zoom"], 0, 1, 13, 3],
            "heatmap-color": [
              "interpolate", ["linear"], ["heatmap-density"],
              0, "rgba(0,0,0,0)",
              0.2, "rgba(14,165,233,0.2)",
              0.5, "rgba(245,158,11,0.4)",
              1, "rgba(239,68,68,0.5)",
            ],
            "heatmap-radius": ["interpolate", ["linear"], ["zoom"], 0, 15, 13, 30],
            "heatmap-opacity": 0.6,
          },
        });
      } else {
        (map.getSource("density-heatmap") as maplibregl.GeoJSONSource).setData(geojson);
      }
    } catch {
      // Graceful
    }
  }

  const resetAllLayers = () => {
    setIsRoutingActive(false);
    setRouteCoordinates([]);
    setShowDisruptionAlert(false);
    setSelectedStation(null);
    setSearchQuery("");
  };

  return (
    <div className="flex h-screen w-full bg-[#0B0B0D] text-[#E8E8E8]">
      {/* Left: Map + all overlays */}
      <div className="relative flex-1 h-full overflow-hidden">
        {/* Map canvas — fills the left panel */}
        <div ref={mapContainer} className="absolute inset-0" />
        {loading && (
          <div className="absolute inset-0 z-20 flex items-center justify-center bg-[#0B0B0D]/90 backdrop-blur-sm">
            <div className="flex items-center gap-2 text-[13px] text-white/50">
              <div className="h-2 w-2 rounded-full bg-[#0EA5E9] animate-pulse" />
              Loading map...
            </div>
          </div>
        )}

        {/* Computing overlay */}
        <AnimatePresence>
          {computingKind && (
            <motion.div
              key="computing-pill"
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.25 }}
              className="absolute top-4 left-1/2 -translate-x-1/2 z-20 glass-panel px-4 py-2 flex items-center gap-2.5"
            >
              <span className="relative flex h-3 w-3">
                <span className="absolute inline-flex h-full w-full rounded-full bg-[#0EA5E9] opacity-60 animate-ping" />
                <span className="relative inline-flex h-3 w-3 rounded-full bg-[#0EA5E9]" />
              </span>
              <span className="text-[12px] text-white/70">
                Computing {COMPUTE_LABELS[computingKind] ?? "data"}…
              </span>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Debug: MapLibre errors */}
        {mapErrors.length > 0 && (
          <div className="absolute bottom-16 left-4 z-30 max-w-sm">
            {mapErrors.map((err, i) => (
              <div
                key={i}
                className="mb-1 rounded bg-[#EF4444]/15 border border-[#EF4444]/30 px-3 py-1.5 text-[10px] text-[#EF4444] font-mono"
              >
                {err}
              </div>
            ))}
          </div>
        )}

        {/* Bottom-left status */}
        <div className="absolute bottom-6 left-4 z-10 flex items-center gap-3 glass-panel px-3 py-1.5">
          <span className="flex items-center gap-1.5 text-[11px] text-white/50">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
            {hazardCount} hazards
          </span>
        </div>

        {/* Top Left - View toggle (away from sidebar edge) */}
        <div className="absolute top-4 left-4 z-10 flex gap-2">
          {isRoutingActive && (
            <button
              onClick={resetAllLayers}
              className="glass-panel px-2.5 py-1.5 text-[11px] font-medium text-white/70 hover:text-white transition-all duration-200"
            >
              Clear route
            </button>
          )}
          <button
            onClick={() => setViewMode(viewMode === "3d" ? "flat" : "3d")}
            className="glass-panel px-2.5 py-1.5 text-[11px] font-medium text-white/70 hover:text-white transition-all duration-200"
          >
            {viewMode === "3d" ? "2D" : "3D"}
          </button>
        </div>

        {/* Chat Assistant — bottom-left, always visible */}
        <div className="fixed bottom-6 left-6 z-50">
          <AnimatePresence>
            {!isAssistantExpanded ? (
              <motion.button
                key="collapsed-bubble"
                layoutId="assistant-container"
                onClick={() => setIsAssistantExpanded(true)}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                animate={busy ? { scale: [1, 1.05, 1] } : {}}
                transition={busy ? { duration: 1.5, repeat: Infinity } : {}}
                className="flex items-center gap-2 bg-[#121214]/90 hover:bg-[#1a1a1c] border border-white/10 text-white/70 px-4 py-2.5 rounded-full text-[12px] font-medium transition-all cursor-pointer"
              >
                {busy ? (
                  <motion.span
                    className="flex gap-0.5"
                    animate={{ opacity: [0.5, 1, 0.5] }}
                    transition={{ duration: 1, repeat: Infinity }}
                  >
                    <span className="h-1.5 w-1.5 rounded-full bg-[#0EA5E9]" />
                    <span className="h-1.5 w-1.5 rounded-full bg-[#0EA5E9]" />
                    <span className="h-1.5 w-1.5 rounded-full bg-[#0EA5E9]" />
                  </motion.span>
                ) : (
                  <span className="h-2 w-2 rounded-full bg-[#0EA5E9]" />
                )}
                {busy ? "Thinking..." : "Ask anything"}
              </motion.button>
          ) : (
            <motion.div
              key="expanded-assistant"
              layoutId="assistant-container"
              className="glass-panel w-[min(480px,calc(100vw-6rem))] max-h-[480px] flex flex-col p-4 overflow-hidden rounded-xl bg-[#121214]/80"
            >
              {/* Header */}
              <div className="flex items-center justify-between pb-2.5">
                <span className="text-[12px] font-medium text-white/70 flex items-center gap-1.5">
                  <span className="h-1.5 w-1.5 rounded-full bg-[#0EA5E9]" />
                  Assistant
                </span>
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="light"
                    isIconOnly
                    className="text-white/40 hover:text-white/70 min-w-0 h-6 w-6"
                    onPress={toggleTts}
                  >
                    {ttsEnabled ? <Volume2 size={15} /> : <VolumeX size={15} />}
                  </Button>
                  <button
                    onClick={() => setIsAssistantExpanded(false)}
                    className="text-white/30 hover:text-white/60 text-[11px] transition-all"
                  >
                    Close
                  </button>
                </div>
              </div>

              {/* Visualizer */}
              <div className="py-1 border-b border-white/5 overflow-hidden">
                <GeminiVisualizer state={visualizerState} />
              </div>

              {/* Messages */}
              <div className="flex-1 min-h-0 overflow-y-auto my-3 pr-1 space-y-3 max-h-[150px]">
                {lines.length === 0 ? (
                  <p className="text-[11px] text-white/30 text-center py-8">
                    Ask about routes, stations, or disruptions
                  </p>
                ) : (
                  lines.map((line) => (
                    <div
                      key={line.id}
                      className={`flex ${line.role === "user" ? "justify-end" : "justify-start"}`}
                    >
                      <div
                        className={`max-w-[85%] rounded-xl px-3 py-2 text-[12px] leading-normal ${
                          line.role === "user"
                            ? "bg-[#0EA5E9]/10 text-white/80"
                            : "bg-white/[0.04] text-white/70"
                        }`}
                      >
                        {line.text}
                      </div>
                    </div>
                  ))
                )}
                {busy && (
                  <div className="flex justify-start">
                    <div className="bg-white/[0.04] rounded-xl px-3 py-2 text-[12px] text-white/50 flex items-center gap-1.5">
                      <motion.span
                        className="flex gap-0.5"
                        animate={{ opacity: [0.5, 1, 0.5] }}
                        transition={{ duration: 1, repeat: Infinity }}
                      >
                        <span className="h-1 w-1 rounded-full bg-[#0EA5E9]" />
                        <span className="h-1 w-1 rounded-full bg-[#0EA5E9]" />
                        <span className="h-1 w-1 rounded-full bg-[#0EA5E9]" />
                      </motion.span>
                      <span>Thinking...</span>
                    </div>
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>

              {/* Input */}
              <div className="flex items-center gap-2 shrink-0 pt-3 border-t border-white/5">
                <VoiceControls
                  supported={voice.supported}
                  listening={voice.listening || voice.transcribing}
                  disabled={busy}
                  onToggleMic={onToggleMic}
                />
                <TextInputBar disabled={busy || voice.listening || voice.transcribing} onSend={send} />
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* TfL Camera Popup */}
      {cameraPopup && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 10 }}
          className="absolute bottom-20 left-4 z-20 glass-panel p-3 w-[320px] rounded-xl"
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-[12px] font-medium text-white/80">{cameraPopup.camera_name}</span>
            <button onClick={() => setCameraPopup(null)} className="text-white/30 hover:text-white/60 text-[11px]">Close</button>
          </div>
          {cameraPopup.image_url ? (
            <div className="relative rounded-lg overflow-hidden bg-black/40">
              <img
                src={cameraPopup.image_url + "?t=" + Date.now()}
                alt="TfL Camera"
                className="w-full h-auto max-h-[200px] object-cover"
                onError={(e) => {
                  (e.target as HTMLImageElement).style.display = "none";
                  const fallback = document.createElement("div");
                  fallback.className = "h-[160px] flex items-center justify-center text-[11px] text-white/30";
                  fallback.textContent = "Camera feed unavailable";
                  e.currentTarget.parentElement?.appendChild(fallback);
                }}
              />
              <div className="absolute top-1.5 right-1.5 flex items-center gap-1 bg-black/60 rounded px-1.5 py-0.5">
                <span className="h-1.5 w-1.5 rounded-full bg-red-500 animate-pulse" />
                <span className="text-[8px] text-white/70 uppercase tracking-wider">Live</span>
              </div>
            </div>
          ) : cameraPopup.video_url ? (
            <video
              src={cameraPopup.video_url}
              autoPlay
              muted
              loop
              playsInline
              className="w-full rounded-lg max-h-[200px] bg-black/40"
            />
          ) : (
            <div className="bg-black/40 rounded-lg h-[160px] flex items-center justify-center">
              <span className="text-[11px] text-white/30">Fetching camera feed…</span>
            </div>
          )}
          <div className="mt-2 flex gap-2 text-[10px] text-white/40">
            <span>Lat: {cameraPopup.lat.toFixed(4)}</span>
            <span>Lon: {cameraPopup.lon.toFixed(4)}</span>
          </div>
        </motion.div>
      )}

      </div>

      {/* Right: Tactical sidebar — responsive, hide on small screens */}
      <div className="hidden lg:flex w-[320px] xl:w-[340px] shrink-0 flex-col gap-3 p-3 overflow-y-auto border-l border-white/5">
        <AnimatePresence>
          {activePanels.map((panel) => {
            const kind = panel.kind as TacticalPanelKind;
            return (
              <div key={kind} className="pointer-events-auto">
                <TacticalCard kind={kind} title={panel.title}>
                  {kind === "disruption" && (
                    <div className="space-y-2">
                      {showDisruptionAlert ? (
                        <div className="flex items-center gap-2 text-[12px] text-white/70">
                          <span className="h-2 w-2 rounded-full bg-[#EF4444] animate-pulse" />
                          Active disruptions visible on map
                        </div>
                      ) : (
                        <div className="text-[12px] text-white/40">No active disruptions</div>
                      )}
                    </div>
                  )}
                  {kind === "route" && (
                    <div className="space-y-2">
                      {isRoutingActive ? (
                        <div className="flex items-center gap-2 text-[12px] text-white/70">
                          <span className="h-2 w-2 rounded-full bg-[#10B981]" />
                          Route active on map
                        </div>
                      ) : (
                        <div className="text-[12px] text-white/40">No active route</div>
                      )}
                    </div>
                  )}
                  {kind === "station" && selectedStation && (
                    <div className="space-y-2">
                      <div className="text-[13px] font-medium text-white/90">{selectedStation}</div>
                      <div className="flex border-b border-white/5 text-[11px]">
                        {(["lifts","escalators","toilets"] as const).map((t) => (
                          <button key={t} onClick={() => setFilterType(t)} className={`flex-1 pb-1.5 text-center ${filterType === t ? "text-[#0EA5E9] border-b border-[#0EA5E9]" : "text-white/30"}`}>{t}</button>
                        ))}
                      </div>
                      <div className="text-[11px] text-white/40">Facility data from TfL API</div>
                    </div>
                  )}
                  {kind === "video" && (
                    <div className="space-y-2">
                      {videoEvents.length === 0 && (
                        <label className="block cursor-pointer text-center">
                          <input type="file" accept="video/*" className="hidden" onChange={handleVideoUpload} disabled={videoUploading} />
                          <span className="block px-3 py-2 text-[11px] text-white/50 border border-white/8 rounded-lg hover:bg-white/[0.03] transition-all">
                            {videoUploading ? "Processing..." : "Upload video"}
                          </span>
                        </label>
                      )}
                      {selectedVideoEvent ? (
                        <div className="space-y-2">
                          <button
                            onClick={() => setSelectedVideoEvent(null)}
                            className="text-[10px] text-white/40 hover:text-white/70 transition-colors"
                          >
                            ← Back to events
                          </button>
                          <VideoDetectionOverlay eventId={selectedVideoEvent} />
                        </div>
                      ) : (
                        <div className="space-y-2 max-h-[180px] overflow-y-auto">
                          {videoEvents.map((evt) => (
                            <button
                              key={evt.event_id}
                              onClick={() => setSelectedVideoEvent(evt.event_id)}
                              className="w-full text-left bg-white/[0.03] border border-white/[0.04] p-2 rounded-lg hover:bg-white/[0.06] transition-all"
                            >
                              <div className="flex justify-between text-[11px]">
                                <span className="text-white/70">{evt.category.replace("_", " ")}</span>
                                <span className="text-white/30">{evt.duration_sec}s</span>
                              </div>
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                  {kind === "live" && (
                    <div className="space-y-2">
                      {liveObservations.length === 0 && liveFeedRunning && (
                        <div className="flex items-center gap-2 text-[11px] text-white/40">
                          <span className="h-1.5 w-1.5 rounded-full bg-[#F59E0B] animate-pulse" />
                          Fetching camera data...
                        </div>
                      )}
                      <div className="space-y-2 max-h-[180px] overflow-y-auto">
                        {liveObservations.map((obs) => (
                          <div key={obs.observation_id} className="bg-white/[0.03] border border-white/[0.04] p-2 rounded-lg">
                            <div className="flex justify-between text-[11px]"><span className="text-white/70 truncate max-w-[180px]">{obs.camera_name}</span><span className={`${obs.mobility_impact === 'severe' ? 'text-[#EF4444]' : obs.mobility_impact === 'moderate' ? 'text-[#F59E0B]' : 'text-[#10B981]'}`}>{obs.mobility_impact}</span></div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {kind === "audio" && (
                    <div className="space-y-2">
                      {audioObservations.length === 0 && (
                        <button onClick={audioRecording ? stopAudioRecording : startAudioRecording} disabled={audioAnalyzing} className="w-full px-3 py-2 text-[11px] text-white/50 border border-white/8 rounded-lg hover:bg-white/[0.03] transition-all">
                          {audioAnalyzing ? "Analyzing..." : audioRecording ? "Stop recording" : "Record audio"}
                        </button>
                      )}
                      <div className="space-y-2 max-h-[180px] overflow-y-auto">
                        {audioObservations.map((obs) => (
                          <div key={obs.observation_id} className="bg-white/[0.03] border border-white/[0.04] p-2 rounded-lg">
                            <div className="flex justify-between text-[11px]"><span className="text-white/70">{obs.soundscape_type.replace("_", " ")}</span><span className={`${obs.accessibility_relevance === 'high' ? 'text-[#EF4444]' : obs.accessibility_relevance === 'moderate' ? 'text-[#F59E0B]' : 'text-[#10B981]'}`}>{obs.accessibility_relevance}</span></div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {kind === "hazard" && (
                    <div className="space-y-2">
                      {hazardCount > 0 ? (
                        <div className="flex items-center gap-2 text-[12px] text-white/70">
                          <span className="h-2 w-2 rounded-full bg-[#EF4444]" />
                          {hazardCount} hazards on map
                        </div>
                      ) : (
                        <div className="text-[12px] text-white/40">No hazards detected</div>
                      )}
                    </div>
                  )}
                  {kind === "detection" && (
                    <div className="space-y-2">
                      {detectionFeed.length > 0 ? (
                        detectionFeed.slice(-1).map((d) => (
                          <div key={d.cameraId} className="space-y-2">
                            <DetectionOverlay
                              imageUrl={d.imageUrl}
                              detections={d.detections.map((det: any) => ({
                                label: det.label,
                                bbox: det.bbox,
                                confidence: det.confidence,
                              }))}
                            />
                            <div className="text-[10px] text-white/40">{d.detections.length} objects detected</div>
                          </div>
                        ))
                      ) : (
                        <div className="text-[12px] text-white/40">No detections</div>
                      )}
                    </div>
                  )}
                </TacticalCard>
              </div>
            );
          })}
        </AnimatePresence>
      </div>
    </div>
  );
}
