"""Tool output shaping, with BigQuery replaced by fakes (tasks T068, T078). No credentials needed."""

import json
from types import SimpleNamespace

import pytest

from readiness_agent import evacuation_tools as tools
from readiness_agent.map_data import shelter_record


def shelter_row(sid, cap=200, wc=None, gen=None, fips="13157", name=None):
    return {
        "shelter_id": sid, "shelter_name": name or f"Shelter {sid}", "address_1": "1 Main St",
        "city": "Commerce", "zip": "30529", "county_fips": fips, "county_name": "Jackson",
        "county_parish": "JACKSON", "latitude": 34.2, "longitude": -83.4,
        "evacuation_capacity": cap, "post_impact_capacity": None, "usage": "EVAC",
        "wheelchair_accessible": wc, "generator_onsite": gen, "is_medical": False,
        "population_code": "GEN", "in_surge_slosh_area": None,
    }


@pytest.fixture
def fake_bq(monkeypatch):
    calls = []
    rows = {"value": []}
    monkeypatch.setattr(tools, "_bigquery", lambda: SimpleNamespace(
        ScalarQueryParameter=lambda name, type_, value: SimpleNamespace(
            name=name, type_=type_, value=value
        ),
        ArrayQueryParameter=lambda name, type_, values: SimpleNamespace(
            name=name, type_=type_, values=values
        ),
    ))

    def run(sql, params=None):
        calls.append((sql, {p.name: getattr(p, "value", getattr(p, "values", None)) for p in params or []}))
        return rows["value"]

    monkeypatch.setattr(tools, "_run_query", run)
    return calls, rows


def test_assess_shelter_accessibility_uses_county_fips_and_returns_ids(fake_bq):
    calls, rows = fake_bq
    rows["value"] = [shelter_row("a", wc=None), shelter_row("b", wc=True), shelter_row("c", wc=False)]
    out = tools.assess_shelter_accessibility(county_fips="13157")
    sql, params = calls[0]
    assert params["county_fips"] == "13157"
    assert "county_fips = @county_fips" in sql
    assert all(s["shelter_id"] and s["county_fips"] == "13157" for s in out["shelters"])


def test_unrecorded_is_never_no(fake_bq):
    _, rows = fake_bq
    rows["value"] = [shelter_row("a", wc=None), shelter_row("b", wc=None), shelter_row("c", wc=False)]
    out = tools.assess_shelter_accessibility(county_fips="13157")
    assert out["shelters"][0]["wheelchair_accessible"] == "UNRECORDED"
    assert out["wheelchair"] == {"yes": 0, "no": 1, "unrecorded": 2}


def test_suspect_capacity_flagged_and_ranked_as_zero_in_sql(fake_bq):
    calls, rows = fake_bq
    rows["value"] = [shelter_row("a", cap=270135, name="Commerce High School")]
    out = tools.assess_shelter_accessibility(county_fips="13157")
    assert "suspect_capacity" in out["shelters"][0]["quality_flags"]
    assert "evacuation_capacity > 100000, 0" in calls[0][0]


def test_rank_county_evacuation_needs_uses_clean_tables_and_reasons(monkeypatch):
    calls = []
    responses = [
        [{
            "tract_id": "13157000100",
            "county_fips": "13157",
            "households_no_vehicle": 24,
            "pct_no_vehicle": 12.5,
            "pct_age_65_plus": 20.0,
            "pct_disability": 14.0,
            "pct_mobility": 18.0,
            "pct_selfcare": 7.0,
            "pct_indeplive": 10.0,
            "mobile_homes": 9,
        }],
        [{
            "facility_id": "115002",
            "provider_name": "Jackson Care Center",
            "avg_residents_per_day": 120.5,
            "avg_residents_per_day_status": "recorded",
            "coastal_flood_exposed": True,
            "coastal_flood_exposed_status": "imputed",
        }],
    ]
    monkeypatch.setattr(
        tools,
        "_scalar",
        lambda name, _type, value: SimpleNamespace(name=name, value=value),
    )

    def run(sql, params=None):
        calls.append((sql, {p.name: p.value for p in params or []}))
        return responses[len(calls) - 1]

    monkeypatch.setattr(tools, "_run_query", run)
    result = tools.rank_county_evacuation_needs(county_fips="13157")

    assert "vulnerability_tracts_clean" in calls[0][0]
    assert "care_facilities_clean" in calls[1][0]
    assert calls[0][1]["tract_county_fips"] == "13157"
    assert calls[1][1]["facility_county_fips"] == "13157"
    assert "24 households without a vehicle" in result["priority_tracts"][0]["priority_reason"]
    assert "7% modeled self-care difficulty" in result["priority_tracts"][0]["priority_reason"]
    assert "CMS average 120.5 residents per day" in result["nursing_home_facilities"][0]["priority_reason"]
    assert "recorded coastal-flood exposure" in result["nursing_home_facilities"][0]["priority_reason"]


def test_find_shelter_support_returns_granular_flags_and_full_county_counts(fake_bq, monkeypatch):
    calls, rows = fake_bq
    monkeypatch.setattr(
        tools,
        "_scalar",
        lambda name, _type, value: SimpleNamespace(name=name, value=value),
    )
    rows["value"] = [{
        "shelter_id": 101,
        "shelter_name": "Jackson Medical Shelter",
        "address_1": "1 Main St",
        "city": "Commerce",
        "zip": "30529",
        "county_fips": "13157",
        "county_name": "Jackson",
        "population_code": "MED",
        "is_medical": True,
        "generator_onsite": None,
        "total_shelters": 3,
        "medical_yes": 1,
        "medical_no": 1,
        "medical_unrecorded": 1,
        "generator_yes": 1,
        "generator_no": 1,
        "generator_unrecorded": 1,
    }]

    result = tools.find_shelter_medical_and_generator_support(county_fips="13157", limit=1)

    sql, params = calls[0]
    assert params["county_fips"] == "13157"
    assert params["state"] == "GA"
    assert "COUNTIF(population_code IS NULL OR is_medical IS NULL) OVER()" in sql
    assert "COUNTIF(generator_onsite IS NULL) OVER()" in sql
    assert result["total_shelters"] == 3
    assert result["returned_shelters"] == 1
    assert result["counts"] == {
        "medical_support": {"yes": 1, "no": 1, "unrecorded": 1},
        "generator_onsite": {"yes": 1, "no": 1, "unrecorded": 1},
    }
    assert result["shelters"][0] == {
        "shelter_id": "101",
        "name": "Jackson Medical Shelter",
        "address": "1 Main St, Commerce, 30529",
        "county_fips": "13157",
        "county_name": "Jackson",
        "medical_support": "YES",
        "generator_onsite": "UNRECORDED",
    }


def test_find_shelter_support_requires_county_and_valid_limit(fake_bq):
    with pytest.raises(ValueError, match="county_fips or county"):
        tools.find_shelter_medical_and_generator_support()
    with pytest.raises(ValueError, match="between 1 and 100"):
        tools.find_shelter_medical_and_generator_support(county="Jackson", limit=101)


def test_find_shelter_support_treats_missing_population_code_as_unrecorded(fake_bq, monkeypatch):
    _, rows = fake_bq
    monkeypatch.setattr(
        tools,
        "_scalar",
        lambda name, _type, value: SimpleNamespace(name=name, value=value),
    )
    rows["value"] = [{
        "shelter_id": 102,
        "shelter_name": "County Shelter",
        "county_fips": "13157",
        "population_code": None,
        "is_medical": False,
        "generator_onsite": False,
        "total_shelters": 1,
        "medical_yes": 0,
        "medical_no": 0,
        "medical_unrecorded": 1,
        "generator_yes": 0,
        "generator_no": 1,
        "generator_unrecorded": 0,
    }]

    result = tools.find_shelter_medical_and_generator_support(county="Jackson")

    assert result["shelters"][0]["medical_support"] == "UNRECORDED"
    assert result["shelters"][0]["generator_onsite"] == "NO"


def test_analyze_county_readiness_gaps_finds_access_and_generator_gaps(monkeypatch):
    accessible = shelter_row("a", wc=True, gen=None, name="Accessible Shelter")
    accessible["in_surge_slosh_area"] = True
    no_generator = shelter_row("b", wc=False, gen=False, name="No Generator Shelter")
    tract_rows = [
        {
            "tract_id": "13157000100",
            "county_fips": "13157",
            "county_name": "Jackson",
            "households_no_vehicle": 5,
            "pct_no_vehicle": 10,
            "pct_age_65_plus": 20,
            "pct_disability": 15,
            "lat": 34.2,
            "lon": -83.4,
        },
        {
            "tract_id": "13157000200",
            "county_fips": "13157",
            "county_name": "Jackson",
            "households_no_vehicle": 12,
            "pct_no_vehicle": 20,
            "pct_age_65_plus": 10,
            "pct_disability": 9,
            "lat": None,
            "lon": None,
        },
        {
            "tract_id": "13157000300",
            "county_fips": "13157",
            "county_name": "Jackson",
            "households_no_vehicle": 7,
            "pct_no_vehicle": 15,
            "pct_age_65_plus": 11,
            "pct_disability": 8,
            "lat": 31.0,
            "lon": -81.0,
        },
    ]
    monkeypatch.setattr(
        tools,
        "_scalar",
        lambda name, _type, value: SimpleNamespace(name=name, value=value),
    )
    monkeypatch.setattr(tools, "_surge_fallback_exists", lambda: False)
    monkeypatch.setattr(tools, "find_power_dependent_counties", lambda **_: {
        "counties": [{"power_dependent_dme": 2500}],
        "source": tools.SOURCES["power"],
    })

    def run(sql, params=None):
        if "v.geo_id AS tract_id" in sql:
            return tract_rows
        if "care_facilities_clean" in sql:
            return [{
                "facility_id": "115002",
                "provider_name": "County Nursing Home",
                "coastal_flood_exposed": True,
                "coastal_flood_exposed_status": "imputed",
            }]
        if "shelters_clean" in sql and "s.county_fips = @county_fips" in sql:
            return [accessible, no_generator]
        if "shelters_clean" in sql:
            return [accessible, no_generator]
        raise AssertionError(f"Unexpected query: {sql}")

    monkeypatch.setattr(tools, "_run_query", run)
    result = tools.analyze_county_readiness_gaps(
        county_fips="13157", reach_km=80, detail_limit=3
    )

    access = result["accessibility_gaps"]
    assert access["tracts_without_accessible_destination_within_reach"] == 2
    assert access["households_no_vehicle_in_all_access_gaps"] == 19
    assert len(access["top_gaps"]) == 2
    assert access["top_gaps"][0]["tract_id"] == "13157000200"
    with_access = next(
        row for row in access["top_tract_destinations"] if row["tract_id"] == "13157000100"
    )
    assert with_access["nearest_accessible_shelter"]["shelter_id"] == "a"
    assert result["generator_gaps"]["shelter_count"] == 2
    assert result["generator_gaps"]["county_power_dependent_dme"] == 2500
    assert result["flood_and_surge_gaps"]["shelters_recorded_in_surge_zone"][0]["shelter_id"] == "a"
    assert result["flood_and_surge_gaps"]["nursing_homes_recorded_coastal_flood_exposed"][0]["facility_id"] == "115002"
    assert "no generator field" in result["flood_and_surge_gaps"]["nursing_home_generator_status"]


def test_analyze_county_readiness_gaps_validates_thresholds():
    with pytest.raises(ValueError, match="county_fips"):
        tools.analyze_county_readiness_gaps("")
    with pytest.raises(ValueError, match="between 25 and 200"):
        tools.analyze_county_readiness_gaps("13157", reach_km=10)


def test_check_receiving_shelters_live_deduplicates_and_limits(monkeypatch):
    checked = []
    monkeypatch.setattr(
        tools,
        "check_shelter_google_maps",
        lambda shelter_id: checked.append(shelter_id) or {"shelter_id": shelter_id},
    )

    result = tools.check_receiving_shelters_live(["a", "a", "b"])

    assert checked == ["a", "b"]
    assert result["checked_count"] == 2
    assert result["checks"] == [{"shelter_id": "a"}, {"shelter_id": "b"}]
    with pytest.raises(ValueError, match="At most 3"):
        tools.check_receiving_shelters_live([str(i) for i in range(4)])


def test_power_counties_have_county_fips(fake_bq):
    calls, rows = fake_bq
    rows["value"] = [{"county": "Chatham", "state": "GA", "power_dependent_dme": 5000, "county_fips": "13051"}]
    out = tools.find_power_dependent_counties(county_fips="13051")
    assert "fips_code AS county_fips" in calls[0][0]
    assert calls[0][1]["county_fips"] == "13051"
    assert out["counties"][0]["county_fips"] == "13051"


def test_get_shelters_caps_ids_and_preserves_order(fake_bq):
    calls, rows = fake_bq
    with pytest.raises(ValueError):
        tools.get_shelters([str(i) for i in range(26)])
    rows["value"] = [shelter_row("b"), shelter_row("a"), shelter_row("c")]
    out = tools.get_shelters(["c", "a", "b"])
    assert [s["shelter_id"] for s in out["shelters"]] == ["c", "a", "b"]
    assert calls[-1][1]["ids"] == ["c", "a", "b"]
    # shelters_clean.shelter_id is INT64; string ids must be compared against a cast.
    assert "CAST(shelter_id AS STRING) IN UNNEST(@ids)" in calls[-1][0]


def test_get_shelters_empty_makes_no_query(fake_bq):
    calls, _ = fake_bq
    assert tools.get_shelters([])["shelters"] == []
    assert calls == []


def test_check_shelter_google_maps_uses_coordinates_and_returns_live_listing(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    monkeypatch.setattr(
        tools,
        "get_shelters",
        lambda ids: {
            "shelters": [
                {
                    "shelter_id": ids[0],
                    "name": "Jackson County High School",
                    "address": "1660 Winder Highway, Jefferson, 30549",
                    "county_name": "Jackson",
                    "lat": 34.2,
                    "lon": -83.4,
                }
            ]
        },
    )
    requests = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self):
            return json.dumps({
                "places": [{
                    "id": "place-1",
                    "displayName": {"text": "Jackson County High School"},
                    "formattedAddress": "1660 Winder Hwy, Jefferson, GA",
                    "location": {"latitude": 34.2001, "longitude": -83.4001},
                    "businessStatus": "OPERATIONAL",
                    "currentOpeningHours": {"openNow": False},
                    "googleMapsUri": "https://maps.google.com/?cid=1",
                }]
            }).encode()

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return Response()

    monkeypatch.setattr(tools.urllib.request, "urlopen", fake_urlopen)
    result = tools.check_shelter_google_maps("363507")

    request, timeout = requests[0]
    request_body = json.loads(request.data)
    assert request.full_url == tools.GOOGLE_PLACES_TEXT_SEARCH_URL
    assert request.get_header("X-goog-api-key") == "test-key"
    assert request_body["locationBias"]["circle"]["center"] == {
        "latitude": 34.2,
        "longitude": -83.4,
    }
    assert timeout == 15
    assert result["shelter_id"] == "363507"
    assert result["candidates"][0]["distance_m"] == 14
    assert result["candidates"][0]["business_status"] == "OPERATIONAL"
    assert result["candidates"][0]["opening_hours_status"] == "closed_now"
    assert "not emergency shelter operations" in result["limitation"]


def test_check_shelter_google_maps_requires_api_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    result = tools.check_shelter_google_maps("363507")
    assert result["status"] == "error" and "GOOGLE_MAPS_API_KEY" in result["message"]
    assert result["candidates"] == [] and "Google Maps" in result["source"]


def test_check_shelter_google_maps_returns_no_match_without_claiming_closed(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    monkeypatch.setattr(
        tools,
        "get_shelters",
        lambda _: {
            "shelters": [{
                "shelter_id": "363507",
                "name": "Jackson County High School",
                "address": "1660 Winder Highway",
                "county_name": "Jackson",
                "lat": 34.2,
                "lon": -83.4,
            }]
        },
    )

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self):
            return b'{"places": []}'

    monkeypatch.setattr(tools.urllib.request, "urlopen", lambda *_args, **_kwargs: Response())
    result = tools.check_shelter_google_maps("363507")
    assert result["candidates"] == []
    assert "ambiguous or missing match is unknown" in result["limitation"]


def test_vulnerable_tracts_map_sentinel_to_none(fake_bq):
    calls, rows = fake_bq
    rows["value"] = [{"tract_id": "13051000100", "county_fips": "13051", "households_no_vehicle": 40,
                      "pct_no_vehicle": 12.0, "pct_age_65_plus": -999, "pct_disability": -999}]
    out = tools.find_vulnerable_tracts(county_fips="13051")
    assert out["tracts"][0]["pct_disability"] is None
    assert out["tracts"][0]["pct_age_65_plus"] is None
    assert out["tracts"][0]["pct_no_vehicle"] == 12.0
    assert calls[0][1]["county_fips"] == "13051"


def test_every_result_names_its_table(fake_bq):
    _, rows = fake_bq
    rows["value"] = []
    for result, table in [
        (tools.assess_shelter_accessibility(county_fips="13051"), "shelters_clean"),
        (tools.get_shelters(["x"]), "shelters_clean"),
        (tools.find_vulnerable_tracts(county_fips="13051"), "vulnerability_tracts_clean"),
        (tools.find_power_dependent_counties(county_fips="13051"), "power_dependent_counties_clean"),
    ]:
        assert table in result["source"]


def test_record_live_check_validates_status():
    with pytest.raises(ValueError):
        tools.record_live_check("a", "gone")
    out = tools.record_live_check("a", "renamed", place_id="p1")["live_check"]
    assert out["shelter_id"] == "a" and out["status"] == "renamed" and out["place_id"] == "p1"
    assert out["checked_at"]


def test_readiness_brief_counts_what_it_could_not_tell(fake_bq, monkeypatch):
    _, rows = fake_bq
    monkeypatch.setattr(tools, "identify_risky_shelters", lambda **kw: {"risky_shelters": []})
    rows["value"] = [shelter_row("a", wc=None, gen=None), shelter_row("b", wc=True, gen=None)]
    monkeypatch.setattr(
        tools,
        "_scalar",
        lambda name, _type, value: SimpleNamespace(name=name, value=value),
    )
    monkeypatch.setattr(tools, "rank_county_evacuation_needs", lambda **_: {
        "priority_tracts": [],
        "nursing_home_facilities": [],
        "source": "test sources",
    })
    monkeypatch.setattr(tools, "analyze_county_readiness_gaps", lambda *_args, **_kwargs: {
        "county_fips": "13157",
        "county_shelter_count": 2,
        "county_flag_counts": {
            "wheelchair_accessible": {"yes": 1, "no": 0, "unrecorded": 1},
            "generator_onsite": {"yes": 0, "no": 0, "unrecorded": 2},
        },
        "accessibility_gaps": {
            "tracts_without_accessible_destination_within_reach": 0,
            "households_no_vehicle_in_all_access_gaps": 0,
        },
        "generator_gaps": {},
        "flood_and_surge_gaps": {"nursing_homes_generator_unrecorded": 0},
    })
    brief = tools.build_readiness_brief("GA", county_fips="13157")
    cnt = brief["could_not_tell"]
    assert cnt["wheelchair_unrecorded"] == 1
    assert cnt["generator_unrecorded"] == 2
    assert cnt["shelters_considered"] == 2
    assert cnt["shelters_not_live_checked"] == 2
    assert "shelters_clean" in brief["sources"]["shelters_to_verify"]
    assert brief["readiness_gaps"]["county_fips"] == "13157"
    assert "live_destination_status" in cnt
    assert cnt["nursing_home_generator_status"].startswith("UNRECORDED")


def test_readiness_brief_requires_a_county():
    with pytest.raises(ValueError):
        tools.build_readiness_brief("GA")


def test_surge_fallback_sql_prefers_registry_and_names_the_source(monkeypatch):
    monkeypatch.setattr(tools, "_surge_fallback_exists", lambda: True)
    sql = tools._shelters_with_surge_fallback()
    # A recorded FEMA value is kept; NOAA's value is used only when the registry is NULL.
    assert "COALESCE(SAFE_CAST(s.in_surge_slosh_area AS BOOL), f.in_surge_fallback)" in sql
    assert "'noaa_slosh'" in sql and "'registry'" in sql
    assert "shelter_surge_noaa_clean" in sql
    assert "LEFT JOIN" in sql  # shelters outside the lookup stay in, unrecorded


def test_missing_fallback_table_leaves_registry_unchanged(monkeypatch):
    monkeypatch.setattr(tools, "_surge_fallback_exists", lambda: False)
    sql = tools._shelters_with_surge_fallback()
    assert "shelter_surge_noaa_clean" not in sql
    assert "'registry' AS in_surge_source" in sql


def test_risky_shelters_read_the_fallback_and_filter_by_county_fips(monkeypatch, fake_bq):
    calls, _ = fake_bq
    monkeypatch.setattr(tools, "_surge_fallback_exists", lambda: True)
    tools.identify_risky_shelters(state="GA", county_fips="13051", limit=1)
    sql, params = calls[0]
    assert "shelter_surge_noaa_clean" in sql and "surge_from_noaa_count" in sql
    assert "s.county_fips = @county_fips" in sql
    assert params["county_fips"] == "13051"


def test_shelter_tool_records_fill_surge_from_noaa_and_mark_it(fake_bq, monkeypatch):
    _, rows = fake_bq
    lookup = {"a": {"status": "inundated", "first_category": "2"}}
    monkeypatch.setattr(tools, "shelter_record", lambda r: shelter_record(r, lookup))
    rows["value"] = [shelter_row("a"), shelter_row("b")]
    out = tools.assess_shelter_accessibility(county_fips="13157")
    a, b = out["shelters"]
    assert (a["in_surge_slosh_area"], a["in_surge_source"]) == ("YES", "noaa_slosh")
    assert (b["in_surge_slosh_area"], b["in_surge_source"]) == ("UNRECORDED", "registry")
