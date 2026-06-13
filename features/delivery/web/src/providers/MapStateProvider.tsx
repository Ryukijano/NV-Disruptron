import {
  createContext,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type DetectionFeedItem = {
  cameraId: string;
  cameraName: string;
  lat: number;
  lon: number;
  imageUrl: string;
  detections: { label: string; bbox: [number, number, number, number]; confidence: number }[];
  expiresAt: number;
};

type MapStateContextValue = {
  isRoutingActive: boolean;
  setIsRoutingActive: (active: boolean) => void;
  searchQuery: string;
  setSearchQuery: (query: string) => void;
  selectedStation: string | null;
  setSelectedStation: (station: string | null) => void;
  showDisruptionAlert: boolean;
  setShowDisruptionAlert: (show: boolean) => void;
  routeCoordinates: [number, number][];
  setRouteCoordinates: (coords: [number, number][]) => void;
  triggerMapIntent: (query: string) => boolean;
  detectionFeed: DetectionFeedItem[];
  pushDetection: (item: Omit<DetectionFeedItem, "expiresAt">, ttlMs?: number) => void;
  clearDetections: () => void;
};

const MapStateContext = createContext<MapStateContextValue | null>(null);

export function MapStateProvider({ children }: { children: ReactNode }) {
  const [isRoutingActive, setIsRoutingActive] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedStation, setSelectedStation] = useState<string | null>(null);
  const [showDisruptionAlert, setShowDisruptionAlert] = useState(false);
  const [routeCoordinates, setRouteCoordinates] = useState<[number, number][]>([]);
  const [detectionFeed, setDetectionFeed] = useState<DetectionFeedItem[]>([]);

  const pushDetection = (item: Omit<DetectionFeedItem, "expiresAt">, ttlMs = 30000) => {
    const expiresAt = Date.now() + ttlMs;
    setDetectionFeed((prev) => [...prev.filter((p) => p.cameraId !== item.cameraId), { ...item, expiresAt }]);
  };
  const clearDetections = () => setDetectionFeed([]);

  const triggerMapIntent = (query: string): boolean => {
    const q = query.toLowerCase();

    // 1. Wayfinding route intent
    if (
      (q.includes("bank") && q.includes("stratford")) ||
      q.includes("route") ||
      q.includes("wayfinding") ||
      q.includes("path")
    ) {
      setSearchQuery("Bank to Stratford, step-free");
      setIsRoutingActive(true);
      setSelectedStation(null);
      setShowDisruptionAlert(false);
      return true;
    }

    // 2. Station deep dive intent
    if (q.includes("station") || q.includes("deep dive") || q.includes("platform") || q.includes("lift") || q.includes("escalator")) {
      let station = "Bank Station";
      if (q.includes("stratford")) {
        station = "Stratford Station";
      } else if (q.includes("london bridge")) {
        station = "London Bridge Station";
      }
      setSelectedStation(station);
      setIsRoutingActive(false);
      setShowDisruptionAlert(false);
      return true;
    }

    // 3. Disruption alert intent
    if (q.includes("disruption") || q.includes("outbreak") || q.includes("broken") || q.includes("fault") || q.includes("alert") || q.includes("suspended")) {
      setShowDisruptionAlert(true);
      setIsRoutingActive(false);
      setSelectedStation(null);
      return true;
    }

    return false;
  };

  const value = useMemo(
    () => ({
      isRoutingActive,
      setIsRoutingActive,
      searchQuery,
      setSearchQuery,
      selectedStation,
      setSelectedStation,
      showDisruptionAlert,
      setShowDisruptionAlert,
      routeCoordinates,
      setRouteCoordinates,
      triggerMapIntent,
      detectionFeed,
      pushDetection,
      clearDetections,
    }),
    [isRoutingActive, searchQuery, selectedStation, showDisruptionAlert, routeCoordinates, detectionFeed]
  );

  return (
    <MapStateContext.Provider value={value}>
      {children}
    </MapStateContext.Provider>
  );
}

export function useMapState() {
  const ctx = useContext(MapStateContext);
  if (!ctx) throw new Error("useMapState must be used within MapStateProvider");
  return ctx;
}
