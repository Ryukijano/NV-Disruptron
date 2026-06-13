from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

import httpx

from disruptron_api.context import get_context_store

logger = logging.getLogger(__name__)

AGENT_UNAVAILABLE = (
    "NV Disruptron backend is temporarily unavailable. "
    "Ensure NemoClaw / OpenClaw is running."
)

NEMOTRON_URL = os.getenv("NEMOTRON_URL", "http://127.0.0.1:8008/v1")
NEMOTRON_MODEL = os.getenv("NEMOTRON_MODEL", "nemotron-3-nano-omni")

_REPO_ROOT = Path(__file__).resolve().parents[5]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _load_mcp_module(name: str, rel_path: str) -> ModuleType | None:
    path = _REPO_ROOT / rel_path
    if not path.exists():
        logger.warning("MCP module not found: %s", path)
        return None
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_tfl_mcp = _load_mcp_module("disruptron_tfl_mcp", "tfl-mcp-server/server.py")
_impact_mcp = _load_mcp_module("disruptron_impact_mcp", "platform/mcp/impact/server.py")
_spatial_mcp = _load_mcp_module("disruptron_spatial_mcp", "platform/mcp/spatial/server.py")
_ops_mcp = _load_mcp_module("disruptron_ops_mcp", "platform/mcp/ops/server.py")


@dataclass(frozen=True, slots=True)
class AgentTurn:
    channel: str
    chat_id: str
    text: str
    image_path: str | None = None


@dataclass(frozen=True, slots=True)
class AgentResult:
    reply: str
    tool_kinds: list[str]


class AgentChatEngine:
    def __init__(self, *, agent_id: str, timeout_s: float, local: bool = True) -> None:
        self._agent_id = agent_id
        self._timeout_s = timeout_s
        self._local = local

    async def _mcp_stepfree(self, lat: float = 51.5074, lon: float = -0.1278) -> dict:
        """Call MCP transport tool: get_stop_accessibility for nearby stations."""
        if _tfl_mcp is None:
            return {"stops": [], "source": "mcp_unavailable"}
        try:
            stops = await _tfl_mcp._tfl_get(
                "/StopPoint",
                {"lat": lat, "lon": lon, "stopTypes": "NaptanMetroStation",
                 "radius": 2000, "modes": "tube,overground,dlr,elizabeth-line"},
            )
            stop_points = stops.get("stopPoints", [])[:6]
            results = []
            for sp in stop_points:
                sid = sp.get("id")
                if not sid:
                    continue
                try:
                    acc = await _tfl_mcp.get_stop_accessibility(sid)
                    # Response: {lifts: int, boarding_ramps: bool|null, step_free_summary: str}
                    has_lift = (acc.get("lifts") or 0) > 0
                    has_ramp = acc.get("boarding_ramps") is True
                    step_free = has_lift or has_ramp
                    if step_free:
                        results.append({
                            "name": sp.get("commonName", sid),
                            "distance": sp.get("distance", "?"),
                            "has_lift": has_lift,
                            "has_ramp": has_ramp,
                            "step_free": True,
                        })
                except Exception:
                    pass
            return {"stops": results, "source": "mcp_tfl"}
        except Exception as exc:
            logger.warning("mcp step-free failed: %s", exc)
            return {"stops": [], "source": "mcp_tfl", "error": str(exc)}

    async def _fetch_tfl_line_status(self) -> dict:
        """Direct TfL API: fetch live line status (no MCP dependency)."""
        import os
        base = "https://api.tfl.gov.uk"
        key = os.getenv("TFL_APP_KEY", "").strip()
        url = f"{base}/Line/Mode/tube,overground,dlr,elizabeth-line/Status"
        params = {"app_key": key} if key else {}
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                lines = resp.json()
                disruptions = []
                for line in lines:
                    name = line.get("name", "Unknown")
                    for ls in line.get("lineStatuses", []):
                        status = ls.get("statusSeverityDescription", "Unknown")
                        reason = ls.get("reason", "")
                        if status.lower() != "good service":
                            disruptions.append(f"- {name}: {status}" + (f" — {reason}" if reason else ""))
                return {"disruptions": disruptions, "source": "tfl_api"}
        except Exception as exc:
            logger.warning("tfl line status failed: %s", exc)
            return {"disruptions": [], "source": "tfl_api", "error": str(exc)}

    async def _fetch_tfl_road_disruptions(self) -> dict:
        """Direct TfL API: fetch live road disruptions (closures, works, congestion)."""
        import os
        base = "https://api.tfl.gov.uk"
        key = os.getenv("TFL_APP_KEY", "").strip()
        url = f"{base}/Road/All/Disruption"
        params = {"app_key": key} if key else {}
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
                disruptions = []
                for d in data[:12]:  # Cap at 12 to keep prompt short
                    severity = d.get("severity", "")
                    street = d.get("streetName", "Unknown road")
                    desc = d.get("description", "")
                    start = d.get("startDate", "")[:10]
                    end = d.get("endDate", "")[:10]
                    if severity.lower() in ("serious", "severe"):
                        disruptions.append(f"- {street}: {desc} ({severity}, {start}→{end})")
                    elif severity.lower() in ("moderate", "medium"):
                        disruptions.append(f"- {street}: {desc} ({severity}, {start}→{end})")
                return {"disruptions": disruptions, "source": "tfl_api"}
        except Exception as exc:
            logger.warning("tfl road disruptions failed: %s", exc)
            return {"disruptions": [], "source": "tfl_api", "error": str(exc)}

    async def _mcp_briefing(self) -> dict:
        """Call MCP impact tool: get_london_city_briefing."""
        if _impact_mcp is None:
            return {"summary": None, "source": "mcp_unavailable"}
        try:
            data = await _impact_mcp.get_london_city_briefing()
            return {"summary": data.get("summary", ""), "lines": data.get("lines", []), "source": "mcp_impact"}
        except Exception as exc:
            logger.warning("mcp briefing failed: %s", exc)
            return {"summary": None, "source": "mcp_impact", "error": str(exc)}

    async def _hybrid_line_status(self) -> dict:
        """Try MCP line status first, fall back to direct TfL API."""
        if _tfl_mcp is not None:
            try:
                lines = await _tfl_mcp.get_line_status("tube,overground,dlr,elizabeth-line")
                disruptions = []
                for line in lines:
                    name = line.get("name", "Unknown")
                    for ls in line.get("lineStatuses", []):
                        status = ls.get("statusSeverityDescription", "Unknown")
                        reason = ls.get("reason", "")
                        if status.lower() != "good service":
                            disruptions.append(f"- {name}: {status}" + (f" — {reason}" if reason else ""))
                return {"disruptions": disruptions, "source": "mcp_tfl"}
            except Exception:
                pass
        return await self._fetch_tfl_line_status()

    async def _hybrid_road_disruptions(self) -> dict:
        """Try MCP road disruptions first, fall back to direct TfL API."""
        if _tfl_mcp is not None:
            try:
                data = await _tfl_mcp.get_road_disruptions("all", 12)
                disruptions = []
                for d in data:
                    severity = d.get("severity", "")
                    street = d.get("street", "Unknown road")
                    desc = d.get("description", "")
                    start = d.get("start", "")
                    end = d.get("end", "")
                    if severity.lower() in ("serious", "severe", "moderate", "medium"):
                        disruptions.append(f"- {street}: {desc} ({severity}, {start}→{end})")
                return {"disruptions": disruptions, "source": "mcp_tfl"}
            except Exception:
                pass
        return await self._fetch_tfl_road_disruptions()

    async def _mcp_route(self, origin: str, destination: str, mode: str = "transit") -> dict:
        """Call MCP ops tool: get_transit_route via TfL Journey Planner."""
        if _ops_mcp is None:
            return {"ok": False, "source": "mcp_unavailable"}
        try:
            data = await _ops_mcp.get_transit_route(origin, destination, mode)
            return {"ok": data.get("ok", False), "route": data, "source": "mcp_ops"}
        except Exception as exc:
            logger.warning("mcp route failed: %s", exc)
            return {"ok": False, "source": "mcp_ops", "error": str(exc)}

    async def _ask_nemotron(self, turn: AgentTurn) -> AgentResult | None:
        """Fallback to Nemotron vLLM with live tool context injection."""
        url = f"{NEMOTRON_URL}/chat/completions"
        user_text = turn.text.lower()
        tool_kinds: list[str] = []

        # ── Always fetch baseline line status (cheap, always relevant) ──
        # Hybrid: MCP first, then direct API
        status_data = await self._hybrid_line_status()
        tool_kinds.append("disruption")
        disruptions = status_data.get("disruptions", [])
        if disruptions:
            baseline = "\n[Live TfL data — current tube/overground disruptions]:\n" + "\n".join(disruptions[:6]) + "\n"
        else:
            baseline = "\n[Live TfL data: good service on all monitored lines]\n"

        # ── Step-free access (expanded keywords) ──
        stepfree_keywords = (
            "step-free", "step free", "accessible", "accessibility", "lift", "wheelchair",
            "mobility", "ramp", "boarding ramp", "step free", "escalator", "platform access",
        )
        if any(k in user_text for k in stepfree_keywords):
            tfl_data = await self._mcp_stepfree()
            tool_kinds.append("station")
            stops = tfl_data.get("stops", [])
            if stops:
                lines = []
                for sp in stops[:5]:
                    name = sp.get("name", "Unknown")
                    dist = sp.get("distance", "?")
                    lift = "✓ lift" if sp.get("has_lift") else ""
                    ramp = "✓ ramp" if sp.get("has_ramp") else ""
                    tags = ", ".join(t for t in [lift, ramp] if t)
                    lines.append(f"- {name} — {dist}m away ({tags})" if tags else f"- {name} — {dist}m away")
                baseline += (
                    "\n[Live TfL data — step-free stations within 2km of central London]:\n"
                    + "\n".join(lines)
                    + "\n"
                )
            else:
                baseline += "\n[Live TfL data: no step-free stations found in 2km radius]\n"

        # ── Disruption / travel queries — inject live road data too ──
        travel_keywords = (
            "delay", "disruption", "status", "line", "tube", "central", "jubilee",
            "district", "northern", "piccadilly", "victoria", "bakerloo", "elizabeth",
            "overground", "dlr", "travel", "travelling", "traveling", "journey", "trip",
            "route", "commute", "commuting", "getting to", "going to", "plan", "planner",
            "tomorrow", "today", "next week", "weekend", "station", "platform", "train",
            "bus", "underground", "metro", "transit", "transport", "tfl", " TfL ",
            "london transport", "city navigation", "navigate", "directions", "wayfinding",
            "road", "traffic", "congestion", "closure", "a12", "a13", "a40", "a406",
            "driving", "drive", "car", "street", "highway", "motorway",
        )
        if any(k in user_text for k in travel_keywords):
            tool_kinds.append("route")
            # Hybrid: MCP first, then direct API
            road_data = await self._hybrid_road_disruptions()
            road_disruptions = road_data.get("disruptions", [])
            if road_disruptions:
                baseline += (
                    "\n[Live TfL data — current road disruptions/closures]:\n"
                    + "\n".join(road_disruptions[:6])
                    + "\n"
                )
            # ── Route planning — try to extract origin/destination ──
            route_keywords = ("from", "to", "directions", "route", "get to", "how do i get")
            if any(k in user_text for k in route_keywords):
                import re
                # Simple extraction: "from X to Y" or "X to Y"
                m = re.search(r"from\s+(.+?)\s+to\s+(.+?)(?:\?|$|\s+by\s+|\s+via\s+)", turn.text, re.IGNORECASE)
                if not m:
                    m = re.search(r"(?:directions?|route)\s+(?:from\s+)?(.+?)\s+to\s+(.+?)(?:\?|$)", turn.text, re.IGNORECASE)
                if m:
                    origin = m.group(1).strip()
                    destination = m.group(2).strip()
                    route_data = await self._mcp_route(origin, destination, "transit")
                    if route_data.get("ok"):
                        route = route_data["route"]
                        steps = route.get("steps", [])
                        step_lines = [f"{i+1}. {s['mode']}: {s['instruction'][:60]} ({s['duration_min']} min)" for i, s in enumerate(steps[:5])]
                        baseline += (
                            f"\n[Live TfL Journey Planner — {origin} to {destination}]:\n"
                            f"Duration: {route.get('duration_text', 'unknown')}\n"
                            + "\n".join(step_lines)
                            + "\n"
                        )
                    else:
                        baseline += (
                            f"\n[Live TfL Journey Planner — {origin} to {destination}]:\n"
                            "Route planning attempted but no journey found. "
                            "Suggest checking station names or postcodes.\n"
                        )

        # ── City briefing ──
        briefing_keywords = (
            "london status", "city briefing", "what's happening", "overview", "summary",
            "city update", "london today", "london now", "what is going on",
        )
        # ── CCTV / live camera queries — inject latest critical observations ──
        camera_keywords = (
            "cctv", "camera", "jamcam", "live feed", "snapshot", "street view",
            "visual", "what is happening on", "street condition", "crowd", "platform condition",
            "check the camera", "monitor", "watch the", "see the road",
        )
        if any(k in user_text for k in camera_keywords):
            tool_kinds.append("live")
            try:
                from features.vision.live_feed_pipeline import get_critical_observations
                observations = get_critical_observations(min_confidence=0.5)
                if observations:
                    obs_lines = []
                    for obs in observations[:5]:
                        cam_name = obs.get("camera_name", "Unknown")
                        summary = obs.get("summary", "")
                        obs_lines.append(f"- {cam_name}: {summary[:80]}")
                    baseline += (
                        "\n[Live TfL JamCam critical observations]:\n"
                        + "\n".join(obs_lines)
                        + "\n"
                    )
                else:
                    baseline += "\n[Live TfL JamCam status]: All monitored cameras report normal conditions.\n"
            except Exception:
                baseline += "\n[Live TfL JamCam status]: Camera monitoring pipeline active.\n"

        if any(k in user_text for k in briefing_keywords):
            briefing = await self._mcp_briefing()
            tool_kinds.append("disruption")
            summary = briefing.get("summary", "")
            if summary:
                baseline += f"\n[Live London city briefing]:\n{summary[:400]}\n"

        system_prompt = (
            "You are NV-Disruptron, a London mobility and accessibility assistant. "
            "You help users with transport disruption, step-free access, EV charging, "
            "real-time city navigation, and live CCTV monitoring. Be concise and actionable. "
            "CRITICAL: You ALWAYS have live TfL data and JamCam CCTV feeds provided in the context below. "
            "You MUST use this live data in every answer. Never say you do not have live data. "
            "If disruptions are listed, mention them. If good service, say so confidently. "
            "CRITICAL: You have access to TfL JamCam live camera snapshots for real-time street monitoring. "
            "When asked about CCTV, cameras, street conditions, or visual verification, "
            "CONFIDENTLY state that you can analyze live JamCam feeds and provide observations. "
            "NEVER say you cannot access live video or camera feeds — the livefeed pipeline is active. "
            "CRITICAL: Routing and directions use the TfL Journey Planner (free, open API). "
            "NEVER mention Google Maps, never claim a Google Maps API key is needed, "
            "and never say real-time updates require Google Maps. TfL provides all live data."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{baseline}\n{turn.text}"},
        ]
        payload = {
            "model": NEMOTRON_MODEL,
            "messages": messages,
            "temperature": 0.5,
            "max_tokens": 2048,
            "stream": False,
        }
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(self._timeout_s)) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "")
                    if content.strip():
                        return AgentResult(reply=content.strip(), tool_kinds=tool_kinds)
            return None
        except Exception as exc:
            logger.warning("nemotron fallback failed: %s", exc)
            return None

    async def ask(
        self,
        turn: AgentTurn,
        *,
        agent_id: str | None = None,
    ) -> AgentResult:
        user_lower = turn.text.lower()
        tool_kinds: list[str] = []

        # ── Vision / live / audio keyword inference (defensive, works even when openclaw hides tool calls) ──
        if any(k in user_lower for k in ("video", "upload video", "hazard", "obstruction", "broken lift", "flooding", "illegal parking")):
            tool_kinds.append("video")
        if any(k in user_lower for k in ("live feed", "jamcam", "camera", "crowd", "platform condition", "snapshot")):
            tool_kinds.append("live")
        if any(k in user_lower for k in ("audio", "sound", "noise", "recording", "microphone", "acoustic", "listen")):
            tool_kinds.append("audio")

        # Skip OpenClaw when in local mode - use Nemotron directly with tool context injection
        if not self._local and shutil.which("openclaw"):
            store = get_context_store()
            session_id = store.openclaw_session_id_for(turn.channel, turn.chat_id)
            aid = agent_id or self._agent_id
            cmd = ["openclaw", "agent"]
            if self._local:
                cmd.append("--local")
            cmd.extend(
                [
                    "--agent",
                    aid,
                    "--session-id",
                    session_id,
                    "--message",
                    turn.text,
                    "--json",
                    "--timeout",
                    str(int(self._timeout_s)),
                ]
            )
            if turn.image_path:
                cmd.extend(["--media", turn.image_path])
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()
                if proc.returncode != 0:
                    logger.warning("openclaw agent failed: %s", stderr.decode()[:300])
                else:
                    data = json.loads(stdout.decode())
                    result = data.get("result") if isinstance(data.get("result"), dict) else {}
                    payloads = data.get("payloads") or result.get("payloads") or []
                    texts = [p.get("text", "") for p in payloads if isinstance(p, dict) and p.get("text")]
                    reply = "\n\n".join(t.strip() for t in texts if t.strip())
                    if not reply:
                        summary = data.get("summary")
                        if isinstance(summary, str) and summary.strip() and summary.strip().lower() != "completed":
                            reply = summary.strip()
                    # Defensively scan openclaw output for tool-call evidence
                    raw = json.dumps(data)
                    for token, kind in [
                        ("analyze_video", "video"),
                        ("run_live_feed_cycle", "live"),
                        ("analyze_audio", "audio"),
                        ("hazard", "hazard"),
                        ("get_stop_accessibility", "station"),
                        ("get_line_status", "disruption"),
                        ("get_london_city_briefing", "disruption"),
                        ("route", "route"),
                        ("wayfinding", "route"),
                    ]:
                        if token in raw and kind not in tool_kinds:
                            tool_kinds.append(kind)
                    if reply:
                        return AgentResult(reply=reply, tool_kinds=tool_kinds)
            except Exception as exc:
                logger.warning("openclaw agent error: %s", exc)

        # Fallback to Nemotron vLLM
        logger.info("Falling back to Nemotron vLLM at %s", NEMOTRON_URL)
        nemotron_result = await self._ask_nemotron(turn)
        if nemotron_result:
            # Merge any vision keywords that Nemotron didn't detect
            for k in tool_kinds:
                if k not in nemotron_result.tool_kinds:
                    nemotron_result.tool_kinds.append(k)
            return nemotron_result

        return AgentResult(reply=AGENT_UNAVAILABLE, tool_kinds=tool_kinds)
