---
name: disruptron-spatial
description: >-
  London ward lookup, postcode geocoding, and IMD 2019 deprivation profiles.
  Use when the user gives a postcode, ward name, borough, or asks about
  deprivation rank, IMD, or "which ward is this".
---

# NV-Disruptron spatial & IMD

## When to activate

- "What ward is SW1A 1AA?"
- "IMD profile for Mayesbrook"
- "Most deprived wards in Newham" (full MCP)
- Linking a location to equity analysis

## Procedure (slim MCP)

1. Postcode → `disruptron_ops__lookup_ward_by_postcode(postcode)`.
2. Ward name or code → `disruptron_ops__get_ward_profile(ward)`.
3. Combine with transport tools if user also asked about disruptions near that ward.

## Full MCP mode

| Need | Tool (`london_spatial__*`) |
|------|----------------------------|
| Fuzzy ward search | `search_london_wards` |
| Borough list | `list_wards_in_borough` |
| Deprivation ranking | `rank_most_deprived_wards` |
| Lat/lon → ward | `lookup_ward_by_coordinates` |

## IMD reminder

- **IMD rank 1** = most deprived ward in England (2019 release)
- Higher rank number = relatively less deprived
- Data: 633 London wards in `data/london_wards_imd.csv`

## Output format

- Ward name, borough, ward code
- IMD average rank (and decile if in profile)
- One-line link to any active transport disruption nearby (if briefing was run)
