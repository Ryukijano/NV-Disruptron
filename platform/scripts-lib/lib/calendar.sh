# Google Calendar MCP (@cocal/google-calendar-mcp) — host HTTP server for OpenClaw.

_disruptron_calendar_mcp_dir() {
  echo "${GOOGLE_CALENDAR_MCP_DIR:-$HOME/google-calendar-mcp}"
}

_disruptron_calendar_mcp_port() {
  echo "${GOOGLE_CALENDAR_MCP_PORT:-3000}"
}

_disruptron_calendar_mcp_host_bind() {
  echo "${GOOGLE_CALENDAR_MCP_HOST:-0.0.0.0}"
}

_disruptron_calendar_mcp_pid_file() {
  echo "${GOOGLE_CALENDAR_MCP_PID_FILE:-$DISRUPTRON_ROOT/logs/google-calendar-mcp.pid}"
}

_disruptron_calendar_mcp_log_file() {
  echo "${GOOGLE_CALENDAR_MCP_LOG:-$DISRUPTRON_ROOT/logs/google-calendar-mcp.log}"
}

_disruptron_calendar_mcp_url_host() {
  echo "http://127.0.0.1:$(_disruptron_calendar_mcp_port)"
}

_disruptron_calendar_mcp_url_sandbox() {
  echo "http://host.openshell.internal:$(_disruptron_calendar_mcp_port)"
}

_disruptron_calendar_tokens_present() {
  [[ -f "${GOOGLE_CALENDAR_MCP_TOKEN_PATH:-$HOME/.config/google-calendar-mcp/tokens.json}" ]]
}

_disruptron_calendar_mcp_health() {
  curl -fsS "$(_disruptron_calendar_mcp_url_host)/health" >/dev/null 2>&1
}

_disruptron_calendar_mcp_stop() {
  local pid_file pid
  pid_file="$(_disruptron_calendar_mcp_pid_file)"
  [[ -f "$pid_file" ]] || return 0
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    sleep 1
    kill -9 "$pid" 2>/dev/null || true
  fi
  rm -f "$pid_file"
}

_disruptron_calendar_mcp_start() {
  local dir port host pid_file log_file
  dir="$(_disruptron_calendar_mcp_dir)"
  port="$(_disruptron_calendar_mcp_port)"
  host="$(_disruptron_calendar_mcp_host_bind)"
  pid_file="$(_disruptron_calendar_mcp_pid_file)"
  log_file="$(_disruptron_calendar_mcp_log_file)"

  if ! _disruptron_calendar_tokens_present; then
    echo "  google-calendar-mcp: no OAuth tokens — run: cd $dir && npm run auth" >&2
    return 1
  fi

  if _disruptron_calendar_mcp_health; then
    echo "  google-calendar-mcp: healthy on :${port}"
    return 0
  fi

  if [[ ! -f "$dir/build/index.js" ]]; then
    echo "  google-calendar-mcp: build missing — run: cd $dir && npm run build" >&2
    return 1
  fi

  mkdir -p "$(dirname "$pid_file")" "$DISRUPTRON_ROOT/logs"
  _disruptron_calendar_mcp_stop

  nohup node "$dir/build/index.js" --transport http --port "$port" --host "$host" \
    >>"$log_file" 2>&1 &
  echo $! >"$pid_file"

  local i
  for i in $(seq 1 30); do
    if _disruptron_calendar_mcp_health; then
      echo "  google-calendar-mcp: started on ${host}:${port}"
      return 0
    fi
    sleep 0.5
  done

  echo "  google-calendar-mcp: failed to become healthy (see $log_file)" >&2
  tail -5 "$log_file" 2>/dev/null >&2 || true
  return 1
}

_disruptron_calendar_register_host_mcp() {
  _disruptron_require_openclaw || return 1
  local url
  url="$(_disruptron_calendar_mcp_url_host)"
  openclaw mcp set google_calendar "$(python3 - <<PY
import json
print(json.dumps({"url": "$url", "transport": "streamable-http"}))
PY
)"
  echo "  host MCP: google_calendar -> ${url}"
}

_disruptron_nemoclaw_sandbox_container() {
  local name="${1:-disruptron}"
  docker ps -q --filter "name=openshell-${name}-" 2>/dev/null | head -1
}

_disruptron_nemoclaw_calendar_policy() {
  _disruptron_require_nemoclaw || return 0
  local name="${1:-disruptron}"
  local preset="$DISRUPTRON_ROOT/platform/nemoclaw/policies/google-calendar-mcp.yaml"
  [[ -f "$preset" ]] || return 1

  if nemoclaw "$name" policy-list 2>/dev/null | rg -q '● google-calendar-mcp '; then
    echo "  sandbox policy: google-calendar-mcp already active"
    return 0
  fi

  if nemoclaw "$name" policy-add --from-file "$preset" -y 2>&1; then
    echo "  sandbox policy: google-calendar-mcp applied"
    return 0
  fi
  echo "  sandbox policy: google-calendar-mcp apply failed (may already exist)" >&2
  return 0
}

_disruptron_nemoclaw_calendar_sandbox_mcp() {
  local name="${1:-disruptron}"
  local cid url
  cid="$(_disruptron_nemoclaw_sandbox_container "$name")"
  [[ -n "$cid" ]] || return 2

  url="$(_disruptron_calendar_mcp_url_sandbox)"
  docker exec "$cid" python3 -c "
import json, subprocess
from pathlib import Path
path = Path('/sandbox/.openclaw/openclaw.json')
cfg = json.loads(path.read_text())
mcp = cfg.setdefault('mcp', {}).setdefault('servers', {})
desired = {'url': '${url}', 'transport': 'streamable-http'}
if mcp.get('google_calendar') == desired:
    print('  sandbox MCP: google_calendar already configured')
    raise SystemExit(2)
mcp['google_calendar'] = desired
path.write_text(json.dumps(cfg, indent=2) + '\n')
subprocess.run(['bash', '-lc', 'cd /sandbox/.openclaw && sha256sum openclaw.json > .config-hash'], check=True)
print(f'  sandbox MCP: google_calendar -> ${url}')
"
}

_disruptron_calendar_ensure() {
  local for_nemoclaw="${1:-0}"
  local name="${2:-disruptron}"

  echo "==> Google Calendar MCP"
  if ! _disruptron_calendar_tokens_present; then
    echo "  Skipped — authenticate: cd $(_disruptron_calendar_mcp_dir) && npm run auth"
    return 0
  fi

  _disruptron_calendar_mcp_start || return 1
  _disruptron_calendar_register_host_mcp || return 1

  if [[ "$for_nemoclaw" -eq 1 ]]; then
    _disruptron_nemoclaw_calendar_policy "$name" || true
    _disruptron_nemoclaw_calendar_sandbox_mcp "$name" || true
  fi

  PYTHONPATH="$DISRUPTRON_ROOT/platform/shared${PYTHONPATH:+:$PYTHONPATH}" \
    python3 - <<'PY' 2>/dev/null || true
from google_calendar_client import connection_status
s = connection_status()
print(f"  calendar API: connected={s.get('connected')} tokens={s.get('token_present')}")
PY
}

_disruptron_nemoclaw_recover() {
  _disruptron_require_nemoclaw || return 1
  local name="${1:-disruptron}"
  local patched=0 rc=0

  _disruptron_calendar_ensure 1 "$name" || true

  echo "==> Recover NemoClaw gateway (${name})"
  nemoclaw "$name" recover

  _disruptron_nemoclaw_calendar_sandbox_mcp "$name" || rc=$?
  if [[ "$rc" -eq 0 ]]; then
    patched=1
  fi

  if [[ "$patched" -eq 1 ]]; then
    echo "==> Re-recover gateway (calendar MCP wired)"
    nemoclaw "$name" recover
  fi
}

disruptron_cmd_calendar() {
  local sub="${1:-status}"
  shift || true
  case "$sub" in
    start)
      _disruptron_calendar_mcp_start
      ;;
    stop)
      _disruptron_calendar_mcp_stop
      echo "  google-calendar-mcp: stopped"
      ;;
    ensure)
      _disruptron_calendar_ensure "${1:-0}" "${2:-disruptron}"
      ;;
    status)
      local port
      port="$(_disruptron_calendar_mcp_port)"
      if _disruptron_calendar_mcp_health; then
        echo "google-calendar-mcp: healthy on :${port}"
      else
        echo "google-calendar-mcp: not running on :${port}"
      fi
      _disruptron_calendar_tokens_present && echo "tokens: present" || echo "tokens: missing"
      openclaw mcp show google_calendar 2>/dev/null || true
      ;;
    -h|help|*)
      cat <<EOF
Usage: disruptron calendar <start|stop|ensure|status>

  Host @cocal/google-calendar-mcp (HTTP streamable MCP on :3000).
  Auto-started on: disruptron configure, disruptron nemoclaw recover

Env:
  GOOGLE_CALENDAR_MCP_DIR   default: ~/google-calendar-mcp
  GOOGLE_CALENDAR_MCP_PORT  default: 3000
EOF
      ;;
  esac
}
