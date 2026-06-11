#!/usr/bin/env python3
"""Smoke test for Workstream 1: 4 new accessibility tools + disability data loader."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "platform" / "mcp" / "transport"))
sys.path.insert(0, str(REPO_ROOT / "platform" / "mcp" / "impact"))
sys.path.insert(0, str(REPO_ROOT / "platform" / "shared"))

from server import (
    get_lift_disruptions,
    get_stop_accessibility,
    plan_step_free_journey,
)
from server import get_accessibility_risk_snapshot
from disruptron_data import (
    _get_ward_disability_pct,
    load_disability_by_ward,
    load_wards,
)


async def test_transport_tools() -> None:
    print("=== Transport MCP tools ===")

    # 1. get_stop_accessibility
    print("\n1. get_stop_accessibility('940GZZLUGFD') ...")
    acc = await get_stop_accessibility("940GZZLUGFD")
    print(f"   name={acc.get('name')}, lifts={acc.get('lifts')}, "
          f"ramps={acc.get('boarding_ramps')}, summary={acc.get('step_free_summary')}")
    assert acc.get("stop_id") == "940GZZLUGFD"
    print("   PASS")

    # 2. get_lift_disruptions (degraded graceful expected)
    print("\n2. get_lift_disruptions() ...")
    lifts = await get_lift_disruptions()
    print(f"   status={lifts.get('status')}, count={lifts.get('count')}")
    assert lifts.get("status") in ("live", "degraded")
    print("   PASS")

    # 3. plan_step_free_journey
    print("\n3. plan_step_free_journey('Stratford', 'Westminster') ...")
    journey = await plan_step_free_journey("Stratford", "Westminster")
    journeys = journey.get("journeys", [])
    print(f"   returned {len(journeys)} journey option(s)")
    # Just assert the response has the expected shape
    assert "journeys" in journey or "recommended" in journey or "fromLocation" in journey
    print("   PASS")


async def test_impact_tool() -> None:
    print("\n=== Impact MCP tool ===")

    # 4. get_accessibility_risk_snapshot
    print("\n4. get_accessibility_risk_snapshot('jubilee') ...")
    snap = await get_accessibility_risk_snapshot("jubilee")
    print(f"   line={snap.get('line_name')}, status={snap.get('current_status')}, "
          f"severity={snap.get('severity_weight')}, "
          f"accessibility_closure={snap.get('accessibility_closure_on_line')}, "
          f"wards={snap.get('wards_analysed')}")
    assert snap.get("line_id") == "jubilee"
    assert "lift_outages" in snap
    assert "top_impacted_wards" in snap
    print("   PASS")


def test_data_loader() -> None:
    print("\n=== Data layer ===")

    # 5. load_wards still works
    print("\n5. load_wards() ...")
    wards = load_wards()
    print(f"   loaded {len(wards)} wards")
    assert len(wards) > 600
    print("   PASS")

    # 6. disability loader (graceful when file missing)
    print("\n6. load_disability_by_ward() ...")
    disability = load_disability_by_ward()
    print(f"   loaded {len(disability)} disability records (0 expected if CSV missing)")
    # Should not raise even when file is absent
    print("   PASS")

    # 7. _get_ward_disability_pct
    print("\n7. _get_ward_disability_pct('E05000026') ...")
    pct = _get_ward_disability_pct("E05000026")
    print(f"   result={pct}")
    # None when file missing, or a float when present
    assert pct is None or isinstance(pct, float)
    print("   PASS")


async def main() -> None:
    await test_transport_tools()
    await test_impact_tool()
    test_data_loader()
    print("\n=== All WS-1 smoke tests passed ===")


if __name__ == "__main__":
    asyncio.run(main())
