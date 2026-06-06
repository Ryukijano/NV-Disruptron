---
name: disruptron-programming
description: >-
  Run Python and shell in the NV-Disruptron workspace for scripting, data pipelines,
  and small automation. Use when analysis scripts need running, debugging, or
  extending; or when building reusable tools under workspace/scripts/.
---

# NV-Disruptron programming

## When to activate

- Run or debug `workspace/scripts/*.py`
- Extend analysis pipeline with a new script
- Batch exec: fetch → analyze → compare
- User asks to "write a script" or "automate" monitoring

## Tools

Use OpenClaw **`exec`** (and `read`/`write` for scripts) in the workspace cwd:

```bash
cd /home/nvidia/NV-Disruptron-Gyana/features/agent/workspace
export PYTHONPATH="/home/nvidia/NV-Disruptron-Gyana/platform/mcp/ops:/home/nvidia/NV-Disruptron-Gyana/platform/shared:/home/nvidia/NV-Disruptron-Gyana"
```

## Standard commands

| Task | Command |
|------|---------|
| Full pipeline | `./scripts/run_analysis_pipeline.sh` |
| Snapshot only | `python3 scripts/fetch_briefing_snapshot.py` |
| Analyze latest | `python3 scripts/analyze_transport.py` |
| Ward ranks | `python3 scripts/analyze_wards.py --top 20` |
| Diff snapshots | `python3 scripts/compare_snapshots.py <older.json>` |
| Context recall | `python3 scripts/context_store.py recall --channel browser --chat-id main` |
| Sync browser sessions | `python3 scripts/sync_openclaw_context.py` or `disruptron context sync` |
| Store memory fact | `python3 scripts/context_store.py fact --text "..." --key label` |

## Extending scripts

- New scripts go in `workspace/scripts/` only (not repo root unless asked).
- Reuse `shared/disruptron_data.py` and `shared/tfl_client.py` via PYTHONPATH.
- Print **JSON to stdout** for machine-readable exec results.
- Write human output to `analysis/reports/` or `analysis/metrics/`.

## Safety

- No `rm -rf`, no editing `~/.openclaw/openclaw.json` via exec.
- Keep scripts idempotent; do not store secrets in workspace.
- Long jobs: `exec` with `background: true`, then `process` poll.

## Feed-forward

After exec succeeds, **read** generated files (`analysis/CONTEXT.md`) before the next MCP call so the agent loop uses fresh metrics.
