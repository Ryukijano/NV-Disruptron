# Sync OpenClaw sessions → SQLite and print browser recall block.

disruptron_cmd_context() {
  local root="$DISRUPTRON_ROOT"
  local py="$root/features/agent/workspace/scripts/context_store.py"
  case "${1:-sync}" in
    sync)
      uv run python "$root/features/agent/workspace/scripts/sync_openclaw_context.py"
      ;;
    recall)
      local channel="${2:-browser}"
      local chat_id="${3:-main}"
      python3 "$py" recall --channel "$channel" --chat-id "$chat_id"
      ;;
    session-id)
      python3 "$py" session-id --channel "${2:-browser}" --chat-id "${3:-main}"
      ;;
    -h|--help|help)
      cat <<EOF
Usage: disruptron context <subcommand>

  sync                 Import ~/.openclaw/disruptron sessions → data/disruptron_context.db
  recall [ch] [id]     Print compact recall for browser/main (default)
  session-id [ch] [id] Stable OpenClaw session id for a conversation

Database: \$DISRUPTRON_CONTEXT_DB or data/disruptron_context.db
API:      http://127.0.0.1:8010/v1/context/ (outputs-api)
EOF
      ;;
    *)
      echo "Unknown: $1 — try: disruptron context sync|recall|session-id" >&2
      return 1
      ;;
  esac
}
