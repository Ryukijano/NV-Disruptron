"""Autonomous NV-Disruptron watcher loop.

A NAT-orchestrated background task that polls rotating JamCams, runs detection,
and pushes events to all connected clients via EventBus. Also checks TfL for
severe disruptions.

Start via DISRUPTRON_WATCHER=1 and WATCH_INTERVAL_S=300 in gateway lifespan.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger("disruptron.watcher")

WatcherEventEmitter = Callable[[dict], Awaitable[None]]


async def _detect_camera(camera_id: str) -> dict | None:
    from disruptron_api.backend.camera_watch import _analyze_camera
    return await _analyze_camera(camera_id)


async def _tfl_disruption_snapshot() -> list[dict]:
    """Return severe TfL disruption entries if available."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get("https://api.tfl.gov.uk/Line/Mode/tube,dlr,overground,tram/Status?detail=true")
            if r.status_code != 200:
                return []
            data = r.json()
            severe = []
            for line in data:
                for status in line.get("lineStatuses", []):
                    if status.get("statusSeverity", 10) <= 6:
                        severe.append({
                            "line": line.get("name"),
                            "severity": status.get("statusSeverityDescription"),
                            "reason": status.get("reason", ""),
                        })
            return severe
    except Exception as exc:
        logger.debug("TfL disruption check failed: %s", exc)
        return []


async def watcher_loop(
    emit: WatcherEventEmitter,
    *,
    interval_s: float = 300.0,
    max_cameras_per_cycle: int = 3,
) -> None:
    """Run forever: sample cameras → detect → push events to all connected sessions."""
    from features.vision.live_feed_pipeline import fetch_jamcam_registry

    logger.info("Watcher started: interval=%ss, cameras=%s", interval_s, max_cameras_per_cycle)
    cycle = 0
    while True:
        try:
            await asyncio.sleep(interval_s)
            cycle += 1
            registry = await fetch_jamcam_registry()
            if not registry:
                logger.warning("Watcher: no cameras in registry")
                continue

            # Rotate through registry deterministically
            n = len(registry)
            start = (cycle * max_cameras_per_cycle) % max(1, n - max_cameras_per_cycle + 1)
            cameras = registry[start : start + max_cameras_per_cycle]
            camera_ids = [c["id"] for c in cameras]
            logger.info("Watcher cycle %s: checking cameras %s", cycle, camera_ids)

            tasks = [_detect_camera(cid) for cid in camera_ids]
            results = await asyncio.gather(*tasks)
            for r in results:
                if r is None:
                    continue
                # Emit all camera snapshots for demo (regardless of detection count)
                logger.info("Watcher: camera %s has %s detections, emitting event", r["camera_id"], r["detection_count"])
                payload = {
                    "type": "detection",
                    "camera_id": r["camera_id"],
                    "camera_name": r["camera_name"],
                    "lat": r["lat"],
                    "lon": r["lon"],
                    "image_url": r["image_url"],
                    "detections": r["detections"],
                    "ttlMs": 45000,
                }
                await emit(payload)
                # Also push a panel directive
                panel = {
                    "type": "panel",
                    "kind": "hazard" if any(
                        d["label"] in ("flooding", "pavement_obstruction", "broken_ev_charger")
                        for d in r["detections"]
                    ) else "detection",
                    "title": f"{r['camera_name']} — {r['detection_count']} objects",
                    "ttlMs": 45000,
                }
                await emit(panel)

            # Severe disruption check
            disruptions = await _tfl_disruption_snapshot()
            if disruptions:
                for d in disruptions:
                    payload = {
                        "type": "panel",
                        "kind": "disruption",
                        "title": f"{d['line']}: {d['severity']}",
                        "ttlMs": 60000,
                    }
                    await emit(payload)
                # Spoken alert summary via eventbus
                summary = f"TfL alert: {disruptions[0]['line']} {disruptions[0]['severity']}"
                alert = {"type": "alert", "title": "TfL Disruption", "body": summary, "ttlMs": 30000}
                await emit(alert)

        except asyncio.CancelledError:
            logger.info("Watcher cancelled")
            raise
        except Exception as exc:
            logger.warning("Watcher cycle %s error: %s", cycle, exc)
