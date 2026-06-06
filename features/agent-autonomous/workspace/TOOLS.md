# LifeLine MCP tools (OpenClaw bundle-mcp)

NemoClaw uses the slim `lifeline_ops` server (9 tools). Names are `lifeline_ops__<tool>`.

## Start here

- `lifeline_ops__get_london_city_briefing` — composite Tube + roads + streets + EV + car parks + equity

## Drill-down

- `lifeline_ops__score_line_disruption_impact` — IMD-weighted ward exposure for a line
- `lifeline_ops__get_london_traffic_snapshot` — full transport snapshot
- `lifeline_ops__get_parking_and_charging_snapshot` — EV + car parks
- `lifeline_ops__get_ev_charge_summary` — connector availability
- `lifeline_ops__get_all_road_status` — road corridors (`congested_only=true` when needed)
- `lifeline_ops__get_street_disruptions` — closures and restrictions
- `lifeline_ops__lookup_ward_by_postcode` / `get_ward_profile` — ward + IMD

## Workspace analysis (exec + read)

| Script | Output |
|--------|--------|
| `scripts/run_analysis_pipeline.sh` | snapshot + metrics + `analysis/CONTEXT.md` |
| `scripts/analyze_wards.py` | IMD rankings → `analysis/metrics/wards_latest.json` |
| `scripts/compare_snapshots.py` | delta → `analysis/metrics/delta_latest.json` |

Set `PYTHONPATH` to repo `lifeline-ops-mcp` + `shared` before running Python scripts.

## Known API limits

- TfL anonymous ~50 req/min — prefer briefing/snapshot tools
- Car park live occupancy (`Occupancy/CarPark`) often HTTP 500 on TfL side
- Street disruptions require date range on some endpoints (MCP handles defaults)
