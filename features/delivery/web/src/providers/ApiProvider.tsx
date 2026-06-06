import { createContext, useContext, useMemo, type ReactNode } from "react";
import { getApiClient, type DisruptronApiClient } from "@/api";

const ApiContext = createContext<DisruptronApiClient | null>(null);

export function ApiProvider({ children }: { children: ReactNode }) {
  const client = useMemo(() => getApiClient(), []);
  return <ApiContext.Provider value={client}>{children}</ApiContext.Provider>;
}

export function useApi() {
  const client = useContext(ApiContext);
  if (!client) throw new Error("useApi must be used within ApiProvider");
  return client;
}
