## Learned User Preferences

- Branding is **NV-Disruptron** only — no legacy aliases in docs or scripts.
- 24/7 autonomous monitor with proactive text + ElevenLabs voice alerts; privacy-safe TTS (no PII in speech).
- EV/charging companion personalized via `features/agent/workspace/USER.md` activity profile.
- Local vLLM Nemotron + OpenClaw gateway; optional AI-Q deep research on `:8001`.
- Web delivery UI lives under `features/delivery/web/` (React + Vite); gateway at `features/delivery/disruptron-api/`.

## Learned Workspace Facts

- Repo `/home/nvidia/NV-Disruptron`; launch: `./scripts/disruptron daemon` (24/7) or `./scripts/disruptron run` (interactive).
- OpenClaw agent id: `disruptron`; MCP prefix: `disruptron_ops__*`; heartbeat every 10m default.
- Voice: `messages.tts` ElevenLabs persona `disruptron-public`; rules in `features/agent/workspace/VOICE.md`.
- Key tools: `get_london_city_briefing`, `get_parking_and_charging_snapshot`, `get_ev_charge_summary`.
- TfL transport MCP path: `platform/mcp/transport/`.
- Vision MCP path: `platform/mcp/vision/`; hazard taxonomy: 7 categories (pavement_obstruction, broken_lift, missing_dropped_kerb, flooding, illegal_parking, broken_ev_charger, missing_tactile_paving).
- LocateAnything-3B client at `features/vision/locate_anything_client.py` with Nemotron Omni OpenAI-compatible fallback.
- Hazard pipeline: `features/vision/hazard_pipeline.py` — 4 stages (detect → parse → geotag → store), writes SQLite + GeoJSON.
- MapLibre GL frontend at `features/delivery/web/src/pages/MapPage.tsx` with hazard point layer + ward boundary placeholder.
- Gateway GeoJSON endpoints: `GET /v1/geo/hazards`, `GET /v1/geo/wards`, `POST /v1/hazard/upload`.
- GPU spatial endpoints: `POST /v1/geo/hazards/cluster` (DBSCAN on real SQLite data), `GET /v1/geo/nearest-step-free` (live TfL StopPoint API), `GET /v1/geo/accessibility-risk` (TfL API + SQLite hazards + ward data).
- RAPIDS GPU layer: `platform/shared/gpu/` — cudf_etl, cuspatial_join, cugraph_network, cuml_clustering. Auto-detects GPU libs; CPU fallback via pandas/geopandas/networkx/sklearn.
- GPU status exposed in integrations snapshot (`/v1/integrations`) as `gpu: {gpu_available, libs_loaded, status}`.
- Smoke tests: `scripts/smoke_test_ws1_v2.py` (transport/impact), `scripts/smoke_test_ws2_ws3.py` (vision + GPU + gateway).
