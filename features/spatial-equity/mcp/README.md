# London Spatial MCP Server

Ward lookup, IMD 2019 deprivation profiles, and coordinate/postcode resolution for LifeLine Grid.

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
uv run --directory london-spatial-mcp python scripts/prepare_data.py

cd london-spatial-mcp
uv sync
uv run python server.py
```

Data: `data/london_wards_imd.xlsx` (London Datastore) → `data/london_wards_imd.csv`
