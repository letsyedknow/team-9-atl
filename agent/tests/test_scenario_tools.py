import json
from types import SimpleNamespace

from readiness_agent.scenario_tools import _context, _track_lonlats, run_scenario


def ctx(payload):
    parts = [SimpleNamespace(text="What happens here?"), SimpleNamespace(text=f"CONTEXT v1 {json.dumps(payload)}")]
    return SimpleNamespace(user_content=SimpleNamespace(parts=parts))


def test_context_is_read_from_the_second_part():
    assert _context(ctx({"county_fips": "13051"})) == {"county_fips": "13051"}


def test_missing_or_bad_context_is_empty():
    assert _context(None) == {}
    bad = SimpleNamespace(user_content=SimpleNamespace(parts=[SimpleNamespace(text="CONTEXT v1 {")]))
    assert _context(bad) == {}


def test_track_accepts_linestring_feature_and_point():
    line = {"type": "LineString", "coordinates": [[-85.0, 29.0], [-84.0, 31.0]]}
    assert _track_lonlats({"track": line}) == [(-85.0, 29.0), (-84.0, 31.0)]
    assert _track_lonlats({"track": {"type": "Feature", "geometry": line}}) == [(-85.0, 29.0), (-84.0, 31.0)]
    assert _track_lonlats({"track": {"type": "Point", "coordinates": [-81.1, 32.0]}}) == [(-81.1, 32.0)]
    assert _track_lonlats({}) == []


def test_without_track_or_position_it_asks_for_one():
    assert run_scenario(tool_context=ctx({}))["status"] == "needs_track_or_position"
