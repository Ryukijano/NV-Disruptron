# Data assets

Source-of-truth datasets for ward IMD and borough GVA reference.

| File | Purpose |
|------|---------|
| `london_wards_imd.csv` | Ward boundaries, IMD ranks, population |
| `london_wards_imd.xlsx` | Source spreadsheet (optional) |
| `borough_gva_per_job.csv` | GVA reference for impact scoring |

## Prepare ward CSV

```bash
./scripts/disruptron setup
# or:
uv run python platform/data/scripts/prepare_wards.py
```

Used by `platform/shared/disruptron_data.py` and all spatial/impact MCP tools.
