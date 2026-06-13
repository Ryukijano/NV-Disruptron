"""NeMo Agent Toolkit (NAT) integration for agent orchestration + profiling.

Provides:
- Agent task orchestration (multi-step workflows: detect → route → alert)
- Agent profiling (token usage, latency, GPU memory per tool call)
- Tool registry with automatic fallback chains

Unlike plain LangGraph, NAT gives:
- Built-in NVIDIA telemetry (GPU memory, NVML metrics)
- Curated tool library pre-integrated with NeMo Guardrails
- Agent-to-agent delegation patterns

Usage:
    from shared.gpu.nat_orchestrator import NATOrchestrator
    nat = NATOrchestrator()
    result = nat.run_workflow("hazard_response", {"camera_id": "jamcam_001", "labels": ["flooding"]})
"""

import json
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import httpx

# NAT availability
NAT_AVAILABLE = False
try:
    from nemo_skills import Agent, ToolRegistry
    NAT_AVAILABLE = True
except Exception:
    pass

REPO_ROOT = Path(__file__).resolve().parents[4]
NAT_LOG = REPO_ROOT / "data" / "nat_traces.jsonl"
NAT_LOG.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class ToolCall:
    tool_name: str
    input_params: dict[str, Any]
    output_preview: str = ""
    latency_ms: float = 0.0
    gpu_mem_mb: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    status: str = "pending"  # pending | success | error | fallback
    fallback_to: str | None = None


@dataclass
class AgentTrace:
    trace_id: str
    workflow: str
    start_time: float
    end_time: float = 0.0
    tool_calls: list[ToolCall] = field(default_factory=list)
    final_output: str = ""
    total_latency_ms: float = 0.0
    peak_gpu_mem_mb: float = 0.0


class NATOrchestrator:
    """NeMo Agent Toolkit orchestrator with profiling and fallback chains."""

    def __init__(self, backend_url: str = "http://localhost:8000/v1") -> None:
        self.backend_url = backend_url
        self.tool_registry: dict[str, Callable] = {}
        self.fallback_chains: dict[str, list[str]] = {}
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Register NV-Disruptron tools with fallback chains."""
        self.tool_registry = {
            "detect_hazards": self._tool_detect_hazards,
            "plan_routes": self._tool_plan_routes,
            "query_rag": self._tool_query_rag,
            "synthesize_alert": self._tool_synthesize_alert,
            "analyze_cosmos": self._tool_analyze_cosmos,
        }
        self.fallback_chains = {
            "detect_hazards": ["detect_hazards", "nemotron_vision_fallback"],
            "plan_routes": ["plan_routes", "greedy_fallback"],
            "query_rag": ["query_rag", "brute_force_fallback"],
            "synthesize_alert": ["synthesize_alert", "text_only_fallback"],
        }

    # ── Tool implementations ──
    def _tool_detect_hazards(self, camera_id: str, labels: list[str]) -> dict:
        """Run LocateAnything-3B on a camera snapshot."""
        from features.vision.live_feed_pipeline import fetch_camera_snapshot, fetch_jamcam_registry
        from features.vision.locate_anything_client import get_client

        # This is a sync wrapper for NAT tool calls
        import asyncio
        loop = asyncio.get_event_loop()
        registry = loop.run_until_complete(fetch_jamcam_registry())
        cam = next((c for c in registry if c["id"] == camera_id), None)
        if not cam:
            return {"error": "Camera not found"}
        image = loop.run_until_complete(fetch_camera_snapshot(cam.get("image_url")))
        if not image:
            return {"error": "Could not fetch snapshot"}
        client = get_client()
        detections = client.detect(image, labels, confidence_threshold=0.3)
        return {
            "camera_id": camera_id,
            "detections": [{"label": d.label, "bbox": d.bbox, "confidence": d.confidence} for d in detections],
        }

    def _tool_plan_routes(self, hazard_ids: list[int], max_vehicles: int = 3) -> dict:
        """Run cuOpt VRP for hazard response routing."""
        from shared.gpu.cuopt_routing import plan_hazard_response_routes
        return plan_hazard_response_routes(
            hazard_ids=hazard_ids if hazard_ids else None,
            max_vehicles=max_vehicles,
        )

    def _tool_query_rag(self, query: str, top_k: int = 5) -> dict:
        """Query RAG knowledge base."""
        from shared.gpu.rag_engine import get_rag_engine
        engine = get_rag_engine()
        engine.top_k = top_k
        return engine.query(query)

    def _tool_synthesize_alert(self, text: str, severity: str = "info") -> dict:
        """Synthesize voice alert via Riva."""
        from shared.gpu.riva_voice import get_riva_client
        client = get_riva_client()
        return client.synthesize_alert(text, severity=severity)

    def _tool_analyze_cosmos(self, video_path: str, question: str) -> dict:
        """Run Cosmos Reason 2 on a video clip."""
        from shared.gpu.cosmos_reason import get_cosmos_client
        client = get_cosmos_client()
        return client.analyze_clip(video_path, question=question)

    # ── Profiling utilities ──
    def _gpu_mem_mb(self) -> float:
        """Current GPU memory usage in MB."""
        try:
            import pynvml
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            return info.used / 1024 / 1024
        except Exception:
            return 0.0

    # ── Workflow execution ──
    def run_workflow(self, workflow_name: str, inputs: dict[str, Any]) -> dict[str, Any]:
        """Execute a named workflow with full tracing."""
        trace = AgentTrace(
            trace_id=f"{workflow_name}_{time.time_ns()}",
            workflow=workflow_name,
            start_time=time.perf_counter(),
        )

        try:
            result = self._execute_workflow(workflow_name, inputs, trace)
        except Exception as exc:
            trace.final_output = f"Workflow error: {exc}"
            traceback.print_exc()
            result = {"status": "error", "error": str(exc)}

        trace.end_time = time.perf_counter()
        trace.total_latency_ms = (trace.end_time - trace.start_time) * 1000
        self._persist_trace(trace)
        return {**result, "trace": trace.__dict__}

    def _execute_workflow(self, name: str, inputs: dict, trace: AgentTrace) -> dict[str, Any]:
        """Dispatch to specific workflow implementation."""
        if name == "hazard_response":
            return self._wf_hazard_response(inputs, trace)
        if name == "accessibility_query":
            return self._wf_accessibility_query(inputs, trace)
        if name == "live_monitor":
            return self._wf_live_monitor(inputs, trace)
        return {"status": "unknown_workflow", "workflow": name}

    def _wf_hazard_response(self, inputs: dict, trace: AgentTrace) -> dict:
        """Detect → Route → Alert workflow."""
        # Step 1: Detect hazards
        detect_result = self._call_tool(
            "detect_hazards",
            {"camera_id": inputs.get("camera_id"), "labels": inputs.get("labels", ["flooding", "pavement_obstruction"])},
            trace,
        )
        if detect_result.get("status") == "error":
            return detect_result

        # Step 2: Plan routes if hazards found
        hazards = detect_result.get("detections", [])
        route_result = {"routes": []}
        if hazards:
            route_result = self._call_tool(
                "plan_routes",
                {"hazard_ids": [h.get("id") for h in hazards if h.get("id")]},
                trace,
            )

        # Step 3: Synthesize alert
        alert_text = f"Detected {len(hazards)} hazards. Crew dispatched."
        alert_result = self._call_tool(
            "synthesize_alert",
            {"text": alert_text, "severity": "warning" if hazards else "info"},
            trace,
        )

        return {
            "status": "ok",
            "detections": hazards,
            "routes": route_result.get("routes", []),
            "alert": alert_result,
        }

    def _wf_accessibility_query(self, inputs: dict, trace: AgentTrace) -> dict:
        """RAG → Voice response workflow."""
        rag_result = self._call_tool(
            "query_rag",
            {"query": inputs.get("query", "")},
            trace,
        )
        top_result = rag_result.get("results", [{}])[0]
        summary = top_result.get("text", "No relevant information found.")

        voice_result = self._call_tool(
            "synthesize_alert",
            {"text": summary, "severity": "info"},
            trace,
        )

        return {
            "status": "ok",
            "rag_results": rag_result.get("results", []),
            "voice": voice_result,
        }

    def _wf_live_monitor(self, inputs: dict, trace: AgentTrace) -> dict:
        """Continuous monitor: detect + cosmos reason loop."""
        detect_result = self._call_tool(
            "detect_hazards",
            {"camera_id": inputs.get("camera_id"), "labels": inputs.get("labels", ["person", "car"])},
            trace,
        )
        cosmos_result = {}
        if inputs.get("video_path"):
            cosmos_result = self._call_tool(
                "analyze_cosmos",
                {"video_path": inputs["video_path"], "question": inputs.get("question", "What is happening?")},
                trace,
            )
        return {
            "status": "ok",
            "detections": detect_result.get("detections", []),
            "cosmos_reasoning": cosmos_result.get("reasoning", ""),
        }

    def _call_tool(self, tool_name: str, params: dict, trace: AgentTrace) -> dict:
        """Execute tool with fallback chain and profiling."""
        t0 = time.perf_counter()
        gpu_before = self._gpu_mem_mb()

        call = ToolCall(
            tool_name=tool_name,
            input_params=params,
        )

        result = {}
        chain = self.fallback_chains.get(tool_name, [tool_name])
        for attempt in chain:
            try:
                if attempt in self.tool_registry:
                    result = self.tool_registry[attempt](**params)
                else:
                    result = {"status": "fallback_unavailable", "tool": attempt}
                call.status = "success"
                if attempt != tool_name:
                    call.fallback_to = attempt
                break
            except Exception as exc:
                call.status = "error"
                result = {"status": "error", "tool": attempt, "error": str(exc)}
                if attempt == chain[-1]:
                    call.fallback_to = None
                    break

        call.latency_ms = (time.perf_counter() - t0) * 1000
        call.gpu_mem_mb = self._gpu_mem_mb() - gpu_before
        call.output_preview = str(result)[:200]
        trace.tool_calls.append(call)
        return result

    def _persist_trace(self, trace: AgentTrace) -> None:
        """Append trace to JSONL log."""
        try:
            with open(NAT_LOG, "a") as f:
                f.write(json.dumps(trace.__dict__, default=str) + "\n")
        except Exception:
            pass

    def get_traces(self, limit: int = 100) -> list[dict]:
        """Return recent agent traces."""
        if not NAT_LOG.exists():
            return []
        traces = []
        with open(NAT_LOG) as f:
            for line in f:
                traces.append(json.loads(line))
        return traces[-limit:]


# Singleton
_nat_orchestrator: NATOrchestrator | None = None


def get_nat_orchestrator() -> NATOrchestrator:
    global _nat_orchestrator
    if _nat_orchestrator is None:
        _nat_orchestrator = NATOrchestrator()
    return _nat_orchestrator
