#!/usr/bin/env python3
"""Smoke test for Workstream 1: 4 new accessibility tools + disability data loader."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_module(name: str, path: Path):
    """Load a module by absolute path with repo root on sys.path."""
    sys.path.insert(0, str(REPO_ROOT))
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


transport = _load_module(
    "transport_server",
    REPO_ROOT / "platform" / "mcp" / "transport" / "server.py",
)
impact = _load_module(
    "impact_server",
    REPO_ROOT / "platform" / "mcp" / "impact" / "server.py",
)
data = _load_module(
    "disruptron_data",
    REPO_ROOT / "platform" / "shared" / "disruptron_data.py",
)


async def test_transport_tools() -> None:
    print("=== Transport MCP tools ===")

    # 1. get_stop_accessibility
    print("\n1. get_stop_accessibility('940GZZLUGFD') ...")
    acc = await transport.get_stop_accessibility("940GZZLUGFD")
    print(f"   name={acc.get('name')}, lifts={acc.get('lifts')}, "
          f"ramps={acc.get('boarding_ramps')}, summary={acc.get('step_free_summary')}")
    assert acc.get("stop_id") == "940GZZLUGFD"
    print("   PASS")

    # 2. get_lift_disruptions (degraded graceful expected)
    print("\n2. get_lift_disruptions() ...")
    lifts = await transport.get_lift_disruptions()
    print(f"   status={lifts.get('status')}, count={lifts.get('count')}")
    assert lifts.get("status") in ("live", "degraded")
    print("   PASS")

    # 3. plan_step_free_journey
    print("\n3. plan_step_free_journey('Stratford', 'Westminster') ...")
    journey = await transport.plan_step_free_journey("Stratford", "Westminster")
    journeys = journey.get("journeys", [])
    print(f"   returned {len(journeys)} journey option(s)")
    assert "journeys" in journey or "recommended" in journey or "fromLocation" in journey
    print("   PASS")


async def test_impact_tool() -> None:
    print("\n=== Impact MCP tool ===")

    # 4. get_accessibility_risk_snapshot
    print("\n4. get_accessibility_risk_snapshot('jubilee') ...")
    snap = await impact.get_accessibility_risk_snapshot("jubilee")
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
    wards = data.load_wards()
    print(f"   loaded {len(wards)} wards")
    assert len(wards) > 600
    print("   PASS")

    # 6. disability loader (graceful when file missing)
    print("\n6. load_disability_by_ward() ...")
    disability = data.load_disability_by_ward()
    print(f"   loaded {len(disability)} disability records (0 expected if CSV missing)")
    print("   PASS")

    # 7. _get_ward_disability_pct
    print("\n7. _get_ward_disability_pct('E05000026') ...")
    pct = data._get_ward_disability_pct("E05000026")
    print(f"   result={pct}")
    assert pct is None or isinstance(pct, float)
    print("   PASS")


async def main() -> None:
    await test_transport_tools()
    await test_impact_tool()
    test_data_loader()
    print("\n=== All WS-1 smoke tests passed ===")


if __name__ == "__main__":
    asyncio.run(main())
