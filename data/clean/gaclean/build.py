import json
from pathlib import Path

import duckdb

from . import rules as R
from .sources import Sources

OUT = Path(__file__).resolve().parents[1] / "out"

# Leading columns, names and order, of the team's BigQuery evacuation_readiness.*_clean tables
# (bq show --schema, 2026-10-27). Clean-layer columns are appended after them.
BQ_COLUMNS = {
    "care_facilities": ["cms_certification_number_ccn", "provider_name", "provider_address", "citytown", "state",
                        "zip_code", "number_of_certified_beds", "ownership_type", "latitude", "longitude"],
    "hazard_tracts": ["geo_id", "POPULATION", "BUILDVALUE", "HRCN_AFREQ", "HRCN_EXPP", "HRCN_EALT", "HRCN_EALP",
                      "CFLD_AFREQ", "CFLD_EXPP", "CFLD_EALT", "CFLD_EALP"],
    "power_dependent_counties": ["objectid", "name", "namelsad", "fips_code_recode", "state", "fips_code",
                                 "county_fips_code", "county", "state_fips_code", "medicare_benes",
                                 "power_dependent_devices_dme", "facility_esrd_dialysis_any_dme",
                                 "o2_services_any_dme", "home_health_services_any_dme", "athome_hospice_any_dme",
                                 "any_healthcare_srvc_any_dme", "shape__area", "shape__length",
                                 "power_dependent_is_censored", "power_dependent_dme"],
}
EMPOWER_FIELDS = {
    "medicare_benes": "Medicare_Benes", "power_dependent": "Power_Dependent_Devices_DME",
    "dialysis": "Facility_ESRD_Dialysis_Any_DME", "oxygen": "O2_Services_Any_DME",
    "home_health": "Home_Health_Services_Any_DME", "hospice": "AtHome_Hospice_Any_DME",
    "any_service": "Any_Healthcare_Srvc_Any_DME",
}
OVERTURE_GROUPS = {
    "assisted_living_facility": "assisted_living", "retirement_home": "retirement_home",
    "ambulance_or_ems_service": "ambulance_ems", "medical_transportation": "medical_transport",
    "home_health_care": "home_health", "hospice": "hospice",
}


def lead(table: str, alias: str) -> str:
    return ", ".join(f'{alias}."{c}"' for c in BQ_COLUMNS[table])


def count(con, sql: str) -> int:
    return con.execute(f"SELECT COUNT(*) FROM ({sql})").fetchall()[0][0]


def expect(con, table: str, n: int) -> None:
    got = count(con, f"SELECT * FROM {table}")
    assert got == n, f"{table}: expected {n} rows, got {got}"
    print(f"  {table}: {got} rows")


def unmatched(con, label: str, sql: str) -> int:
    rows = con.execute(sql).fetchall()
    print(f"  unmatched {label}: {len(rows)}" + (f" e.g. {rows[:3]}" if rows else ""))
    return len(rows)


def connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial; SET geometry_always_xy = true;")
    return con


def register(con, src: Sources) -> None:
    src.check()
    for name, table in (("raw_shelters", "shelters"), ("raw_tracts", "vulnerability_tracts"),
                        ("raw_hazard", "hazard_tracts"), ("raw_care", "care_facilities"),
                        ("raw_power", "power_dependent_counties")):
        con.execute(f"CREATE VIEW {name} AS SELECT * FROM read_parquet('{src.snapshot / table / 'data.parquet'}')")
    con.execute(f"""CREATE VIEW raw_empower_live AS SELECT * FROM read_csv('{src.empower_live_county}',
                    types={{'FIPS_Code': 'VARCHAR'}})""")
    con.execute(f"""CREATE VIEW raw_empower_zip AS SELECT * FROM read_csv('{src.empower_live_zip}',
                    types={{'Zip_Code': 'VARCHAR', 'FIPS_Code': 'VARCHAR'}})""")
    con.execute(f"CREATE VIEW raw_cms_nh AS SELECT * FROM read_parquet('{src.cms / 'nursing_homes_ga.parquet'}')")
    con.execute(f"CREATE VIEW raw_cms_dialysis AS SELECT * FROM read_parquet('{src.cms / 'dialysis_facilities_ga.parquet'}')")
    con.execute(f"CREATE VIEW raw_dialysis_geo AS SELECT * FROM read_csv('{src.dialysis_geocoded}', types={{'ccn': 'VARCHAR'}})")
    con.execute(f"CREATE VIEW raw_overture AS SELECT * FROM read_parquet('{src.overture_places}')")


def build_hazard_tracts(con) -> None:
    con.execute(f"""
        CREATE TABLE hazard_tracts AS
        SELECT {lead('hazard_tracts', 'h')},
               left(h.geo_id, 5) AS county_fips, 'fips_from_geo_id' AS county_fips_rule,
               PERCENT_RANK() OVER (ORDER BY h.HRCN_EALP) AS hrcn_ealp_pctile,
               CASE WHEN h.HRCN_EALP IS NULL THEN 'unrecorded' ELSE 'recorded' END AS hrcn_ealp_pctile_status,
               'hrcn_ealp_percentile' AS hrcn_ealp_pctile_rule,
               COALESCE(h.CFLD_EXPP, 0) AS cfld_expp_clean,
               CASE WHEN h.POPULATION > 0 THEN LEAST(COALESCE(h.CFLD_EXPP, 0) / h.POPULATION, 1.0) END AS cfld_share,
               COALESCE(h.CFLD_EXPP, 0) > 0 AS coastal_flood_exposed,
               CASE WHEN h.CFLD_EXPP IS NULL THEN 'imputed' ELSE 'recorded' END AS cfld_status,
               CASE WHEN h.CFLD_EXPP IS NULL THEN 'cfld_null_outside_layer' ELSE 'source_value' END AS cfld_rule,
               t.geo_id IS NOT NULL AS has_vulnerability_tract
        FROM raw_hazard h LEFT JOIN (SELECT geo_id FROM raw_tracts) t USING (geo_id)
        ORDER BY h.geo_id
    """)
    expect(con, "hazard_tracts", count(con, "SELECT * FROM raw_hazard"))
    unmatched(con, "hazard rows without a vulnerability tract",
              "SELECT geo_id FROM hazard_tracts WHERE NOT has_vulnerability_tract")
    missing = con.execute("""SELECT COUNT(*), COALESCE(SUM(total_pop), 0)
                             FROM raw_tracts ANTI JOIN raw_hazard USING (geo_id)""").fetchall()[0]
    assert missing[1] == 0, f"{missing[0]} tracts without a hazard row hold {missing[1]} people"
    unmatched(con, "vulnerability tracts without a hazard row (pop 0)",
              "SELECT geo_id FROM raw_tracts ANTI JOIN raw_hazard USING (geo_id)")


def build_power_dependent_counties(con) -> None:
    live = []
    for name, col in EMPOWER_FIELDS.items():
        v, lo, st = R.empower_value(f"l.{col}")
        live.append(f"{v} AS {name}_live, {lo} AS {name}_live_low, {st} AS {name}_live_status, "
                    f"CASE WHEN l.{col} = 11 THEN 'empower_suppressed_1_11' ELSE 'empower_live_canonical' END "
                    f"AS {name}_live_rule")
    con.execute(f"""
        CREATE TABLE power_dependent_counties AS
        WITH d AS (
            SELECT z.FIPS_Code AS fips_code, COUNT(*) AS dialysis_centers,
                   SUM(TRY_CAST(c."# of Dialysis Stations" AS INTEGER)) AS dialysis_stations
            FROM raw_cms_dialysis c JOIN raw_empower_zip z ON z.Zip_Code = left(c."ZIP Code", 5)
            GROUP BY 1
        )
        SELECT {lead('power_dependent_counties', 'p')},
               'recorded' AS power_dependent_dme_status, 'source_value' AS power_dependent_dme_rule,
               'suspect' AS facility_esrd_dialysis_any_dme_status,
               'empower_snapshot_unverified' AS facility_esrd_dialysis_any_dme_rule,
               {', '.join(live)},
               COALESCE(d.dialysis_centers, 0) AS dialysis_centers,
               COALESCE(d.dialysis_stations, 0) AS dialysis_stations,
               'cms_dialysis_stations' AS dialysis_stations_rule,
               l.Facility_ESRD_Dialysis_Any_DME / NULLIF(d.dialysis_stations, 0) AS dialysis_patients_per_station
        FROM raw_power p
        JOIN raw_empower_live l ON l.FIPS_Code = p.fips_code
        LEFT JOIN d ON d.fips_code = p.fips_code
        ORDER BY p.fips_code
    """)
    expect(con, "power_dependent_counties", count(con, "SELECT * FROM raw_power"))
    unmatched(con, "live emPOWER counties not in snapshot",
              "SELECT l.FIPS_Code FROM raw_empower_live l ANTI JOIN raw_power p ON p.fips_code = l.FIPS_Code")
    unmatched(con, "CMS dialysis ZIPs without an emPOWER county",
              """SELECT "ZIP Code" FROM raw_cms_dialysis c
                 ANTI JOIN raw_empower_zip z ON z.Zip_Code = left(c."ZIP Code", 5)""")


def nearest_tract(con, table: str, key: str, lon: str, lat: str) -> None:
    con.execute(f"""
        CREATE TABLE {table}_nearest AS
        SELECT x.{key}, t.geo_id AS nearest_tract_geo_id, t.county_fips AS nearest_tract_county_fips,
               ST_Distance({R.point('x.' + lon, 'x.' + lat)}, {R.point('t.lon', 't.lat')}) / 1000 AS km_to_tract_centroid
        FROM {table}_pre x CROSS JOIN raw_tracts t
        WHERE x.{lat} IS NOT NULL
        QUALIFY ROW_NUMBER() OVER (PARTITION BY x.{key}
                ORDER BY ST_Distance({R.point('x.' + lon, 'x.' + lat)}, {R.point('t.lon', 't.lat')}), t.geo_id) = 1
    """)


def build_care_facilities(con) -> None:
    con.execute(f"""
        CREATE TABLE care_facilities_pre AS
        SELECT {lead('care_facilities', 'c')},
               {R.trim('c.provider_name')} AS provider_name_clean,
               {R.trim('c.provider_address')} AS provider_address_clean,
               {R.trim('c.citytown')} AS citytown_clean,
               'nullif_trim' AS text_rule,
               {R.trim('n."County/Parish"')} AS cms_county_text,
               TRY_CAST(n."Number of Certified Beds" AS DOUBLE) AS cms_certified_beds,
               TRY_CAST(n."Average Number of Residents per Day" AS DOUBLE) AS avg_residents_per_day,
               {R.recorded_or_unrecorded('TRY_CAST(n."Average Number of Residents per Day" AS DOUBLE)')}
                   AS avg_residents_per_day_status,
               TRY_CAST(n."Average Number of Residents per Day" AS DOUBLE)
                   / NULLIF(TRY_CAST(n."Number of Certified Beds" AS DOUBLE), 0) AS occupancy_rate,
               {R.recorded_or_unrecorded('TRY_CAST(n."Average Number of Residents per Day" AS DOUBLE)')}
                   AS occupancy_rate_status,
               'cms_occupancy' AS occupancy_rate_rule,
               {R.trim('n."Provider Type"')} AS cms_provider_type,
               {R.trim('n."Automatic Sprinkler Systems in All Required Areas"')} AS cms_sprinklers_all_required_areas,
               'cms_join_ccn' AS cms_rule
        FROM raw_care c JOIN raw_cms_nh n ON n."CMS Certification Number (CCN)" = c.cms_certification_number_ccn
    """)
    expect(con, "care_facilities_pre", count(con, "SELECT * FROM raw_care"))
    unmatched(con, "CMS nursing homes not in snapshot",
              """SELECT "CMS Certification Number (CCN)" FROM raw_cms_nh
                 ANTI JOIN raw_care ON cms_certification_number_ccn = "CMS Certification Number (CCN)\"""")
    nearest_tract(con, "care_facilities", "cms_certification_number_ccn", "longitude", "latitude")
    con.execute(f"""
        CREATE TABLE care_facilities AS
        WITH med AS (SELECT {R.point('longitude', 'latitude')} AS g FROM raw_shelters WHERE is_medical)
        SELECT p.*,
               n.nearest_tract_geo_id, n.km_to_tract_centroid, 'nearest_tract_centroid' AS nearest_tract_rule,
               n.nearest_tract_county_fips AS county_fips, 'imputed' AS county_fips_status,
               'nearest_tract_centroid' AS county_fips_rule,
               h.hrcn_ealp_pctile, h.HRCN_AFREQ AS hrcn_afreq, h.cfld_share, h.coastal_flood_exposed,
               (SELECT MIN(ST_Distance({R.point('p.longitude', 'p.latitude')}, med.g)) / 1000 FROM med)
                   AS km_nearest_medical_shelter,
               'assumption' AS km_nearest_medical_shelter_status,
               'medical_shelter_distance_pending' AS km_nearest_medical_shelter_rule
        FROM care_facilities_pre p JOIN care_facilities_nearest n USING (cms_certification_number_ccn)
        LEFT JOIN hazard_tracts h ON h.geo_id = n.nearest_tract_geo_id
        ORDER BY p.cms_certification_number_ccn
    """)
    expect(con, "care_facilities", count(con, "SELECT * FROM raw_care"))
    unmatched(con, "care facilities whose tract has no hazard row",
              "SELECT cms_certification_number_ccn FROM care_facilities WHERE hrcn_ealp_pctile IS NULL")


def build_dialysis_centers(con) -> None:
    con.execute(f"""
        CREATE TABLE dialysis_centers AS
        SELECT d."CMS Certification Number (CCN)" AS ccn,
               {R.trim('d."Facility Name"')} AS facility_name, {R.trim('d."Address Line 1"')} AS address,
               {R.trim('d."City/Town"')} AS city, left(d."ZIP Code", 5) AS zip,
               {R.trim('d."County/Parish"')} AS cms_county_text,
               z.FIPS_Code AS county_fips, 'imputed' AS county_fips_status, 'zip_to_county_empower' AS county_fips_rule,
               TRY_CAST(d."# of Dialysis Stations" AS INTEGER) AS stations,
               {R.trim('d."Late Shift"')} AS late_shift,
               {R.trim('d."Offers in-center hemodialysis"')} AS offers_in_center_hemodialysis,
               {R.trim('d."Offers peritoneal dialysis"')} AS offers_peritoneal,
               {R.trim('d."Offers home hemodialysis training"')} AS offers_home_hemodialysis_training,
               {R.trim('d."Profit or Non-Profit"')} AS profit_status, {R.trim('d."Chain Organization"')} AS chain,
               CASE WHEN g.location_status LIKE 'geocoded%' THEN g.lat END AS latitude,
               CASE WHEN g.location_status LIKE 'geocoded%' THEN g.lon END AS longitude,
               CASE WHEN g.location_status LIKE 'geocoded%' THEN 'external' ELSE 'unrecorded' END AS coordinates_status,
               CASE WHEN g.location_status LIKE 'geocoded%' THEN 'census_geocoder' ELSE 'coordinates_absent' END
                   AS coordinates_rule,
               g.location_status AS coordinates_confidence
        FROM raw_cms_dialysis d JOIN raw_empower_zip z ON z.Zip_Code = left(d."ZIP Code", 5)
        LEFT JOIN raw_dialysis_geo g ON g.ccn = d."CMS Certification Number (CCN)"
        ORDER BY ccn
    """)
    expect(con, "dialysis_centers", count(con, "SELECT * FROM raw_cms_dialysis"))
    unmatched(con, "dialysis centers missing from geocoder output",
              "SELECT ccn FROM dialysis_centers WHERE coordinates_confidence IS NULL")


def build_overture_places(con) -> None:
    groups = " ".join(f"WHEN '{k}' THEN '{v}'" for k, v in OVERTURE_GROUPS.items())
    con.execute(f"""
        CREATE TABLE overture_places_pre AS
        SELECT *, CASE category {groups} END AS place_group, 'external' AS record_status, 'overture_places' AS record_rule
        FROM raw_overture WHERE category IN ({', '.join(f"'{k}'" for k in OVERTURE_GROUPS)})
    """)
    nearest_tract(con, "overture_places", "id", "lon", "lat")
    con.execute("""
        CREATE TABLE overture_places AS
        SELECT p.*, n.nearest_tract_geo_id, n.nearest_tract_county_fips AS county_fips,
               'imputed' AS county_fips_status, 'nearest_tract_centroid' AS county_fips_rule
        FROM overture_places_pre p LEFT JOIN overture_places_nearest n USING (id)
        ORDER BY place_group, id
    """)
    expect(con, "overture_places", count(con, "SELECT * FROM overture_places_pre"))
    unmatched(con, "overture places without coordinates", "SELECT id FROM overture_places WHERE county_fips IS NULL")


TABLES = {
    "care_facilities": "SELECT * FROM care_facilities",
    "hazard_tracts": "SELECT * FROM hazard_tracts",
    "power_dependent_counties": "SELECT * FROM power_dependent_counties",
    "dialysis_centers": "SELECT * FROM dialysis_centers",
    "overture_places": "SELECT * FROM overture_places",
}


def build_all(con) -> None:
    for step in (build_hazard_tracts, build_power_dependent_counties, build_care_facilities, build_dialysis_centers,
                 build_overture_places):
        print(step.__name__)
        step(con)


def numbers(con) -> dict:
    def q(sql: str):
        return con.execute(sql).fetchall()[0]

    p = q("""SELECT SUM(power_dependent_live), SUM(power_dependent_dme), SUM(dialysis_live),
                    SUM(facility_esrd_dialysis_any_dme), SUM(dialysis_stations), SUM(dialysis_centers)
             FROM power_dependent_counties""")
    suppressed = {name: q(f"SELECT COUNT(*) FROM power_dependent_counties WHERE {name}_live_status = 'imputed'")[0]
                  for name in EMPOWER_FIELDS}
    h = q("""SELECT COUNT(*) FILTER (WHERE cfld_status = 'imputed'), COUNT(*) FILTER (WHERE coastal_flood_exposed),
                    SUM(POPULATION), COUNT(*) FILTER (WHERE NOT has_vulnerability_tract)
             FROM hazard_tracts""")
    c = q("""SELECT SUM(number_of_certified_beds), SUM(cms_certified_beds), SUM(avg_residents_per_day),
                    SUM(avg_residents_per_day) / SUM(cms_certified_beds) FILTER (WHERE avg_residents_per_day IS NOT NULL),
                    COUNT(*) FILTER (WHERE avg_residents_per_day IS NULL),
                    COUNT(*) FILTER (WHERE coastal_flood_exposed), COUNT(*) FILTER (WHERE hrcn_ealp_pctile >= 0.8),
                    median(km_nearest_medical_shelter)
             FROM care_facilities""")
    return {
        "rows": {name: count(con, sql) for name, sql in TABLES.items()},
        "hazard_tracts": {"cfld_imputed_outside_layer": h[0], "coastal_flood_exposed": h[1], "nri_population": h[2],
                          "without_vulnerability_tract": h[3],
                          "vulnerability_tracts_without_hazard_row": q(
                              "SELECT COUNT(*) FROM raw_tracts ANTI JOIN raw_hazard USING (geo_id)")[0]},
        "power_dependent_counties": {
            "power_dependent_live": p[0], "power_dependent_snapshot": p[1], "dialysis_live": p[2],
            "facility_esrd_dialysis_any_dme_snapshot": p[3], "dialysis_stations": p[4], "dialysis_centers": p[5],
            "dialysis_patients_per_station": p[2] / p[4], "counties_suppressed_1_11": suppressed,
        },
        "care_facilities": {
            "snapshot_certified_beds": c[0], "cms_certified_beds": c[1], "avg_residents_per_day": c[2],
            "occupancy_rate": c[3], "occupancy_unrecorded": c[4], "in_coastal_flood_tract": c[5],
            "in_top_quintile_hurricane_tract": c[6], "median_km_nearest_medical_shelter_pending": c[7],
            "cms_county_text_disagrees_with_imputed_fips": q("""
                SELECT COUNT(*) FROM care_facilities f JOIN raw_power p ON p.fips_code = f.county_fips
                WHERE lower(replace(f.cms_county_text, ' ', '')) <> lower(replace(p.name, ' ', ''))""")[0],
        },
        "dialysis_centers": {
            "coordinates_confidence": {k: n for k, n in con.execute(
                "SELECT coordinates_confidence, COUNT(*) FROM dialysis_centers GROUP BY 1 ORDER BY 1").fetchall()},
            "stations_without_coordinates": q("SELECT SUM(stations) FROM dialysis_centers WHERE latitude IS NULL")[0],
        },
        "overture_places": {
            g: {"places": n, "not_permanently_closed": o}
            for g, n, o in con.execute("""
                SELECT place_group, COUNT(*), COUNT(*) FILTER (WHERE operating_status IS DISTINCT FROM 'permanently_closed')
                FROM overture_places GROUP BY 1 ORDER BY 1""").fetchall()
        },
    }


def rounded(value):
    if isinstance(value, dict):
        return {k: rounded(v) for k, v in value.items()}
    if isinstance(value, float):
        return round(value, 4)
    return value


def write(con, out: Path = OUT) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    for name, sql in TABLES.items():
        con.execute(f"COPY ({sql}) TO '{out / (name + '.parquet')}' (FORMAT parquet, COMPRESSION zstd)")
    nums = rounded(numbers(con))
    (out / "numbers.json").write_text(json.dumps(nums, indent=2, sort_keys=True, default=float) + "\n")
    (out / "rules.json").write_text(json.dumps(R.RULES, indent=2, sort_keys=True) + "\n")
    return nums


def main() -> None:
    from .gaps import write_gaps
    from .report import write_cleaning, write_post

    con = connect()
    register(con, Sources.from_env())
    build_all(con)
    nums = write(con)
    write_gaps(nums)
    write_cleaning(con)
    write_post(con)
    print(json.dumps(nums["rows"], indent=2))


if __name__ == "__main__":
    main()
