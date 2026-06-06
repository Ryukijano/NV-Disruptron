---
name: disruptron-deep-research
description: >-
  Multi-step deep research on London transport, equity, and disruption impact.
  Use for report-style answers, cross-source analysis, or when shallow MCP
  tools are insufficient. Calls the local AI-Q API sidecar (port 8001).
---

# NV-Disruptron deep research

## When to activate

- User asks for a **report**, **deep dive**, **full analysis**, or **compare across sources**
- Shallow MCP tools returned partial data and user wants synthesis
- Question spans multiple domains (tube + roads + equity + EV) with citations
- User says "research", "investigate thoroughly", "write me a briefing"

## When NOT to use (use MCP tools directly instead)

- "How's London right now?" → `disruptron_ops__get_london_city_briefing` first
- Single line / single ward / single metric → narrow MCP tool from decision tree
- Heartbeat / quick status → briefing only

## Procedure

1. **Quick live context** — call `disruptron_ops__get_london_city_briefing` (or relevant MCP tools) so the report is grounded in current TfL data.
2. **Check AI-Q sidecar**:
   ```bash
   export AIQ_SERVER_URL="${AIQ_SERVER_URL:-http://127.0.0.1:8001}"
   python3 skills/disruptron-deep-research/scripts/aiq.py health
   ```
3. **Submit research** (from workspace root):
   ```bash
   cd /home/nvidia/NV-Disruptron-Gyana/features/agent/workspace
   export AIQ_SERVER_URL="${AIQ_SERVER_URL:-http://127.0.0.1:8001}"
   python3 skills/disruptron-deep-research/scripts/aiq.py chat "<USER_QUESTION with live context summary>"
   ```
4. If response contains `deep_research_running` and a `job_id`, poll:
   ```bash
   python3 skills/disruptron-deep-research/scripts/aiq.py research_poll <JOB_ID>
   ```
5. Present the report with **Situation / Impact / Evidence / Recommended actions**. Keep citations intact.

## Depth routing (same agent, different backends)

| User intent | First action | Escalation |
|-------------|--------------|------------|
| Live status | MCP briefing | — |
| Drill-down | 2–6 MCP tools | — |
| Multi-domain analysis | MCP chain + `run_analysis_pipeline.sh` | AI-Q shallow via `chat` |
| Publication report | MCP orient + AI-Q `research` or `chat` | async `research_poll` |

## API reference

| Command | Purpose |
|---------|---------|
| `aiq.py health` | Sidecar reachable? |
| `aiq.py chat "…"` | Routed shallow/deep (may return job_id) |
| `aiq.py research "…"` | Submit + poll to completion |
| `aiq.py research_poll <id>` | Resume async job |

Server: `AIQ_SERVER_URL` (default `http://127.0.0.1:8001`). Started by `./scripts/disruptron run`.
