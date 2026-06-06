#!/usr/bin/env python3
"""Analyze a briefing snapshot → metrics JSON + markdown report (feeds next agent turn)."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]


def _load_snapshot(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _metrics_from_briefing(briefing: dict) -> dict:
    tube = (briefing.get("live_transport") or {}).get("tube") or {}
    roads = (briefing.get("live_transport") or {}).get("roads") or {}
    streets = (briefing.get("live_transport") or {}).get("streets") or {}
    parking = briefing.get("parking_and_charging") or {}
    ev = parking.get("ev_charging") or {}
    equity = briefing.get("equity_impact") or []

    total_ev = ev.get("total_connectors") or 0
    avail_ev = ev.get("available") or 0
    ev_ratio = round(avail_ev / total_ev, 3) if total_ev else None

    return {
        "tube_lines_bad": len(tube.get("lines_not_good_service") or []),
        "tube_disruptions": tube.get("active_disruption_count", 0),
        "congested_corridors": roads.get("congested_corridor_count", 0),
        "road_disruptions": roads.get("total_active_disruptions", 0),
        "street_segments": streets.get("total_disrupted_segments", 0),
        "street_closures": streets.get("closed_or_restricted_count", 0),
        "ev_available_ratio": ev_ratio,
        "ev_out_of_service": ev.get("out_of_service", 0),
        "equity_lines_scored": len(equity),
        "top_vulnerable_wards": [
            {
                "line": e.get("line"),
                "ward": (e.get("top_vulnerable_ward") or {}).get("ward_name"),
                "imd_rank": (e.get("top_vulnerable_ward") or {}).get("imd_average_rank_rank")
                or (e.get("top_vulnerable_ward") or {}).get("imd_rank"),
            }
            for e in equity[:5]
            if e.get("top_vulnerable_ward")
        ],
        "stress_score": _stress_score(tube, roads, streets, ev),
    }


def _stress_score(tube: dict, roads: dict, streets: dict, ev: dict) -> float:
    score = 0.0
    score += min(len(tube.get("lines_not_good_service") or []), 5) * 12
    score += min(roads.get("congested_corridor_count", 0), 10) * 5
    score += min(streets.get("closed_or_restricted_count", 0), 20) * 2
    total = ev.get("total_connectors") or 1
    oos = ev.get("out_of_service") or 0
    score += min(oos / total * 100, 30)
    return round(min(score, 100), 1)


def _markdown_report(ts: str, summary: str, metrics: dict) -> str:
    lines = [
        f"# LifeLine transport analysis — {ts}",
        "",
        "## Summary",
        summary or "(no summary)",
        "",
        "## Metrics",
        f"- Stress score: **{metrics['stress_score']}/100**",
        f"- Tube lines not good: {metrics['tube_lines_bad']}",
        f"- Congested corridors: {metrics['congested_corridors']}",
        f"- Street closures/restrictions: {metrics['street_closures']}",
        f"- EV availability ratio: {metrics['ev_available_ratio']}",
        "",
        "## Vulnerable wards (from briefing)",
    ]
    for w in metrics.get("top_vulnerable_wards") or []:
        lines.append(f"- {w.get('line')}: {w.get('ward')} (IMD rank {w.get('imd_rank')})")
    lines.extend(
        [
            "",
            "## Suggested next agent steps",
            "1. If stress_score > 50 → drill equity on worst tube line.",
            "2. If congested_corridors >= 5 → `get_all_road_status(congested_only=true)`.",
            "3. If ev_available_ratio < 0.3 → `get_ev_charge_summary`.",
        ]
    )
    return "\n".join(lines)


def _write_context(metrics: dict, report_path: Path) -> None:
    ctx = WORKSPACE / "analysis" / "CONTEXT.md"
    ctx.parent.mkdir(parents=True, exist_ok=True)
    ctx.write_text(
        "\n".join(
            [
                "# Analysis context (auto-updated — read on next turn)",
                "",
                f"- Latest stress score: **{metrics['stress_score']}/100**",
                f"- Report: `{report_path.relative_to(WORKSPACE)}`",
                f"- Metrics: `analysis/metrics/latest.json`",
                "",
                "Re-run: `python3 scripts/analyze_transport.py` after a new snapshot.",
            ]
        ),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, default=WORKSPACE / "analysis" / "snapshots" / "latest.json")
    args = parser.parse_args()

    if not args.snapshot.exists():
        print(json.dumps({"ok": False, "error": f"missing snapshot: {args.snapshot}"}))
        return 1

    snap = _load_snapshot(args.snapshot)
    briefing = snap.get("briefing") or snap
    ts = snap.get("fetched_at") or datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")
    metrics = _metrics_from_briefing(briefing)

    metrics_dir = WORKSPACE / "analysis" / "metrics"
    reports_dir = WORKSPACE / "analysis" / "reports"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    metrics_path = metrics_dir / "latest.json"
    metrics_path.write_text(json.dumps({"fetched_at": ts, "metrics": metrics}, indent=2), encoding="utf-8")

    report_path = reports_dir / f"{ts}.md"
    report_md = _markdown_report(ts, briefing.get("summary", ""), metrics)
    report_path.write_text(report_md, encoding="utf-8")

    _write_context(metrics, report_path)
    print(json.dumps({"ok": True, "metrics": metrics, "report": str(report_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
