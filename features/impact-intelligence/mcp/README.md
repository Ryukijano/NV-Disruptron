# London Impact MCP Server

Scores transport disruption equity and economic exposure by combining TfL live data with IMD deprivation weighting.

## Tools

| Tool | Description |
|------|-------------|
| `get_impact_data_status` | Health check |
| `map_line_to_wards` | TfL line → wards along route |
| `rank_vulnerable_wards_on_line` | Deprived wards on a line |
| `score_line_disruption_impact` | Live TfL status + IMD impact index |
| `compare_lines_disruption_impact` | Compare multiple lines |
| `estimate_citywide_vulnerability_exposure` | Scenario model for top-deprived wards |

## Setup

```bash
uv run --directory london-spatial-mcp python scripts/prepare_data.py
cd london-impact-mcp
uv sync
uv run python server.py
```

TfL works without an API key (optional `TFL_APP_KEY` for higher rate limits).
