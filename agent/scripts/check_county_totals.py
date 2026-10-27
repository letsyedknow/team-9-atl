"""SC-002 cross-check (task T062): the map payload's county figures must match a direct GROUP BY.

Needs Application Default Credentials. Run from agent/:
    GOOGLE_CLOUD_PROJECT=<project> .venv/bin/python scripts/check_county_totals.py [--dataset evac_prod]
Exits non-zero if any county differs.
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from readiness_agent.map_data import SUSPECT_HIGH, SUSPECT_LOW, get_georgia_map_data  # noqa: E402

SQL = f"""
SELECT county_fips,
       COUNT(*) AS n,
       SUM(IF(evacuation_capacity BETWEEN {SUSPECT_LOW} AND {SUSPECT_HIGH}, evacuation_capacity, 0)) AS cap,
       COUNTIF(wheelchair_accessible IS NULL) AS wc_unrec
FROM `{{project}}.{{dataset}}.shelters_clean`
WHERE state = 'GA' AND latitude IS NOT NULL AND longitude IS NOT NULL
GROUP BY county_fips
"""


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--dataset", default=os.environ.get("EVAC_DATASET", "evac_prod"))
    a = p.parse_args()
    project = os.environ["GOOGLE_CLOUD_PROJECT"]

    from google.cloud import bigquery

    direct = {
        r["county_fips"]: r
        for r in bigquery.Client(project=project).query(SQL.format(project=project, dataset=a.dataset)).result()
    }
    payload = get_georgia_map_data(project, a.dataset)

    mismatches = 0
    for c in payload["counties"]:
        d = direct.get(c["county_fips"])
        want = (d["n"], float(d["cap"] or 0), d["wc_unrec"]) if d else (0, 0.0, 0)
        got = (c["shelter_count"], float(c["capacity_total"]["value"] or 0), c["wheelchair"]["unrecorded"])
        if want != got:
            mismatches += 1
            print(f"{c['county_fips']} {c['name']}: payload {got} != BigQuery {want}")
    print(f"{len(payload['counties'])} counties checked, {mismatches} mismatches")
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
