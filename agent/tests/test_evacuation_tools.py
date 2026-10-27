from readiness_agent import evacuation_tools as et


def test_fallback_sql_prefers_registry_and_names_the_source(monkeypatch):
    monkeypatch.setattr(et, "_surge_fallback_exists", lambda: True)
    sql = et._shelters_with_surge_fallback()
    # A recorded FEMA value is kept; NOAA's value is used only when the registry is NULL.
    assert "COALESCE(SAFE_CAST(s.in_surge_slosh_area AS BOOL), f.in_surge_fallback)" in sql
    assert "'noaa_slosh'" in sql and "'registry'" in sql
    assert "shelter_surge_noaa_clean" in sql
    assert "LEFT JOIN" in sql  # shelters outside the lookup stay in, unrecorded


def test_missing_fallback_table_leaves_registry_unchanged(monkeypatch):
    monkeypatch.setattr(et, "_surge_fallback_exists", lambda: False)
    sql = et._shelters_with_surge_fallback()
    assert "shelter_surge_noaa_clean" not in sql
    assert "'registry' AS in_surge_source" in sql


def test_tools_select_from_the_fallback_view(monkeypatch):
    monkeypatch.setattr(et, "_surge_fallback_exists", lambda: True)
    seen = []
    monkeypatch.setattr(et, "_run_query", lambda sql, params=None: seen.append(sql) or [])
    et.assess_shelter_accessibility(state="GA", limit=1)
    et.identify_risky_shelters(state="GA", limit=1)
    assert seen and all("shelter_surge_noaa_clean" in s and "in_surge_source" in s for s in seen)
