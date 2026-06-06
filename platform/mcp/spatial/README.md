# London Spatial MCP Server

Ward lookup, IMD 2019 deprivation profiles, and coordinate/postcode resolution for NV-Disruptron.

## Tools

| Tool | Description |
|------|-------------|
| `get_data_status` | Check ward/IMD dataset is loaded |
| `search_london_wards` | Search by ward name, borough, or code |
| `get_ward_profile` | Full IMD + population + GVA profile |
| `list_wards_in_borough` | All wards in a borough |
| `rank_most_deprived_wards` | Top deprived wards (optional borough filter) |
| `lookup_ward_by_coordinates` | Lat/lon → ward via postcodes.io |
| `lookup_ward_by_postcode` | Postcode → ward profile |

## Setup

```bash
# From repo root — converts London Datastore xlsx to CSV
make setup
# or: uv run python platform/data/scripts/prepare_wards.py

cd platform/mcp/spatial
uv sync
uv run python server.py
```

Data: `data/london_wards_imd.xlsx` (London Datastore) → `data/london_wards_imd.csv`
