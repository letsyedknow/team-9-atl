"""Tool output shaping, with BigQuery replaced by fakes (tasks T068, T078). No credentials needed."""

import pytest

from readiness_agent import evacuation_tools as tools


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


def test_readiness_brief_counts_what_it_could_not_tell(fake_bq):
    _, rows = fake_bq
    rows["value"] = [shelter_row("a", wc=None, gen=None), shelter_row("b", wc=True, gen=None)]
    brief = tools.build_readiness_brief("GA", county_fips="13157")
    cnt = brief["could_not_tell"]
    assert cnt["wheelchair_unrecorded"] == 1
    assert cnt["generator_unrecorded"] == 2
    assert cnt["shelters_considered"] == 2
    assert "shelters_clean" in brief["sources"]["shelters_to_verify"]


def test_readiness_brief_requires_a_county():
    with pytest.raises(ValueError):
        tools.build_readiness_brief("GA")
