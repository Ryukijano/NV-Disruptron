#!/usr/bin/env python3
"""Ward / IMD data analysis from london_wards_imd.csv — outputs ranked tables."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
REPO = WORKSPACE.parents[2]  # workspace → agent-autonomous → features → repo
IMD_CSV = REPO / "data" / "london_wards_imd.csv"


def _load_rows(borough: str | None = None) -> list[dict]:
    rows: list[dict] = []
    with IMD_CSV.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if borough and borough.lower() not in (row.get("Borough") or "").lower():
                continue
            rows.append(
                {
                    "ward_code": row["Ward Code"],
                    "ward_name": row["Ward Name"],
                    "borough": row["Borough"],
                    "population": int(row["Population"] or 0),
                    "imd_rank": int(float(row["IMD average rank rank"] or 0)),
                }
            )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--borough", type=str, default=None)
    parser.add_argument("--top", type=int, default=15, help="Most deprived wards to return")
    parser.add_argument("--out", type=Path, default=WORKSPACE / "analysis" / "metrics" / "wards_latest.json")
    args = parser.parse_args()

    rows = _load_rows(args.borough)
    rows.sort(key=lambda r: r["imd_rank"])
    top = rows[: max(1, args.top)]

    payload = {
        "borough_filter": args.borough,
        "ward_count": len(rows),
        "most_deprived": top,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "path": str(args.out), "top_ward": top[0] if top else None}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
