# NVIDIA NemoClaw + Nemotron Omni on DGX Spark (OpenShell sandbox → host vLLM).

_disruptron_require_nemoclaw() {
  if ! command -v nemoclaw >/dev/null 2>&1; then
    echo "NemoClaw CLI not found — install:" >&2
    echo "  curl -fsSL https://www.nvidia.com/nemoclaw.sh | bash" >&2
    return 1
  fi
}

_disruptron_nemoclaw_sandbox_name() {
  echo "${NEMOCLAW_SANDBOX_NAME:-disruptron}"
}

_disruptron_nemoclaw_vllm_model_id() {
  curl -fsS "${VLLM_BASE_URL:-http://127.0.0.1:8000/v1}/models" 2>/dev/null \
    | python3 -c "import json,sys; d=json.load(sys.stdin).get('data',[]); print(d[0]['id'] if d else '')" 2>/dev/null \
    || echo "${VLLM_SERVED_MODEL:-nemotron-3-nano-omni}"
}

_disruptron_nemoclaw_install_cloudflared() {
  if command -v cloudflared >/dev/null 2>&1; then
    echo "  cloudflared: $(cloudflared --version 2>&1 | head -1)"
    return 0
  fi
  local arch deb
  arch="$(uname -m)"
  case "$arch" in
    aarch64|arm64) deb="cloudflared-linux-arm64.deb" ;;
    x86_64|amd64) deb="cloudflared-linux-amd64.deb" ;;
    *)
      echo "  cloudflared: unsupported arch $arch — install manually" >&2
      return 1
      ;;
  esac
  echo "  Installing cloudflared ($deb)..."
  local tmp bin_url
  tmp="$(mktemp -d)"
  case "$arch" in
    aarch64|arm64) bin_url="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64" ;;
    x86_64|amd64) bin_url="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64" ;;
  esac
  if command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
    curl -fsSL -o "$tmp/$deb" "https://github.com/cloudflare/cloudflared/releases/latest/download/$deb"
    sudo dpkg -i "$tmp/$deb"
  else
    mkdir -p "$HOME/.local/bin"
    curl -fsSL -o "$HOME/.local/bin/cloudflared" "$bin_url"
    chmod +x "$HOME/.local/bin/cloudflared"
    export PATH="$HOME/.local/bin:$PATH"
    echo "  Installed to ~/.local/bin/cloudflared (no sudo)"
  fi
  rm -rf "$tmp"
  cloudflared --version
}

_disruptron_nemoclaw_policy_setup() {
  _disruptron_require_nemoclaw || return 1
  local name presets=(telegram) with_tunnel=0 install_cf=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --name) name="$2"; shift 2 ;;
      --preset) presets+=("$2"); shift 2 ;;
      --tunnel) with_tunnel=1; shift ;;
      --install-cloudflared) install_cf=1; shift ;;
      -h|--help)
        cat <<EOF
Usage: disruptron nemoclaw policy-setup [options]

  Apply NVIDIA Spark NemoClaw policy presets (Telegram egress, etc.).
  See: https://build.nvidia.com/spark/nemoclaw-applications/policy-setup

Options:
  --name disruptron           Sandbox name (default: disruptron)
  --preset <name>             Extra preset (repeatable): brave, slack, ...
  --install-cloudflared       Install cloudflared deb if missing (Spark aarch64)
  --tunnel                    Run nemoclaw tunnel start (needs cloudflared + Telegram onboard)

Note: policy-add opens network egress only. Telegram messaging also requires
TELEGRAM_BOT_TOKEN and onboard with Telegram enabled (recreate sandbox).
EOF
        return 0
        ;;
      *) echo "Unknown option: $1" >&2; return 1 ;;
    esac
  done
  name="${name:-$(_disruptron_nemoclaw_sandbox_name)}"
  export SANDBOX_NAME="$name"

  echo "==> NemoClaw policy setup (sandbox: ${name})"
  local preset
  for preset in "${presets[@]}"; do
    echo "  Applying preset: ${preset}"
    if ! nemoclaw "$name" policy-add "$preset" -y 2>&1; then
      if nemoclaw "$name" policy-list 2>/dev/null | rg -q "● ${preset} "; then
        echo "  (preset '${preset}' already active — continuing)"
      else
        return 1
      fi
    fi
  done

  if command -v openshell >/dev/null 2>&1; then
    echo "==> Verify egress"
    if openshell policy get "$name" --full 2>/dev/null | rg -q 'api.telegram.org'; then
      echo "  ✓ api.telegram.org allowed"
    else
      echo "  ⚠ telegram egress not found in policy dump" >&2
    fi
  fi

  echo "==> Recover sandbox gateway"
  _disruptron_nemoclaw_recover "$name"

  if [[ "$install_cf" -eq 1 ]]; then
    echo "==> cloudflared"
    _disruptron_nemoclaw_install_cloudflared || true
  fi

  if [[ -n "${TELEGRAM_BOT_TOKEN:-}" ]]; then
    echo "==> Telegram token present — registering channel (rebuild may take a few minutes)"
    nemoclaw "$name" channels add telegram --dry-run 2>/dev/null || true
    if nemoclaw "$name" channels add telegram 2>&1; then
      echo "  ✓ Telegram channel configured"
    else
      echo "  ⚠ channels add failed — recreate with: disruptron nemoclaw onboard --name ${name}" >&2
    fi
  else
    echo "  TELEGRAM_BOT_TOKEN not set — skipped channels add (egress-only policy applied)."
  fi

  if [[ "$with_tunnel" -eq 1 ]]; then
    if command -v cloudflared >/dev/null 2>&1; then
      echo "==> Public webhook tunnel"
      nemoclaw tunnel start 2>&1 || true
    else
      echo "  cloudflared missing — run: disruptron nemoclaw policy-setup --install-cloudflared --tunnel" >&2
    fi
  fi

  echo ""
  nemoclaw "$name" policy-list 2>/dev/null | rg 'telegram|●|○' || true
  echo ""
  echo "Policy setup done. Dashboard: $(nemoclaw "$name" dashboard-url --quiet 2>/dev/null || echo http://127.0.0.1:18790/)"
}

disruptron_cmd_nemoclaw() {
  local sub="${1:-help}"
  shift || true

  case "$sub" in
    onboard)
      _disruptron_require_nemoclaw || return 1
      local name sandbox_gpu=--sandbox-gpu
      while [[ $# -gt 0 ]]; do
        case "$1" in
          --name) name="$2"; shift 2 ;;
          --no-sandbox-gpu) sandbox_gpu=--no-sandbox-gpu; shift ;;
          -h|--help)
            cat <<EOF
Usage: disruptron nemoclaw onboard [--name <sandbox>] [--no-sandbox-gpu]

  Start host vLLM (Nemotron Omni), apply NemoClaw OpenClaw profile, then run
  nemoclaw onboard against localhost:8000 (vllm-local).
EOF
            return 0
            ;;
          *) echo "Unknown option: $1" >&2; return 1 ;;
        esac
      done
      name="${name:-$(_disruptron_nemoclaw_sandbox_name)}"
      local model_id
      model_id="$(_disruptron_nemoclaw_vllm_model_id)"

      echo "==> Nemotron Omni vLLM"
      disruptron_cmd_vllm || return 1

      echo "==> OpenClaw profile (NemoClaw / reasoning / 256k)"
      NEMOCLAW_REASONING=1 DISRUPTRON_REASONING=1 disruptron_cmd_configure || return 1

      echo "==> NemoClaw onboard (sandbox: ${name}, model: ${model_id})"
      export NEMOCLAW_NON_INTERACTIVE=1
      export NEMOCLAW_PROVIDER="${NEMOCLAW_PROVIDER:-vllm}"
      export NEMOCLAW_MODEL="${NEMOCLAW_MODEL:-$model_id}"
      export NEMOCLAW_REASONING="${NEMOCLAW_REASONING:-true}"
      export NEMOCLAW_CONTEXT_WINDOW="${NEMOCLAW_CONTEXT_WINDOW:-${VLLM_MAX_MODEL_LEN:-262144}}"
      export NEMOCLAW_MAX_TOKENS="${NEMOCLAW_MAX_TOKENS:-4096}"

      export NEMOCLAW_ACCEPT_THIRD_PARTY_SOFTWARE="${NEMOCLAW_ACCEPT_THIRD_PARTY_SOFTWARE:-1}"

      nemoclaw onboard --non-interactive -y --yes-i-accept-third-party-software \
        --gpu --name "$name" $sandbox_gpu "$@"

      echo ""
      echo "NemoClaw sandbox '${name}' ready."
      _disruptron_nemoclaw_recover "$name" || true
      disruptron_cmd_nemoclaw url --name "$name" 2>/dev/null || true
      ;;
    url)
      _disruptron_require_nemoclaw || return 1
      local name quiet=0
      while [[ $# -gt 0 ]]; do
        case "$1" in
          --name) name="$2"; shift 2 ;;
          -q|--quiet) quiet=1; shift ;;
          *) shift ;;
        esac
      done
      name="${name:-$(_disruptron_nemoclaw_sandbox_name)}"
      if [[ "$quiet" -eq 1 ]]; then
        nemoclaw "$name" dashboard-url --quiet
      else
        echo "Dashboard:"
        nemoclaw "$name" dashboard-url
        echo "Gateway token:"
        nemoclaw "$name" gateway-token --quiet 2>/dev/null || \
          python3 -c "import json; print(json.load(open('$HOME/.openclaw/openclaw.json'))['gateway']['auth']['token'])"
      fi
      ;;
    status)
      _disruptron_require_nemoclaw || return 1
      local name="${1:-$(_disruptron_nemoclaw_sandbox_name)}"
      nemoclaw list 2>/dev/null || true
      echo ""
      nemoclaw "$name" status 2>/dev/null || echo "Sandbox '$name' not running — try: disruptron nemoclaw onboard"
      curl -fsS "${VLLM_BASE_URL:-http://127.0.0.1:8000/v1}/models" 2>/dev/null \
        | python3 -c "import json,sys; d=json.load(sys.stdin)['data'][0]; print(f\"vLLM: {d['id']} max_model_len={d['max_model_len']}\")" 2>/dev/null \
        || echo "vLLM: not responding on :8000"
      ;;
    profile)
      NEMOCLAW_REASONING=1 DISRUPTRON_REASONING=1 disruptron_cmd_configure "$@"
      openclaw gateway restart 2>/dev/null || true
      echo "NemoClaw OpenClaw profile applied (reasoning on, Nemotron Omni)."
      ;;
    policy-setup)
      _disruptron_nemoclaw_policy_setup "$@"
      ;;
    recover)
      _disruptron_require_nemoclaw || return 1
      local name="${1:-$(_disruptron_nemoclaw_sandbox_name)}"
      _disruptron_nemoclaw_recover "$name"
      ;;
    -h|help|*)
      cat <<EOF
Usage: disruptron nemoclaw <subcommand>

  NVIDIA NemoClaw + Nemotron Omni (OpenShell sandbox, host vLLM on :8000).

Subcommands:
  onboard [--name disruptron]   vLLM + OpenClaw profile + nemoclaw onboard
  policy-setup [--tunnel]       Spark playbook: Telegram egress + recover (+ optional tunnel)
  recover [sandbox]             Restart gateway + ensure Google Calendar MCP
  profile                       Reasoning-enabled OpenClaw config only (no sandbox)
  url [--name disruptron]       Dashboard URL + gateway token
  status [sandbox]              Sandbox + vLLM health

Spark policy guide: https://build.nvidia.com/spark/nemoclaw-applications/policy-setup

Host stack (no sandbox):  disruptron run
Full NemoClaw install:    curl -fsSL https://www.nvidia.com/nemoclaw.sh | bash
Docs:                     https://docs.nvidia.com/nemoclaw/
EOF
      ;;
  esac
}
