---
name: lifeline-data-analysis
description: >-
  Quantitative analysis of London transport snapshots, ward IMD rankings, stress
  scores, and trend deltas. Use when the user wants charts, metrics, rankings,
  comparisons over time, or structured reports beyond raw MCP tool JSON.
---

# LifeLine data analysis

## When to activate

- "Analyze London transport data"
- "Stress score" / "rank wards" / "compare to last hour"
- After MCP briefing — need metrics, tables, or a report file
- User wants output that feeds the next agent turn

## Feedback loop (always prefer this)

```bash
cd /home/nvidia/NV-Disruptron/nemoclaw/workspace
export PYTHONPATH="/home/nvidia/NV-Disruptron/lifeline-ops-mcp:/home/nvidia/NV-Disruptron/shared"
python3 scripts/fetch_briefing_snapshot.py
python3 scripts/analyze_transport.py
```

Or one shot:

```bash
./scripts/run_analysis_pipeline.sh
```

## Artifacts (read back on next turn)

| Path | Contents |
|------|----------|
| `analysis/CONTEXT.md` | **Read first** — stress score + pointers |
| `analysis/metrics/latest.json` | Numeric metrics |
| `analysis/reports/<ts>.md` | Human report + suggested next steps |
| `analysis/snapshots/latest.json` | Raw briefing JSON |
| `analysis/metrics/wards_latest.json` | IMD ward rankings |
| `analysis/metrics/delta_latest.json` | Snapshot diff |

## Ward analysis

```bash
python3 scripts/analyze_wards.py --borough "Newham" --top 10
```

## Compare two snapshots

```bash
python3 scripts/compare_snapshots.py analysis/snapshots/<older>.json
```

## After analysis

1. Read `analysis/CONTEXT.md` and `analysis/metrics/latest.json`.
2. Use metrics to choose MCP drill-down (equity, roads, EV).
3. Summarize for user; cite stress_score and key deltas.
4. Append one line to `memory/YYYY-MM-DD.md` if monitoring.

## Do not

- Hand-calculate metrics that scripts already produce
- Skip snapshot save when user asks for "analysis" or "report"
