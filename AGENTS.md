## Learned User Preferences

- Project pivoted from Lifeline (multilingual benefits assistant, Public Services) to LifeLine Grid / NV-Disruptron (transport disruption intelligence, Urban Operations).
- No cloud API keys required: local vLLM Nemotron + TfL/London open data MCPs. Optional TFL_APP_KEY for higher rate limits.

## Learned Workspace Facts

- Hackathon repo is `/home/nvidia/NV-Disruptron`; product name is LifeLine Grid; primary track is Urban Operations.
- Core loop: TfL live APIs → spatial join to ward/LSOA boundaries → IMD deprivation weighting → GLA population normalization → GVA economic impact → Nemotron reasoning → Folium choropleth dashboard.
- Essential datasets: TfL Unified API, London ward/LSOA boundaries (GeoJSON), IMD 2019 London rebased, GLA population projections, and GVA per workforce job.
- Data sources: api-portal.tfl.gov.uk, data.london.gov.uk, Trust for London IMD CSV, data.gov.uk, and dfl.london.gov.uk.
- Inference: Nemotron Omni via vLLM 0.20 on port 8000 (OpenAI-compatible API); agent orchestration options include OpenClaw, NeMoClaw, and LangGraph with NeMo Agent Toolkit.
