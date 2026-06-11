"""GPU-accelerated transport network graph: step-free connectivity + shortest path.

CPU fallback: networkx.
"""

from __future__ import annotations

from typing import Any

from shared.gpu import GPU_AVAILABLE
from shared.gpu.cuspatial_join import haversine_km

if GPU_AVAILABLE:
    import cugraph
    import cudf
else:
    import networkx as cugraph  # type: ignore[no-redef]


def build_step_free_graph(stations: Any) -> Any:
    """Build a graph where nodes = step-free stations, edges = line connections.

    Edge weight = distance in km (haversine) between connected stations.
    CPU fallback: networkx Graph.
    """
    if GPU_AVAILABLE:
        return _build_graph_gpu(stations)
    return _build_graph_cpu(stations)


def _build_graph_gpu(stations: Any) -> Any:
    """cuGraph from station DataFrame with lat/lon."""
    # Build edges: connect stations on same line within reasonable distance
    edges: list[dict] = []
    if "line_id" not in stations.columns:
        # No line info — fall through to nearest-neighbor edges
        return _build_knn_edges_gpu(stations)

    lines = stations["line_id"].unique()
    for line in lines:
        line_stations = stations[stations["line_id"] == line].sort_values("sequence")
        for i in range(len(line_stations) - 1):
            s1 = line_stations.iloc[i]
            s2 = line_stations.iloc[i + 1]
            dist = haversine_km(
                float(s1["lat"]), float(s1["lon"]),
                float(s2["lat"]), float(s2["lon"]),
            )
            edges.append({
                "src": s1["stop_id"],
                "dst": s2["stop_id"],
                "weight": dist,
                "line_id": line,
            })

    if not edges:
        return None

    edge_df = cudf.DataFrame(edges)
    G = cugraph.Graph()
    G.from_cudf_edgelist(edge_df, source="src", destination="dst", edge_attr="weight")
    return G


def _build_knn_edges_gpu(stations: Any, k: int = 3) -> Any:
    """Fallback: connect each station to k nearest neighbors."""
    edges: list[dict] = []
    for i in range(len(stations)):
        s1 = stations.iloc[i]
        distances = []
        for j in range(len(stations)):
            if i == j:
                continue
            s2 = stations.iloc[j]
            dist = haversine_km(
                float(s1["lat"]), float(s1["lon"]),
                float(s2["lat"]), float(s2["lon"]),
            )
            distances.append((dist, j))
        distances.sort()
        for dist, j in distances[:k]:
            s2 = stations.iloc[j]
            edges.append({
                "src": s1["stop_id"],
                "dst": s2["stop_id"],
                "weight": dist,
            })

    if not edges:
        return None

    edge_df = cudf.DataFrame(edges)
    G = cugraph.Graph()
    G.from_cudf_edgelist(edge_df, source="src", destination="dst", edge_attr="weight")
    return G


def _build_graph_cpu(stations: Any) -> Any:
    """networkx Graph fallback."""
    import networkx as nx

    G = nx.Graph()
    for _, s in stations.iterrows():
        G.add_node(s["stop_id"], **{k: s[k] for k in s.index if k != "stop_id"})

    if "line_id" in stations.columns:
        lines = stations["line_id"].unique()
        for line in lines:
            line_stations = stations[stations["line_id"] == line].sort_values("sequence")
            for i in range(len(line_stations) - 1):
                s1 = line_stations.iloc[i]
                s2 = line_stations.iloc[i + 1]
                dist = haversine_km(
                    float(s1["lat"]), float(s1["lon"]),
                    float(s2["lat"]), float(s2["lon"]),
                )
                G.add_edge(s1["stop_id"], s2["stop_id"], weight=dist, line_id=line)
    else:
        # Nearest-neighbor fallback
        for i in range(len(stations)):
            s1 = stations.iloc[i]
            distances = []
            for j in range(len(stations)):
                if i == j:
                    continue
                s2 = stations.iloc[j]
                dist = haversine_km(
                    float(s1["lat"]), float(s1["lon"]),
                    float(s2["lat"]), float(s2["lon"]),
                )
                distances.append((dist, s2["stop_id"]))
            distances.sort()
            for dist, sid in distances[:3]:
                G.add_edge(s1["stop_id"], sid, weight=dist)

    return G


def recompute_paths_on_disruption(
    graph: Any,
    disrupted_nodes: list[str],
    origin: str,
    destinations: list[str],
) -> dict[str, Any]:
    """When a lift goes out, recompute shortest step-free paths.

    Returns:
        Dict mapping destination_id → {path: [node_ids], distance_km: float, disrupted: bool}
    """
    if GPU_AVAILABLE:
        return _recompute_paths_gpu(graph, disrupted_nodes, origin, destinations)
    return _recompute_paths_cpu(graph, disrupted_nodes, origin, destinations)


def _recompute_paths_gpu(
    graph: Any,
    disrupted_nodes: list[str],
    origin: str,
    destinations: list[str],
) -> dict[str, Any]:
    """cuGraph shortest path with node removal."""
    # Create subgraph without disrupted nodes
    # cuGraph doesn't support node deletion easily; use edge filtering
    all_edges = graph.edges
    mask = ~all_edges["src"].isin(disrupted_nodes) & ~all_edges["dst"].isin(disrupted_nodes)
    filtered = all_edges[mask]

    if len(filtered) == 0:
        return {d: {"path": None, "distance_km": None, "disrupted": True} for d in destinations}

    G2 = cugraph.Graph()
    G2.from_cudf_edgelist(filtered, source="src", destination="dst", edge_attr="weight")

    results: dict[str, Any] = {}
    for dest in destinations:
        if dest == origin:
            results[dest] = {"path": [origin], "distance_km": 0.0, "disrupted": False}
            continue
        try:
            path = cugraph.shortest_path(G2, origin, dest)
            dist = path["distance"].iloc[-1] if len(path) > 0 else None
            results[dest] = {
                "path": path["vertex"].to_arrow().to_pylist() if len(path) > 0 else None,
                "distance_km": float(dist) if dist is not None else None,
                "disrupted": False,
            }
        except Exception:
            results[dest] = {"path": None, "distance_km": None, "disrupted": True}
    return results


def _recompute_paths_cpu(
    graph: Any,
    disrupted_nodes: list[str],
    origin: str,
    destinations: list[str],
) -> dict[str, Any]:
    """networkx shortest path with node removal."""
    import networkx as nx

    G2 = graph.copy()
    G2.remove_nodes_from(disrupted_nodes)

    results: dict[str, Any] = {}
    for dest in destinations:
        if dest == origin:
            results[dest] = {"path": [origin], "distance_km": 0.0, "disrupted": False}
            continue
        try:
            path = nx.shortest_path(G2, origin, dest, weight="weight")
            dist = nx.shortest_path_length(G2, origin, dest, weight="weight")
            results[dest] = {
                "path": path,
                "distance_km": float(dist),
                "disrupted": False,
            }
        except nx.NetworkXNoPath:
            results[dest] = {"path": None, "distance_km": None, "disrupted": True}
    return results
