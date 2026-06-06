# OpenClaw + MCP registration for NV-Disruptron.

_disruptron_register_mcp() {
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

_disruptron_unset_mcp() {
  openclaw mcp unset "$1" 2>/dev/null || true
}

_disruptron_configure_channels() {
  local token="${TELEGRAM_BOT_TOKEN:-}"
  local openclaw_config="${OPENCLAW_CONFIG:-$HOME/.openclaw/openclaw.json}"

  if [[ -z "$token" ]]; then
    echo "TELEGRAM_BOT_TOKEN not set — skipping Telegram channel config." >&2
    echo "  Set in .env then re-run: disruptron configure --channels" >&2
    return 0
  fi

  local dm_policy="${TELEGRAM_DM_POLICY:-pairing}"
  local allow_from="${TELEGRAM_ALLOW_FROM:-}"

  python3 - <<'PY' "$openclaw_config" "$token" "$dm_policy" "$allow_from"
import json
import sys
from pathlib import Path

cfg_path = Path(sys.argv[1])
token = sys.argv[2]
dm_policy = sys.argv[3]
allow_from = sys.argv[4].strip()

cfg = json.loads(cfg_path.read_text())

bindings = [b for b in cfg.get("bindings", []) if b.get("match", {}).get("channel") != "telegram"]
bindings.append({"agentId": "disruptron", "match": {"channel": "telegram"}})
cfg["bindings"] = bindings

channels = cfg.setdefault("channels", {})
telegram = channels.setdefault("telegram", {})
telegram["enabled"] = True
telegram["botToken"] = token
telegram["dmPolicy"] = dm_policy
streaming = telegram.get("streaming")
if not isinstance(streaming, dict):
    streaming = {}
streaming.setdefault("mode", "partial")
telegram["streaming"] = streaming
telegram.setdefault("groups", {})["*"] = {"requireMention": True}

if allow_from:
    telegram["allowFrom"] = [int(x.strip()) for x in allow_from.split(",") if x.strip()]

cfg_path.write_text(json.dumps(cfg, indent=2) + "\n")
print(f"  telegram: enabled (agent disruptron, dmPolicy={dm_policy})")
PY
}

disruptron_cmd_configure() {
  local with_channels=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --channels) with_channels=1; shift ;;
      -h|--help)
        cat <<EOF
Usage: disruptron configure [--channels]

  Register MCP servers + patch OpenClaw agent (disruptron, TTS, heartbeat).
  --channels   Also enable Telegram bindings (needs TELEGRAM_BOT_TOKEN)
EOF
        return 0
        ;;
      *) echo "Unknown option: $1" >&2; return 1 ;;
    esac
  done

  _disruptron_require_openclaw || return 1

  local root="$DISRUPTRON_ROOT"
  local workspace="${DISRUPTRON_WORKSPACE:-$root/features/agent/workspace}"
  local openclaw_config="${OPENCLAW_CONFIG:-$HOME/.openclaw/openclaw.json}"
  local vllm_model="${VLLM_SERVED_MODEL:-nemotron-3-nano-omni}"
  local reasoning_on="${DISRUPTRON_REASONING:-1}"
  local heartbeat_every="${DISRUPTRON_HEARTBEAT_EVERY:-10m}"
  local slim_mcp="${DISRUPTRON_SLIM_MCP:-true}"

  mkdir -p "$root/logs" "$root/data"

  echo "==> Registering NV-Disruptron MCP (slim=$slim_mcp)"
  if [[ "$slim_mcp" == "true" ]]; then
    (cd "$root/platform/mcp/ops" && uv sync --quiet 2>/dev/null || uv sync)
    _disruptron_register_mcp disruptron_ops "$root/platform/mcp/ops"
    _disruptron_unset_mcp tfl_london
    _disruptron_unset_mcp london_spatial
    _disruptron_unset_mcp london_impact
  else
    _disruptron_register_mcp tfl_london "$root/platform/mcp/transport"
    _disruptron_register_mcp london_spatial "$root/platform/mcp/spatial"
    _disruptron_register_mcp london_impact "$root/platform/mcp/impact"
    _disruptron_unset_mcp disruptron_ops
    _disruptron_unset_mcp disruptron_ops
  fi

  echo "==> Patching OpenClaw: disruptron agent + ElevenLabs TTS + heartbeat"
  python3 - <<'PY' "$openclaw_config" "$workspace" "$vllm_model" "$slim_mcp" "$root" "$heartbeat_every" "$reasoning_on"
import json
import os
import sys
from pathlib import Path

cfg_path = Path(sys.argv[1])
workspace = sys.argv[2]
model_id = sys.argv[3]
slim = sys.argv[4].lower() == "true"
root = sys.argv[5]
heartbeat_every = sys.argv[6]
reasoning_on = sys.argv[7].lower() in ("1", "true", "yes", "on")
primary = f"vllm/{model_id}"
eleven_key = os.environ.get("ELEVENLABS_API_KEY") or os.environ.get("XI_API_KEY")
voice_id = os.environ.get("ELEVENLABS_VOICE_ID", "pMsXgVXv3BLzUgSXRplE")

cfg = json.loads(cfg_path.read_text())
cfg.setdefault("agents", {}).setdefault("defaults", {})["workspace"] = workspace
cfg["agents"]["defaults"]["thinkingDefault"] = os.environ.get(
    "DISRUPTRON_THINKING_DEFAULT", "medium"
)
model_params = {}
if reasoning_on:
    model_params["params"] = {
        "chat_template_kwargs": {
            "enable_thinking": True,
            "force_nonempty_content": True,
        }
    }
cfg["agents"]["defaults"].setdefault("models", {})[primary] = model_params
cfg["agents"]["defaults"]["model"] = {"primary": primary}

tools = cfg.setdefault("tools", {})
tools["profile"] = tools.get("profile") or "coding"
if slim:
    tools.pop("toolSearch", None)
else:
    tools["toolSearch"] = {"mode": "tools"}

media = tools.setdefault("media", {})
if eleven_key:
    media["audio"] = {
        "enabled": True,
        "language": "en",
        "models": [{"provider": "elevenlabs", "model": "scribe_v2"}],
    }
media.setdefault("image", {"enabled": True})

messages = cfg.setdefault("messages", {})
tts = messages.setdefault("tts", {})
tts["auto"] = "always" if eleven_key else "inbound"
tts["provider"] = "elevenlabs" if eleven_key else "edge"
tts["maxTextLength"] = 480
tts["persona"] = "disruptron-public"
tts.setdefault("personas", {})["disruptron-public"] = {
    "label": "NV-Disruptron public voice",
    "description": "Spoken alerts without private user data",
    "fallbackPolicy": "provider-defaults",
    "prompt": {
        "profile": "Calm London mobility assistant for NV-Disruptron",
        "style": "Clear, concise, neutral British English",
        "pacing": "Moderate; pause between alert sections",
        "constraints": [
            "NEVER speak full postcodes, street addresses, names, phone numbers, email, or license plates",
            "NEVER read calendar event titles, meeting names, or Telegram usernames aloud",
            "Use 'your area', 'near you', 'your route' instead of precise locations",
            "EV alerts: say connector counts and availability only, not payment or account info",
            "Transport alerts: line names and delay severity OK; ward names OK; no personal commute details",
            "If text contains private data, summarize to a generic public alert before speech",
        ],
    },
}
if eleven_key:
    tts.setdefault("providers", {})["elevenlabs"] = {
        "apiKey": "${ELEVENLABS_API_KEY}",
        "modelId": os.environ.get("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2"),
        "voiceId": voice_id,
        "voiceSettings": {
            "stability": 0.55,
            "similarityBoost": 0.75,
            "speed": 1.0,
        },
        "applyTextNormalization": "auto",
        "languageCode": "en",
    }

agents_list = cfg.setdefault("agents", {}).setdefault("list", [])
cfg["agents"]["list"] = [a for a in agents_list if a.get("id") not in ("disruptron",)]

disruptron_tools = {
    "profile": "coding",
    "alsoAllow": ["message", "web_fetch", "browser"],
}

cfg.setdefault("browser", {})
cfg["browser"]["enabled"] = True
cfg["browser"]["defaultProfile"] = "openclaw"
cfg["browser"]["headless"] = os.environ.get("DISRUPTRON_BROWSER_HEADLESS", "true").lower() == "true"
cfg["browser"]["noSandbox"] = True
browser_profiles = cfg["browser"].setdefault("profiles", {})
if "openclaw" not in browser_profiles:
    browser_profiles["openclaw"] = {"color": "#76B900", "cdpPort": 18800}
else:
    browser_profiles["openclaw"].setdefault("cdpPort", 18800)
    browser_profiles["openclaw"].setdefault("color", "#76B900")
plugins = cfg.setdefault("plugins", {})
plugins.setdefault("entries", {})["browser"] = {"enabled": True}

agents_defaults = cfg.setdefault("agents", {}).setdefault("defaults", {})

context_window = int(
    os.environ.get(
        "DISRUPTRON_CONTEXT_WINDOW",
        os.environ.get("VLLM_MAX_MODEL_LEN", "262144"),
    )
)
max_output_tokens = int(os.environ.get("DISRUPTRON_MAX_OUTPUT_TOKENS", "4096"))

agents_defaults["imageMaxDimensionPx"] = int(os.environ.get("DISRUPTRON_IMAGE_MAX_PX", "768"))
agents_defaults["bootstrapMaxChars"] = int(os.environ.get("DISRUPTRON_BOOTSTRAP_MAX_CHARS", "4000"))
agents_defaults["bootstrapTotalMaxChars"] = int(os.environ.get("DISRUPTRON_BOOTSTRAP_TOTAL_MAX_CHARS", "12000"))
agents_defaults["startupContext"] = {
    "enabled": True,
    "applyOn": ["new", "reset"],
    "dailyMemoryDays": int(os.environ.get("DISRUPTRON_STARTUP_MEMORY_DAYS", "1")),
    "maxFileChars": int(os.environ.get("DISRUPTRON_STARTUP_MEMORY_FILE_CHARS", "800")),
    "maxTotalChars": int(os.environ.get("DISRUPTRON_STARTUP_MEMORY_TOTAL_CHARS", "1600")),
}
agents_defaults["contextLimits"] = {
    "toolResultMaxChars": int(os.environ.get("DISRUPTRON_TOOL_RESULT_MAX_CHARS", "6000")),
    "postCompactionMaxChars": int(os.environ.get("DISRUPTRON_POST_COMPACTION_MAX_CHARS", "2000")),
    "memoryGetMaxChars": int(os.environ.get("DISRUPTRON_MEMORY_GET_MAX_CHARS", "4000")),
    "memoryGetDefaultLines": int(os.environ.get("DISRUPTRON_MEMORY_GET_LINES", "80")),
}
agents_defaults["contextPruning"] = {
    "mode": "cache-ttl",
    "ttl": os.environ.get("DISRUPTRON_CONTEXT_PRUNE_TTL", "10m"),
    "keepLastAssistants": int(os.environ.get("DISRUPTRON_CONTEXT_PRUNE_KEEP_ASSISTANTS", "2")),
    "minPrunableToolChars": int(os.environ.get("DISRUPTRON_CONTEXT_PRUNE_MIN_CHARS", "8000")),
    "softTrim": {
        "maxChars": int(os.environ.get("DISRUPTRON_CONTEXT_SOFT_TRIM_MAX", "3000")),
        "headChars": 1200,
        "tailChars": 1200,
    },
    "hardClear": {
        "enabled": True,
        "placeholder": "[tool output trimmed to save context — full result on disk if saved]",
    },
}
agents_defaults["compaction"] = {
    "mode": "safeguard",
    "reserveTokensFloor": 0,
    "reserveTokens": int(os.environ.get("DISRUPTRON_COMPACTION_RESERVE_TOKENS", "4096")),
    "keepRecentTokens": int(os.environ.get("DISRUPTRON_COMPACTION_KEEP_RECENT", "8192")),
    "maxHistoryShare": float(os.environ.get("DISRUPTRON_COMPACTION_MAX_HISTORY_SHARE", "0.55")),
    "truncateAfterCompaction": True,
    "notifyUser": True,
    "midTurnPrecheck": {"enabled": True},
    "memoryFlush": {
        "enabled": True,
        "softThresholdTokens": int(os.environ.get("DISRUPTRON_MEMORY_FLUSH_THRESHOLD", "4000")),
        "prompt": (
            "Session nearing compaction. Persist durable London mobility facts to "
            "memory/YYYY-MM-DD.md (detail) and MEMORY.md (compact index). Include stress "
            "scores, line/ward names, EV ratios — no private user PII. Reply NO_REPLY if "
            "nothing to store."
        ),
    },
    "customInstructions": (
        "Preserve TfL line names, ward/equity scores, EV availability ratios, stress scores, "
        "and recommended next investigations. Drop raw JSON blobs and duplicate tool output."
    ),
}

cfg.setdefault("skills", {}).setdefault("limits", {})["maxSkillsPromptChars"] = int(
    os.environ.get("DISRUPTRON_MAX_SKILLS_PROMPT_CHARS", "2500")
)
session_cfg = cfg.setdefault("session", {})
session_cfg.setdefault("reset", {})["idleMinutes"] = int(
    os.environ.get("DISRUPTRON_SESSION_IDLE_MINUTES", "120")
)

heartbeat_prompt = (
    "Read HEARTBEAT.md and USER.md. Call disruptron_ops__get_london_city_briefing once. "
    "Check EV/charging vs USER mobility profile. Proactively alert on material changes "
    "(tube/roads/EV near user). Apply VOICE.md before any spoken output. Else HEARTBEAT_OK."
)
disruptron_agent = next((a for a in cfg["agents"]["list"] if a.get("id") == "disruptron"), None)
agent_entry = {
    "id": "disruptron",
    "name": "NV-Disruptron",
    "workspace": workspace,
    "thinkingDefault": os.environ.get("DISRUPTRON_THINKING_DEFAULT", "medium"),
    "tools": disruptron_tools,
    "default": True,
    "heartbeat": {
        "every": heartbeat_every,
        "target": "last",
        "lightContext": True,
        "isolatedSession": True,
        "skipWhenBusy": False,
        "prompt": heartbeat_prompt,
    },
}
if disruptron_agent is None:
    cfg["agents"]["list"].append(agent_entry)
else:
    disruptron_agent.update(agent_entry)

providers = cfg.setdefault("models", {}).setdefault("providers", {})
vllm = providers.setdefault("vllm", {})
vllm.setdefault("baseUrl", "http://127.0.0.1:8000/v1")
vllm.setdefault("api", "openai-completions")
vllm.setdefault("apiKey", "VLLM_API_KEY")
models = vllm.setdefault("models", [])
entry = next((m for m in models if m.get("id") == model_id), None)
modalities = ["text", "image"]
if os.environ.get("VLLM_MULTIMODAL", "0") == "1":
    modalities.append("audio")
if entry is None:
    models.append(
        {
            "id": model_id,
            "name": model_id,
            "reasoning": reasoning_on,
            "input": modalities,
            "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
            "contextWindow": context_window,
            "maxTokens": max_output_tokens,
        }
    )
else:
    entry["input"] = modalities
    entry["contextWindow"] = context_window
    entry["maxTokens"] = max_output_tokens
    entry["reasoning"] = reasoning_on

env_block = cfg.setdefault("env", {})
env_block["DISRUPTRON_ROOT"] = root
env_block["DISRUPTRON_ROOT"] = root
env_block["AIQ_SERVER_URL"] = os.environ.get("AIQ_SERVER_URL", "http://127.0.0.1:8001")
if eleven_key:
    env_block["ELEVENLABS_API_KEY"] = eleven_key

cfg_path.write_text(json.dumps(cfg, indent=2) + "\n")
print(f"  workspace:  {workspace}")
print(f"  agent:      disruptron (heartbeat {heartbeat_every})")
print(f"  model:      {primary}")
print(f"  tts:        {tts['provider']} auto={tts['auto']}")
print(f"  stt:        {'elevenlabs scribe_v2' if eleven_key else 'disabled'}")
print(f"  browser:    enabled (profile openclaw)")
print(f"  vision:     {modalities}")
print(f"  context:    window={context_window} maxOut={max_output_tokens} compaction=safeguard prune=on")
print(f"  reasoning:  {'on' if reasoning_on else 'off'} thinkingDefault={cfg['agents']['defaults'].get('thinkingDefault')}")
print(f"  mcp:        {'disruptron_ops (slim)' if slim else 'full catalog'}")
PY

  if [[ "$with_channels" -eq 1 ]]; then
    echo "==> Telegram channels"
    _disruptron_configure_channels
  fi

  openclaw mcp list 2>/dev/null || true
  echo "Done. Restart gateway: openclaw gateway restart"
}
