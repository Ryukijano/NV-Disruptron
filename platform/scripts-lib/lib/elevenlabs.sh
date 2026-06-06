# ElevenLabs API key + OpenClaw TTS setup.

disruptron_cmd_elevenlabs() {
  local root="$DISRUPTRON_ROOT"
  local env_file="$root/.env"
  local key=""

  echo "NV-Disruptron — ElevenLabs setup"
  echo ""
  echo "Get your API key: https://elevenlabs.io/app/settings/api-keys"
  echo ""

  if [[ -n "${ELEVENLABS_API_KEY:-}" ]]; then
    key="$ELEVENLABS_API_KEY"
    echo "Using ELEVENLABS_API_KEY from environment."
  elif [[ -f "$env_file" ]] && grep -qE '^ELEVENLABS_API_KEY=.+' "$env_file"; then
    # shellcheck disable=SC1090
    set -a && source "$env_file" && set +a
    key="${ELEVENLABS_API_KEY:-}"
    echo "Using ELEVENLABS_API_KEY from $env_file"
  else
    read -r -s -p "Paste ElevenLabs API key (hidden): " key
    echo ""
    if [[ -z "$key" ]]; then
      echo "No key provided. Add to $env_file: ELEVENLABS_API_KEY=sk_..." >&2
      return 1
    fi
    [[ -f "$env_file" ]] || cp "$root/.env.example" "$env_file"
    if grep -q '^ELEVENLABS_API_KEY=' "$env_file"; then
      sed -i "s|^ELEVENLABS_API_KEY=.*|ELEVENLABS_API_KEY=$key|" "$env_file"
    else
      echo "ELEVENLABS_API_KEY=$key" >>"$env_file"
    fi
    echo "Saved to $env_file"
  fi

  echo ""
  echo "==> Validating key with ElevenLabs API..."
  if ! curl -fsS "https://api.elevenlabs.io/v1/user" -H "xi-api-key: $key" >/dev/null; then
    echo "FAIL: ElevenLabs rejected the key" >&2
    return 1
  fi
  echo "OK: API key valid"

  export ELEVENLABS_API_KEY="$key"
  disruptron_cmd_configure || return 1

  if curl -fsS "http://127.0.0.1:18789/health" >/dev/null 2>&1; then
    echo ""
    echo "Restarting gateway to load ElevenLabs..."
    openclaw gateway restart 2>/dev/null || true
  fi

  echo ""
  echo "ElevenLabs ready. Test: disruptron run (Talk Mode) or disruptron daemon"
}
