#!/usr/bin/env bash
# Register LifeLine MCP servers and point OpenClaw at the LifeLine workspace + vLLM model.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
WORKSPACE="${NEMOCLAW_WORKSPACE:-$ROOT/features/agent-autonomous/workspace}"
OPENCLAW_CONFIG="${OPENCLAW_CONFIG:-$HOME/.openclaw/openclaw.json}"
VLLM_MODEL="${VLLM_SERVED_MODEL:-nemotron_3_nano_omni}"
# Slim 9-tool MCP fits 16k context with direct tool exposure (default). Set false for full 45-tool catalog.
NEMOCLAW_SLIM_MCP="${NEMOCLAW_SLIM_MCP:-true}"

register_mcp() {
  local name="$1" dir="$2"
  openclaw mcp set "$name" "$(python3 - <<EOF
import json
print(json.dumps({
    "command": "uv",
    "args": ["--directory", "$dir", "run", "python", "server.py"],
}))
EOF
)"
}

unset_mcp() {
  local name="$1"
  openclaw mcp unset "$name" 2>/dev/null || true
}

echo "==> Registering LifeLine MCP servers in OpenClaw (slim=$NEMOCLAW_SLIM_MCP)"
if [[ "$NEMOCLAW_SLIM_MCP" == "true" ]]; then
  (cd "$ROOT/lifeline-ops-mcp" && uv sync --quiet)
  register_mcp lifeline_ops "$ROOT/features/agent-autonomous/mcp"
  unset_mcp tfl_london
  unset_mcp london_spatial
  unset_mcp london_impact
else
  register_mcp tfl_london "$ROOT/features/transport-live/mcp"
  register_mcp london_spatial "$ROOT/features/spatial-equity/mcp"
  register_mcp london_impact "$ROOT/features/impact-intelligence/mcp"
  unset_mcp lifeline_ops
fi

echo "==> Patching OpenClaw config: workspace + vLLM model"
python3 - <<'PY' "$OPENCLAW_CONFIG" "$WORKSPACE" "$VLLM_MODEL" "$NEMOCLAW_SLIM_MCP"
import json
import sys
from pathlib import Path

cfg_path = Path(sys.argv[1])
workspace = sys.argv[2]
model_id = sys.argv[3]
slim = sys.argv[4].lower() == "true"
primary = f"vllm/{model_id}"

cfg = json.loads(cfg_path.read_text())
cfg.setdefault("agents", {}).setdefault("defaults", {})["workspace"] = workspace
cfg["agents"]["defaults"].setdefault("models", {})[primary] = {}
cfg["agents"]["defaults"]["model"] = {"primary": primary}
tools = cfg.setdefault("tools", {})
tools["profile"] = tools.get("profile") or "coding"
# Slim catalog: direct MCP tools. Full catalog: compact tool search surface.
if slim:
    tools.pop("toolSearch", None)
else:
    tools["toolSearch"] = {"mode": "tools"}

agents_list = cfg.setdefault("agents", {}).setdefault("list", [])
lifeline_agent = next((a for a in agents_list if a.get("id") == "lifeline"), None)
lifeline_tools = {
    "profile": "coding",
    "alsoAllow": ["message"],
}
if lifeline_agent is None:
    agents_list.append(
        {
            "id": "lifeline",
            "name": "LifeLine Grid",
            "workspace": workspace,
            "tools": lifeline_tools,
        }
    )
else:
    lifeline_agent["workspace"] = workspace
    lifeline_agent["tools"] = lifeline_tools

providers = cfg.setdefault("models", {}).setdefault("providers", {})
vllm = providers.setdefault("vllm", {})
vllm.setdefault("baseUrl", "http://127.0.0.1:8000/v1")
vllm.setdefault("api", "openai-completions")
vllm.setdefault("apiKey", "VLLM_API_KEY")
models = vllm.setdefault("models", [])
entry = next((m for m in models if m.get("id") == model_id), None)
if entry is None:
    models.append(
        {
            "id": model_id,
            "name": model_id,
            "reasoning": False,
            "input": ["text"],
            "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
            "contextWindow": 16384,
            "maxTokens": 1536,
        }
    )
else:
    entry["contextWindow"] = 16384
    entry["maxTokens"] = 1536

cfg_path.write_text(json.dumps(cfg, indent=2) + "\n")
print(f"  workspace: {workspace}")
print(f"  model:     {primary}")
print(f"  mcp mode:  {'slim lifeline_ops (9 tools)' if slim else 'full + toolSearch'}")
PY

openclaw mcp list

if [[ -x "$ROOT/features/delivery/scripts/configure_channels_lifeline.sh" ]]; then
  "$ROOT/features/delivery/scripts/configure_channels_lifeline.sh"
fi

echo "Done. Restart gateway if it is already running: openclaw gateway restart"
