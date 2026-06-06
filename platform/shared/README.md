# Shared libraries

Python modules imported by all MCP servers and analysis scripts.

| Module | Purpose |
|--------|---------|
| `disruptron_data.py` | Ward CSV, IMD ranks, GVA, severity weights |
| `tfl_client.py` | TfL HTTP client, traffic/parking snapshots |
| `disruptron_agent_policy.py` | Agent loop constants (step budget, tool caps) |
| `google_calendar_client.py` | Calendar API (shared OAuth with outputs-api) |

Add new cross-cutting logic here — not duplicated in individual MCP `server.py` files.
