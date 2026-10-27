# Local Georgia data

A local copy of the Challenge 4 Georgia snapshot plus the medical-readiness results, so you can build without BigQuery access.

Source: the challenge packet, `gs://class-demo/a4i-2026/challenge-4-evacuation/GA/<table>/data.parquet` (the packet's own tables, licensed for the event). These are the raw tables, not cleaned. Cleaned tables come later and keep these keys and column names.

## Files

| Path | What |
|---|---|
| `parquet/<table>.parquet` | Raw snapshot tables (DuckDB, pandas, Arrow) |
| `json/<table>.json` | Same rows as JSON arrays of objects |
| `geojson/shelters.geojson` | 1,792 shelters as points, `id` = `shelter_id` |
| `geojson/care_facilities.geojson` | 356 nursing homes as points, `id` = CMS certification number |
| `geojson/vulnerability_tracts.geojson` | 2,796 tract centroids, `id` = `geo_id` |
| `medical/home.csv` | Each nursing home with tract hazard, nearest medical shelter and distance (km) |
| `medical/county.csv` | Each county: power-dependent counts (Aug snapshot and Oct live), nursing beds, medical seats within 50 km |
| `medical/catchment.csv` | Each medical-needs shelter: counties served, power-dependent and beds per seat |
| `medical/summary.json` | Headline numbers and data-quality counts behind https://share.merchantry.systems/ga-medical-readiness/ |
| `counts.json` | Row counts per table |
| `export_local.py` | Regenerates parquet/json/geojson from the snapshot |

## Tables and keys

| Table | Rows | Key | Joins |
|---|---|---|---|
| shelters | 1,792 | `shelter_id` | `county_fips` to counties |
| vulnerability_tracts | 2,796 | `geo_id` | `geo_id` to hazard_tracts, `county_fips` to counties |
| hazard_tracts | 2,791 | `geo_id` | 5 tracts (population 0) have no hazard row |
| care_facilities | 356 | `cms_certification_number_ccn` | nearest tract by coordinates |
| power_dependent_counties | 159 | `fips_code` | `county_fips` |

Join on fips codes and ids, never on county or facility names.

## Show these correctly in the UI

- **Unrecorded is not no.** `wheelchair_accessible`, `generator_onsite`, `in_surge_slosh_area` are true / false / null. Null means nobody recorded it (about 75% of shelters). Give it its own color or label, never "no" or "low risk".
- **Capacity is not all real.** Commerce High (270,135) and Commerce Primary (225,112) are impossible; they are 43.5% of reported capacity. 219 shelters have capacity 0 or null, 72 have 1 or 2 (placeholders), and `usage = 'POST'` sites are post-landfall only. Clean capacity is about 572k, not 1.14M.
- **`shelter_status_code` is never OPEN.** This is a registry, not live status. Do not show shelters as open.
- **Power dependence is county level.** It says how many people, not where in the county. Color counties, do not place dots.
- **Two emPOWER vintages.** `medical/county.csv` has `pd`/`dialysis` (Aug snapshot) and `pd_live`/`dialysis_live` (HHS live feed, Oct 7). Use `dialysis_live`; the snapshot dialysis figure is unresolved. A value of 11 means 1 to 11 (suppressed).
- **Hazard.** `CFLD_*` (coastal flood) is null outside the coastal layer (2,588 of 2,791 tracts); null means outside, not zero risk data. Use percentiles of `HRCN_EALP` for hurricane exposure.
- **Distances are straight-line** until Maps routing is wired in.

## Google Maps rules

- Never draw Google Maps or Routes output (places, routes, drive times) on OpenStreetMap or Leaflet tiles. Our own data above can go on any basemap.
- Store only Maps `place_id`; fetch place details and routes live and show Google attribution next to them.
- This is a pre-season planning tool, not live emergency operations.

## Cleaned tables (`clean/`)

Cleaned versions of care facilities, hazard tracts and power-dependent counties, built by `data/clean` on `lane/data` (codex-reviewed). One row per source row, same keys. The leading columns are the raw values with the same names as the team BigQuery `*_clean` tables; cleaned and added values sit after them, and every added column `x` has `x_status` (recorded / unrecorded / imputed / assumption / suspect / external) and `x_rule` (the rule that set it).

| File | Rows | Key | Notable added columns |
|---|---|---|---|
| `clean/care_facilities` | 356 | `cms_certification_number_ccn` | `nearest_tract_geo_id`, `county_fips`, `occupancy_rate`, `hrcn_ealp_pctile`, `coastal_flood_exposed`, `km_nearest_medical_shelter` |
| `clean/hazard_tracts` | 2,791 | `geo_id` | `county_fips`, `hrcn_ealp_pctile`, `cfld_expp_clean` (0 outside the coastal layer, status `imputed`), `coastal_flood_exposed` |
| `clean/power_dependent_counties` | 159 | `fips_code` | live emPOWER columns (`dialysis_live` = 18,026), `*_low` bounds for suppressed 1-11 cells, `dialysis_centers`, `dialysis_stations` |
| `clean/dialysis_centers` | 355 | CMS CCN | Census-geocoded coordinates with match quality |
| `clean/overture_places` | 2 | | CC0 rows only; 4,856 CDLA-Permissive/Apache rows held until the organizers rule on those licences |

Each table is in `clean/*.parquet` and `clean/json/*.json`. Rules and counts: `clean/CLEANING.md`; information gaps and how each is filled: `clean/GAPS.md`; sources and licences: `clean/SOURCES.md`.

Distances to medical shelters use the raw shelters table until the teammate shelters_clean exists. Shelters are not cleaned here.
