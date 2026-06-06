# Targeted test suites (nested under: disruptron test <suite>).

_disruptron_test_skills() {
  local skills_dir="$DISRUPTRON_ROOT/features/agent/workspace/skills"
  local -a expected=(
    disruptron-proactive-alert disruptron-ev-companion disruptron-voice disruptron-vision-browser
    disruptron-ops disruptron-monitor disruptron-tube disruptron-roads disruptron-parking-charging
    disruptron-equity disruptron-spatial disruptron-channel-reply disruptron-data-analysis
    disruptron-programming disruptron-context-memory disruptron-feedback-loop disruptron-deep-research disruptron-multi-tool-analysis
  )
  local fail=0 name f

  for name in "${expected[@]}"; do
    f="$skills_dir/$name/SKILL.md"
    if [[ ! -f "$f" ]]; then
      echo "MISSING: $f"
      fail=1
      continue
    fi
    if ! grep -q "^name: $name" "$f"; then
      echo "BAD frontmatter name in $f"
      fail=1
    fi
    if ! grep -q '^description:' "$f"; then
      echo "MISSING description in $f"
      fail=1
    fi
    echo "OK: $name"
  done

  [[ -f "$skills_dir/README.md" ]] && echo "OK: skills/README.md" || { echo "MISSING: skills/README.md"; fail=1; }
  [[ "$fail" -eq 0 ]] || return 1
  echo "All ${#expected[@]} skills validated."
}

_disruptron_test_analysis() {
  local root="$DISRUPTRON_ROOT"
  local ws="$root/features/agent/workspace"
  cd "$ws"
  chmod +x scripts/run_analysis_pipeline.sh
  (
    cd "$root/platform/mcp/ops"
    uv run python "$ws/scripts/fetch_briefing_snapshot.py"
    uv run python "$ws/scripts/analyze_transport.py"
  )
  test -f analysis/metrics/latest.json
  test -f analysis/snapshots/latest.json
  grep -q stress_score analysis/metrics/latest.json
  grep -qi 'stress score' analysis/CONTEXT.md
  echo "Analysis pipeline test passed."
}

_disruptron_test_transport() {
  local root="$DISRUPTRON_ROOT"
  cd "$root/platform/mcp/transport"
  uv run python -c "
import asyncio, json
from server import (
    get_parking_and_charging_snapshot,
    get_ev_charge_connectors,
    list_tfl_car_parks,
    get_stop_car_parks,
    get_london_traffic_snapshot,
)

async def main():
    snap = await get_parking_and_charging_snapshot()
    print(json.dumps(snap, indent=2))
    avail = await get_ev_charge_connectors(status='Available', limit=3)
    print('available sample:', avail['connectors'])
    parks = await list_tfl_car_parks(limit=2)
    print('car parks sample:', parks['car_parks'])
    stop = await get_stop_car_parks('940GZZLUGFD')
    print('Greenford stop parks:', stop['car_park_count'])
    traffic = await get_london_traffic_snapshot()
    assert 'ev_charging' in traffic and 'car_parks' in traffic
    print('traffic snapshot includes ev_charging + car_parks: OK')

asyncio.run(main())
"
  echo "Transport (EV + car parks) test passed."
}

_disruptron_test_agent() {
  _disruptron_require_openclaw || return 1
  disruptron_cmd_configure || return 1

  if ! curl -fsS "http://127.0.0.1:8000/v1/models" >/dev/null 2>&1; then
    echo "ERROR: vLLM not reachable on :8000 — run: disruptron vllm" >&2
    return 1
  fi

  local prompt="${1:-Monitor London transport right now. Use live tools, then tell me the top 3 things to investigate next.}"
  local log="/tmp/disruptron_agent_test.log"
  local session_id="disruptron-test-$(date +%s)"

  echo "==> openclaw agent --local (disruptron)"
  echo "Prompt: $prompt"
  openclaw agent --local --agent disruptron --session-id "$session_id" --timeout 300 -m "$prompt" 2>&1 | tee "$log"

  if grep -qiE "isn't available|I need to stop retrying" "$log"; then
    echo "FAIL: agent gave up on MCP tools — inspect $log"
    return 1
  fi
  if grep -qiE 'Tube:|congested|EV charging|disruption|Recommended|investigate|ward' "$log"; then
    echo "PASS: agent returned live London ops intelligence"
  else
    echo "FAIL: response lacks live transport signals — inspect $log"
    return 1
  fi
}

disruptron_cmd_test() {
  local suite="${1:-all}"
  shift || true

  case "$suite" in
    skills) _disruptron_test_skills ;;
    analysis) _disruptron_test_analysis ;;
    transport) _disruptron_test_transport ;;
    agent) _disruptron_test_agent "$@" ;;
    all)
      _disruptron_test_skills
      _disruptron_test_analysis
      _disruptron_test_transport
      ;;
    -h|--help|help)
      cat <<EOF
Usage: disruptron test [suite]

Suites:
  all        skills + analysis + transport (default)
  skills     SKILL.md frontmatter check
  analysis   workspace feedback pipeline
  transport  TfL EV + car park MCP smoke
  agent      live OpenClaw agent turn (needs vLLM)
EOF
      ;;
    *)
      echo "Unknown test suite: $suite — run: disruptron test help" >&2
      return 1
      ;;
  esac
}
