# NV-Disruptron 24/7 daemon — vLLM + research API + OpenClaw gateway + heartbeat.

disruptron_cmd_daemon() {
  local skip_vllm=0 skip_research=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --no-vllm) skip_vllm=1; shift ;;
      --no-research) skip_research=1; shift ;;
      -h|--help)
        cat <<EOF
Usage: disruptron daemon [options]

  Run NV-Disruptron 24/7: vLLM, AI-Q research, OpenClaw gateway, heartbeat alerts.
  Proactive text + ElevenLabs audio when ELEVENLABS_API_KEY is set.

Options:
  --no-vllm       Assume vLLM already on :8000
  --no-research   Skip AI-Q sidecar

Install as user service:
  disruptron install

EOF
        return 0
        ;;
      *) break ;;
    esac
  done

  local bootstrap_args=(--no-check)
  [[ "$skip_vllm" -eq 1 ]] && bootstrap_args+=(--no-vllm)
  [[ "$skip_research" -eq 1 ]] && bootstrap_args+=(--no-research)
  _disruptron_bootstrap "${bootstrap_args[@]}" || return 1

  echo ""
  echo "NV-Disruptron daemon active."
  echo "  Heartbeat:  every ${DISRUPTRON_HEARTBEAT_EVERY:-10m}"
  echo "  Gateway:    http://127.0.0.1:18789/"
  echo "  TTS:        ${ELEVENLABS_API_KEY:+ElevenLabs enabled}${ELEVENLABS_API_KEY:-set ELEVENLABS_API_KEY for voice alerts}"
  echo "  Logs:       openclaw logs --follow"
  echo ""
  echo "Press Ctrl+C to stop foreground attach (gateway keeps running)."
  exec openclaw logs --follow
}

disruptron_cmd_install() {
  local root="$DISRUPTRON_ROOT"
  local unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
  local unit_file="$unit_dir/nv-disruptron.service"
  local disruptron="$root/scripts/disruptron"

  mkdir -p "$unit_dir" "$root/logs"

  cat >"$unit_file" <<EOF
[Unit]
Description=NV-Disruptron autonomous London mobility agent
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$root
Environment=DISRUPTRON_ROOT=$root
EnvironmentFile=-$root/.env
ExecStart=$disruptron daemon --no-check
Restart=always
RestartSec=30

[Install]
WantedBy=default.target
EOF

  systemctl --user daemon-reload
  echo "Installed: $unit_file"
  echo ""
  echo "  systemctl --user enable --now nv-disruptron.service"
  echo "  systemctl --user status nv-disruptron.service"
  echo "  journalctl --user -u nv-disruptron.service -f"
}
