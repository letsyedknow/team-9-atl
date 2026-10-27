"""Regenerate frontend/tests/mocks/mapData.fixture.json from build_payload (tasks T020, T059).

Synthetic rows only: real coordinates for a few Georgia places, invented shelters. Run from agent/:
    .venv/bin/python scripts/make_frontend_fixture.py
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agent"))

from readiness_agent.map_data import build_payload  # noqa: E402

SCHEMA = ROOT / "specs/001-georgia-shelter-map/contracts/map-data.schema.json"
OUT = ROOT / "frontend/tests/mocks/mapData.fixture.json"


def shelter(sid, name, fips, county, lat, lon, cap, wc=None, gen=None, surge=None, med=False,
            pop="GENERAL", usage="EVAC"):
    return dict(
        shelter_id=sid, shelter_name=name, address_1="1 Main St", city=county, zip="30000",
        county_fips=fips, county_name=county, county_parish=county.upper(), latitude=lat,
        longitude=lon, evacuation_capacity=cap, post_impact_capacity=None, usage=usage,
        wheelchair_accessible=wc, generator_onsite=gen, is_medical=med, population_code=pop,
        in_surge_slosh_area=surge,
    )


SHELTERS = [
    shelter("J1", "Commerce High School", "13157", "Jackson", 34.204, -83.457, 270135),
    shelter("J2", "Commerce Primary School", "13157", "Jackson", 34.199, -83.462, 225112),
    shelter("J3", "Jackson County Comprehensive High School", "13157", "Jackson", 34.117, -83.574,
            600, wc=True, gen=True),
    shelter("G1", "Glynn Academy", "13127", "Glynn", 31.155, -81.489, 400, wc=False, surge=True),
    shelter("G2", "Brunswick High School", "13127", "Glynn", 31.200, -81.480, 500, usage="POST"),
    shelter("C1", "Savannah Civic Center", "13051", "Chatham", 32.081, -81.094, 1200, wc=True,
            surge=True, gen=True),
    shelter("C2", "Groves High School", "13051", "Chatham", 32.103, -81.163, 300, surge=False),
    shelter("B1", "Cobb Civic Center", "13067", "Cobb", 33.952, -84.548, 800),
    shelter("M1", "Macon Centreplex", "13021", "Bibb", 32.838, -83.628, 1500, wc=True, med=True),
    shelter("W1", "Waycross Middle School", "13299", "Ware", 31.213, -82.354, 700, gen=False),
    shelter("Y1", "Wayne County High School", "13305", "Wayne", 31.607, -81.885, 350),
    # Coordinates outside any Georgia county: exercises location_disagrees.
    shelter("X1", "Misplaced Shelter", None, "Fulton", 38.30, -122.50, 250, pop=None),
]

COUNTIES = [
    ("13157", "Jackson"), ("13127", "Glynn"), ("13051", "Chatham"), ("13001", "Appling"),
    ("13067", "Cobb"), ("13021", "Bibb"), ("13299", "Ware"), ("13305", "Wayne"),
]

TRACTS = [
    {"geo_id": f + "000100", "total_pop": 4000, "households_no_vehicle": 120, "pop_65_plus": 600,
     "pct_disability": 14.2}
    for f, _ in COUNTIES
] + [
    # SVI's -999 sentinel: must be excluded, not averaged in.
    {"geo_id": "13127000200", "total_pop": 2000, "households_no_vehicle": 80, "pop_65_plus": 500,
     "pct_disability": -999},
]


def main() -> None:
    payload = build_payload(SHELTERS, TRACTS, COUNTIES,
                            generated_at=datetime(2026, 10, 27, tzinfo=timezone.utc))
    jsonschema.validate(payload, json.loads(SCHEMA.read_text()))
    OUT.write_text(json.dumps(payload, indent=1) + "\n")
    print(f"Wrote {len(payload['shelters'])} shelters, {len(payload['counties'])} counties to {OUT}")


if __name__ == "__main__":
    main()
