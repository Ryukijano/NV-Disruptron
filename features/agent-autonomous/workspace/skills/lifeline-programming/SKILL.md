---
name: lifeline-programming
description: >-
  Run Python and shell in the LifeLine workspace for scripting, data pipelines,
  and small automation. Use when analysis scripts need running, debugging, or
  extending; or when building reusable tools under workspace/scripts/.
---

# LifeLine programming

## When to activate

- Run or debug `workspace/scripts/*.py`
- Extend analysis pipeline with a new script
- Batch exec: fetch → analyze → compare
- User asks to "write a script" or "automate" monitoring

## Tools

Use OpenClaw **`exec`** (and `read`/`write` for scripts) in the workspace cwd:

```bash
cd /home/nvidia/NV-Disruptron/nemoclaw/workspace
export PYTHONPATH="/home/nvidia/NV-Disruptron/lifeline-ops-mcp:/home/nvidia/NV-Disruptron/shared:/home/nvidia/NV-Disruptron"
```

## Standard commands

| Task | Command |
|------|---------|
| Full pipeline | `./scripts/run_analysis_pipeline.sh` |
| Snapshot only | `python3 scripts/fetch_briefing_snapshot.py` |
| Analyze latest | `python3 scripts/analyze_transport.py` |
| Ward ranks | `python3 scripts/analyze_wards.py --top 20` |
| Diff snapshots | `python3 scripts/compare_snapshots.py <older.json>` |

## Extending scripts

- New scripts go in `workspace/scripts/` only (not repo root unless asked).
- Reuse `shared/lifeline_data.py` and `shared/tfl_client.py` via PYTHONPATH.
- Print **JSON to stdout** for machine-readable exec results.
- Write human output to `analysis/reports/` or `analysis/metrics/`.

## Safety

- No `rm -rf`, no editing `~/.openclaw/openclaw.json` via exec.
- Keep scripts idempotent; do not store secrets in workspace.
- Long jobs: `exec` with `background: true`, then `process` poll.

## Feed-forward

After exec succeeds, **read** generated files (`analysis/CONTEXT.md`) before the next MCP call so the agent loop uses fresh metrics.
