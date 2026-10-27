# Sources and licences

Every input is read locally; nothing is fetched at build time. Paths are the defaults in
`gaclean/sources.py`, and each can be overridden by the environment variable shown.

| Input | Default path (env) | Publisher | Licence | Used for |
|---|---|---|---|---|
| Georgia snapshot: `care_facilities`, `hazard_tracts`, `power_dependent_counties`, `vulnerability_tracts`, `shelters` | `~/work/c4data/GA/<table>/data.parquet` (`C4DATA_GA`) | Challenge staging of CMS, FEMA NRI, HHS emPOWER, Census ACS/CDC SVI, FEMA NSS | Per the repository README: CMS and emPOWER US Government work; FEMA NRI terms of use, attribution required, planning purposes only; NSS US Government work (FEMA and American Red Cross co-attributed) | Base rows and leading columns of the three clean tables; tract centroids; shelters read only for the pending medical-shelter distance |
| HHS emPOWER REST service, county and ZIP layers (fetched 2026-10-27) | `$EXTDATA/emPOWER/empower_ga_{county,zip}.csv` (`EXTDATA`, default `~/work/extdata`) | HHS ASPR / CMS | US Government work, de-identified; use only for emergency preparedness and make no attempt to identify any individual | Canonical live counts (`*_live`); ZIP-to-county for dialysis centers |
| CMS Provider Data: Nursing Home Provider Information, Dialysis Facility listing (GA rows) | `$CMS_DIR/{nursing_homes_ga,dialysis_facilities_ga}.parquet` (`CMS_DIR`) | Centers for Medicare & Medicaid Services | US Government work | Residents per day, CMS beds, provider type, sprinklers; dialysis stations |
| Census Geocoder results for the CMS dialysis addresses | `dialysis_centers_geocoded.csv` (`DIALYSIS_GEOCODED`) | US Census Bureau | US Government work | Dialysis center coordinates and match quality |
| Overture Maps Places, release 2026-10-21.0, Georgia care and transport categories | `places_ga_care_transport.parquet` (`OVERTURE_PLACES`) | Overture Maps Foundation | Per row in `source_license`: CDLA-Permissive-2.0 (Meta, Microsoft, BrightQuery, Uberall, Birdeye, RenderSEO), Apache-2.0 (Foursquare), CC0-1.0 (AllThePlaces) | Assisted living, retirement homes, home health, hospice, ambulance and medical-transport listings |

Not used: the GDOT evacuation-route layer (no stated licence), DCH licensed-facility lists (no
stated licence), and Census TIGER/Line roads (public domain, used by `analysis/flow`, not here).
No phone numbers, emails or websites are carried from Overture.

## Licence bar

The repository bar is public domain, CC0 or US Government work, and no non-commercial,
no-derivatives, share-alike, unstated licence or individual-level personal data. Overture's
CDLA-Permissive-2.0 and Apache-2.0 rows are permissive and carry none of the excluded terms; they
are kept with their per-row licence so any consumer can filter to CC0 only.

## Attribution

- Centers for Medicare & Medicaid Services, Provider Data Catalog (data.cms.gov), accessed 2026-10-27.
- HHS emPOWER Program (ASPR/CMS), HHS emPOWER REST Service, accessed 2026-10-27.
- FEMA National Risk Index. For planning purposes only.
- US Census Bureau Geocoder.
- Overture Maps Foundation, overturemaps.org. Data from Meta, Microsoft, Foursquare, AllThePlaces and
  others under CDLA Permissive 2.0, Apache 2.0 and CC0.

Foursquare rows (`source_dataset = 'Foursquare'`) are redistributed under Apache 2.0 with this notice:
"Copyright 2024 Foursquare Labs, Inc. All rights reserved. Available under Apache 2.0."
