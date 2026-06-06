# One-time repo setup: sync MCP packages + ward data.

disruptron_cmd_setup() {
  local root="$DISRUPTRON_ROOT"
  echo "==> Syncing MCP packages"
  for d in platform/mcp/transport platform/mcp/spatial platform/mcp/impact platform/mcp/ops platform/delivery/outputs-api; do
    [[ -d "$root/$d" ]] || continue
    echo "  $d"
    (cd "$root/$d" && uv sync)
  done
  echo "==> Ward / IMD data"
  uv run python "$root/platform/data/scripts/prepare_wards.py"
  echo "Setup complete."
}
