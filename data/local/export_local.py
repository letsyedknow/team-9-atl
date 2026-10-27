import json
import sys
from pathlib import Path

import duckdb

SNAP = Path(sys.argv[1])
OUT = Path(sys.argv[2])
TABLES = ["shelters", "vulnerability_tracts", "hazard_tracts", "care_facilities", "power_dependent_counties"]
EXPECTED = {"shelters": 1792, "vulnerability_tracts": 2796, "hazard_tracts": 2791, "care_facilities": 356, "power_dependent_counties": 159}
POINTS = {
    "shelters": ("latitude", "longitude", "shelter_id"),
    "care_facilities": ("latitude", "longitude", "cms_certification_number_ccn"),
    "vulnerability_tracts": ("lat", "lon", "geo_id"),
}

con = duckdb.connect()
for sub in ["parquet", "json", "geojson"]:
    (OUT / sub).mkdir(parents=True, exist_ok=True)

counts = {}
for t in TABLES:
    src = SNAP / t / "data.parquet"
    rel = con.sql(f"SELECT * FROM '{src}'")
    n = con.sql(f"SELECT count(*) FROM '{src}'").fetchall()[0][0]
    if n != EXPECTED[t]:
        raise AssertionError(f"{t}: {n} rows, expected {EXPECTED[t]}")
    counts[t] = n
    con.execute(f"COPY (SELECT * FROM '{src}') TO '{OUT / 'parquet' / (t + '.parquet')}' (FORMAT parquet)")
    cols = rel.columns
    rows = [dict(zip(cols, r, strict=True)) for r in rel.fetchall()]
    (OUT / "json" / f"{t}.json").write_text(json.dumps(rows, default=str))
    if t in POINTS:
        lat, lon, key = POINTS[t]
        feats = [
            {"type": "Feature", "id": r[key], "geometry": {"type": "Point", "coordinates": [r[lon], r[lat]]},
             "properties": {k: v for k, v in r.items() if k not in (lat, lon)}}
            for r in rows if r[lat] is not None and r[lon] is not None
        ]
        (OUT / "geojson" / f"{t}.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats}, default=str))

(OUT / "counts.json").write_text(json.dumps(counts, indent=1))
print(json.dumps(counts))
